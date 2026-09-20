import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pvlib
from pvlib.location import Location

class PVLibWeatherFetcher:
    def __init__(self, user_agent="user-agent"):
        self.geolocator = Nominatim(user_agent=user_agent)
        self.ROOT = Path().resolve().parents[1]

    def fetch(self, location_name: str, start: int, end: int):
        loc = self.geolocator.geocode(location_name)
        START = datetime.strptime(str(start), "%Y%m%d").date().isoformat()
        END = datetime.strptime(str(end), "%Y%m%d").date().isoformat()
        if not loc:
            raise ValueError("Location not found")

        data_path = self.ROOT / 'src' / 'data' / 'weather.csv'
        df, meta = pvlib.iotools.get_nasa_power(loc.latitude, loc.longitude,
                                                START, END,
                                     parameters=['dni', 'dhi', 'ghi',
                                                 'temp_air', 'wind_speed'],
                                     url='https://power.larc.nasa.gov/api/temporal/hourly/point')

        tf = TimezoneFinder()
        timezone = tf.timezone_at(lng=loc.longitude, lat=loc.latitude)
        location = Location(latitude=loc.latitude, longitude=loc.longitude,
                            tz=timezone)
        return df, meta, location