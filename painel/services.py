import hashlib
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit

import requests
from django.conf import settings
from django.core.cache import cache


PAIR_LABELS = {
    "USD-BRL": "Dólar americano / Real",
    "EUR-BRL": "Euro / Real",
    "GBP-BRL": "Libra esterlina / Real",
    "BTC-BRL": "Bitcoin / Real",
    "USD-EUR": "Dólar americano / Euro",
    "EUR-USD": "Euro / Dólar americano",
    "BTC-USD": "Bitcoin / Dólar americano",
    "BTC-EUR": "Bitcoin / Euro",
}


def _cache_key(pair):
    endpoint = hashlib.sha256(settings.COTACAO_URL.encode()).hexdigest()[:16]
    return f"cotacao:{endpoint}:{pair}"


def _url_for_pairs(pairs):
    parsed = urlsplit(settings.COTACAO_URL)
    pair_path = ",".join(pairs)
    path, replacements = re.subn(
        r"(/last/)[^/]+/?$",
        lambda match: f"{match.group(1)}{pair_path}",
        parsed.path,
        count=1,
        flags=re.IGNORECASE,
    )
    if not replacements and pairs != ["USD-BRL"]:
        raise ValueError(
            "COTACAO_URL precisa usar o endpoint /last/PAIR para consultar "
            "múltiplos pares."
        )
    return urlunsplit(parsed._replace(path=path))


def _parse_value(data, pair):
    if not isinstance(data, dict):
        raise ValueError("A API externa respondeu em um formato inesperado.")
    quote = data.get(pair.replace("-", ""))
    if not isinstance(quote, dict):
        raise ValueError(f"A API não retornou a cotação de {pair}.")
    try:
        value = Decimal(str(quote["bid"]))
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise ValueError(f"A API retornou um valor inválido para {pair}.") from exc
    if not value.is_finite() or value <= 0:
        raise ValueError(f"A API retornou um valor inválido para {pair}.")
    return value


def fetch_cotations(pairs):
    """Busca os pares que não estão em cache e retorna (valores, pares novos)."""
    values = {}
    missing = []

    for pair in pairs:
        cached_value = cache.get(_cache_key(pair))
        if cached_value is None:
            missing.append(pair)
        else:
            values[pair] = Decimal(cached_value)

    if missing:
        resposta = requests.get(_url_for_pairs(missing), timeout=5)
        resposta.raise_for_status()
        dados = resposta.json()
        fetched = {pair: _parse_value(dados, pair) for pair in missing}
        for pair, value in fetched.items():
            cache.set(
                _cache_key(pair),
                str(value),
                timeout=settings.COTACAO_CACHE_SECONDS,
            )
        values.update(fetched)

    return values, set(missing)
