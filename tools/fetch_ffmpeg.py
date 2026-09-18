"""Downloads the LGPL FFmpeg build the app ships with into bin/.

The binaries are not kept in the repository (about 165 MB), so run this once after
cloning and before packaging. LGPL matters: the GPL builds that most download pages
offer cannot be distributed through the Microsoft Store.
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import sys
import urllib.request
import zipfile

RELEASE = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
ASSET = "ffmpeg-n8.1-latest-win64-lgpl-shared-8.1.zip"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(HERE, "bin")
WANTED_EXES = ("ffmpeg.exe", "ffprobe.exe")


def download(url: str) -> bytes:
    print(f"downloading {url}")
    with urllib.request.urlopen(url) as r:  # noqa: S310 - fixed https URL
        total = int(r.headers.get("Content-Length") or 0)
        buf, read = io.BytesIO(), 0
        while chunk := r.read(1 << 20):
            buf.write(chunk)
            read += len(chunk)
            if total:
                print(f"\r  {read / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", flush=True)
        print()
        return buf.getvalue()


def main() -> int:
    blob = download(RELEASE + ASSET)
    print("  sha256:", hashlib.sha256(blob).hexdigest())
    os.makedirs(BIN, exist_ok=True)
    kept = []
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for name in z.namelist():
            base = os.path.basename(name)
            if "/bin/" in name and (base in WANTED_EXES or base.endswith(".dll")):
                if base.startswith("ffplay"):
                    continue
                target = os.path.join(BIN, base)
            elif base == "LICENSE.txt":
                target = os.path.join(BIN, "FFMPEG-LICENSE.txt")
            else:
                continue
            with z.open(name) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            kept.append(base)
    missing = [e for e in WANTED_EXES if not os.path.isfile(os.path.join(BIN, e))]
    if missing:
        print("missing after extract:", missing, file=sys.stderr)
        return 1
    size = sum(os.path.getsize(os.path.join(BIN, f)) for f in os.listdir(BIN))
    print(f"installed {len(kept)} files into bin/  ({size / 1e6:.1f} MB)")
    print("LGPL v3: the licence text is in bin/FFMPEG-LICENSE.txt and the source is at")
    print("https://github.com/BtbN/FFmpeg-Builds (unmodified binaries, run as a separate process)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
