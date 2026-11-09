from django.contrib import admin

from .models import RegistroCotacao


@admin.register(RegistroCotacao)
class RegistroCotacaoAdmin(admin.ModelAdmin):
    list_display = (
        "moeda_origem",
        "moeda_destino",
        "valor",
        "data_hora_consulta",
    )
    list_filter = ("moeda_origem", "moeda_destino")
    ordering = ("-data_hora_consulta", "-id")
