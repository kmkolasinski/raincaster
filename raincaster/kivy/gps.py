# https://github.com/kivy/plyer/blob/master/plyer/platforms/android/gps.py
# https://github.com/kivy/plyer/blob/master/plyer/facades/gps.py
# https://github.com/kivy/plyer/pull/665/files/1f84fcd24a44877522a8e2edf885c708e8158466#diff-7b226d7966dc78fa6d19906d5f3998770aeae657b2cdbcd34533f2c14b5d24da
from jnius import PythonJavaClass, autoclass, java_method
from plyer.facades import GPS
from plyer.platforms.android import activity

# from plyer import gps
from plyer.utils import platform

Looper = autoclass("android.os.Looper")
LocationManager = autoclass("android.location.LocationManager")
Context = autoclass("android.content.Context")

if platform == "android":
    Location = autoclass("android.location.Location")


class MyLocationListener(PythonJavaClass):
    __javainterfaces__ = ["android/location/LocationListener"]
    __javacontext__ = "app"

    def __init__(self, root: "AndroidGPS"):
        self.root = root
        super().__init__()

    # old API (<= 30)
    @java_method("(Landroid/location/Location;)V", name="onLocationChanged")
    def onLocationChanged_location(self, location):
        print(f">> onLocationChanged: {location}")
        self._dispatch(location)

    # old API (<=30)
    @java_method("(Landroid/location/Location;)V")
    def onLocationChanged(self, location):
        print(f">> onLocationChanged: {location}")
        self._dispatch(location)

    # new API (>=31)
    @java_method("(Ljava/util/List;)V")
    def onLocationChanged(self, locations):  # noqa
        print(f">> onLocationChanged[list]: {locations}")
        if locations and locations.size() > 0:
            self._dispatch(locations.get(0))

    def _dispatch(self, loc):
        self.root.on_location(lat=loc.getLatitude(), lon=loc.getLongitude())

    @java_method("(Ljava/lang/String;)V")
    def onProviderEnabled(self, provider):
        pass

    @java_method("(Ljava/lang/String;)V")
    def onProviderDisabled(self, provider):
        pass

    @java_method("(Ljava/lang/String;ILandroid/os/Bundle;)V")
    def onStatusChanged(self, provider, status, extras):
        if self.root.on_status:
            s_status = "unknown"
            if status == 0x00:
                s_status = "out-of-service"
            elif status == 0x01:
                s_status = "temporarily-unavailable"
            elif status == 0x02:
                s_status = "available"
            self.root.on_status("provider-status", f"{provider}: {s_status}")


class AndroidGPS(GPS):
    def _configure(self):
        if not hasattr(self, "_location_manager"):
            self._location_manager = activity.getSystemService(Context.LOCATION_SERVICE)
            self._location_listener = MyLocationListener(self)

    def _start(self, **kwargs):
        min_time = kwargs.get("minTime")
        min_distance = kwargs.get("minDistance")
        providers = self._location_manager.getProviders(False).toArray()
        for provider in providers:
            self._location_manager.requestLocationUpdates(
                provider,
                min_time,  # minTime, in milliseconds
                min_distance,  # minDistance, in meters
                self._location_listener,
                Looper.getMainLooper(),
            )

    def _stop(self):
        self._location_manager.removeUpdates(self._location_listener)
