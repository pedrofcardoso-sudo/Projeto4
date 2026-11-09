import hashlib
import logging
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
COINBASE_RATES_URL = "https://api.coinbase.com/v2/exchange-rates"
logger = logging.getLogger(__name__)


def _cache_key(pair, namespace):
    endpoint = hashlib.sha256(settings.COTACAO_URL.encode()).hexdigest()[:16]
    return f"cotacao:{namespace}:{endpoint}:{pair}"


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


def _parse_fallback_rate(rates, currency):
    try:
        value = Decimal(str(rates[currency]))
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise ValueError(
            f"A API alternativa não retornou uma taxa válida para {currency}."
        ) from exc
    if not value.is_finite() or value <= 0:
        raise ValueError(
            f"A API alternativa não retornou uma taxa válida para {currency}."
        )
    return value


def _fetch_fallback_cotations(pairs):
    response = requests.get(
        COINBASE_RATES_URL,
        params={"currency": "USD"},
        timeout=5,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
        raise ValueError("A API alternativa respondeu em um formato inesperado.")
    rates = data["data"].get("rates")
    if not isinstance(rates, dict) or data["data"].get("currency") != "USD":
        raise ValueError("A API alternativa respondeu em um formato inesperado.")

    values = {}
    for pair in pairs:
        source, target = pair.split("-")
        source_rate = _parse_fallback_rate(rates, source)
        target_rate = _parse_fallback_rate(rates, target)
        values[pair] = target_rate / source_rate
    return values


def fetch_cotations(pairs, *, cache_seconds=None, cache_namespace="standard"):
    """Busca cotações e retorna seus valores e os pares consultados na API."""
    values = {}
    missing = []

    for pair in pairs:
        cached_value = cache.get(_cache_key(pair, cache_namespace))
        if cached_value is None:
            missing.append(pair)
        else:
            values[pair] = Decimal(cached_value)

    if missing:
        try:
            response = requests.get(_url_for_pairs(missing), timeout=5)
            response.raise_for_status()
            data = response.json()
            fetched = {pair: _parse_value(data, pair) for pair in missing}
        except requests.exceptions.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 429:
                raise
            logger.warning(
                "AwesomeAPI retornou HTTP 429; usando o provedor alternativo."
            )
            fetched = _fetch_fallback_cotations(missing)

        timeout = (
            cache_seconds
            if cache_seconds is not None
            else settings.COTACAO_CACHE_SECONDS
        )
        for pair, value in fetched.items():
            cache.set(
                _cache_key(pair, cache_namespace),
                str(value),
                timeout=timeout,
            )
        values.update(fetched)

    return values, set(missing)
