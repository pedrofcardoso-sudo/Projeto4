from decimal import Decimal
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import RegistroCotacao
from .services import fetch_cotations


class HealthCheckTest(TestCase):
    def test_endpoint_informa_que_aplicacao_esta_responsiva(self):
        resposta = self.client.get(reverse("health-check"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"status": "ok"})


class CotacaoFallbackTest(TestCase):
    def setUp(self):
        cache.clear()

    @patch("painel.services.requests.get")
    def test_limite_da_awesomeapi_usa_taxas_da_coinbase(self, get):
        erro = requests.exceptions.HTTPError("HTTP 429")
        erro.response = MagicMock(status_code=429)
        resposta_awesomeapi = MagicMock()
        resposta_awesomeapi.raise_for_status.side_effect = erro
        resposta_coinbase = resposta_falsa(
            {
                "data": {
                    "currency": "USD",
                    "rates": {
                        "USD": "1",
                        "BRL": "5",
                        "EUR": "0.8",
                        "BTC": "0.00002",
                    },
                }
            }
        )
        get.side_effect = [resposta_awesomeapi, resposta_coinbase]

        with self.assertLogs("painel.services", level="WARNING"):
            valores, consultados = fetch_cotations(
                ["USD-BRL", "EUR-BRL", "BTC-BRL"],
                cache_namespace="fallback-test",
            )

        self.assertEqual(valores["USD-BRL"], Decimal("5"))
        self.assertEqual(valores["EUR-BRL"], Decimal("6.25"))
        self.assertEqual(valores["BTC-BRL"], Decimal("250000"))
        self.assertEqual(consultados, {"USD-BRL", "EUR-BRL", "BTC-BRL"})
        self.assertEqual(get.call_count, 2)


def resposta_falsa(json_data, status=200):
    resposta = MagicMock()
    resposta.json.return_value = json_data
    if status >= 400:
        erro = requests.exceptions.HTTPError(f"HTTP {status}")
        erro.response = MagicMock(status_code=status)
        resposta.raise_for_status.side_effect = erro
    return resposta


class ConsultarCotacaoTest(TestCase):
    def setUp(self):
        cache.clear()

    @patch("painel.views.requests.get")
    def test_sucesso_salva_registro(self, get):
        get.return_value = resposta_falsa({"USDBRL": {"bid": "5.1234"}})

        resposta = self.client.get(reverse("consultar"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Cotação registrada")
        registro = RegistroCotacao.objects.get()
        self.assertEqual(registro.valor, Decimal("5.1234"))
        self.assertEqual(get.call_args.kwargs["timeout"], 5)

    @patch(
        "painel.views.requests.get",
        side_effect=requests.exceptions.Timeout(),
    )
    def test_timeout_nao_quebra_a_pagina(self, get):
        with self.assertLogs("painel.views", level="WARNING") as logs:
            resposta = self.client.get(reverse("consultar"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Não foi possível consultar")
        self.assertIn("Timeout", logs.output[0])
        self.assertEqual(RegistroCotacao.objects.count(), 0)

    @patch("painel.views.requests.get")
    def test_erro_http_da_api_nao_salva_registro(self, get):
        get.return_value = resposta_falsa({}, status=500)

        with self.assertLogs("painel.views", level="WARNING") as logs:
            resposta = self.client.get(reverse("consultar"))

        self.assertContains(resposta, "Não foi possível consultar")
        self.assertIn("HTTP 500", logs.output[0])
        self.assertEqual(RegistroCotacao.objects.count(), 0)

    @patch("painel.views.requests.get")
    def test_formato_inesperado_nao_salva_registro(self, get):
        get.return_value = resposta_falsa({"outra": "coisa"})

        resposta = self.client.get(reverse("consultar"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "formato inesperado")
        self.assertEqual(RegistroCotacao.objects.count(), 0)

    def test_template_usa_fetch_e_trata_falha(self):
        with patch(
            "painel.views.requests.get",
            side_effect=requests.exceptions.ConnectionError(),
        ):
            resposta = self.client.get(reverse("consultar"))

        self.assertContains(resposta, "fetch('/api/historico/')")
        self.assertContains(resposta, ".catch(")

    @patch("painel.views.requests.get")
    def test_consulta_multiplos_pares_em_uma_requisicao(self, get):
        get.return_value = resposta_falsa(
            {
                "USDBRL": {"bid": "5.1234"},
                "EURBRL": {"bid": "6.2345"},
            }
        )

        resposta = self.client.get(
            reverse("consultar"),
            {"pares": ["USD-BRL", "EUR-BRL"]},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "USD-BRL")
        self.assertContains(resposta, "EUR-BRL")
        self.assertEqual(get.call_count, 1)
        self.assertEqual(RegistroCotacao.objects.count(), 2)

    @patch("painel.views.requests.get")
    def test_reutiliza_cotacao_em_cache_sem_nova_chamada_ou_registro(self, get):
        get.return_value = resposta_falsa({"USDBRL": {"bid": "5.1234"}})

        self.client.get(reverse("consultar"))
        resposta = self.client.get(reverse("consultar"))

        self.assertEqual(get.call_count, 1)
        self.assertEqual(RegistroCotacao.objects.count(), 1)
        self.assertContains(resposta, "recuperada do cache")

    def test_pares_invalidos_nao_chamam_api(self):
        with patch("painel.views.requests.get") as get:
            resposta = self.client.get(
                reverse("consultar"),
                {"pares": "XXX-YYY"},
            )

        self.assertContains(resposta, "Selecione somente pares")
        get.assert_not_called()

    def test_tela_inclui_grafico_tempo_e_formulario_de_multiplas_moedas(self):
        with patch(
            "painel.views.requests.get",
            return_value=resposta_falsa({"USDBRL": {"bid": "5.1234"}}),
        ):
            resposta = self.client.get(reverse("consultar"))

        self.assertContains(resposta, "chart.js")
        self.assertContains(resposta, "Clima")
        self.assertContains(resposta, "usamos taxas da Coinbase")
        self.assertContains(resposta, 'name="pares"')

    @patch(
        "painel.views.requests.get",
        return_value=resposta_falsa({"USDBRL": {"bid": "5.1234"}}),
    )
    def test_pagina_inicial_redireciona_para_painel_com_atalhos(self, get):
        resposta_inicial = self.client.get("/")

        self.assertRedirects(resposta_inicial, reverse("consultar"))
        resposta_painel = self.client.get(reverse("consultar"))
        self.assertContains(resposta_painel, 'aria-label="Acesso rápido"')
        self.assertContains(resposta_painel, 'href="#consulta"')
        self.assertContains(resposta_painel, 'href="/api/historico/"')
        self.assertContains(resposta_painel, 'href="/admin/"')


class ClimaTest(TestCase):
    def setUp(self):
        cache.clear()

    @patch("painel.weather.requests.get")
    def test_clima_com_chave_configurada(self, get):
        get.return_value = resposta_falsa(
            {
                "name": "Brasília",
                "main": {"temp": 21.5},
                "weather": [{"description": "céu limpo"}],
            }
        )

        with self.settings(OPENWEATHERMAP_API_KEY="teste-chave"):
            resposta = self.client.get(reverse("consultar"))

        self.assertContains(resposta, "21,5")
        self.assertEqual(get.call_count, 2)
        self.assertEqual(
            get.call_args_list[1].kwargs["params"]["appid"],
            "teste-chave",
        )

    @patch("painel.weather.requests.get")
    def test_sem_chave_clima_exibe_instrucao_sem_chamar_api(self, get):
        get.return_value = resposta_falsa({"USDBRL": {"bid": "5.1234"}})

        with self.settings(OPENWEATHERMAP_API_KEY=""):
            resposta = self.client.get(reverse("consultar"))

        self.assertContains(resposta, "Configure OPENWEATHERMAP_API_KEY")
        self.assertEqual(get.call_count, 1)
        self.assertIn("/json/last/", get.call_args.args[0])

    @patch(
        "painel.weather.requests.get",
        side_effect=[
            resposta_falsa({"USDBRL": {"bid": "5.1234"}}),
            requests.exceptions.Timeout(),
        ],
    )
    def test_falha_da_api_de_clima_nao_quebra_o_painel(self, get):
        with self.settings(OPENWEATHERMAP_API_KEY="teste-chave"):
            resposta = self.client.get(reverse("consultar"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Não foi possível consultar o clima")


class ConsultaAgendadaTest(TestCase):
    def setUp(self):
        cache.clear()

    @patch("painel.services.requests.get")
    def test_comando_agendavel_salva_pares_e_reaproveita_cache(self, get):
        get.return_value = resposta_falsa(
            {
                pair.replace("-", ""): {"bid": "5.1234"}
                for pair in (
                    "USD-BRL",
                    "EUR-BRL",
                    "GBP-BRL",
                    "BTC-BRL",
                    "USD-EUR",
                    "EUR-USD",
                    "BTC-USD",
                    "BTC-EUR",
                )
            }
        )

        call_command("consultar_cotacoes")
        call_command("consultar_cotacoes")

        self.assertEqual(get.call_count, 1)
        self.assertEqual(RegistroCotacao.objects.count(), 8)


class HistoricoAPITest(TestCase):
    def setUp(self):
        cache.clear()

    def test_salva_cotacao_de_alto_valor_com_precisao_ampliada(self):
        valor = Decimal("12345678901234.1234")

        registro = RegistroCotacao.objects.create(
            moeda_origem="BTC",
            moeda_destino="BRL",
            valor=valor,
        )

        self.assertEqual(registro.valor, valor)

    def test_lista_registros_do_mais_recente_ao_mais_antigo(self):
        antigo = RegistroCotacao.objects.create(valor=Decimal("5.0000"))
        meio = RegistroCotacao.objects.create(valor=Decimal("5.1000"))
        recente = RegistroCotacao.objects.create(valor=Decimal("5.2000"))

        resposta = self.client.get(reverse("api-historico"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            [registro["id"] for registro in resposta.json()],
            [recente.id, meio.id, antigo.id],
        )

    def test_endpoint_e_somente_leitura(self):
        resposta = self.client.post(
            reverse("api-historico"),
            {"valor": "1.0000"},
        )

        self.assertEqual(resposta.status_code, 405)

    def test_historico_vazio_retorna_lista_vazia(self):
        resposta = self.client.get(reverse("api-historico"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), [])

    @patch("painel.views.requests.get")
    def test_api_tempo_real_consulta_e_salva_multiplos_pares(self, get):
        get.return_value = resposta_falsa(
            {
                "USDBRL": {"bid": "5.1234"},
                "EURBRL": {"bid": "6.2345"},
            }
        )

        resposta = self.client.get(
            reverse("api-cotacoes-tempo-real"),
            {"pares": ["USD-BRL", "EUR-BRL"]},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            [registro["moeda_origem"] for registro in resposta.json()["registros"]],
            ["USD", "EUR"],
        )
        self.assertIn("verificado_em", resposta.json())
        self.assertEqual(get.call_count, 1)
        self.assertEqual(RegistroCotacao.objects.count(), 2)

    @patch("painel.views.requests.get")
    def test_api_tempo_real_nao_duplica_valor_inalterado(self, get):
        get.return_value = resposta_falsa({"USDBRL": {"bid": "5.1234"}})

        primeira = self.client.get(reverse("api-cotacoes-tempo-real"))
        segunda = self.client.get(reverse("api-cotacoes-tempo-real"))

        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(RegistroCotacao.objects.count(), 1)
        self.assertEqual(get.call_count, 1)

    def test_api_tempo_real_rejeita_pares_invalidos(self):
        resposta = self.client.get(
            reverse("api-cotacoes-tempo-real"),
            {"pares": "XXX-YYY"},
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(RegistroCotacao.objects.count(), 0)
