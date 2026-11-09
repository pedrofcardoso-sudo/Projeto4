import math

import requests
from django.conf import settings
from django.core.cache import cache


def get_weather():
    city = settings.WEATHER_CITY
    cache_key = f"weather:{city.casefold()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    api_key = settings.OPENWEATHERMAP_API_KEY
    if not api_key:
        return {
            "available": False,
            "message": (
                "Configure OPENWEATHERMAP_API_KEY para exibir a previsão do tempo."
            ),
        }

    try:
        resposta = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "q": city,
                "appid": api_key,
                "units": "metric",
                "lang": "pt_br",
            },
            timeout=5,
        )
        resposta.raise_for_status()
        dados = resposta.json()
        raw_temperature = dados["main"]["temp"]
        if isinstance(raw_temperature, bool):
            raise ValueError
        temperature = float(raw_temperature)
        description = dados["weather"][0]["description"]
        if not math.isfinite(temperature) or not isinstance(description, str):
            raise ValueError
        weather = {
            "available": True,
            "city": dados.get("name", city),
            "temperature": temperature,
            "description": description,
        }
    except requests.exceptions.RequestException:
        return {
            "available": False,
            "message": "Não foi possível consultar o clima neste momento.",
        }
    except (ValueError, KeyError, TypeError, IndexError):
        return {
            "available": False,
            "message": "A API de clima respondeu em um formato inesperado.",
        }

    cache.set(cache_key, weather, timeout=settings.WEATHER_CACHE_SECONDS)
    return weather
