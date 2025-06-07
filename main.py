import datetime

import kivy
from kivy.clock import mainthread
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import (
    ListProperty,
    NumericProperty,
    StringProperty,
)
from kivy.uix.screenmanager import Screen, ScreenManager
from kivymd.app import MDApp
from kivymd.uix import button as md_button
from kivymd.uix import slider, textfield
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.widget import Widget as MDWidget

from raincaster import core
from raincaster.kivy import radar_image

if kivy.platform == "linux":
    Window.size = (500, 900)  # width, height in pixels
    Window.minimum_width = 400
    Window.minimum_height = 600

# Constants for zoom levels
MAX_ZOOM_LEVEL = 8
MIN_ZOOM_LEVEL = 5


def get_local_utc_offset_hours():
    import datetime

    now = datetime.datetime.now(datetime.UTC).astimezone()
    offset = now.utcoffset()
    return int(offset.total_seconds() // 3600)


class RadarScreen(Screen):
    current_frame = NumericProperty(0)
    zoom_level = NumericProperty(7)
    past_images = ListProperty()
    past_times = ListProperty()
    current_time_str = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(name="radar", **kwargs)

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

        # Input fields for lat, lon, utc_offset, color
        self.lat_input = textfield.MDTextField(
            textfield.MDTextFieldHintText(text="Latitude"),
            mode="filled",
            text="50.07317",
            input_filter="float",
            size_hint_y=None,
            height=dp(48),
        )
        self.lon_input = textfield.MDTextField(
            textfield.MDTextFieldHintText(text="Longitude"),
            mode="filled",
            text="19.8948",
            input_filter="float",
            size_hint_y=None,
            height=dp(48),
        )
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

        self.image_widget = radar_image.RadarImage()

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
        self.slider = slider.MDSlider(
            slider.MDSliderHandle(),
            slider.MDSliderValueLabel(),
            min=0,
            max=1,
            value=0,
            step=1,
            size_hint_y=None,
            height=dp(48),
        )
        self.slider.bind(value=self.on_slider_value)
        layout.add_widget(self.slider)
        layout.add_widget(MDWidget())

        self.add_widget(layout)
        self.fetch_radar_data()

    def on_location_button(self, *_):
        try:
            from raincaster.kivy.gps import AndroidGPS

        except ImportError:
            # plyer is not installed
            self.lat_input.text = ""
            self.lon_input.text = ""
            self.time_label.text = "plyer not installed"
            return

        @mainthread
        def on_location(**kwargs):
            lat = kwargs.get("lat")
            lon = kwargs.get("lon")
            if lat is not None and lon is not None:
                self.lat_input.text = str(lat)
                self.lon_input.text = str(lon)
                self.time_label.text = "Location updated"
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
        self.fetch_radar_data()

    def on_zoom_in(self, _instance):
        # Increase radar image zoom (decrease size parameter)
        self.zoom_level += 1
        if self.zoom_level > MAX_ZOOM_LEVEL:
            self.zoom_level = MAX_ZOOM_LEVEL
            return
        self.fetch_radar_data()

    def on_zoom_out(self, _instance):
        # Decrease radar image zoom (increase size parameter)
        self.zoom_level -= 1
        if self.zoom_level < MIN_ZOOM_LEVEL:
            self.zoom_level = MIN_ZOOM_LEVEL
            return
        self.fetch_radar_data()

    def fetch_radar_data(self):
        # Get parameters from input fields
        lat = float(self.lat_input.text)
        lon = float(self.lon_input.text)
        self.utc_offset = get_local_utc_offset_hours()

        color = int(self.color_input.text)

        weather_map = core.fetch_weather_maps()
        past_data, future_data = weather_map.fetch_all_radar_maps(
            lat=lat, lon=lon, zoom=self.zoom_level, color=color
        )
        self.frame_data = past_data + future_data
        self.update_ui()

    def update_ui(self):
        self.slider.max = len(self.frame_data) - 1 if self.frame_data else 1
        self.on_slider_value(self.slider, self.slider.value)

    def on_slider_value(self, _instance, value):
        idx = int(value)
        new_time_str = self.frame_data[idx][0].time_str(self.utc_offset)

        self.image_widget.set_radar_tile_size_km(
            core.tile_size_km(self.zoom_level, float(self.lat_input.text))
        )
        self.image_widget.set_image(self.frame_data[idx][1])

        # Determine if the frame is in the past or future

        frame_time = self.frame_data[idx][0].time_datetime(self.utc_offset)
        now = datetime.datetime.now(frame_time.tzinfo)
        label_str = f"+{new_time_str}" if frame_time > now else f"-{new_time_str}"

        self.time_label.text = label_str
        self.current_frame = idx
        self.current_time_str = new_time_str


class RaincasterApp(MDApp):
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
                ]
            )

        self.theme_cls.theme_style = "Dark"

        sm = ScreenManager()
        sm.add_widget(RadarScreen())
        return sm


if __name__ == "__main__":
    RaincasterApp().run()
