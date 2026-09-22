"""Helpers for downloading hourly NASA POWER weather data."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Tuple

import pvlib
from geopy.geocoders import Nominatim
from pvlib.location import Location
from timezonefinder import TimezoneFinder


class PVLibWeatherFetcher:
    """Resolve a place name and fetch weather data suitable for pvlib."""

    def __init__(self, user_agent: str = "masters-thesis-weather-fetcher") -> None:
        """Create a geocoder with an explicit user-agent required by Nominatim."""
        if not user_agent.strip():
            raise ValueError("user_agent must not be empty")
        self.geolocator = Nominatim(user_agent=user_agent)

    @staticmethod
    def _parse_date(value: int) -> str:
        """Convert `YYYYMMDD` integer input to an ISO date."""
        try:
            return datetime.strptime(str(value), "%Y%m%d").date().isoformat()
        except ValueError as error:
            raise ValueError(f"Invalid date {value!r}; expected YYYYMMDD") from error

    def fetch(self, location_name: str, start: int, end: int) -> Tuple[Any, dict, Location]:
        """Fetch weather, metadata and a timezone-aware pvlib location."""
        if not location_name or not location_name.strip():
            raise ValueError("location_name must not be empty")
        start_date, end_date = self._parse_date(start), self._parse_date(end)
        if start_date > end_date:
            raise ValueError("start must not be after end")
        location = self.geolocator.geocode(location_name)
        if location is None:
            raise ValueError(f"Location not found: {location_name}")
        df, metadata = pvlib.iotools.get_nasa_power(
            location.latitude, location.longitude, start_date, end_date,
            parameters=["dni", "dhi", "ghi", "temp_air", "wind_speed"],
            url="https://power.larc.nasa.gov/api/temporal/hourly/point",
        )
        timezone = TimezoneFinder().timezone_at(lng=location.longitude, lat=location.latitude) or "UTC"
        pv_location = Location(location.latitude, location.longitude, tz=timezone)
        return df, metadata, pv_location
