"""Parser for the container layer of AnyDesk session recordings (.anydesk).

Only the framing is understood; the picture payload is AnyDesk's proprietary
DeskRT codec and is not decoded here.

Layout (observed on AnyDesk 5.4 recordings):
    "anydesk\\0" | u32be header_len | header | packets...
    header  = 38 fixed bytes | (u32be len, name, u32be id) x 2
              bytes 6..10 of the header: u32be length in ms (0 if never finalized)
    packet  = 0x00 | type | flag | varint timestamp_ms | varint len | payload
"""
from __future__ import annotations

import mmap
import struct
from dataclasses import dataclass, field

MAGIC = b"anydesk\x00"
_HEADER_FIXED = 38
_PICTURE_TYPES = (5, 6, 7)


class NotAnAnyDeskRecording(ValueError):
    pass


@dataclass
class RecordingInfo:
    path: str
    size: int
    peers: list[tuple[str, int]] = field(default_factory=list)
    width: int | None = None
    height: int | None = None
    packets: int | None = 0  # None when the file was not walked to the end
    duration: float | None = None  # seconds; None when framing could not be walked
    first_picture: float | None = None  # seconds into the timeline of the first frame

    def describe(self) -> str:
        peers = " -> ".join(f"{n} ({i})" for n, i in self.peers) or "?"
        res = f"{self.width}x{self.height}" if self.width else "?"
        dur = _fmt_duration(self.duration) if self.duration is not None else "unknown"
        return (f"{self.path}\n  peers     : {peers}\n  resolution: {res}\n"
                f"  duration  : {dur}\n"
                f"  size      : {self.size / 1e6:.1f} MB")


def _fmt_duration(sec: float) -> str:
    m, s = divmod(int(round(sec)), 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d} ({sec:.1f}s)"


def _varint(buf, pos: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        b = buf[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        if b < 0x80:
            return value, pos
        shift += 7
        if shift > 63:
            raise ValueError("varint too long")


def _parse_peers(header: bytes) -> list[tuple[str, int]]:
    peers = []
    pos = _HEADER_FIXED
    try:
        while pos + 4 <= len(header) and len(peers) < 2:
            (n,) = struct.unpack_from(">I", header, pos)
            pos += 4
            name = header[pos:pos + n].decode("utf-8", "replace")
            pos += n
            (peer_id,) = struct.unpack_from(">I", header, pos)
            pos += 4
            peers.append((name, peer_id))
    except struct.error:
        pass
    return peers


def read_info(path: str, full: bool = False) -> RecordingInfo:
    """Metadata of a recording. Unless `full`, the length comes from the header and only
    the first packets are read, so multi-gigabyte files cost the same as small ones."""
    with open(path, "rb") as f:
        size = f.seek(0, 2)
        if size < 12:
            raise NotAnAnyDeskRecording(path)
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as buf:
            if buf[:8] != MAGIC:
                raise NotAnAnyDeskRecording(path)
            (header_len,) = struct.unpack_from(">I", buf, 8)
            info = RecordingInfo(path=path, size=size)
            info.peers = _parse_peers(buf[12:12 + header_len])
            (header_ms,) = struct.unpack_from(">I", buf, 12 + 6) if header_len >= 10 else (0,)
            quick = not full and header_ms > 0

            pos = 12 + header_len
            last = None
            try:
                while pos < size:
                    if buf[pos] != 0:  # byte 2 is a flag (usually 0), not checked
                        raise ValueError(f"unexpected packet prefix at {pos:#x}")
                    ptype = buf[pos + 1]
                    ts, p = _varint(buf, pos + 3)
                    length, p = _varint(buf, p)
                    if p + length > size:
                        raise ValueError(f"packet overruns file at {pos:#x}")
                    # display-geometry control packet: 0a .. u32be w, u32be h
                    if (info.width is None and ptype == 4 and 10 <= length <= 12
                            and buf[p] == 0x0A):
                        w, h = struct.unpack_from(">II", buf, p + 2)
                        if 0 < w <= 16384 and 0 < h <= 16384:
                            info.width, info.height = w, h
                    if info.first_picture is None and ptype in _PICTURE_TYPES:
                        info.first_picture = ts / 1000.0
                    last = ts
                    info.packets += 1
                    if quick and info.first_picture is not None and (
                            info.width is not None or info.packets > 400):
                        info.packets = None
                        info.duration = header_ms / 1000.0
                        return info
                    pos = p + length
                # playback timeline starts at 0, so the last timestamp is the length
                info.duration = last / 1000.0 if last is not None else 0.0
            except (ValueError, IndexError):
                # truncated/unknown framing: keep what we have, duration unknown
                info.duration = None
            return info


if __name__ == "__main__":
    import sys
    for arg in sys.argv[1:]:
        print(read_info(arg).describe())
