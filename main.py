import time
import webbrowser

import kivy
from kivy.clock import mainthread, Clock
from kivy.metrics import dp
from kivy.core.window import Window


from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivymd.app import MDApp
from kivymd.uix import dialog as md_dialog
from kivymd.uix import list as md_list
from kivymd.uix import textfield
from kivymd.uix import appbar
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix import button as md_button
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.list import MDList
from kivymd.uix.scrollview import ScrollView, MDScrollView
from kivymd.uix import selectioncontrol
from kivymd.uix.widget import Widget
from kivymd.uix.divider import MDDivider
from kivymd.uix import progressindicator
from kivymd.uix import segmentedbutton as md_segmentedbutton
from raincaster import core
from kivy.uix.image import Image
from kivy.properties import NumericProperty, ListProperty, StringProperty
from kivymd.uix.slider import MDSlider
from kivy.graphics import Color, Rectangle
from PIL import Image as PILImage
from kivy.core.image import Image as CoreImage
from io import BytesIO
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.graphics import Color, Ellipse, Rectangle
from kivymd.uix.textfield import MDTextField
from kivy.properties import ObjectProperty
from kivy.uix.widget import Widget
from kivy.properties import ObjectProperty, BooleanProperty
from kivy.graphics import Rectangle, Color, Ellipse, Line


if kivy.platform == "linux":
    Window.size = (500, 900)  # width, height in pixels
    Window.minimum_width = 400
    Window.minimum_height = 600


class ImageWithCircle(Widget):
    texture = ObjectProperty(None, allownone=True)
    keep_ratio = BooleanProperty(True)

    def __init__(self, texture=None, keep_ratio=True, **kwargs):
        super().__init__(**kwargs)
        self.texture = texture
        self.keep_ratio = keep_ratio
        self.bind(
            pos=self.update_canvas,
            size=self.update_canvas,
            texture=self.update_canvas,
            keep_ratio=self.update_canvas,
        )

    def update_canvas(self, *args):
        self.canvas.clear()
        with self.canvas:
            if self.texture:
                if self.keep_ratio:
                    # Calculate rectangle preserving aspect ratio
                    tex_w, tex_h = self.texture.size
                    box_w, box_h = self.width, self.height
                    scale = min(box_w / tex_w, box_h / tex_h)
                    draw_w, draw_h = tex_w * scale, tex_h * scale
                    draw_x = self.x + (box_w - draw_w) / 2
                    draw_y = self.y + (box_h - draw_h) / 2
                    Rectangle(
                        texture=self.texture,
                        pos=(draw_x, draw_y),
                        size=(draw_w, draw_h),
                    )
                else:
                    Rectangle(texture=self.texture, pos=self.pos, size=self.size)
            # You can leave this part or change as needed
            Color(0, 0, 0, 0.7)
            d = min(self.width, self.height) / 5
            d = min(self.width, self.height) / 5
            Line(
                ellipse=(
                    self.center_x - d / 2,  # x
                    self.center_y - d / 2,  # y
                    d,  # width
                    d,  # height
                ),
                width=2,
            )  # set width of outline as desired
            d = d / 10
            Ellipse(
                pos=(self.center_x - d / 2, self.center_y - d / 2),
                size=(d, d),
            )  # Draw the circle with the texture


def pil_to_texture(pil_image):
    # Composite alpha channel over white
    if pil_image.mode in ("RGBA", "LA"):
        background = PILImage.new("RGBA", pil_image.size, (255, 255, 255, 255))
        background.paste(
            pil_image, mask=pil_image.split()[-1]
        )  # Use alpha channel as mask
        pil_image = background.convert("RGB")
    else:
        pil_image = pil_image.convert("RGB")

    buf = BytesIO()
    pil_image.save(buf, format="PNG")
    buf.seek(0)
    return CoreImage(buf, ext="png").texture


class RadarScreen(Screen):
    current_frame = NumericProperty(0)
    past_images = ListProperty()
    past_times = ListProperty()
    current_time_str = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(name="radar", **kwargs)

        layout = MDBoxLayout(orientation="vertical", padding=[dp(8)], spacing=dp(8))

        # Input fields for lat, lon, utc_offset, color
        self.lat_input = MDTextField(
            hint_text="Latitude",
            text="51.27373",
            input_filter="float",
            size_hint_y=None,
            height=dp(48),
        )
        self.lon_input = MDTextField(
            hint_text="Longitude",
            text="15.93661",
            input_filter="float",
            size_hint_y=None,
            height=dp(48),
        )
        self.utc_offset_input = MDTextField(
            hint_text="UTC Offset",
            text="2",
            input_filter="int",
            size_hint_x=0.3,
            size_hint_y=None,
            height=dp(48),
        )
        self.color_input = MDTextField(
            hint_text="Color Number",
            text="8",
            input_filter="int",
            size_hint_y=None,
            size_hint_x=0.3,
            height=dp(48),
        )

        input_box = MDBoxLayout(
            orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(48)
        )
        input_box.add_widget(self.lat_input)
        input_box.add_widget(self.lon_input)
        input_box.add_widget(self.utc_offset_input)
        input_box.add_widget(self.color_input)
        layout.add_widget(input_box)

        # Fetch button
        self.fetch_button = md_button.MDButton(
            md_button.MDButtonText(
                text="Fetch Radar Data", pos_hint={"center_x": 0.5, "center_y": 0.5}
            ),
            on_release=self.on_fetch_button,
            theme_width="Custom",
            size_hint_x=1.0,
        )

        # Time label above image
        self.time_label = MDLabel(
            text="Loading...",
            halign="center",
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(32),
        )

        self.image_widget = ImageWithCircle(texture=None)
        layout.add_widget(self.image_widget)
        layout.add_widget(self.fetch_button)
        layout.add_widget(self.time_label)
        # Add a divider
        layout.add_widget(MDDivider())
        layout.add_widget(Widget())

        # Slider below image
        self.slider = MDSlider(
            min=0,
            max=1,
            value=0,
            step=1,
            size_hint_y=None,
            height=dp(48),
        )
        self.slider.bind(value=self.on_slider_value)
        layout.add_widget(self.slider)

        self.add_widget(layout)
        self.fetch_radar_data()  # Initial fetch

    def on_fetch_button(self, instance):
        self.fetch_radar_data()

    def fetch_radar_data(self):
        # Get parameters from input fields
        lat = float(self.lat_input.text)
        lon = float(self.lon_input.text)
        self.utc_offset = int(self.utc_offset_input.text)
        color = int(self.color_input.text)

        weather_map = core.fetch_weather_maps()
        past_data, future_data = weather_map.fetch_all_radar_maps(
            lat=lat, lon=lon, size=512, color=color
        )
        self.frame_data = past_data + future_data
        self.update_ui()

    def update_ui(self):
        self.slider.max = len(self.frame_data) - 1 if self.frame_data else 1
        self.on_slider_value(self.slider, self.slider.value)

    def on_slider_value(self, instance, value):
        idx = int(value)
        new_texture = pil_to_texture(self.frame_data[idx][1])
        new_time_str = self.frame_data[idx][0].time_str(self.utc_offset)
        self.image_widget.texture = new_texture
        self.time_label.text = new_time_str
        self.current_frame = idx
        self.current_time_str = new_time_str


class RaincasterApp(MDApp):

    def build(self):
        if kivy.platform == "android":
            from android.permissions import request_permissions, Permission  # type: ignore

            request_permissions([
                Permission.INTERNET,
                Permission.ACCESS_COARSE_LOCATION,
                Permission.ACCESS_FINE_LOCATION,
            ])

        self.theme_cls.theme_style = "Dark"

        sm = ScreenManager()
        sm.add_widget(RadarScreen())
        return sm


if __name__ == "__main__":
    RaincasterApp().run()
