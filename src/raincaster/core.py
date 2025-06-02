import requests
from dataclasses import dataclass, field
from typing import List, Optional
import json

RAIN_VIEWER_API_URL = "https://api.rainviewer.com/public/weather-maps.json"


@dataclass
class RadarFrame:
    time: int
    path: str


@dataclass
class SatelliteFrame:
    time: int
    path: str


@dataclass
class Radar:
    past: List[RadarFrame]
    nowcast: Optional[List[RadarFrame]] = field(default_factory=list)


@dataclass
class Satellite:
    infrared: List[SatelliteFrame]


@dataclass
class WeatherMaps:
    version: str
    generated: int
    host: str
    radar: Radar
    satellite: Satellite


def fetch_weather_maps(api_url: str = RAIN_VIEWER_API_URL) -> WeatherMaps:
    """
    Fetches weather maps JSON data from RainViewer API.

    Parameters:
        api_url (str): URL of the RainViewer API.

    Returns:
        tuple: A tuple containing the host and radar data.
    """

    response = requests.get(api_url)
    if response.status_code == 200:
        return WeatherMaps(**response.json())
    else:
        raise Exception(f"Failed to fetch weather maps: {response.status_code}")
