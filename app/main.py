from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.schemas import (
    HealthResponse,
    WeatherLocation,
    WeatherLocationCreate,
    WeatherLocationUpdate,
    WeatherResponse,
)
from app.services.locations import (
    create_location,
    delete_location,
    list_locations,
    update_location,
)
from app.services.weather import fetch_weather_many

API_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = API_DIR.parent
NEXT_OUT_DIR = PROJECT_DIR / "WeatherSystem_UI" / "out"

app = FastAPI(title=settings.app_name, version="1.0.0")

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
def api_create_location(payload: WeatherLocationCreate) -> WeatherLocation:
    return create_location(payload)


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
