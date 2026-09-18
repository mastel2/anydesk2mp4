"""ffmpeg process control: capture a window by handle, then write the final container."""
from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
import threading
import time

import paths
from dataclasses import dataclass

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass(frozen=True)
class Format:
    ext: str            # file extension of the result
    codec: str          # codec used while capturing: "h264" or "hevc"
    max_width: int      # widest picture the codec's decoders accept
    transcode: tuple[str, ...] = ()  # final re-encode; empty = stream copy
    label: str = ""


FORMATS = {
    "mp4": Format("mp4", "h264", 4096, label="MP4 (H.264) - plays everywhere"),
    "mp4-hevc": Format("mp4", "hevc", 8192, label="MP4 (H.265) - smaller, keeps ultra-wide screens"),
    "mkv": Format("mkv", "h264", 4096, label="MKV (H.264)"),
    "mov": Format("mov", "h264", 4096, label="MOV (H.264) - for Apple editors"),
    "webm": Format("webm", "h264", 4096, label="WebM (VP9) - for the web, slow to finish",
                   transcode=("-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-row-mt", "1",
                              "-cpu-used", "4", "-pix_fmt", "yuv420p")),
}


def tool(name: str) -> str:
    """Path of ffmpeg/ffprobe: a copy shipped next to the program wins over PATH, so a
    packaged build never runs whatever happens to be first on the user's PATH."""
    for folder in (os.path.join(paths.app_dir(), "bin"), paths.app_dir()):
        cand = os.path.join(folder, name + ".exe")
        if os.path.isfile(cand):
            return cand
    found = shutil.which(name)
    if not found:
        raise FileNotFoundError(f"{name} was not found (put it in a 'bin' folder or on PATH)")
    return found


# Encoders to try, best first. GPU encoders come first; Media Foundation is part of
# Windows itself and uses whatever hardware is there, which also covers AMD and Intel.
# h264_amf is deliberately absent: it ignores forced keyframes and, without an AMD GPU,
# is slower than real time.
LADDERS = {
    "h264": ("h264_nvenc", "h264_qsv", "h264_mf", "libopenh264"),
    "hevc": ("hevc_nvenc", "hevc_qsv", "hevc_mf", "libkvazaar"),
}


@functools.lru_cache(maxsize=None)
def has_encoder(name: str) -> bool:
    """Can this machine really encode with it? Probed at a size close to what we capture,
    because some encoders accept a tiny test frame and then fail on a real one."""
    r = subprocess.run(
        [tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
         "color=black:s=1280x720:r=30:d=0.5", "-c:v", name, "-f", "null", "-"],
        capture_output=True, creationflags=_NO_WINDOW)
    return r.returncode == 0


@functools.lru_cache(maxsize=None)
def pick_encoder(codec: str) -> str:
    for name in LADDERS[codec]:
        if has_encoder(name):
            return name
    raise RuntimeError(f"no usable {codec} encoder in this ffmpeg build")


def _bitrate(width: int, height: int, cq: int) -> int:
    """For encoders that only take a bitrate. Calibrated on real conversions: screen
    content at the default quality lands near 0.42 Mbit/s per megapixel."""
    factor = 2.0 ** ((24 - cq) / 6.0)          # one quality step ~ doubles the bitrate
    return max(1_200_000, int(0.42e6 * (width * height / 1e6) * factor))


def encoder_args(codec: str, cq: int, fps: int, dense_until: float,
                 width: int = 1920, height: int = 1080) -> list[str]:
    # The head is cut on a keyframe after the rewind, so keyframes are dense
    # (0.5s) only while that cut can still happen, then sparse to keep files small.
    keyframes = f"expr:gte(t,n_forced*if(lt(t,{dense_until:.0f}),0.5,5))"
    common = ["-g", str(fps * 10), "-force_key_frames", keyframes, "-pix_fmt", "yuv420p"]
    name = pick_encoder(codec)
    if name.endswith("_nvenc"):
        quality = ["-preset", "p5", "-rc", "vbr", "-cq", str(cq), "-b:v", "0", "-forced-idr", "1"]
    elif name.endswith("_qsv"):
        quality = ["-preset", "faster", "-global_quality", str(cq)]
    elif name.endswith("_mf"):
        # Media Foundation takes 0-100, the other way round from a quantiser
        quality = ["-rate_control", "quality", "-quality", str(max(10, min(95, 110 - 2 * cq)))]
    else:  # libopenh264 / libkvazaar: bitrate only
        rate = _bitrate(width, height, cq)
        quality = ["-b:v", str(rate), "-maxrate", str(int(rate * 1.5)), "-bufsize", str(rate * 2)]
    return ["-c:v", name] + quality + common


def output_size(w: int, h: int, max_width: int, max_height: int | None) -> tuple[int, int]:
    """Largest even size within the limits that keeps the aspect ratio (never enlarges)."""
    scale = min(1.0, max_width / w, (max_height / h) if max_height else 1.0)
    return max(2, int(w * scale) & ~1), max(2, int(h * scale) & ~1)


class Recorder:
    """Captures `hwnd` with gdigrab into `out_path` (Matroska) until stop()."""

    def __init__(self, hwnd: int, out_path: str, fps: int, cq: int,
                 crop: tuple[int, int, int, int] | None, fmt: Format,
                 max_height: int | None = None, dense_until: float = 30.0):
        filters = []
        if crop:
            w, h, x, y = crop
            filters.append(f"crop={w}:{h}:{x}:{y}")
            ow, oh = output_size(w, h, fmt.max_width, max_height)
            if (ow, oh) != (w, h):
                filters.append(f"scale={ow}:{oh}:flags=bicubic")
        else:  # size unknown: let ffmpeg apply the limits, keeping even dimensions
            filters.append(f"scale='min({fmt.max_width},iw)':-2:flags=bicubic")
            if max_height:
                filters.append(f"scale=-2:'min({max_height},ih)':flags=bicubic")
        cmd = [tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostats", "-y",
               "-progress", "pipe:1", "-stats_period", "0.25",
               "-f", "gdigrab", "-framerate", str(fps), "-draw_mouse", "0",
               "-i", f"hwnd={hwnd}", "-vf", ",".join(filters)]
        size = (crop[0], crop[1]) if crop else (1920, 1080)
        cmd += encoder_args(fmt.codec, cq, fps, dense_until, *size) + ["-f", "matroska", out_path]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True,
                                     creationflags=_NO_WINDOW)
        self.started_at: float | None = None  # wall clock of output t=0
        self.out_time = 0.0
        self.speed = ""
        self._stderr: list[str] = []
        threading.Thread(target=self._read_progress, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_progress(self) -> None:
        for line in self.proc.stdout:
            key, _, val = line.strip().partition("=")
            if key == "out_time_us" and val.lstrip("-").isdigit():
                self.out_time = int(val) / 1e6
                if self.started_at is None and self.out_time > 0:
                    self.started_at = time.time() - self.out_time
            elif key == "speed":
                self.speed = val

    def _read_stderr(self) -> None:
        for line in self.proc.stderr:
            self._stderr.append(line.rstrip())

    def wait_started(self, timeout: float = 20.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if self.started_at is not None:
                return True
            if self.proc.poll() is not None:
                return False
            time.sleep(0.05)
        return False

    def running(self) -> bool:
        return self.proc.poll() is None

    def errors(self) -> str:
        return "\n".join(self._stderr[-8:])

    def stop(self) -> None:
        if self.proc.poll() is None:
            try:
                self.proc.stdin.write("q")
                self.proc.stdin.flush()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def cut_point(path: str, t: float, tolerance: float = 0.4) -> float:
    """Where to start the finished file, given that we want to drop everything before `t`.

    A stream copy can only start on a keyframe. Prefer the first one just after `t`; if the
    encoder placed none nearby, fall back to the last one *before* `t` - that keeps a little
    of the run-up rather than cutting away the beginning of the recording.
    """
    r = subprocess.run(
        [tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey",
         "-read_intervals", f"%+{t + 8:.3f}",
         "-show_entries", "frame=pts_time", "-of", "json", path],
        capture_output=True, text=True, creationflags=_NO_WINDOW)
    try:
        times = sorted(float(f["pts_time"]) for f in json.loads(r.stdout)["frames"]
                       if "pts_time" in f)
    except (ValueError, KeyError):
        return t
    after = next((k for k in times if k >= t), None)
    if after is not None and after - t <= tolerance:
        return after
    before = [k for k in times if k <= t]
    return before[-1] if before else (after if after is not None else t)


def finalize(src: str, dst: str, start: float, length: float | None, fmt: Format) -> None:
    """Cut the head off the capture and write the requested container."""
    cmd = [tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y"]
    if start > 0:
        cmd += ["-ss", f"{start + 0.001:.3f}"]
    cmd += ["-i", src]
    if length is not None:
        cmd += ["-t", f"{length:.3f}"]
    cmd += list(fmt.transcode) if fmt.transcode else ["-c", "copy"]
    if fmt.ext in ("mp4", "mov"):
        cmd += ["-movflags", "+faststart"]
        if fmt.codec == "hevc":
            cmd += ["-tag:v", "hvc1"]  # without it Apple players refuse H.265 in MP4
    r = subprocess.run(cmd + [dst], capture_output=True, text=True, creationflags=_NO_WINDOW)
    if r.returncode != 0:
        raise RuntimeError(f"writing {fmt.ext} failed: {r.stderr.strip()[-400:]}")


def probe(path: str) -> dict:
    r = subprocess.run(
        [tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=codec_name,width,height,avg_frame_rate:format=duration,size",
         "-of", "json", path], capture_output=True, text=True, creationflags=_NO_WINDOW)
    data = json.loads(r.stdout or "{}")
    out = dict((data.get("streams") or [{}])[0])
    out.update(data.get("format") or {})
    return out
