from django.urls import path

from . import views


urlpatterns = [
    path("consultar/", views.consultar_cotacao, name="consultar"),
    path(
        "api/historico/",
        views.HistoricoCotacaoView.as_view(),
        name="api-historico",
    ),
]
