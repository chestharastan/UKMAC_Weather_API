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


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[Any] = None
