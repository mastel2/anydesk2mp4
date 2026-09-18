"""Generates the tile and logo images an MSIX package needs, from assets/app.png.

Development-time only (needs Pillow); the results go into the staging folder that
tools/pack_msix.ps1 builds, not into the repository.
"""
from __future__ import annotations

import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(HERE, "assets", "app.png")
BACKDROP = (15, 23, 42)          # the app's dark ink, so square tiles are not transparent

# name -> (width, height, how much of the tile the icon fills)
TILES = {
    "Square44x44Logo": (44, 44, 1.0),
    "Square71x71Logo": (71, 71, 0.66),
    "Square150x150Logo": (150, 150, 0.66),
    "Square310x310Logo": (310, 310, 0.66),
    "Wide310x150Logo": (310, 150, 0.60),
    "StoreLogo": (50, 50, 1.0),
}
# Windows picks the closest scale; 100 % and 200 % cover every display we target
SCALES = (100, 200)


def render(master: Image.Image, w: int, h: int, fill: float, transparent: bool) -> Image.Image:
    tile = Image.new("RGBA", (w, h), (0, 0, 0, 0) if transparent else BACKDROP + (255,))
    side = int(min(w, h) * fill)
    icon = master.resize((side, side), Image.LANCZOS)
    tile.alpha_composite(icon, ((w - side) // 2, (h - side) // 2))
    return tile


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "build", "Assets")
    os.makedirs(out, exist_ok=True)
    master = Image.open(SOURCE).convert("RGBA")
    made = 0
    for name, (w, h, fill) in TILES.items():
        # the small app-list icon is drawn on the user's accent colour, so it stays transparent
        transparent = name == "Square44x44Logo"
        for scale in SCALES:
            img = render(master, w * scale // 100, h * scale // 100, fill, transparent)
            img.save(os.path.join(out, f"{name}.scale-{scale}.png"), optimize=True)
            made += 1
        # unscaled copies as well: makeappx accepts either naming
        render(master, w, h, fill, transparent).save(os.path.join(out, f"{name}.png"), optimize=True)
        made += 1
    # taskbar / alt-tab sizes for the app-list icon
    for size in (16, 24, 32, 48, 256):
        render(master, size, size, 1.0, True).save(
            os.path.join(out, f"Square44x44Logo.targetsize-{size}.png"), optimize=True)
        render(master, size, size, 1.0, True).save(
            os.path.join(out, f"Square44x44Logo.targetsize-{size}_altform-unplated.png"), optimize=True)
        made += 2
    # the Store listing itself asks for a 300x300 logo, separate from the tiles
    render(master, 300, 300, 0.78, False).save(os.path.join(out, "StoreListing300x300.png"),
                                               optimize=True)
    made += 1
    print(f"wrote {made} images into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
