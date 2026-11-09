from rest_framework import serializers

from .models import RegistroCotacao


class RegistroCotacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroCotacao
        fields = "__all__"
