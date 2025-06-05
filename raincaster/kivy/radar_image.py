from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.properties import (
    BooleanProperty,
    ObjectProperty,
)

from io import BytesIO

from kivy.core.image import Image as CoreImage
from PIL import Image as PILImage
from kivymd.uix.widget import Widget as MDWidget


class RadarImage(MDWidget):
    texture = ObjectProperty(None, allownone=True)
    keep_ratio = BooleanProperty(True)

    def __init__(self, texture=None, keep_ratio=True, **kwargs):
        super().__init__(**kwargs)

        if texture is None:
            image = PILImage.new("RGB", (512, 512), (255, 255, 255))
            texture = pil_to_texture(image)

        self.texture = texture
        self.keep_ratio = keep_ratio
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
            )
            d = d / 10
            Ellipse(
                pos=(self.center_x - d / 2, self.center_y - d / 2),
                size=(d, d),
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
