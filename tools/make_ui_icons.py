"""Draws the small pictures used in the header: language flags and the sun / moon of the
theme switch. Development-time only (needs Pillow); the PNGs are committed.

A flag file is named after its locale file: locales/th.json -> assets/ui/flag_th.png.
A language without a flag simply shows its name only.
"""
import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "assets", "ui")
SS = 8                      # supersampling
FLAG_W, FLAG_H = 24, 16     # final pixels
ICON = 16


def _finish(im: Image.Image, size: tuple[int, int], radius: float = 0) -> Image.Image:
    if radius:
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius * SS, fill=255)
        im.putalpha(mask)
    return im.resize(size, Image.LANCZOS)


def _star(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, rot: float, fill) -> None:
    pts = []
    for i in range(10):
        rad = r if i % 2 == 0 else r * 0.382
        a = rot + i * math.pi / 5
        pts.append((cx + rad * math.sin(a), cy - rad * math.cos(a)))
    d.polygon(pts, fill=fill)


def flag_th() -> Image.Image:
    w, h = FLAG_W * SS, FLAG_H * SS
    im = Image.new("RGBA", (w, h), "#A51931")
    d = ImageDraw.Draw(im)
    d.rectangle([0, h / 6, w, h * 5 / 6], fill="#F4F5F8")
    d.rectangle([0, h / 3, w, h * 2 / 3], fill="#2D2A4A")
    return im


def flag_zh() -> Image.Image:
    w, h = FLAG_W * SS, FLAG_H * SS
    im = Image.new("RGBA", (w, h), "#DE2910")
    d = ImageDraw.Draw(im)
    u = h / 20                      # the flag is specified on a 30 x 20 grid
    _star(d, 5 * u, 5 * u, 3 * u, 0, "#FFDE00")
    for gx, gy in ((10, 2), (12, 4), (12, 7), (10, 9)):
        rot = math.atan2(5 - gx, gy - 5)   # each small star points at the big one
        _star(d, gx * u, gy * u, 1.05 * u, rot, "#FFDE00")
    return im


def flag_en() -> Image.Image:
    w, h = FLAG_W * SS, FLAG_H * SS
    im = Image.new("RGBA", (w, h), "#012169")
    d = ImageDraw.Draw(im)
    for a, b in (((0, 0), (w, h)), ((0, h), (w, 0))):
        d.line([a, b], fill="#FFFFFF", width=int(h * 0.20))
    for a, b in (((0, 0), (w, h)), ((0, h), (w, 0))):
        d.line([a, b], fill="#C8102E", width=int(h * 0.075))
    d.rectangle([w / 2 - h * 0.17, 0, w / 2 + h * 0.17, h], fill="#FFFFFF")
    d.rectangle([0, h / 2 - h * 0.17, w, h / 2 + h * 0.17], fill="#FFFFFF")
    d.rectangle([w / 2 - h * 0.10, 0, w / 2 + h * 0.10, h], fill="#C8102E")
    d.rectangle([0, h / 2 - h * 0.10, w, h / 2 + h * 0.10], fill="#C8102E")
    return im


def sun() -> Image.Image:
    n = ICON * SS
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c, col = n / 2, "#FCD34D"
    for i in range(8):
        a = i * math.pi / 4
        d.line([(c + math.cos(a) * n * 0.33, c + math.sin(a) * n * 0.33),
                (c + math.cos(a) * n * 0.47, c + math.sin(a) * n * 0.47)], fill=col, width=int(n * 0.085))
    r = n * 0.215
    d.ellipse([c - r, c - r, c + r, c + r], fill=col)
    return im


def moon() -> Image.Image:
    n = ICON * SS
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([n * 0.12, n * 0.10, n * 0.88, n * 0.86], fill="#E2E8F0")
    cut = Image.new("L", (n, n), 0)
    ImageDraw.Draw(cut).ellipse([n * 0.36, n * 0.02, n * 1.06, n * 0.72], fill=255)
    alpha = im.getchannel("A")
    alpha.paste(0, mask=cut)       # bite a second disc out of the first: a crescent
    im.putalpha(alpha)
    return im


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for name, im in (("flag_th", flag_th()), ("flag_zh-Hans", flag_zh()), ("flag_en", flag_en())):
        _finish(im, (FLAG_W, FLAG_H), radius=2.5).save(os.path.join(OUT, name + ".png"), optimize=True)
    for name, im in (("sun", sun()), ("moon", moon())):
        _finish(im, (ICON, ICON)).save(os.path.join(OUT, name + ".png"), optimize=True)
    print("wrote", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
