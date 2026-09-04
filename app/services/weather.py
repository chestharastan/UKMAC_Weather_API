from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from app.config import settings
from app.schemas import DailyWeather, CurrentWeather, WeatherLocation, WeatherReport

OPEN_METEO_URL = settings.open_meteo_base_url

def weather_code_label(code: Optional[int]) -> str:
    if code == 0:
        return "Clear"
    if code in {1, 2, 3}:
        return "Cloudy"
    if code in {45, 48}:
        return "Fog"
    if code in {51, 53, 55, 56, 57}:
        return "Drizzle"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "Rain"
    if code in {71, 73, 75, 77, 85, 86}:
        return "Snow"
    if code in {95, 96, 99}:
        return "Storm"
    return "Mixed"


def _fallback_report(location: WeatherLocation, days: int, warning: str) -> WeatherReport:
    daily: list[DailyWeather] = []
    today = datetime.now(timezone.utc).date()
    for index in range(days):
        base = index / 2
        rain = max(0, round(4 + (base % 2) * 3 + (index % 3) * 1.2, 1))
        daily.append(
            DailyWeather(
                date=(today + timedelta(days=index)).isoformat(),
                rainSum=rain,
                temperatureMax=round(31 + (base % 2) * 2, 1),
                temperatureMin=round(24 + (base % 1), 1),
                uvIndexMax=round(7 + (base % 1), 1),
                weatherCode=80 if rain > 6 else 3,
                weatherLabel="Rain" if rain > 6 else "Cloudy",
                windSpeedMax=round(12 + index * 0.8, 1),
            )
        )

    return WeatherReport(
        current=CurrentWeather(
            apparentTemperature=32,
            precipitation=0,
            rain=0,
            relativeHumidity=74,
            temperature=30,
            time=datetime.now(timezone.utc).isoformat(),
            weatherCode=3,
            weatherLabel="Cloudy",
            windDirection=190,
            windSpeed=8,
        ),
        daily=daily,
        location=location,
        provider="demo-fallback",
        timezone="local",
        units={"precipitation": "mm", "temperature": "C", "windSpeed": "km/h"},
        warning=warning,
    )


def _daily_value(payload: dict[str, Any], field: str, index: int) -> Any:
    values = payload.get("daily", {}).get(field) or []
    return values[index] if index < len(values) else None


def _map_open_meteo(payload: dict[str, Any], location: WeatherLocation) -> WeatherReport:
    current_payload = payload.get("current") or {}
    daily = []
    for index, date in enumerate(payload.get("daily", {}).get("time") or []):
        weather_code = _daily_value(payload, "weather_code", index)
        daily.append(
            DailyWeather(
                date=date,
                precipitationProbabilityMax=_daily_value(
                    payload, "precipitation_probability_max", index
                ),
                rainSum=_daily_value(payload, "rain_sum", index),
                temperatureMax=_daily_value(payload, "temperature_2m_max", index),
                temperatureMin=_daily_value(payload, "temperature_2m_min", index),
                uvIndexMax=_daily_value(payload, "uv_index_max", index),
                weatherCode=weather_code,
                weatherLabel=weather_code_label(weather_code),
                windSpeedMax=_daily_value(payload, "wind_speed_10m_max", index),
            )
        )

    current_code = current_payload.get("weather_code")
    return WeatherReport(
        current=CurrentWeather(
            apparentTemperature=current_payload.get("apparent_temperature"),
            precipitation=current_payload.get("precipitation"),
            rain=current_payload.get("rain"),
            relativeHumidity=current_payload.get("relative_humidity_2m"),
            temperature=current_payload.get("temperature_2m"),
            time=current_payload.get("time"),
            weatherCode=current_code,
            weatherLabel=weather_code_label(current_code),
            windDirection=current_payload.get("wind_direction_10m"),
            windSpeed=current_payload.get("wind_speed_10m"),
        ),
        daily=daily,
        location=location,
        provider="open-meteo",
        timezone=payload.get("timezone") or "auto",
        units={
            "precipitation": payload.get("current_units", {}).get("rain") or "mm",
            "temperature": payload.get("current_units", {}).get("temperature_2m") or "C",
            "windSpeed": payload.get("current_units", {}).get("wind_speed_10m") or "km/h",
        },
    )


async def fetch_weather(location: WeatherLocation, days: int) -> WeatherReport:
    forecast_days = min(max(days, 1), 16)
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "timezone": "auto",
        "forecast_days": forecast_days,
        "current": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation",
                "rain",
                "weather_code",
                "wind_speed_10m",
                "wind_direction_10m",
            ]
        ),
        "daily": ",".join(
            [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "rain_sum",
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "uv_index_max",
            ]
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(OPEN_METEO_URL, params=params)
            response.raise_for_status()
        return _map_open_meteo(response.json(), location)
    except Exception as exc:
        return _fallback_report(location, forecast_days, f"Live weather unavailable: {exc}")


async def fetch_weather_many(locations: list[WeatherLocation], days: int) -> list[WeatherReport]:
    return await asyncio.gather(*(fetch_weather(location, days) for location in locations))
