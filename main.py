import datetime
import threading

import kivy
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.screenmanager import ScreenManager
from kivymd.app import MDApp
from kivymd.uix import button as md_button
from kivymd.uix import slider, textfield
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.widget import Widget as MDWidget

from raincaster import core
from raincaster.kivy import radar_image_widget

if kivy.platform == "linux":
    Window.size = (500, 900)  # width, height in pixels
    Window.minimum_width = 400
    Window.minimum_height = 600

# Constants for zoom levels
MAX_ZOOM_LEVEL = 8
MIN_ZOOM_LEVEL = 5


def get_local_utc_offset_hours() -> int:
    import datetime

    now = datetime.datetime.now(datetime.UTC).astimezone()
    offset = now.utcoffset()
    return int(offset.total_seconds() // 3600)


class RadarScreen(MDScreen):
    zoom_level = NumericProperty(7)

    def __init__(self, app: "RaincasterApp", **kwargs):
        super().__init__(name="radar", **kwargs)
        self.app = app
        self.frame_past_data = []  # List of tuples (frame, image) for past data
        self.frame_data = []  # List of tuples (frame, image)
        self.location_info_text = ""
        layout = MDBoxLayout(orientation="vertical", padding=[dp(8)], spacing=dp(8))

        # Buttons row: location, zoom in, zoom out
        self.location_button = md_button.MDButton(
            md_button.MDButtonIcon(icon="crosshairs-gps"),
            on_release=self.on_location_button,
            theme_width="Custom",
            size_hint_x=None,
            size_hint_y=None,
            width=dp(48),
            height=dp(48),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            radius=[dp(0)],
        )

        self.location_info_label = MDLabel(
            text="...",
            halign="center",
            size_hint_y=None,
            md_bg_color=(0.6, 0.6, 0.5, 0.5),
            role="small",
            height=dp(32),
            padding=[dp(8)],
        )

        # Input fields for lat, lon, utc_offset, color
        self.lat_input = textfield.MDTextField(
            textfield.MDTextFieldHintText(text="Latitude"),
            mode="filled",
            text="50.2584",
            input_filter="float",
            size_hint_y=None,
            height=dp(48),
        )
        self.lon_input = textfield.MDTextField(
            textfield.MDTextFieldHintText(text="Longitude"),
            mode="filled",
            text="19.0275",
            input_filter="float",
            size_hint_y=None,
            height=dp(48),
        )
        # bind edit finished to lat and lon inputs to update location info
        self.lat_input.bind(on_text_validate=self.location_changed)
        self.lon_input.bind(on_text_validate=self.location_changed)

        self.color_input = textfield.MDTextField(
            text="8",
            input_filter="int",
            size_hint_y=None,
            size_hint_x=0.3,
            height=dp(48),
        )

        input_box = MDBoxLayout(
            orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(48)
        )
        input_box.add_widget(self.location_button)
        input_box.add_widget(self.lat_input)
        input_box.add_widget(self.lon_input)
        input_box.add_widget(self.color_input)
        layout.add_widget(input_box)
        layout.add_widget(self.location_info_label)

        # Fetch button
        self.fetch_button = md_button.MDButton(
            md_button.MDButtonIcon(icon="reload"),
            on_release=self.on_fetch_button,
            theme_width="Custom",
            size_hint_x=None,
            size_hint_y=None,
            width=dp(48),
            height=dp(48),
            radius=[dp(0)],
        )

        self.zoom_in_button = md_button.MDButton(
            md_button.MDButtonIcon(icon="magnify-plus-outline"),
            on_release=self.on_zoom_in,
            theme_width="Custom",
            size_hint_x=None,
            size_hint_y=None,
            width=dp(48),
            height=dp(48),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            radius=[dp(0)],
        )
        self.zoom_out_button = md_button.MDButton(
            md_button.MDButtonIcon(icon="magnify-minus-outline"),
            on_release=self.on_zoom_out,
            theme_width="Custom",
            size_hint_x=None,
            size_hint_y=None,
            width=dp(48),
            height=dp(48),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            radius=[dp(0)],
        )

        # Time label above image
        self.time_label = MDLabel(
            text="Loading...",
            halign="center",
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(48),
        )

        self.image_widget = radar_image_widget.RadarImageWidget(height=dp(350), size_hint_y=None)

        buttons_row = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(48),
        )

        buttons_row.add_widget(MDWidget())  # left spacer
        buttons_row.add_widget(self.zoom_in_button)
        buttons_row.add_widget(self.fetch_button)
        buttons_row.add_widget(self.zoom_out_button)
        buttons_row.add_widget(MDWidget())  # right spacer

        layout.add_widget(self.image_widget)
        layout.add_widget(buttons_row)
        layout.add_widget(self.time_label)

        # Slider below image
        self.time_slider = slider.MDSlider(
            slider.MDSliderHandle(),
            slider.MDSliderValueLabel(),
            min=0,
            max=1,
            value=0,
            step=1,
            size_hint_y=None,
            height=dp(48),
        )
        self.time_slider.bind(value=self.on_slider_value)

        self.direction_slider = slider.MDSlider(
            slider.MDSliderHandle(),
            slider.MDSliderValueLabel(),
            min=0,
            max=360,
            value=180,
            step=5,
            size_hint_y=None,
            height=dp(32),
        )
        self.direction_slider.bind(
            value=self.update_ui,
        )
        self.direction_slider.bind(
            on_touch_up=self._on_direction_slider_touch_up,
        )

        self.rain_arrive_forcast_label = MDLabel(
            text="...",
            halign="center",
            role="small",
            size_hint_y=None,
            md_bg_color=(0.6, 0.6, 0.8, 0.5),
            height=dp(48),
        )

        layout.add_widget(self.time_slider)
        layout.add_widget(
            MDLabel(
                text="Pick direction (degrees):",
                halign="center",
                size_hint_y=None,
                height=dp(32),
                md_bg_color=(0.6, 0.6, 0.8, 0.5),
                role="small",
                padding=[dp(8)],
            ),
        )
        layout.add_widget(self.direction_slider)
        layout.add_widget(self.rain_arrive_forcast_label)
        layout.add_widget(MDWidget())

        self.add_widget(layout)

        self.load_from_config()

    @mainthread
    def show_loading(self):
        self.time_label.text = "Fetching Radar Data ..."

    @mainthread
    def hide_loading(self):
        pass

    def on_enter(self, *_):
        self.show_loading()
        threading.Thread(target=self.fetch_radar_data).start()

    def load_from_config(self):
        """
        Load initial values from the app's config.
        This is called when the app starts to set default lat/lon/color.
        """
        config = self.app.app_config
        if "lat" in config:
            self.lat_input.text = str(config["lat"]["value"])
        if "lon" in config:
            self.lon_input.text = str(config["lon"]["value"])
        if "color" in config:
            self.color_input.text = str(config["color"]["value"])
        if "location_info" in config:
            self.location_info_text = config["location_info"]["value"]
            self.location_info_label.text = config["location_info"]["value"]

    def update_config(self):
        """
        Update the app's config with current lat/lon/color values.
        This is called after fetching radar data or when the user changes inputs.
        """
        self.app.app_config.put("lat", value=float(self.lat_input.text))
        self.app.app_config.put("lon", value=float(self.lon_input.text))
        self.app.app_config.put("color", value=int(self.color_input.text))
        self.app.app_config.put("location_info", value=self.location_info_text)

    def location_changed(self, *_):
        print("Location changed:", self.lat_input.text, self.lon_input.text)
        lat = float(self.lat_input.text)
        lon = float(self.lon_input.text)
        self.show_loading()
        self.location_info_text = core.get_location_info(lat=lat, lon=lon)
        threading.Thread(target=self.fetch_radar_data).start()

    def on_location_button(self, *_):
        try:
            from raincaster.kivy.gps import AndroidGPS

        except ImportError:
            # plyer is not installed
            self.lat_input.text = ""
            self.lon_input.text = ""
            self.time_label.text = "plyer not installed"
            return

        location_updated = False

        @mainthread
        def on_location(**kwargs):
            nonlocal location_updated
            lat = kwargs.get("lat")
            lon = kwargs.get("lon")
            if lat is not None and lon is not None:
                self.lat_input.text = str(lat)
                self.lon_input.text = str(lon)
                self.time_label.text = "Location updated"
                if not location_updated:
                    self.location_changed()
                    location_updated = True
                print(f"Location: lat={lat}, lon={lon}")
            else:
                self.time_label.text = "Location unavailable"

            gps.stop()

        def on_status(status_type: str, *_):
            if status_type == "provider-enabled":
                self.time_label.text = "Getting location..."
            elif status_type == "provider-disabled":
                self.time_label.text = "Location provider disabled"

        gps = AndroidGPS()
        gps.configure(on_location=on_location, on_status=on_status)
        try:
            gps.start()
            self.time_label.text = "Requesting location..."
        except (AttributeError, RuntimeError) as e:
            self.time_label.text = f"GPS error: {e}"

    def on_fetch_button(self, _instance):
        self.show_loading()
        threading.Thread(target=self.fetch_radar_data).start()

    def on_zoom_in(self, _instance):
        # Increase radar image zoom (decrease size parameter)
        self.zoom_level += 1
        if self.zoom_level > MAX_ZOOM_LEVEL:
            self.zoom_level = MAX_ZOOM_LEVEL
            return
        self.show_loading()
        threading.Thread(target=self.fetch_radar_data).start()

    def on_zoom_out(self, _instance):
        # Decrease radar image zoom (increase size parameter)
        self.zoom_level -= 1
        if self.zoom_level < MIN_ZOOM_LEVEL:
            self.zoom_level = MIN_ZOOM_LEVEL
            return
        self.show_loading()
        threading.Thread(target=self.fetch_radar_data).start()

    def fetch_radar_data(self, *_):
        try:
            # Get parameters from input fields
            lat = float(self.lat_input.text)
            lon = float(self.lon_input.text)
            color = int(self.color_input.text)

            weather_map = core.fetch_weather_maps()
            past_data, future_data = weather_map.fetch_all_radar_maps(
                lat=lat, lon=lon, zoom=self.zoom_level, color=color
            )
            self.frame_past_data = past_data
            self.frame_data = past_data + future_data
            self.update_ui()
            self.update_config()
        finally:
            # Ensure hiding overlay on main thread
            Clock.schedule_once(lambda *_: self.hide_loading(), 0)

    @mainthread
    def update_ui(self, *_args):
        self.time_slider.max = len(self.frame_data) - 1 if self.frame_data else 1
        self.location_info_label.text = self.location_info_text
        self.rain_arrive_forcast_label.text = ""
        self.on_slider_value(self.time_slider, self.time_slider.value)

    def on_slider_value(self, _instance, value: str | int):
        utc_offset = get_local_utc_offset_hours()
        idx = int(value)
        if not self.frame_data or idx < 0 or idx >= len(self.frame_data):
            self.time_label.text = "No data available"
            return
        frame, image = self.frame_data[idx]

        self.image_widget.set_radar_tile_size_km(
            core.tile_size_km(self.zoom_level, float(self.lat_input.text))
        )
        self.image_widget.set_radar_direction(self.direction_slider.value)
        self.image_widget.set_image(image)

        # Determine if the frame is in the past or future
        frame_time = frame.time_datetime(utc_offset)
        now = datetime.datetime.now(frame_time.tzinfo)

        new_time_str = frame.time_str(utc_offset)
        label_str = f"+{new_time_str}" if frame_time > now else f"-{new_time_str}"
        self.time_label.text = label_str

    def _on_direction_slider_touch_up(self, instance, touch):
        # Only trigger if the touch is on the slider handle
        if instance.collide_point(*touch.pos):
            self.direction_slider_updated()

    def direction_slider_updated(self, *_args):
        print(f"Direction slider updated: {self.direction_slider.value}")
        arrive_in_min, confidence, num_points = core.estimate_time_to_rain_start(
            self.frame_past_data, self.direction_slider.value
        )
        if arrive_in_min is None:
            info_str = "No rain prediction available!"
        elif arrive_in_min < 0:
            info_str = "Cannot estimate rain start time!"
        else:
            confidence = abs(int(confidence * 100))
            info_str = (
                f"Estimated rain start in {int(arrive_in_min)} minutes "
                f"(confidence={confidence}%, num samples={num_points})"
            )
        print(
            f"Estimated rain start in {arrive_in_min} minutes, "
            f"confidence: {confidence}, points: {num_points}"
        )
        self.rain_arrive_forcast_label.text = info_str


class RaincasterApp(MDApp):
    app_config = JsonStore("raincaster-config.json")

    def build(self):
        if kivy.platform == "android":
            from android.permissions import (  # type: ignore[import-untyped]
                Permission,
                request_permissions,
            )

            request_permissions(
                [
                    Permission.INTERNET,
                    Permission.ACCESS_COARSE_LOCATION,
                    Permission.ACCESS_FINE_LOCATION,
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE,
                ]
            )

        self.theme_cls.theme_style = "Dark"

        sm = ScreenManager()
        sm.add_widget(RadarScreen(self, md_bg_color=self.theme_cls.backgroundColor))
        return sm


if __name__ == "__main__":
    RaincasterApp().run()
