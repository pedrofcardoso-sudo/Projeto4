from django.urls import path

from . import views


urlpatterns = [
    path("consultar/", views.consultar_cotacao, name="consultar"),
    path("health/", views.health_check, name="health-check"),
    path(
        "api/cotacoes/tempo-real/",
        views.atualizar_cotacoes_tempo_real,
        name="api-cotacoes-tempo-real",
    ),
    path(
        "api/historico/",
        views.HistoricoCotacaoView.as_view(),
        name="api-historico",
    ),
]
