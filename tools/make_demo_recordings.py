"""Writes small stand-in .anydesk files for screenshots and tests.

They carry a readable header - peer names, screen size, length - so the queue window
shows realistic rows without putting anyone's real session on a Store page. They hold
no picture data and are not meant to be played.
"""
from __future__ import annotations

import os
import struct
import sys

DEMO = [
    #  from                to            w     h     seconds   bytes of filler
    ("Workstation-07", "HELPDESK", 1920, 1080, 22 * 60 + 14, 40_000_000),
    ("Reception-PC", "HELPDESK", 1920, 1080, 6 * 60 + 41, 12_000_000),
    ("Sales-Laptop", "HELPDESK", 2560, 1440, 41 * 60 + 8, 71_000_000),
    ("Warehouse-Term", "HELPDESK", 1366, 768, 3 * 60 + 52, 5_400_000),
    ("Branch-Office", "HELPDESK", 1920, 1080, 14 * 60 + 30, 26_000_000),
]


def varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def packet(ptype: int, ts_ms: int, payload: bytes) -> bytes:
    return bytes([0, ptype, 0]) + varint(ts_ms) + varint(len(payload)) + payload


def build(a: str, a_id: int, b: str, b_id: int, w: int, h: int, seconds: int, size: int) -> bytes:
    header = bytearray(38)
    struct.pack_into(">I", header, 6, seconds * 1000)       # length, as the real format stores it
    for name, peer_id in ((a, a_id), (b, b_id)):
        raw = name.encode("utf-8")
        header += struct.pack(">I", len(raw)) + raw + struct.pack(">I", peer_id)
    body = packet(4, 120, b"\x0a\x00" + struct.pack(">II", w, h))   # screen geometry
    body += packet(6, 480, b"\x0b\x02" + b"\0" * 64)                 # stands in for a picture
    # pad to a believable file size; only the length is ever read back
    filler = max(0, size - (12 + len(header) + len(body) + 8))
    body += packet(6, seconds * 1000, b"\x0b\x02" + bytes(filler))
    return b"anydesk\x00" + struct.pack(">I", len(header)) + bytes(header) + body


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "demo")
    os.makedirs(out, exist_ok=True)
    for i, (a, w_from, w, h, secs, size) in enumerate(DEMO):
        blob = build(a, 100_000_001 + i * 7919, w_from, 100_000_000, w, h, secs, size)
        name = f"incoming {a} ({100_000_001 + i * 7919})-{w_from} (100000000) {i}.anydesk"
        with open(os.path.join(out, name), "wb") as f:
            f.write(blob)
        print(f"  {name}  ({len(blob) / 1e6:.1f} MB, {secs // 60}:{secs % 60:02d}, {w}x{h})")
    print(f"\nwrote {len(DEMO)} stand-in recordings into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
