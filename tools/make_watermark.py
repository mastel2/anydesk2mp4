"""Builds the faint KEEP_DARK watermark shown in the empty part of the queue list.

Development-time only (needs Pillow); the generated PNGs are committed, the app itself
stays standard-library only.
"""
import os

from PIL import Image, ImageEnhance

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "assets", "brand", "keep-dark-emblem.png")
HEIGHT = 132


def build(name: str, alpha: float, invert: bool) -> None:
    im = Image.open(SRC).convert("RGBA")
    w = round(im.width * HEIGHT / im.height)
    im = im.resize((w, HEIGHT), Image.LANCZOS)
    r, g, b, a = im.split()
    grey = Image.merge("RGB", (r, g, b)).convert("L")
    if invert:  # on a dark card the emblem has to be light to read at all
        grey = grey.point(lambda v: 255 - v // 2)
    grey = ImageEnhance.Contrast(grey).enhance(1.1)
    a = a.point(lambda v: int(v * alpha))
    Image.merge("RGBA", (grey, grey, grey, a)).save(os.path.join(HERE, "assets", name), optimize=True)
    print("wrote assets/" + name)


build("watermark_light.png", 0.13, invert=False)
build("watermark_dark.png", 0.10, invert=True)
