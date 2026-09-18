"""Draws the app icon with no third-party packages and writes assets/app.ico (+ a PNG preview).

Design: dark rounded tile (KEEP_DARK), a cyan "play" triangle turning into a film strip edge -
"a recording becomes a video". Deliberately no red, to stay clear of AnyDesk's branding.
"""
import os
import struct
import zlib

BG, BG2 = (17, 24, 39), (30, 41, 59)
ACCENT, ACCENT2 = (34, 211, 238), (56, 189, 248)
SS = 4  # supersampling factor


def _inside_round_rect(x, y, size, r):
    cx = min(max(x, r), size - r)
    cy = min(max(y, r), size - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _inside_triangle(x, y, a, b, c):
    def s(p, q, r_):
        return (p[0] - r_[0]) * (q[1] - r_[1]) - (q[0] - r_[0]) * (p[1] - r_[1])
    d1, d2, d3 = s((x, y), a, b), s((x, y), b, c), s((x, y), c, a)
    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))


def render(size):
    n = size * SS
    tri = ((n * 0.36, n * 0.27), (n * 0.36, n * 0.73), (n * 0.76, n * 0.50))
    hole = max(1.0, n * 0.045)
    rows = []
    for py in range(size):
        row = bytearray()
        for px in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(SS):
                for sx in range(SS):
                    x, y = px * SS + sx + 0.5, py * SS + sy + 0.5
                    if not _inside_round_rect(x, y, n, n * 0.22):
                        continue
                    t = y / n
                    col = tuple(int(BG[i] + (BG2[i] - BG[i]) * t) for i in range(3))
                    if _inside_triangle(x, y, *tri):
                        col = tuple(int(ACCENT[i] + (ACCENT2[i] - ACCENT[i]) * t) for i in range(3))
                    elif n * 0.16 <= x <= n * 0.25:  # film-strip perforations on the left
                        for k in range(4):
                            cy = n * (0.29 + 0.14 * k)
                            if abs(y - cy) <= hole and abs(x - n * 0.205) <= hole:
                                col = ACCENT
                    for i in range(3):
                        acc[i] += col[i]
                    acc[3] += 255
            k = SS * SS
            a = acc[3] // k
            cov = max(1, acc[3] // 255)
            row += bytes((acc[0] // cov, acc[1] // cov, acc[2] // cov, a))
        rows.append(bytes(row))
    return rows  # RGBA rows, top-down


def png(rows, size):
    raw = b"".join(b"\x00" + r for r in rows)
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def dib(rows, size):
    """32-bit BMP icon image (needed for small sizes: Tk and older shells reject PNG there)."""
    head = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    pixels = b"".join(bytes(b for i in range(0, len(r), 4) for b in (r[i + 2], r[i + 1], r[i], r[i + 3]))
                      for r in reversed(rows))
    mask = bytes(((size + 31) // 32) * 4) * size
    return head + pixels + mask


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    images = []
    for size in (16, 24, 32, 48, 64, 256):
        rows = render(size)
        images.append((size, png(rows, size) if size == 256 else dib(rows, size)))
        if size == 256:
            with open(os.path.join(here, "assets", "app.png"), "wb") as f:
                f.write(png(rows, size))
    out = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    for size, data in images:
        out += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    with open(os.path.join(here, "assets", "app.ico"), "wb") as f:
        f.write(out + b"".join(d for _, d in images))
    print("wrote assets/app.ico and assets/app.png")


if __name__ == "__main__":
    main()
