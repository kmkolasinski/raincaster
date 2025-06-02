"""
Rain Viewer Weather Maps API https://www.rainviewer.com/api/weather-maps-api.html

"""

import requests
import dataclasses
import functools
from concurrent import futures
from PIL import Image
from io import BytesIO
import datetime

RAIN_VIEWER_API_URL = "https://api.rainviewer.com/public/weather-maps.json"


@dataclasses.dataclass
class RadarFrame:
    time: int
    path: str

    @property
    def time_datetime(self, tz_shift: int = 0) -> datetime.datetime:
        """
        Map frame generation data in UNIX timestamp format (UTC).
        The map frame typically contains the images (radar, satellite) from different times,
        so this is not the time of the data rather than frame generation time.

        Parameters:
            tz_shift (int): Timezone shift in hours from UTC (e.g., 2 for UTC+2).

        Returns:
            dt: datetime object representing the time of the frame in the shifted timezone.
        """
        dt_utc = datetime.datetime.fromtimestamp(self.time, tz=datetime.timezone.utc)
        if tz_shift == 0:
            return dt_utc
        return dt_utc.astimezone(datetime.timezone(datetime.timedelta(hours=tz_shift)))


@dataclasses.dataclass
class Radar:
    past: list[RadarFrame]
    nowcast: list[RadarFrame] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Satellite:
    infrared: list[RadarFrame]


@dataclasses.dataclass
class WeatherMaps:
    version: str
    generated: int
    host: str
    radar: Radar
    satellite: Satellite

    @classmethod
    def from_dict(cls, data: dict) -> "WeatherMaps":
        radar_data = data.get("radar", {})
        satellite_data = data.get("satellite", {})

        radar = Radar(
            past=[RadarFrame(**frame) for frame in radar_data.get("past", [])],
            nowcast=[RadarFrame(**frame) for frame in radar_data.get("nowcast", [])],
        )

        satellite = Satellite(
            infrared=[
                RadarFrame(**frame) for frame in satellite_data.get("infrared", [])
            ]
        )

        return cls(
            version=data["version"],
            generated=data["generated"],
            host=data["host"],
            radar=radar,
            satellite=satellite,
        )

    def num_past_radar_frames(self) -> int:
        """
        Returns the number of radar frames available in the past.
        """
        return len(self.radar.past)

    def num_nowcast_radar_frames(self) -> int:
        """
        Returns the number of radar frames available in the nowcast.
        """
        return len(self.radar.nowcast)

    def fetch_all_radar_maps(
        self,
        *,
        lat: float = 50.061,
        lon: float = 19.938,
        zoom: int = 7,
        size: int = 512,
        color: int = 2,
        options: str = "1_0",
    ) -> tuple[list[tuple[RadarFrame, Image.Image]], list[tuple[RadarFrame, Image.Image]]]:
        """
        Fetches all radar maps from the past frames.

        Parameters:
            lat (float): Latitude for the map center.
            lon (float): Longitude for the map center.
            zoom (int): Zoom level of the map.
            size (int): Size of the map image.
            color (int): Color scheme for the map.
            options (str): Additional options for the map.

        Returns:
            tuple: A tuple containing two lists:
                - Past radar frames with their corresponding images.
                - Nowcast radar frames with their corresponding images.
        """

        _fetch_fn = functools.partial(
            fetch_radar_map_raw,
            host=self.host,
            lat=lat,
            lon=lon,
            zoom=zoom,
            size=size,
            color=color,
            options=options,
        )

        with futures.ThreadPoolExecutor() as executor:
            past_images = list(executor.map(_fetch_fn, self.radar.past))
            nowcast_images = list(executor.map(_fetch_fn, self.radar.nowcast))

        past_data = list(zip(self.radar.past, past_images))
        nowcast_data = list(zip(self.radar.nowcast, nowcast_images))
        return past_data, nowcast_data


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
        return WeatherMaps.from_dict(response.json())
    else:
        raise Exception(f"Failed to fetch weather maps: {response.status_code}")


def fetch_radar_map_raw(
    frame: RadarFrame,
    host: str,
    *,
    lat: float,
    lon: float,
    zoom: int = 7,
    size: int = 512,
    color: int = 2,
    options: str = "1_0",
) -> Image.Image:
    """Fetches a radar map image from RainViewer."""
    tile_url = f"{host}/{frame.path}/{size}/{zoom}/{lat}/{lon}/{color}/{options}.png"
    response = requests.get(tile_url)
    if response.status_code == 200:
        return Image.open(BytesIO(response.content))
    else:
        raise ValueError(f"Failed to download the radar tile: {response.status_code}")
