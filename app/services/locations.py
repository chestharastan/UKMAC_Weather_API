from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.schemas import WeatherLocation, WeatherLocationCreate, WeatherLocationUpdate

API_DIR = Path(__file__).resolve().parents[2]
LOCATIONS_PATH = API_DIR / "data" / "locations.json"


def _read_raw_locations() -> list[dict]:
    if not LOCATIONS_PATH.exists():
        LOCATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCATIONS_PATH.write_text("[]\n", encoding="utf-8")
    return json.loads(LOCATIONS_PATH.read_text(encoding="utf-8"))


def _write_raw_locations(locations: list[dict]) -> None:
    LOCATIONS_PATH.write_text(json.dumps(locations, indent=2) + "\n", encoding="utf-8")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48]
    return slug or str(uuid4())


def _create_id(name: str, locations: list[dict]) -> str:
    base = _slugify(name)
    existing = {location["id"] for location in locations}
    candidate = base
    index = 2
    while candidate in existing:
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def _normalize_coordinates(payload: dict) -> dict:
    if "latitude" in payload and payload["latitude"] is not None:
        payload["latitude"] = round(float(payload["latitude"]), 6)
    if "longitude" in payload and payload["longitude"] is not None:
        payload["longitude"] = round(float(payload["longitude"]), 6)
    if "name" in payload and payload["name"] is not None:
        payload["name"] = payload["name"].strip()
    return payload


def list_locations() -> list[WeatherLocation]:
    return [WeatherLocation(**location) for location in _read_raw_locations()]


def get_location(location_id: str) -> Optional[WeatherLocation]:
    for location in _read_raw_locations():
        if location["id"] == location_id:
            return WeatherLocation(**location)
    return None


def create_location(payload: WeatherLocationCreate) -> WeatherLocation:
    locations = _read_raw_locations()
    now = datetime.now(timezone.utc).isoformat()
    data = _normalize_coordinates(payload.model_dump())
    location = {
        "id": _create_id(data["name"], locations),
        **data,
        "createdAt": now,
        "updatedAt": now,
    }
    locations.append(location)
    _write_raw_locations(locations)
    return WeatherLocation(**location)


def update_location(location_id: str, payload: WeatherLocationUpdate) -> Optional[WeatherLocation]:
    locations = _read_raw_locations()
    updates = _normalize_coordinates(payload.model_dump(exclude_unset=True))
    for index, location in enumerate(locations):
        if location["id"] == location_id:
            locations[index] = {
                **location,
                **updates,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }
            _write_raw_locations(locations)
            return WeatherLocation(**locations[index])
    return None


def delete_location(location_id: str) -> bool:
    locations = _read_raw_locations()
    next_locations = [location for location in locations if location["id"] != location_id]
    if len(next_locations) == len(locations):
        return False
    _write_raw_locations(next_locations)
    return True
