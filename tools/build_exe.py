"""Builds the Windows program with PyInstaller.

One .exe does both jobs: started normally it is the window, started with --worker it
converts a single recording (that is how the window runs conversions).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "Recording Converter for AnyDesk"
DIST = os.path.join(HERE, "dist")
VERSION = "1.0.0"


def version_resource() -> str:
    """Windows file-properties block, so the .exe is not anonymous in Task Manager."""
    v = tuple(int(x) for x in VERSION.split(".")) + (0,)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={v}, prodvers={v}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
        StringStruct('CompanyName', 'KEEP_DARK'),
        StringStruct('FileDescription', '{NAME}'),
        StringStruct('FileVersion', '{VERSION}'),
        StringStruct('InternalName', 'anydesk2mp4'),
        StringStruct('LegalCopyright', 'Copyright 2026 KEEP_DARK. Apache-2.0. '
                                       'Not affiliated with AnyDesk Software GmbH.'),
        StringStruct('OriginalFilename', '{NAME}.exe'),
        StringStruct('ProductName', '{NAME}'),
        StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ])
"""


def main() -> int:
    if not os.path.isfile(os.path.join(HERE, "bin", "ffmpeg.exe")):
        print("bin/ffmpeg.exe is missing - run tools/fetch_ffmpeg.py first", file=sys.stderr)
        return 1
    ver_file = os.path.join(HERE, "build", "version.txt")
    os.makedirs(os.path.dirname(ver_file), exist_ok=True)
    with open(ver_file, "w", encoding="utf-8") as f:
        f.write(version_resource())

    sep = os.pathsep
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--name", NAME,
        "--windowed",                      # no console window
        "--icon", os.path.join(HERE, "assets", "app.ico"),
        "--version-file", ver_file,
        "--add-data", f"{os.path.join(HERE, 'assets')}{sep}assets",
        "--add-data", f"{os.path.join(HERE, 'locales')}{sep}locales",
        "--distpath", DIST,
        "--workpath", os.path.join(HERE, "build"),
        "--specpath", os.path.join(HERE, "build"),
        os.path.join(HERE, "gui.py"),
    ]
    print(" ".join(args))
    if subprocess.run(args, cwd=HERE).returncode:
        return 1

    app = os.path.join(DIST, NAME)
    # ffmpeg and the licence files sit next to the .exe, not inside the bundle
    shutil.copytree(os.path.join(HERE, "bin"), os.path.join(app, "bin"), dirs_exist_ok=True)
    for name in ("LICENSE", "NOTICE", "README.md", "README.th.md"):
        shutil.copy2(os.path.join(HERE, name), app)
    size = sum(os.path.getsize(os.path.join(r, f))
               for r, _, fs in os.walk(app) for f in fs)
    print(f"\nbuilt: {os.path.join(app, NAME + '.exe')}")
    print(f"folder size: {size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
