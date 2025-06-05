"""
Rain Viewer Weather Maps API https://www.rainviewer.com/api/weather-maps-api.html

"""

import dataclasses
import datetime
import functools
import math
from concurrent import futures
from io import BytesIO

import numpy as np
import requests
from PIL import Image

RAIN_VIEWER_API_URL = "https://api.rainviewer.com/public/weather-maps.json"

# source https://www.noaa.gov/jetstream/reflectivity
# dBZ values must be checked *downward* (start high), to match the correct rain rate
dbz_thresholds = [65, 60, 55, 50, 45, 40, 35, 30, 25, 20]
rain_rate_in_hr = [
    "16+",
    "8.00",
    "4.00",
    "1.90",
    "0.92",
    "0.45",
    "0.22",
    "0.10",
    "0.05",
    "0.01",
]
rain_rate_mm_hr = ["420+", "205", "100", "47", "24", "12", "6", "3", "1", "Trace"]


@dataclasses.dataclass
class RadarFrame:
    time: int
    path: str

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
        dt_utc = datetime.datetime.fromtimestamp(self.time, tz=datetime.UTC)
        if tz_shift == 0:
            return dt_utc
        return dt_utc.astimezone(datetime.timezone(datetime.timedelta(hours=tz_shift)))

    def time_str(self, tz_shift: int = 0) -> str:
        """
        Returns the time of the frame as a formatted string in the shifted timezone.

        Parameters:
            tz_shift (int): Timezone shift in hours from UTC (e.g., 2 for UTC+2).

        Returns:
            str: Formatted time string.
        """
        return self.time_datetime(tz_shift).strftime("%H:%M:%S")


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
            infrared=[RadarFrame(**frame) for frame in satellite_data.get("infrared", [])]
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
        color: int = 0,
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

        past_data = list(zip(self.radar.past, past_images, strict=False))
        nowcast_data = list(zip(self.radar.nowcast, nowcast_images, strict=False))
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


def dbz_to_rain_rate(dbz: int) -> tuple[str, str]:
    """
    Given a dBZ value, return the corresponding rain rate
    in in/hr and mm/hr as strings from the category table.
    """
    for thresh, inhr, mmhr in zip(dbz_thresholds, rain_rate_in_hr, rain_rate_mm_hr, strict=False):
        if dbz >= thresh:
            return inhr, mmhr
    # If below lowest threshold, return lowest rain rates
    return rain_rate_in_hr[-1], rain_rate_mm_hr[-1]


def cross_section(image, angle: float, channel: int = 0) -> list[float]:
    """
    Sample pixels along a line at the given angle (in degrees) through the center of the image.
    Does not use interpolation, just nearest-pixel sampling.

    Args:
        image: np.ndarray (H, W, C) or (H, W)
        angle: float (degrees)
        channel: int, for color images

    Returns:
        List of pixel values along the line (center included)
    """
    img = np.asarray(image)
    if img.ndim == 3:
        img = img[..., channel]
    H, W = img.shape
    cy, cx = (H) / 2, (W) / 2  # Image center

    angle = np.deg2rad(angle)
    dx = np.cos(angle)
    dy = np.sin(angle)
    # print(f"Cross-section angle: {angle} radians, direction: ({dx}, {dy})")

    # Maximum number of steps in either direction from the center
    max_dist = int(np.ceil(np.sqrt(H**2 + W**2) / 2))

    coords = []
    # Forward direction
    for n in range(max_dist):
        x = cx + n * dx
        y = cy + n * dy
        ix, iy = int(round(x)), int(round(y))
        # print(n, x, y, ix, iy)
        if 0 <= ix < W and 0 <= iy < H:
            coords.append((iy, ix))
        else:
            break
    # Backward direction
    for n in range(1, max_dist):  # start from 1 to avoid duplicating the center
        x = cx - n * dx
        y = cy - n * dy
        ix, iy = int(round(x)), int(round(y))
        if 0 <= ix < W and 0 <= iy < H:
            coords.insert(0, (iy, ix))
        else:
            break

    # Sort points along the line (by their n, which is their projection along direction)
    coords = list(coords)
    # To sort, project to direction vector (dx,dy) from center
    # coords.sort(key=lambda pt: (pt[0] - cy) * dy + (pt[1] - cx) * dx)
    # print(coords)
    values = [img[pt[0], pt[1]] for pt in coords]
    return coords, np.array(values)


def tile_size_km(zoom: int, latitude: float = 0.0) -> float:
    """
    Returns the approximate width (and height) in km of a map tile at a given zoom level and latitude.
    By default, calculation is for the equator.
    """
    # Earth's circumference in kilometers (at the equator)
    earth_circum_km = 40075.0
    # Number of tiles per axis at this zoom
    n_tiles = 2**zoom
    # Tile size at equator
    tile_km = earth_circum_km / n_tiles
    # Adjust for latitude
    tile_km_lat = tile_km * math.cos(math.radians(latitude))
    return tile_km_lat
