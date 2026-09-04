from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class WeatherLocationBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class WeatherLocationCreate(WeatherLocationBase):
    pass


class WeatherLocationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)


class WeatherLocation(WeatherLocationBase):
    id: str
    createdAt: datetime
    updatedAt: datetime


class CurrentWeather(BaseModel):
    apparentTemperature: Optional[float] = None
    precipitation: Optional[float] = None
    rain: Optional[float] = None
    relativeHumidity: Optional[float] = None
    temperature: Optional[float] = None
    time: Optional[str] = None
    weatherCode: Optional[int] = None
    weatherLabel: Optional[str] = None
    windDirection: Optional[float] = None
    windSpeed: Optional[float] = None


class DailyWeather(BaseModel):
    date: str
    precipitationProbabilityMax: Optional[float] = None
    rainSum: Optional[float] = None
    temperatureMax: Optional[float] = None
    temperatureMin: Optional[float] = None
    uvIndexMax: Optional[float] = None
    weatherCode: Optional[int] = None
    weatherLabel: Optional[str] = None
    windSpeedMax: Optional[float] = None


class WeatherReport(BaseModel):
    current: CurrentWeather
    daily: list[DailyWeather]
    location: WeatherLocation
    provider: str
    timezone: str
    units: dict[str, str]
    warning: Optional[str] = None


class WeatherResponse(BaseModel):
    generatedAt: datetime
    weather: list[WeatherReport]


class WeatherRecord(BaseModel):
    date: str
    dataType: str
    weather_code: Optional[int] = None
    temperature_2m_max: Optional[float] = None
    temperature_2m_min: Optional[float] = None
    apparent_temperature_max: Optional[float] = None
    apparent_temperature_mean: Optional[float] = None
    apparent_temperature_min: Optional[float] = None
    precipitation_sum: Optional[float] = None
    rain_sum: Optional[float] = None
    precipitation_probability_max: Optional[float] = None
    wind_speed_10m_max: Optional[float] = None
    wind_speed_10m_mean: Optional[float] = None
    wind_gusts_10m_max: Optional[float] = None
    wind_direction_10m_dominant: Optional[float] = None
    relative_humidity_2m_mean: Optional[float] = None
    dew_point_2m_mean: Optional[float] = None
    surface_pressure_mean: Optional[float] = None
    cloud_cover_mean: Optional[float] = None
    visibility_mean: Optional[float] = None
    shortwave_radiation_sum: Optional[float] = None
    et0_fao_evapotranspiration: Optional[float] = None
    vapour_pressure_deficit_max: Optional[float] = None
    uv_index_max: Optional[float] = None


class WeatherSyncStatus(BaseModel):
    provider: str
    status: str
    lastAttempt: Optional[datetime] = None
    lastError: Optional[str] = None
    lastSuccessfulSync: Optional[datetime] = None


class WeatherDashboardResponse(BaseModel):
    location: WeatherLocation
    records: list[WeatherRecord]
    sync: WeatherSyncStatus
    today: str
    units: dict[str, str]


class WeatherHourlyPoint(BaseModel):
    time: str
    rain: Optional[float] = None
    precipitationProbability: Optional[float] = None


class WeatherHourlyResponse(BaseModel):
    location: WeatherLocation
    timezone: str
    points: list[WeatherHourlyPoint]


class SyncResult(BaseModel):
    status: str
    lastAttempt: Optional[datetime] = None
    lastError: Optional[str] = None
    lastSuccessfulSync: Optional[datetime] = None


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[Any] = None
