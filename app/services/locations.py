from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.db import SessionLocal
from app.models import LocationModel
from app.schemas import WeatherLocation, WeatherLocationCreate, WeatherLocationUpdate

API_DIR = Path(__file__).resolve().parents[2]
LOCATIONS_SEED_PATH = API_DIR / "data" / "locations.json"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48]
    return slug or str(uuid4())


def _create_id(name: str, existing_ids: set[str]) -> str:
    base = _slugify(name)
    candidate = base
    index = 2
    while candidate in existing_ids:
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def _to_schema(row: LocationModel) -> WeatherLocation:
    return WeatherLocation(
        id=row.id,
        name=row.name,
        latitude=row.latitude,
        longitude=row.longitude,
        createdAt=row.created_at,
        updatedAt=row.updated_at,
    )


def seed_locations_from_json() -> None:
    if not LOCATIONS_SEED_PATH.exists():
        return

    with SessionLocal() as db:
        if db.query(LocationModel).first() is not None:
            return

        raw_locations = json.loads(LOCATIONS_SEED_PATH.read_text(encoding="utf-8"))
        for item in raw_locations:
            created_at = datetime.fromisoformat(item["createdAt"].replace("Z", "+00:00"))
            updated_at = datetime.fromisoformat(item["updatedAt"].replace("Z", "+00:00"))
            db.add(
                LocationModel(
                    id=item["id"],
                    name=item["name"],
                    latitude=item["latitude"],
                    longitude=item["longitude"],
                    created_at=created_at,
                    updated_at=updated_at,
                )
            )
        db.commit()


def list_locations() -> list[WeatherLocation]:
    with SessionLocal() as db:
        rows = db.query(LocationModel).order_by(LocationModel.name).all()
        return [_to_schema(row) for row in rows]


def get_location(location_id: str) -> Optional[WeatherLocation]:
    with SessionLocal() as db:
        row = db.get(LocationModel, location_id)
        return _to_schema(row) if row else None


def create_location(payload: WeatherLocationCreate) -> WeatherLocation:
    with SessionLocal() as db:
        existing_ids = {row.id for row in db.query(LocationModel.id).all()}
        now = datetime.now(timezone.utc)
        row = LocationModel(
            id=_create_id(payload.name.strip(), existing_ids),
            name=payload.name.strip(),
            latitude=round(payload.latitude, 6),
            longitude=round(payload.longitude, 6),
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_schema(row)


def update_location(location_id: str, payload: WeatherLocationUpdate) -> Optional[WeatherLocation]:
    with SessionLocal() as db:
        row = db.get(LocationModel, location_id)
        if row is None:
            return None

        if payload.name is not None:
            row.name = payload.name.strip()
        if payload.latitude is not None:
            row.latitude = round(payload.latitude, 6)
        if payload.longitude is not None:
            row.longitude = round(payload.longitude, 6)
        row.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(row)
        return _to_schema(row)


def delete_location(location_id: str) -> bool:
    with SessionLocal() as db:
        row = db.get(LocationModel, location_id)
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True
