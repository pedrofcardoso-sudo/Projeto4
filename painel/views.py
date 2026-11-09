import requests
from django.shortcuts import render
from django.views.decorators.http import require_GET
from rest_framework import generics

from .models import RegistroCotacao
from .services import PAIR_LABELS, fetch_cotations
from .serializers import RegistroCotacaoSerializer
from .weather import get_weather


@require_GET
def consultar_cotacao(request):
    requested_pairs = request.GET.getlist("pares")
    selected_pairs = list(dict.fromkeys(requested_pairs or ["USD-BRL"]))
    invalid_pairs = [pair for pair in selected_pairs if pair not in PAIR_LABELS]
    cotacoes = []
    erro = None

    if invalid_pairs:
        erro = "Selecione somente pares de moedas disponíveis no painel."
    else:
        try:
            values, fresh_pairs = fetch_cotations(selected_pairs)
            for pair in selected_pairs:
                registro = (
                    RegistroCotacao.objects.filter(
                        moeda_origem=pair[:3],
                        moeda_destino=pair[4:],
                    )
                    .first()
                )
                if pair in fresh_pairs or registro is None:
                    registro = RegistroCotacao.objects.create(
                        moeda_origem=pair[:3],
                        moeda_destino=pair[4:],
                        valor=values[pair],
                    )
                cotacoes.append(
                    {
                        "par": pair,
                        "descricao": PAIR_LABELS[pair],
                        "valor": values[pair],
                        "registro": registro,
                        "cacheada": pair not in fresh_pairs,
                    }
                )
        except requests.exceptions.RequestException:
            erro = (
                "Não foi possível consultar as cotações agora. "
                "Tente novamente em instantes."
            )
        except (ValueError, KeyError, TypeError):
            erro = "A API externa respondeu em um formato inesperado."

    return render(
        request,
        "painel/consultar.html",
        {
            "cotacoes": cotacoes,
            "pares_disponiveis": PAIR_LABELS.items(),
            "pares_selecionados": selected_pairs,
            "erro": erro,
            "clima": get_weather(),
        },
    )


class HistoricoCotacaoView(generics.ListAPIView):
    """Expõe o histórico em modo somente leitura, do mais recente ao mais antigo."""

    serializer_class = RegistroCotacaoSerializer

    def get_queryset(self):
        return RegistroCotacao.objects.order_by("-data_hora_consulta", "-id")[:500]
