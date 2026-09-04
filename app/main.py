from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from datetime import date as date_type, datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import SessionLocal, init_db
from app.models import LocationModel, WeatherRecordModel, WeatherSyncStatusModel
from app.schemas import (
    HealthResponse,
    SyncResult,
    WeatherDashboardResponse,
    WeatherHourlyPoint,
    WeatherHourlyResponse,
    WeatherLocation,
    WeatherLocationCreate,
    WeatherLocationUpdate,
    WeatherRecord,
    WeatherResponse,
    WeatherSyncStatus,
)
from app.services.locations import (
    create_location,
    delete_location,
    list_locations,
    seed_locations_from_json,
    update_location,
)
from app.services.weather import fetch_weather_many
from app.services.weather_sync import HISTORICAL_FLOOR, ensure_range_backfilled, sync_location

API_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = API_DIR.parent
NEXT_OUT_DIR = PROJECT_DIR / "WeatherSystem_UI" / "out"


async def _periodic_sync_loop() -> None:
    while True:
        try:
            with SessionLocal() as db:
                locations = db.query(LocationModel).all()
            for location in locations:
                await sync_location(location)
        except Exception:
            pass
        await asyncio.sleep(settings.weather_sync_interval_minutes * 60)


async def _sync_created_location(location_id: str) -> None:
    with SessionLocal() as db:
        location = db.get(LocationModel, location_id)
    if location is not None:
        await sync_location(location)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_locations_from_json()
    task = asyncio.create_task(_periodic_sync_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/locations", response_model=list[WeatherLocation])
def api_list_locations() -> list[WeatherLocation]:
    return list_locations()


@app.post("/api/locations", response_model=WeatherLocation, status_code=201)
def api_create_location(payload: WeatherLocationCreate, background_tasks: BackgroundTasks) -> WeatherLocation:
    location = create_location(payload)
    background_tasks.add_task(_sync_created_location, location.id)
    return location


@app.patch("/api/locations/{location_id}", response_model=WeatherLocation)
def api_update_location(location_id: str, payload: WeatherLocationUpdate) -> WeatherLocation:
    location = update_location(location_id, payload)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found.")
    return location


@app.delete("/api/locations/{location_id}", status_code=204)
def api_delete_location(location_id: str) -> None:
    if not delete_location(location_id):
        raise HTTPException(status_code=404, detail="Location not found.")


@app.get("/api/weather", response_model=WeatherResponse)
async def api_weather(
    location: Optional[str] = None,
    days: int = Query(default=7, ge=1, le=16),
) -> WeatherResponse:
    locations = list_locations()
    if location:
        selected = [item for item in locations if item.id == location]
        if not selected:
            raise HTTPException(status_code=404, detail="Location not found.")
    else:
        selected = locations

    return WeatherResponse(
        generatedAt=datetime.now(timezone.utc),
        weather=await fetch_weather_many(selected, days),
    )


def _get_location_model(location_id: str) -> LocationModel:
    with SessionLocal() as db:
        location = db.get(LocationModel, location_id)
        if location is None:
            raise HTTPException(status_code=404, detail="Location not found.")
        db.expunge(location)
        return location


@app.get("/api/weather/dashboard", response_model=WeatherDashboardResponse)
async def api_weather_dashboard(
    location_id: str = Query(...),
    start_date: date_type = Query(...),
    end_date: date_type = Query(...),
) -> WeatherDashboardResponse:
    location = _get_location_model(location_id)

    today_utc = datetime.now(timezone.utc).date()
    clamped_start = max(start_date, HISTORICAL_FLOOR)
    clamped_end = max(end_date, clamped_start)

    backfill_end = min(clamped_end, today_utc)
    if backfill_end >= clamped_start:
        await ensure_range_backfilled(location, clamped_start, backfill_end)

    with SessionLocal() as db:
        rows = (
            db.query(WeatherRecordModel)
            .filter(
                WeatherRecordModel.location_id == location_id,
                WeatherRecordModel.date >= clamped_start,
                WeatherRecordModel.date <= clamped_end,
            )
            .order_by(WeatherRecordModel.date)
            .all()
        )
        sync_row = db.get(WeatherSyncStatusModel, location_id)

    records = [
        WeatherRecord(
            date=row.date.isoformat(),
            dataType=row.data_type,
            weather_code=row.weather_code,
            temperature_2m_max=row.temperature_2m_max,
            temperature_2m_min=row.temperature_2m_min,
            apparent_temperature_max=row.apparent_temperature_max,
            apparent_temperature_mean=row.apparent_temperature_mean,
            apparent_temperature_min=row.apparent_temperature_min,
            precipitation_sum=row.precipitation_sum,
            rain_sum=row.rain_sum,
            precipitation_probability_max=row.precipitation_probability_max,
            wind_speed_10m_max=row.wind_speed_10m_max,
            wind_speed_10m_mean=row.wind_speed_10m_mean,
            wind_gusts_10m_max=row.wind_gusts_10m_max,
            wind_direction_10m_dominant=row.wind_direction_10m_dominant,
            relative_humidity_2m_mean=row.relative_humidity_2m_mean,
            dew_point_2m_mean=row.dew_point_2m_mean,
            surface_pressure_mean=row.surface_pressure_mean,
            cloud_cover_mean=row.cloud_cover_mean,
            visibility_mean=row.visibility_mean,
            shortwave_radiation_sum=row.shortwave_radiation_sum,
            et0_fao_evapotranspiration=row.et0_fao_evapotranspiration,
            vapour_pressure_deficit_max=row.vapour_pressure_deficit_max,
            uv_index_max=row.uv_index_max,
        )
        for row in rows
    ]

    forecast_dates = [row.date for row in rows if row.data_type == "forecast"]
    today = (min(forecast_dates) if forecast_dates else today_utc).isoformat()

    sync = (
        WeatherSyncStatus(
            provider=sync_row.provider,
            status=sync_row.status,
            lastAttempt=sync_row.last_attempt,
            lastError=sync_row.last_error,
            lastSuccessfulSync=sync_row.last_successful_sync,
        )
        if sync_row is not None
        else WeatherSyncStatus(provider="open-meteo", status="updating")
    )

    return WeatherDashboardResponse(
        location=WeatherLocation(
            id=location.id,
            name=location.name,
            latitude=location.latitude,
            longitude=location.longitude,
            createdAt=location.created_at,
            updatedAt=location.updated_at,
        ),
        records=records,
        sync=sync,
        today=today,
        units={
            "temperature": "°C",
            "wind": "km/h",
            "precipitation": "mm",
            "shortwave_radiation_sum": "MJ/m²",
        },
    )


@app.get("/api/weather/hourly", response_model=WeatherHourlyResponse)
async def api_weather_hourly(
    location_id: str = Query(...),
    hours: int = Query(default=24, ge=1, le=48),
) -> WeatherHourlyResponse:
    location = _get_location_model(location_id)

    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "timezone": "auto",
        "forecast_days": 3,
        "hourly": "rain,precipitation_probability",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(settings.open_meteo_base_url, params=params)
            response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not load hourly forecast: {exc}") from exc

    hourly = payload.get("hourly") or {}
    times: list[str] = hourly.get("time") or []

    # Open-Meteo's timezone=auto returns hourly.time as the location's local
    # civil time with no UTC offset in the string, so "now" must be computed
    # in that same local timezone rather than compared against real UTC.
    try:
        location_tz = ZoneInfo(payload.get("timezone") or "UTC")
    except Exception:
        location_tz = timezone.utc
    local_now_hour = datetime.now(location_tz).replace(minute=0, second=0, microsecond=0, tzinfo=None)

    points: list[WeatherHourlyPoint] = []
    for index, time_value in enumerate(times):
        point_time = datetime.fromisoformat(time_value)
        if point_time < local_now_hour:
            continue
        rain_values = hourly.get("rain") or []
        probability_values = hourly.get("precipitation_probability") or []
        points.append(
            WeatherHourlyPoint(
                time=time_value,
                rain=rain_values[index] if index < len(rain_values) else None,
                precipitationProbability=(
                    probability_values[index] if index < len(probability_values) else None
                ),
            )
        )
        if len(points) >= hours:
            break

    return WeatherHourlyResponse(
        location=WeatherLocation(
            id=location.id,
            name=location.name,
            latitude=location.latitude,
            longitude=location.longitude,
            createdAt=location.created_at,
            updatedAt=location.updated_at,
        ),
        timezone=payload.get("timezone") or "auto",
        points=points,
    )


@app.post("/api/weather/sync/{location_id}", response_model=SyncResult)
async def api_weather_sync(location_id: str) -> SyncResult:
    location = _get_location_model(location_id)
    status = await sync_location(location)
    return SyncResult(
        status=status.status,
        lastAttempt=status.last_attempt,
        lastError=status.last_error,
        lastSuccessfulSync=status.last_successful_sync,
    )


if NEXT_OUT_DIR.exists():
    app.mount("/_next", StaticFiles(directory=NEXT_OUT_DIR / "_next"), name="next-static")


@app.get("/{path:path}", include_in_schema=False)
def serve_next(path: str) -> FileResponse:
    if not NEXT_OUT_DIR.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "Next.js UI has not been built. Run `npm install` and "
                "`npm run build` inside WeatherSystem_UI."
            ),
        )

    requested = NEXT_OUT_DIR / path
    if path and requested.is_file():
        return FileResponse(requested)

    if path:
        nested_index = requested / "index.html"
        if nested_index.is_file():
            return FileResponse(nested_index)

    return FileResponse(NEXT_OUT_DIR / "index.html")
