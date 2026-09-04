from __future__ import annotations

from datetime import date as date_type, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import LocationModel, WeatherRecordModel, WeatherSyncStatusModel
from app.services.weather_science import aggregate_daily_from_hourly

ROLLING_PAST_DAYS = 92
ROLLING_FORECAST_DAYS = 16
HISTORICAL_FLOOR = date_type(2015, 1, 1)
PROVIDER = "open-meteo"

FORECAST_HOURLY_VARS = ",".join(
    [
        "temperature_2m",
        "relative_humidity_2m",
        "dew_point_2m",
        "apparent_temperature",
        "precipitation",
        "rain",
        "weather_code",
        "surface_pressure",
        "cloud_cover",
        "visibility",
        "wind_speed_10m",
        "wind_gusts_10m",
        "wind_direction_10m",
        "vapour_pressure_deficit",
    ]
)
FORECAST_DAILY_VARS = ",".join(
    [
        "weather_code",
        "temperature_2m_max",
        "temperature_2m_min",
        "apparent_temperature_max",
        "apparent_temperature_min",
        "rain_sum",
        "precipitation_sum",
        "precipitation_probability_max",
        "wind_speed_10m_max",
        "wind_gusts_10m_max",
        "wind_direction_10m_dominant",
        "shortwave_radiation_sum",
        "et0_fao_evapotranspiration",
        "uv_index_max",
    ]
)
ARCHIVE_HOURLY_VARS = ",".join(
    [
        "temperature_2m",
        "relative_humidity_2m",
        "dew_point_2m",
        "apparent_temperature",
        "precipitation",
        "rain",
        "weather_code",
        "surface_pressure",
        "cloud_cover",
        "wind_speed_10m",
        "wind_gusts_10m",
        "wind_direction_10m",
        "vapour_pressure_deficit",
    ]
)
ARCHIVE_DAILY_VARS = ",".join(
    [
        "weather_code",
        "temperature_2m_max",
        "temperature_2m_min",
        "apparent_temperature_max",
        "apparent_temperature_min",
        "rain_sum",
        "precipitation_sum",
        "wind_speed_10m_max",
        "wind_gusts_10m_max",
        "wind_direction_10m_dominant",
        "shortwave_radiation_sum",
        "et0_fao_evapotranspiration",
    ]
)

DAILY_NATIVE_FIELDS = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "rain_sum",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
    "uv_index_max",
]

def _daily_value(daily: Dict[str, Any], field: str, index: int) -> Any:
    values = daily.get(field) or []
    return values[index] if index < len(values) else None


def _rows_from_response(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Builds one row dict per date, skipping dates with no real daily data at all."""
    daily = payload.get("daily") or {}
    dates: List[str] = daily.get("time") or []
    hourly_aggregates = aggregate_daily_from_hourly(payload.get("hourly") or {})

    rows: List[Dict[str, Any]] = []
    for index, date_str in enumerate(dates):
        row: Dict[str, Any] = {"date": date_str}
        for field in DAILY_NATIVE_FIELDS:
            row[field] = _daily_value(daily, field, index)
        row.update(hourly_aggregates.get(date_str, {}))

        has_real_data = any(value is not None for key, value in row.items() if key != "date")
        if has_real_data:
            rows.append(row)

    return rows


def _local_today(response_timezone: str) -> date_type:
    try:
        tz = ZoneInfo(response_timezone)
    except Exception:
        tz = timezone.utc
    return datetime.now(tz).date()


async def _fetch_json(client: httpx.AsyncClient, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    response = await client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def _upsert_rows(
    db: Session,
    location_id: str,
    rows: List[Dict[str, Any]],
    today: date_type,
    mode: str,
) -> None:
    """mode "overwrite": every synced column replaces whatever was stored (used for the
    rolling forecast-API window, which is the freshest source for every field it covers).
    mode "coalesce": only fills columns that are currently NULL, never replaces a real
    value (used for Archive API gap-fill, since the archive lacks fields — visibility,
    UV, rain probability — that a forecast-API row may already have captured for the
    same date; a plain overwrite would permanently erase those)."""
    if not rows:
        return

    table = WeatherRecordModel.__table__
    values = []
    for row in rows:
        row_date = date_type.fromisoformat(row["date"])
        data_type = "historical" if row_date < today else "forecast"
        values.append({"location_id": location_id, "data_type": data_type, **row})

    stmt = pg_insert(table).values(values)
    if mode == "overwrite":
        update_columns = {
            column.name: stmt.excluded[column.name]
            for column in table.columns
            if column.name not in ("id", "location_id", "date")
        }
    else:
        update_columns = {
            column.name: func.coalesce(table.c[column.name], stmt.excluded[column.name])
            for column in table.columns
            if column.name not in ("id", "location_id", "date")
        }
    stmt = stmt.on_conflict_do_update(
        index_elements=["location_id", "date"],
        set_=update_columns,
    )

    db.execute(stmt)


async def sync_location(location: LocationModel) -> WeatherSyncStatusModel:
    """Rolling-window sync: always overwrites the last ~92 days back + 16 days forward."""
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "timezone": "auto",
        "past_days": ROLLING_PAST_DAYS,
        "forecast_days": ROLLING_FORECAST_DAYS,
        "hourly": FORECAST_HOURLY_VARS,
        "daily": FORECAST_DAILY_VARS,
    }

    with SessionLocal() as db:
        status = db.get(WeatherSyncStatusModel, location.id)
        if status is None:
            status = WeatherSyncStatusModel(location_id=location.id, provider=PROVIDER)
            db.add(status)
        status.status = "updating"
        status.last_attempt = datetime.now(timezone.utc)
        db.commit()

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                payload = await _fetch_json(client, settings.open_meteo_base_url, params)

            today = _local_today(payload.get("timezone") or "UTC")
            rows = _rows_from_response(payload)
            _upsert_rows(db, location.id, rows, today, mode="overwrite")

            status.status = "success"
            status.last_error = None
            status.last_successful_sync = datetime.now(timezone.utc)
            db.commit()
        except Exception as exc:
            status.status = "failed"
            status.last_error = str(exc)
            db.commit()

        db.refresh(status)
        return status


async def ensure_range_backfilled(location: LocationModel, start_date: date_type, end_date: date_type) -> None:
    """Gap-fills any dates in [start_date, end_date] missing real daily data, from the Archive API.

    A date can already have a *row* without having real coverage: the forecast-API's
    rolling window returns some fields (e.g. rain probability) further back than others
    (e.g. temperature), so a date near the edge of that window can end up with a row
    that only has the earlier-available fields and nulls for the rest. Using
    temperature_2m_max — always present whenever a date has real daily coverage, from
    either API — as the "is this date actually covered" signal catches both a fully
    missing row and a partially-populated one.
    """
    clamped_start = max(start_date, HISTORICAL_FLOOR)
    if clamped_start > end_date:
        return

    with SessionLocal() as db:
        covered_dates = {
            row[0]
            for row in db.execute(
                select(WeatherRecordModel.date).where(
                    WeatherRecordModel.location_id == location.id,
                    WeatherRecordModel.date >= clamped_start,
                    WeatherRecordModel.date <= end_date,
                    WeatherRecordModel.temperature_2m_max.is_not(None),
                )
            ).all()
        }

        all_dates = {clamped_start + timedelta(days=offset) for offset in range((end_date - clamped_start).days + 1)}
        missing_dates = sorted(all_dates - covered_dates)
        if not missing_dates:
            return

        gap_start, gap_end = missing_dates[0], missing_dates[-1]

        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "timezone": "auto",
            "start_date": gap_start.isoformat(),
            "end_date": gap_end.isoformat(),
            "hourly": ARCHIVE_HOURLY_VARS,
            "daily": ARCHIVE_DAILY_VARS,
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                payload = await _fetch_json(client, settings.open_meteo_archive_url, params)

            today = _local_today(payload.get("timezone") or "UTC")
            rows = _rows_from_response(payload)
            _upsert_rows(db, location.id, rows, today, mode="coalesce")
            db.commit()
        except Exception:
            # Best-effort backfill: leave the gap for next time rather than fail the read.
            db.rollback()
