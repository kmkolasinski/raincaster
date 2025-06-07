from raincaster import core


def test__fetch_weather_maps():
    maps = core.fetch_weather_maps()
    assert hasattr(maps, "host")
    assert hasattr(maps, "radar")
    assert hasattr(maps, "satellite")
    assert isinstance(maps.host, str)
    assert hasattr(maps.radar, "past")
    assert isinstance(maps.radar.past, list)


def test__tile_size_km():
    size = core.tile_size_km(zoom=7, latitude=50.061)
    assert int(size) == 200


def test__get_location_info():
    location = core.get_location_info(lat=50, lon=14)
    assert location != "Cannot GPS location info"
