"""Takes the Store / README screenshots from the real window.

Uses the stand-in recordings from make_demo_recordings.py, so nothing from a real
session appears, and stages a few rows as if a queue had been running.
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import time
import tkinter as tk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import capture  # noqa: E402
import gui  # noqa: E402
import i18n  # noqa: E402
import win32util as w  # noqa: E402

DEMO = os.path.join(ROOT, "build", "demo")
OUT = os.path.join(ROOT, "docs", "screenshots")
SHOTS = [("en", "light"), ("en", "dark"), ("th", "light"), ("zh-Hans", "light")]
WINDOW = "1600x900"          # comfortably over the Store minimum of 1366x768
CANVAS = (1600, 900)         # small dialogs are centred on a plate of this size


def settle(widget, rounds: int = 12) -> None:
    """Let Tk finish laying out and painting before the picture is taken."""
    for _ in range(rounds):
        widget.update_idletasks()
        widget.update()
        time.sleep(0.05)


def save(hwnd: str, name: str, plate: str | None = None) -> None:
    """Grab a window. With `plate`, centre it on a canvas of that colour so a small
    dialog still meets the Store's minimum picture size."""
    from PIL import Image
    width, height, px = w.grab_window(hwnd)
    img = Image.frombuffer("RGBA", (width, height), px, "raw", "BGRA", 0, 1)
    if plate:
        canvas = Image.new("RGB", CANVAS, plate)
        canvas.paste(img.convert("RGB"),
                     ((CANVAS[0] - width) // 2, (CANVAS[1] - height) // 2))
        img = canvas
    img.convert("RGB").save(os.path.join(OUT, name), optimize=True)
    print(f"  wrote {name}  ({img.width}x{img.height})")


def stage(app: gui.App) -> None:
    """Make the queue look like a session in progress."""
    rows = list(app.tree.get_children())
    done_sizes = (18_400_000, 7_900_000)
    for i, iid in enumerate(rows):
        item = app.items[iid]
        if i < 2:
            item["out_size"] = done_sizes[i]
            item["out"] = os.path.join(r"D:\Recordings\converted",
                                       os.path.basename(item["path"])[:-8] + ".mp4")
            app._set(iid, "done", "status.done")
        elif i == 2:
            item["done"], item["pct"] = 11 * 60 + 5, 27
            app._set(iid, "running", "status.recording",
                     done=gui.fmt_clock(item["done"]), total=gui.fmt_clock(item["duration"]), pct=27)
            app.progress["value"] = 270
    # the buttons must match: a queue that is running
    app.running = True
    app.btn_pause.configure(state="normal")
    app.btn_stop.configure(state="normal")
    app.usage.configure(text=gui.t("bar.usage", cpu="3", ram="0.9 GB"))
    app._refresh_now()


def shoot(lang: str, theme: str) -> None:
    cfg = dict(gui.DEFAULTS)
    cfg.update(lang=lang, theme=theme, tray_hint=True, out_mode="folder",
               out_dir=r"D:\Recordings\converted")
    i18n.load(lang)
    root = tk.Tk()
    app = gui.App(root, cfg, [])
    root.geometry(WINDOW)
    app.add_paths(sorted(glob.glob(os.path.join(DEMO, "*.anydesk"))))
    root.update()
    for _ in range(80):
        root.update()
        if not any(it["state"] == "reading" for it in app.items.values()):
            break
        root.after(100)
    stage(app)
    root.update_idletasks()
    root.update()
    hwnd = int(root.wm_frame(), 16)
    w.bring_to_front(hwnd)
    settle(root)
    save(hwnd, f"queue-{lang}-{theme}.png")
    if (lang, theme) == ("en", "light"):
        app.options()
        root.update()
        for child in root.winfo_children():
            if isinstance(child, tk.Toplevel):
                settle(child)
                save(int(child.wm_frame(), 16), "options-en.png", plate="#1e293b")
                child.destroy()
        app.about()
        root.update()
        for child in root.winfo_children():
            if isinstance(child, tk.Toplevel):
                settle(child)
                save(int(child.wm_frame(), 16), "about-en.png", plate="#1e293b")
                child.destroy()
    app.running = False       # nothing is really converting; close without a prompt
    app.on_close()
    root.update()


def main() -> int:
    if not glob.glob(os.path.join(DEMO, "*.anydesk")):
        print("no stand-in recordings - run tools/make_demo_recordings.py first", file=sys.stderr)
        return 1
    os.makedirs(OUT, exist_ok=True)
    # never write over the user's real settings while posing for pictures
    gui.SETTINGS_FILE = os.path.join(OUT, "_settings.json")
    gui.QUEUE_FILE = os.path.join(OUT, "_queue.json")
    for lang, theme in SHOTS:
        shoot(lang, theme)
    for junk in ("_settings.json", "_queue.json"):
        path = os.path.join(OUT, junk)
        if os.path.exists(path):
            os.remove(path)
    print(f"\nscreenshots in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
