from __future__ import annotations

from datetime import date as date_type, datetime
from typing import List, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class LocationModel(Base):
    __tablename__ = "weather_locations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    records: Mapped[List["WeatherRecordModel"]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )
    sync_status: Mapped[Optional["WeatherSyncStatusModel"]] = relationship(
        back_populates="location", cascade="all, delete-orphan", uselist=False
    )


class WeatherRecordModel(Base):
    __tablename__ = "weather_records"
    __table_args__ = (UniqueConstraint("location_id", "date", name="uq_weather_records_location_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("weather_locations.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    data_type: Mapped[str] = mapped_column(String(16), nullable=False)
    weather_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    temperature_2m_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temperature_2m_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    apparent_temperature_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    apparent_temperature_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    apparent_temperature_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precipitation_sum: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rain_sum: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precipitation_probability_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_speed_10m_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_speed_10m_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_gusts_10m_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_direction_10m_dominant: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    relative_humidity_2m_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dew_point_2m_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    surface_pressure_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cloud_cover_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    visibility_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shortwave_radiation_sum: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    et0_fao_evapotranspiration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vapour_pressure_deficit_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uv_index_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    location: Mapped["LocationModel"] = relationship(back_populates="records")


class WeatherSyncStatusModel(Base):
    __tablename__ = "weather_sync_status"

    location_id: Mapped[str] = mapped_column(
        ForeignKey("weather_locations.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="open-meteo")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="updating")
    last_attempt: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_successful_sync: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    location: Mapped["LocationModel"] = relationship(back_populates="sync_status")
