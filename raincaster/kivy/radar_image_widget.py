import math
from io import BytesIO

from kivy.core.image import Image as CoreImage
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.properties import (
    BooleanProperty,
    ObjectProperty,
)
from kivymd.uix.widget import Widget as MDWidget
from PIL import Image as PILImage


class RadarImageWidget(MDWidget):
    texture = ObjectProperty(None, allownone=True)
    keep_ratio = BooleanProperty(defaultvalue=True)

    def __init__(self, texture=None, keep_ratio=True, **kwargs):
        super().__init__(**kwargs)

        self.texture = texture
        self.keep_ratio = keep_ratio
        self.radar_tile_size_km = None
        self.radar_direction = None
        self.bind(
            pos=self.update_canvas,
            size=self.update_canvas,
            texture=self.update_canvas,
            keep_ratio=self.update_canvas,
        )

    def set_image(self, image: PILImage.Image):
        """
        Set the image to be displayed. The image should be a PIL Image.
        """
        self.texture = pil_to_texture(image)

    def set_radar_tile_size_km(self, size_km: float):
        """
        Set the radar tile size in kilometers.
        This is used to calculate the size of the radar tile in pixels.
        """
        self.radar_tile_size_km = size_km

    def set_radar_direction(self, direction: float | None):
        """
        Set the radar direction in degrees.
        """
        self.radar_direction = direction
        self.update_canvas()

    def get_km_circle_radius(self, radius_km: float) -> float:
        """
        Calculate the radius of a circle (in pixels) for a given km radius.
        This is based on the radar tile size in kilometers.
        """
        if self.radar_tile_size_km is None:
            return 0
        return (radius_km / self.radar_tile_size_km) * min(self.width, self.height)

    def update_canvas(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(1.0, 1.0, 1.0, 0.7)
            Rectangle(pos=self.pos, size=self.size)
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

            if not self.texture:
                return
            # Draw 25 km and 50 km circles with labels
            # Use a light blue color for better visibility
            Color(0.0, 0.1, 0.2, 0.7)
            for km in (25, 50):
                d_km = self.get_km_circle_radius(km)
                Line(
                    ellipse=(
                        self.center_x - d_km,
                        self.center_y - d_km,
                        2 * d_km,
                        2 * d_km,
                    ),
                    width=1.5,
                )
                # Draw label for each circle
                label = CoreLabel(text=f"{km} km", font_size=20, color=(0.0, 0.1, 0.2, 1))
                label.refresh()
                # Place label at the top of the circle
                label_x = self.center_x - label.texture.size[0] / 2
                label_y = self.center_y + d_km - label.texture.size[1] - 2
                Rectangle(
                    texture=label.texture,
                    pos=(label_x, label_y),
                    size=label.texture.size,
                )
            d = 10
            Ellipse(
                pos=(self.center_x - d / 2, self.center_y - d / 2),
                size=(d, d),
            )
            # Draw a line indicating the radar direction
            if self.radar_direction is not None:
                angle_rad = self.radar_direction * (3.141592653589793 / 180.0)
                line_length = min(self.width, self.height) / 2
                end_x = self.center_x + line_length * math.cos(angle_rad)
                end_y = self.center_y - line_length * math.sin(angle_rad)
                # Use a nice, visible color for the radar direction line (e.g., bright orange)
                Color(1.0, 0.5, 0.0, 1.0)
                Line(
                    points=[self.center_x, self.center_y, end_x, end_y],
                    width=2,
                    cap="round",
                )


def pil_to_texture(pil_image: PILImage.Image) -> CoreImage:
    # Composite alpha channel over white
    if pil_image.mode in ("RGBA", "LA"):
        background = PILImage.new("RGBA", pil_image.size, (255, 255, 255, 255))
        background.paste(pil_image, mask=pil_image.split()[-1])
        pil_image = background.convert("RGB")
    else:
        pil_image = pil_image.convert("RGB")

    buf = BytesIO()
    pil_image.save(buf, format="PNG")
    buf.seek(0)
    return CoreImage(buf, ext="png").texture
