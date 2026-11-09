import logging

import requests
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from rest_framework import generics

from .models import RegistroCotacao
from .services import PAIR_LABELS, fetch_cotations
from .serializers import RegistroCotacaoSerializer
from .weather import get_weather


logger = logging.getLogger(__name__)


@require_GET
def health_check(request):
    """Endpoint simples para verificar se o processo web está respondendo."""
    return JsonResponse({"status": "ok"})


@require_GET
def atualizar_cotacoes_tempo_real(request):
    """Atualiza as cotações selecionadas e devolve o histórico recente."""
    pares = list(dict.fromkeys(request.GET.getlist("pares") or ["USD-BRL"]))
    if not pares or any(par not in PAIR_LABELS for par in pares):
        return JsonResponse(
            {"erro": "Selecione somente pares de moedas disponíveis."},
            status=400,
        )

    try:
        values, _ = fetch_cotations(
            pares,
            cache_seconds=settings.COTACAO_LIVE_CACHE_SECONDS,
            cache_namespace="live",
        )
    except requests.exceptions.RequestException as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        logger.warning(
            "Falha na atualização de cotações: %s (HTTP %s)",
            type(exc).__name__,
            status_code or "sem resposta HTTP",
        )
        return JsonResponse(
            {"erro": "Não foi possível atualizar as cotações neste momento."},
            status=503,
        )
    except (ValueError, KeyError, TypeError):
        return JsonResponse(
            {"erro": "A API externa respondeu em um formato inesperado."},
            status=502,
        )

    registros = []
    for par in pares:
        origem, destino = par.split("-")
        ultimo_registro = RegistroCotacao.objects.filter(
            moeda_origem=origem,
            moeda_destino=destino,
        ).first()
        if ultimo_registro is None or ultimo_registro.valor != values[par]:
            ultimo_registro = RegistroCotacao.objects.create(
                moeda_origem=origem,
                moeda_destino=destino,
                valor=values[par],
            )
        registros.append(ultimo_registro)

    return JsonResponse(
        {
            "verificado_em": timezone.now().isoformat(),
            "registros": RegistroCotacaoSerializer(registros, many=True).data,
        }
    )


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
        except requests.exceptions.RequestException as exc:
            status_code = (
                exc.response.status_code if exc.response is not None else None
            )
            logger.warning(
                "Falha na consulta de cotações: %s (HTTP %s)",
                type(exc).__name__,
                status_code or "sem resposta HTTP",
            )
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
