import requests
from django.core.management.base import BaseCommand, CommandError

from painel.models import RegistroCotacao
from painel.services import PAIR_LABELS, fetch_cotations


class Command(BaseCommand):
    help = "Consulta e salva as cotações configuradas que ainda não estão em cache."

    def handle(self, *args, **options):
        pairs = list(PAIR_LABELS)
        try:
            values, fresh_pairs = fetch_cotations(pairs)
        except requests.exceptions.RequestException as exc:
            raise CommandError(f"Falha ao consultar a API de cotações: {exc}") from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise CommandError(f"Resposta inválida da API de cotações: {exc}") from exc

        for pair in fresh_pairs:
            RegistroCotacao.objects.create(
                moeda_origem=pair[:3],
                moeda_destino=pair[4:],
                valor=values[pair],
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Consulta concluída: {len(fresh_pairs)} registro(s) novo(s); "
                f"{len(pairs) - len(fresh_pairs)} par(es) atendido(s) pelo cache."
            )
        )
