"""Keyless weather forecast via open-meteo (geocoding + forecast). Only these two hosts are ever called."""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field, model_validator

from forge.runtime.tools.base import Tool

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherArgs(BaseModel):
    location: str | None = Field(default=None, description="City or port name, e.g. 'Rotterdam'")
    latitude: float | None = None
    longitude: float | None = None
    days: int = Field(default=3, ge=1, le=7)

    @model_validator(mode="after")
    def _need_place(self):
        if not self.location and (self.latitude is None or self.longitude is None):
            raise ValueError("give a location name or latitude+longitude")
        return self


class WeatherTool(Tool):
    name = "http_weather"
    description = "Daily weather forecast (temperature, precipitation, max wind) for a place, from open-meteo."
    Args = WeatherArgs

    def __init__(self, config=None, base_dir=None, client: httpx.Client | None = None):
        super().__init__(config, base_dir)
        self.client = client or httpx.Client(timeout=5.0)

    def _run(self, args: WeatherArgs):
        place = args.location or f"{args.latitude},{args.longitude}"
        lat, lon = args.latitude, args.longitude
        if lat is None or lon is None:
            r = self.client.get(GEO_URL, params={"name": args.location, "count": 1})
            r.raise_for_status()
            results = r.json().get("results") or []
            if not results:
                raise ValueError(f"place not found: {args.location}")
            g = results[0]
            lat, lon = g["latitude"], g["longitude"]
            place = ", ".join(x for x in (g.get("name"), g.get("country")) if x)
        r = self.client.get(FORECAST_URL, params={
            "latitude": lat, "longitude": lon, "forecast_days": args.days, "timezone": "auto",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max"})
        r.raise_for_status()
        daily = r.json().get("daily", {})
        days = []
        for i, day in enumerate(daily.get("time", [])):
            days.append({"date": day,
                         "temp_max_c": daily.get("temperature_2m_max", [None])[i],
                         "temp_min_c": daily.get("temperature_2m_min", [None])[i],
                         "precipitation_mm": daily.get("precipitation_sum", [None])[i],
                         "wind_max_kmh": daily.get("wind_speed_10m_max", [None])[i]})
        return {"place": place, "latitude": lat, "longitude": lon, "source": "open-meteo", "daily": days}
