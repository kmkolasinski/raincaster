"""
Rain Viewer Weather Maps API https://www.rainviewer.com/api/weather-maps-api.html

"""

import dataclasses
import datetime
import functools
import math
from concurrent import futures
from io import BytesIO

import certifi
import numpy as np
import requests
from PIL import Image

RAIN_VIEWER_API_URL = "https://api.rainviewer.com/public/weather-maps.json"


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


def fetch_weather_maps(api_url: str = RAIN_VIEWER_API_URL, timeout: float = 100) -> WeatherMaps:
    """
    Fetches weather maps JSON data from RainViewer API.

    Parameters:
        api_url (str): URL of the RainViewer API.
        timeout (float): Timeout for the API request in seconds.

    Returns:
        tuple: A tuple containing the host and radar data.
    """

    response = requests.get(api_url, timeout=timeout)
    if response.ok:
        return WeatherMaps.from_dict(response.json())
    raise ValueError(f"Failed to fetch weather maps: {response.status_code}")


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
    timeout: float = 100.0,
) -> Image.Image:
    """Fetches a radar map image from RainViewer."""
    tile_url = f"{host}/{frame.path}/{size}/{zoom}/{lat}/{lon}/{color}/{options}.png"
    response = requests.get(tile_url, timeout=timeout)
    if response.ok:
        return Image.open(BytesIO(response.content))
    raise ValueError(f"Failed to download the radar tile: {response.status_code}")


def cross_section(
    image, angle: float, channel: int = 0
) -> tuple[list[tuple[int, int]], list[float], list[float]]:
    """
    Sample pixels along a line at the given angle (in degrees) through the center of the image.
    Does not use interpolation, just nearest-pixel sampling.

    Args:
        image: np.ndarray (H, W, C) or (H, W)
        angle: float (degrees)
        channel: int, for color images

    Returns:
        coords: list of (y, x) tuples representing pixel coordinates along the cross-section
        values: list of pixel values at those coordinates
        distances: list of distances from the center of the image to each coordinate

    """
    img = np.asarray(image)
    if img.ndim == 3:  # noqa: PLR2004
        img = img[..., channel]
    height, width = img.shape
    cy, cx = height / 2, width / 2  # Image center

    angle = np.deg2rad(angle)
    dx = np.cos(angle)
    dy = np.sin(angle)

    # Maximum number of steps in either direction from the center
    max_dist = int(np.ceil(np.sqrt(height**2 + width**2) / 2))

    coords: list[tuple[int, int]] = []

    for n in range(max_dist):
        x = cx + n * dx
        y = cy + n * dy
        ix, iy = int(round(x)), int(round(y))
        if 0 <= ix < width and 0 <= iy < height:
            coords.append((iy, ix))
        else:
            break

    def _distance(pt: tuple[int, int]) -> float:
        """Calculate distance from the center."""
        return math.sqrt((pt[0] - cy) ** 2 + (pt[1] - cx) ** 2)

    coords = sorted(coords, key=lambda pt: _distance(pt))
    values = np.array([float(img[pt[0], pt[1]]) for pt in coords])
    distances = [_distance(pt) for pt in coords]
    return coords, values, distances


def cluster_cross_section_rain_regions(
    values: np.ndarray, threshold: float = 0.3
) -> list[np.ndarray]:
    values = np.array(values)

    values[values < threshold] = 0.0
    values[values >= threshold] = 1.0

    indices = np.where(values == 1.0)[0]
    return np.split(indices, np.where(np.diff(indices) != 1)[0] + 1)


def simplify_cross_section_rain_regions(
    values: np.ndarray, min_cluster_size: float, threshold: float = 0.3
) -> np.ndarray:
    clusters = cluster_cross_section_rain_regions(values, threshold)
    new_values = np.zeros_like(values)

    if len(clusters) <= 1:
        for cluster in clusters:
            new_values[cluster] = 1.0
        return new_values

    clusters_indices = list(range(len(clusters)))
    for left_i, right_i in zip(clusters_indices[:-1], clusters_indices[1:], strict=True):  # noqa: RUF007
        left_max_idx = clusters[left_i].max()
        right_min_idx = clusters[right_i].min()
        if right_min_idx - left_max_idx < min_cluster_size:
            clusters[right_i] = np.arange(clusters[left_i].min(), clusters[right_i].max() + 1)

    for cluster in clusters[1:-1]:
        if len(cluster) >= min_cluster_size:
            new_values[cluster] = 1.0

    for cluster in [clusters[0], clusters[-1]]:
        new_values[cluster] = 1.0

    return new_values


def find_first_above_threshold(cross: np.ndarray, threshold: float = 0.5) -> int:
    for i, value in enumerate(cross):
        if value > threshold:
            return i
    return -1


def estimate_time_to_rain_start(
    frame_data: list[tuple[RadarFrame, Image.Image]], direction_angle: float
):
    signal_data = []

    for frame, image in frame_data:
        image_np = np.array(image)
        alpha = image_np[..., 3] / 255.0
        image_np = image_np[..., :3].mean(axis=-1) * alpha
        image_np /= image_np.max()

        coords, cross, distances = cross_section(image_np, direction_angle)
        signal_data.append((frame.time, coords, cross, distances))

    clusters = []
    sizes = []
    for _, _, cross, _ in signal_data:
        cluster = cluster_cross_section_rain_regions(cross)
        sizes += [len(c) for c in cluster]
        clusters.append(cluster)
    mean_size = 0.5 * float(np.mean(sizes))
    print(f"Mean Rain cluster size: {mean_size:.2f}")

    distance_to_rain = []
    timestamps = []

    for timestamp, _, cross, distances in signal_data:
        cross_simp = simplify_cross_section_rain_regions(cross, mean_size)
        first_index = find_first_above_threshold(cross_simp)
        if first_index == -1:
            timestamps = []
            distance_to_rain = []
            continue
        distance = distances[first_index]
        if distance < 1:
            timestamps = []
            distance_to_rain = []
            continue
        timestamps.append(timestamp)
        distance_to_rain.append(distance)

    if len(timestamps) < 3:
        return None, None, len(timestamps)

    if len(timestamps) > 5:
        print("Too many timestamps, using only the last 5 for fitting.")
        # Use only the last 5 timestamps for fitting
        timestamps = timestamps[-5:]
        distance_to_rain = distance_to_rain[-5:]

    to_arrive, correlation_coefficient = fit_time_to_rain(timestamps, distance_to_rain)
    return to_arrive / 60, correlation_coefficient, len(timestamps)


def fit_time_to_rain(timestamps: list[int], distance_to_rain: list[float]) -> tuple[float, float]:
    coefficients = np.polyfit(timestamps, distance_to_rain, 1)
    correlation_matrix = np.corrcoef(timestamps, distance_to_rain)
    correlation_coefficient = correlation_matrix[0, 1]

    time_to_arrive = -distance_to_rain[-1] / coefficients[0]
    arrive_at_timestamp = timestamps[-1] + time_to_arrive
    seconds_to_arrive = arrive_at_timestamp - datetime.datetime.now(tz=datetime.UTC).timestamp()

    return seconds_to_arrive, correlation_coefficient


def tile_size_km(zoom: int, latitude: float = 0.0) -> float:
    """
    Returns the approximate width (and height) in km of a map tile at a given zoom
    level and latitude. By default, calculation is for the equator.
    """
    # Earth's circumference in kilometers (at the equator)
    earth_circum_km = 40075.0
    # Number of tiles per axis at this zoom
    n_tiles = 2**zoom
    # Tile size at equator
    tile_km = earth_circum_km / n_tiles
    # Adjust for latitude
    return tile_km * math.cos(math.radians(latitude))


def get_location_info(lat: float, lon: float, timeout: float = 100.0) -> str:
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "accept-language": "en",
        "addressdetails": 1,
    }
    headers = {"User-Agent": "Raincaster/1.0 (raincaster@app.com)"}

    response = requests.get(
        url, timeout=timeout, params=params, headers=headers, verify=certifi.where()
    )

    if response.ok:
        location_data = response.json()
        if "address" in location_data:
            address = location_data["address"]
            house_number = address.get("house_number", "")
            road = address.get("road", "") or address.get("neighbourhood", "")
            city = address.get("city", "") or address.get("town", "") or address.get("village", "")
            return f"{road} {house_number}, {city}".replace("  ", " ").replace(" , ", ", ").strip()

        return "Cannot Parse Location info"

    return "Cannot Get Location Info"
