"""Where things live, both when running from source and when packaged as an .exe."""
from __future__ import annotations

import os
import sys

FROZEN = getattr(sys, "frozen", False)
_SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))


def resource_dir() -> str:
    """Read-only files that ship with the program: assets/, locales/.

    PyInstaller unpacks them beside the program under `_MEIPASS`.
    """
    return getattr(sys, "_MEIPASS", _SOURCE_DIR)


def app_dir() -> str:
    """The folder the program was started from - where bin/ffmpeg.exe sits."""
    return os.path.dirname(os.path.abspath(sys.executable)) if FROZEN else _SOURCE_DIR


def resource(*parts: str) -> str:
    return os.path.join(resource_dir(), *parts)


def worker_command() -> list[str]:
    """How to start one conversion as a child process.

    Packaged, the program is its own worker: the same .exe run with --worker. From
    source it is the interpreter running the converter script.
    """
    if FROZEN:
        return [sys.executable, "--worker"]
    return [sys.executable, "-u", os.path.join(_SOURCE_DIR, "anydesk2mp4.py")]


def launch_command() -> list[str]:
    """How Explorer should start the window (for the right-click entry and shortcut)."""
    if FROZEN:
        return [sys.executable]
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pythonw if os.path.isfile(pythonw) else sys.executable
    return [exe, os.path.join(_SOURCE_DIR, "gui.py")]
