from __future__ import annotations

from typing import Any, Dict, List, Optional

# Hourly variables that get aggregated into a daily value because Open-Meteo
# does not expose a native daily aggregate for them. Each maps to how the
# 24 (or fewer, at range edges) hourly values for that day are reduced.
HOURLY_MEAN_FIELDS = {
    "relative_humidity_2m": "relative_humidity_2m_mean",
    "dew_point_2m": "dew_point_2m_mean",
    "surface_pressure": "surface_pressure_mean",
    "cloud_cover": "cloud_cover_mean",
    "apparent_temperature": "apparent_temperature_mean",
    "wind_speed_10m": "wind_speed_10m_mean",
    "visibility": "visibility_mean",
}
HOURLY_MAX_FIELDS = {
    "vapour_pressure_deficit": "vapour_pressure_deficit_max",
}


def _mean(values: List[Optional[float]]) -> Optional[float]:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


def _max(values: List[Optional[float]]) -> Optional[float]:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return max(present)


def group_hourly_by_date(hourly: Dict[str, Any]) -> Dict[str, Dict[str, List[Optional[float]]]]:
    """Groups hourly.time-indexed arrays into {date: {field: [values for that day]}}."""
    times: List[str] = hourly.get("time") or []
    by_date: Dict[str, Dict[str, List[Optional[float]]]] = {}

    for index, timestamp in enumerate(times):
        date = timestamp[:10]
        bucket = by_date.setdefault(date, {})
        for field in list(HOURLY_MEAN_FIELDS) + list(HOURLY_MAX_FIELDS):
            values = hourly.get(field)
            if values is None:
                continue
            bucket.setdefault(field, []).append(values[index] if index < len(values) else None)

    return by_date


def aggregate_daily_from_hourly(hourly: Dict[str, Any]) -> Dict[str, Dict[str, Optional[float]]]:
    """Returns {date: {aggregated_field: value}} for every date present in hourly.time."""
    grouped = group_hourly_by_date(hourly)
    result: Dict[str, Dict[str, Optional[float]]] = {}

    for date, fields in grouped.items():
        aggregated: Dict[str, Optional[float]] = {}
        for source_field, target_field in HOURLY_MEAN_FIELDS.items():
            aggregated[target_field] = _mean(fields.get(source_field, []))
        for source_field, target_field in HOURLY_MAX_FIELDS.items():
            aggregated[target_field] = _max(fields.get(source_field, []))
        result[date] = aggregated

    return result
