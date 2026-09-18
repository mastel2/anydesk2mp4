"""Recording Converter for AnyDesk - queue window.

The window only manages the list; each recording is converted by running
anydesk2mp4.py as a child process with --json and following its events.
"""
from __future__ import annotations

import ctypes
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import webbrowser
from ctypes import wintypes
from multiprocessing.connection import Client, Listener
from tkinter import filedialog, messagebox, ttk

import adrec
import anydesk2mp4
import capture
import i18n
import paths
import procstats
import tray
from i18n import t

APP_VERSION = "1.0.0"
WORKS_URL = "https://www.keep-dark.com/works/"
PRODUCT_URL = "https://www.keep-dark.com/works/recording-converter-for-anydesk/"
PRIVACY_URL = PRODUCT_URL + "privacy/"
SOURCE_URL = "https://github.com/mastel2/anydesk2mp4"
HERE = paths.resource_dir()
ICON = paths.resource("assets", "app.ico")
ICON_PNG = paths.resource("assets", "app.png")
DATA_DIR = os.path.join(os.environ.get("APPDATA", HERE), "anydesk2mp4")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
QUEUE_FILE = os.path.join(DATA_DIR, "queue.json")
PIPE = r"\\.\pipe\anydesk2mp4-gui"
PIPE_KEY = b"anydesk2mp4"
PER_FILE_OVERHEAD = 15  # seconds of opening/rewinding/finishing around each recording
QUALITY_CQ = {"small": 30, "balanced": 24, "high": 19}
# Rough output size, calibrated on real conversions (H.264, balanced): Mbit/s per megapixel
# for the first 30 s (dense keyframes) and for the rest. Screen content varies a lot, so
# the result is only shown as an estimate ("≈"); it errs on the high side on purpose.
EST_HEAD_MBPS, EST_TAIL_MBPS = 1.2, 0.42
EST_QUALITY = {"small": 0.5, "balanced": 1.0, "high": 1.8}
EST_FORMAT = {"mp4": 1.0, "mkv": 1.0, "mov": 1.0, "mp4-hevc": 0.65, "webm": 0.6}
RESOLUTIONS = (0, 2160, 1440, 1080, 720, 480)  # 0 = original
FPS_CHOICES = (10, 15, 24, 30, 60)
DEFAULTS = {"lang": None, "out_mode": "source", "out_dir": "", "format": "mp4", "max_height": 0,
            "quality": "balanced", "fps": 30, "rewind": True, "skip_existing": True,
            "keep_awake": True, "shutdown": False, "tray": True, "last_dir": "", "tray_hint": False,
            "theme": "light", "stealth": True, "wait_busy": True}
ANYDESK_PATHS = [r"C:\Program Files (x86)\AnyDesk\AnyDesk.exe", r"C:\Program Files\AnyDesk\AnyDesk.exe"]
ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x1, 0x2

# look
THEMES = {
    "light": {"head": "#0f172a", "text": "#0f172a", "soft": "#64748b", "paper": "#f1f5f9",
              "card": "#ffffff", "alt": "#f8fafc", "line": "#e2e8f0", "field": "#ffffff",
              "accent": "#0284c7", "accent_down": "#0369a1", "accent_off": "#cbd5e1",
              "good": "#15803d", "bad": "#b91c1c", "select": "#bae6fd", "select_text": "#0f172a"},
    "dark": {"head": "#020617", "text": "#e2e8f0", "soft": "#94a3b8", "paper": "#0f172a",
             "card": "#1e293b", "alt": "#233044", "line": "#334155", "field": "#0b1220",
             "accent": "#0ea5e9", "accent_down": "#0284c7", "accent_off": "#334155",
             "good": "#4ade80", "bad": "#f87171", "select": "#075985", "select_text": "#f8fafc"},
}
C = dict(THEMES["light"])  # the colours in use; App.apply_look() swaps them in place
FONT = "Segoe UI"


# ------------------------------------------------------------------ settings
def clean_settings(raw: dict) -> dict:
    """Settings come from a user-editable file: keep only known keys with sane values."""
    cfg = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        val = raw.get(key, default)
        if default is None or isinstance(default, str):
            ok = val is None or isinstance(val, str)
        else:
            ok = type(val) is type(default)
        if ok:
            cfg[key] = val
    if cfg["format"] not in capture.FORMATS:
        cfg["format"] = DEFAULTS["format"]
    if cfg["quality"] not in QUALITY_CQ:
        cfg["quality"] = DEFAULTS["quality"]
    if cfg["max_height"] not in RESOLUTIONS:
        cfg["max_height"] = 0
    if cfg["fps"] not in FPS_CHOICES:
        cfg["fps"] = DEFAULTS["fps"]
    if cfg["out_mode"] not in ("source", "folder"):
        cfg["out_mode"] = "source"
    if cfg["theme"] not in THEMES:
        cfg["theme"] = "light"
    return cfg


def load_settings() -> dict:
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        return clean_settings(raw if isinstance(raw, dict) else {})
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save_json(path: str, data) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except OSError:
        pass


def save_settings(cfg: dict) -> None:
    save_json(SETTINGS_FILE, cfg)


# ------------------------------------------------------------------- helpers
def sysdll(name: str) -> ctypes.WinDLL:
    """A Windows DLL loaded from System32 only (never from the app folder or the CWD)."""
    return ctypes.WinDLL(name, winmode=0x800)


def system_tool(*parts: str) -> str:
    """Absolute path of a Windows tool, so PATH cannot substitute another program."""
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), *parts)


def fmt_clock(sec: float) -> str:
    sec = int(max(0, sec))
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_eta(sec: float) -> str:
    sec = int(max(0, sec))
    h, m = sec // 3600, sec % 3600 // 60
    return t("eta.hours_minutes", h=h, m=m) if h else t("eta.minutes", m=max(1, m))


def fmt_size(n: float) -> str:
    return f"{n / 1e9:.2f} GB" if n >= 1e9 else f"{n / 1e6:.1f} MB"


def expand_paths(paths) -> list[str]:
    out = []
    for p in paths:
        if not isinstance(p, str):
            continue
        if os.path.isdir(p):
            out += sorted(os.path.join(p, n) for n in os.listdir(p) if n.lower().endswith(".anydesk"))
        elif os.path.isfile(p):
            out.append(p)
    return [os.path.normpath(p) for p in out]


class DropTarget:
    """Accept files dropped from Explorer onto a Tk toplevel (WM_DROPFILES)."""
    WM_DROPFILES, GWLP_WNDPROC = 0x0233, -4
    _PROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                               wintypes.WPARAM, wintypes.LPARAM)

    def __init__(self, toplevel: tk.Tk, on_drop):
        self.on_drop = on_drop
        u, sh = sysdll("user32"), sysdll("shell32")
        u.SetWindowLongPtrW.restype = ctypes.c_void_p
        u.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        u.CallWindowProcW.restype = ctypes.c_ssize_t
        u.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                                      wintypes.WPARAM, wintypes.LPARAM]
        sh.DragQueryFileW.argtypes = [ctypes.c_void_p, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
        sh.DragFinish.argtypes = [ctypes.c_void_p]
        sh.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
        self._u, self._sh = u, sh
        self.hwnd = int(toplevel.wm_frame(), 16)
        self._proc = self._PROC(self._wndproc)  # keep a reference or it is collected
        self._old = u.SetWindowLongPtrW(self.hwnd, self.GWLP_WNDPROC,
                                        ctypes.cast(self._proc, ctypes.c_void_p))
        sh.DragAcceptFiles(self.hwnd, True)

    def close(self) -> None:
        """Hand the window back before it is destroyed, so no message reaches a dead callback."""
        if self._old:
            self._sh.DragAcceptFiles(self.hwnd, False)
            self._u.SetWindowLongPtrW(self.hwnd, self.GWLP_WNDPROC, self._old)
            self._old = None

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == self.WM_DROPFILES:
            try:
                n = self._sh.DragQueryFileW(wparam, 0xFFFFFFFF, None, 0)
                names = []
                for i in range(min(n, 5000)):
                    buf = ctypes.create_unicode_buffer(32768)
                    self._sh.DragQueryFileW(wparam, i, buf, len(buf))
                    names.append(buf.value)
                self._sh.DragFinish(wparam)
                self.on_drop(names)
            except Exception:  # never let an exception unwind into the window procedure
                pass
            return 0
        return self._u.CallWindowProcW(self._old, hwnd, msg, wparam, lparam)


class PrimaryButton(tk.Button):
    """The one accent-coloured call to action; ttk cannot colour buttons on Windows."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["accent"], fg="white", activebackground=C["accent_down"],
                         activeforeground="white", disabledforeground="white", relief="flat",
                         bd=0, padx=22, pady=7, cursor="hand2", font=(FONT, 10, "bold"), **kw)
        self.bind("<Enter>", lambda e: self["state"] == "normal" and self.configure(bg=C["accent_down"]))
        self.bind("<Leave>", lambda e: self.configure(
            bg=C["accent"] if self["state"] == "normal" else C["accent_off"]))

    def enable(self, on: bool) -> None:
        self.configure(state="normal" if on else "disabled", bg=C["accent"] if on else C["accent_off"],
                       cursor="hand2" if on else "arrow")


# ----------------------------------------------------------------------- app
class App:
    def __init__(self, root: tk.Tk, cfg: dict, initial: list[str]):
        self.root, self.cfg = root, cfg
        self.items: dict[str, dict] = {}      # tree iid -> item
        self.ui: queue.Queue = queue.Queue()  # other threads / window procedures -> Tk thread
        self.running = False                  # the queue is being worked through
        self.pause_after = False
        self.child: subprocess.Popen | None = None
        self.stop_file = os.path.join(tempfile.gettempdir(), f"anydesk2mp4-stop-{os.getpid()}")
        self.current: str | None = None
        self.scheduled_at: float | None = None
        self.meter = procstats.Meter()
        self.counts = {"ok": 0, "failed": 0}
        self.tray: tray.TrayIcon | None = None
        self.closing = False
        self._refresh_pending = False
        # Tk is single-threaded: the conversion worker reads these plain copies instead of
        # asking the widgets, which would be a cross-thread Tk call.
        self._order: list[str] = []
        self._out: tuple[str, str] = (cfg["out_mode"], cfg["out_dir"])
        self._to_read: queue.Queue = queue.Queue()
        threading.Thread(target=self._reader, daemon=True).start()

        root.title(t("app.title"))
        root.geometry("1120x720")
        root.minsize(900, 520)
        C.update(THEMES[cfg["theme"]])
        root.configure(bg=C["paper"])
        if os.path.isfile(ICON):
            try:
                root.iconbitmap(default=ICON)
            except tk.TclError:
                pass
        self._style()
        self._build()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.bind("<Unmap>", self._on_unmap)
        try:
            self.drop = DropTarget(root, lambda names: self.ui.put(("add", names)))
        except Exception:
            self.drop = None
        if os.path.isfile(ICON):
            try:
                self.tray = tray.TrayIcon(ICON, t("tray.tip_idle"),
                                          lambda: self.ui.put(("show",)),
                                          lambda: self.ui.put(("tray_menu",)))
            except Exception:
                self.tray = None
        self._timers: dict[str, str] = {}
        self._timers['pump'] = self.root.after(100, self._pump)
        self._timers['tick'] = self.root.after(1000, self._tick)
        self._restore_queue()
        if initial:
            self.add_paths(initial)
        self._refresh()
        self._check_requirements()

    # ---------------------------------------------------------------- look
    def _style(self) -> None:
        st = ttk.Style(self.root)
        dark = self.cfg["theme"] == "dark"
        # The native theme cannot be recoloured, so dark mode runs on "clam", which can.
        st.theme_use("clam" if dark else "vista")
        base = (FONT, 10)
        st.configure(".", font=base, foreground=C["text"])
        for name in ("TFrame", "TLabel", "TRadiobutton", "TCheckbutton", "TLabelframe", "TLabelframe.Label"):
            st.configure(name, background=C["paper"], foreground=C["text"])
        st.configure("Card.TFrame", background=C["card"])
        st.configure("Muted.TLabel", foreground=C["soft"], background=C["paper"])
        st.configure("TLabelframe.Label", foreground=C["soft"], font=(FONT, 9, "bold"))
        st.configure("TButton", padding=(10, 4))
        st.configure("Treeview", rowheight=30, font=base, background=C["card"],
                     fieldbackground=C["card"], foreground=C["text"])
        st.configure("Treeview.Heading", font=(FONT, 9, "bold"), padding=(6, 6))
        st.map("Treeview", background=[("selected", C["select"])], foreground=[("selected", C["select_text"])])
        if dark:
            st.configure(".", background=C["paper"], fieldbackground=C["field"], bordercolor=C["line"],
                         darkcolor=C["line"], lightcolor=C["line"], troughcolor=C["field"],
                         selectbackground=C["select"], selectforeground=C["select_text"],
                         insertcolor=C["text"])
            st.configure("TButton", background=C["card"], foreground=C["text"])
            st.map("TButton", background=[("active", C["line"]), ("disabled", C["paper"])],
                   foreground=[("disabled", C["soft"])])
            st.configure("Treeview.Heading", background=C["paper"], foreground=C["soft"])
            for name in ("TCombobox", "TEntry", "TSpinbox"):
                st.configure(name, fieldbackground=C["field"], foreground=C["text"], background=C["card"],
                             arrowcolor=C["text"])
                st.map(name, fieldbackground=[("readonly", C["field"]), ("disabled", C["paper"])],
                       foreground=[("readonly", C["text"]), ("disabled", C["soft"])])
            st.configure("TProgressbar", background=C["accent"], troughcolor=C["field"])
            st.configure("TScrollbar", background=C["card"], troughcolor=C["paper"], arrowcolor=C["text"])
        # the drop-down list of a combobox is a plain Tk listbox
        for opt, val in (("background", C["field"]), ("foreground", C["text"]),
                         ("selectBackground", C["select"]), ("selectForeground", C["select_text"])):
            self.root.option_add("*TCombobox*Listbox." + opt, val)
        self._dark_titlebar(self.root)

    def _dark_titlebar(self, win) -> None:
        try:
            win.update_idletasks()
            on = ctypes.c_int(1 if self.cfg["theme"] == "dark" else 0)
            sysdll("dwmapi").DwmSetWindowAttribute(
                wintypes.HWND(int(win.wm_frame(), 16)), 20, ctypes.byref(on), ctypes.sizeof(on))
        except (AttributeError, OSError, ValueError, tk.TclError):
            pass

    def apply_look(self, theme: str | None = None, lang: str | None = None) -> None:
        """Switch theme and/or language and rebuild the window in place; the queue,
        a running conversion and the row ids the worker refers to all stay as they are."""
        if theme:
            self.cfg["theme"] = theme
            C.clear()
            C.update(THEMES[theme])
        if lang:
            self.cfg["lang"] = lang
            i18n.load(lang)
        save_settings(self.cfg)
        order, selected = list(self.tree.get_children()), self._selected()
        progress = self.progress["value"]
        for child in self.root.winfo_children():
            child.destroy()
        self.root.configure(bg=C["paper"])
        self.root.title(t("app.title"))
        self._style()
        self._build()
        for iid in order:
            self.tree.insert("", "end", iid=iid, values=self._row(self.items[iid]))
        self.tree.selection_set([i for i in selected if i in self.items])
        self.progress["value"] = progress
        if self.running:
            self.btn_pause.configure(state="normal",
                                     text=t("btn.resume") if self.pause_after else t("btn.pause_after"))
            self.btn_stop.configure(state="normal")
        self._refresh()

    def _build(self) -> None:
        # brand header
        head = tk.Frame(self.root, bg=C["head"], height=54)
        head.pack(fill="x")
        head.pack_propagate(False)
        self._logo = None
        if os.path.isfile(ICON_PNG):
            try:
                self._logo = tk.PhotoImage(file=ICON_PNG).subsample(8)
                tk.Label(head, image=self._logo, bg=C["head"]).pack(side="left", padx=(14, 8))
            except tk.TclError:
                pass
        tk.Label(head, text=t("app.title"), bg=C["head"], fg="#f8fafc", font=(FONT, 13, "bold")).pack(side="left")
        link = tk.Label(head, text=t("header.more"), bg=C["head"], fg="#7dd3fc", cursor="hand2",
                        font=(FONT, 10, "bold"))  # no underline: it would hide the "_" in KEEP_DARK
        link.bind("<Enter>", lambda e: link.configure(fg="#e0f2fe"))
        link.bind("<Leave>", lambda e: link.configure(fg="#7dd3fc"))
        link.pack(side="right", padx=16)
        link.bind("<Button-1>", lambda e: webbrowser.open(WORKS_URL))

        def picture(name: str):
            """A small PNG from assets/ui, or None - then the control shows text only."""
            path = paths.resource("assets", "ui", name + ".png")
            if not os.path.isfile(path):
                return None
            try:
                img = tk.PhotoImage(file=path)
            except tk.TclError:
                return None
            self._pictures.append(img)  # Tk drops images nobody references
            return img

        def chip(text: str, image=None) -> dict:
            opts = dict(text=text, bg="#1e293b", fg="#e2e8f0", activebackground="#334155",
                        activeforeground="#ffffff", relief="flat", bd=0, padx=12, pady=4,
                        cursor="hand2", font=(FONT, 9, "bold"))
            if image is not None:
                opts.update(image=image, compound="left", text="  " + text)
            return opts

        self._pictures = []
        other = "light" if self.cfg["theme"] == "dark" else "dark"
        tk.Button(head, command=lambda: self.apply_look(theme=other),
                  **chip(t("theme." + other), picture("sun" if other == "light" else "moon"))
                  ).pack(side="right", padx=(0, 10))
        langs = i18n.available()
        current = self.cfg["lang"] or i18n.system_language()
        lang_btn = tk.Menubutton(head, **chip(langs.get(current, "English") + "  ▾",
                                              picture("flag_" + current)))
        lang_menu = tk.Menu(lang_btn, tearoff=0)
        for code, name in langs.items():
            flag = picture("flag_" + code)
            extra = dict(image=flag, compound="left") if flag is not None else {}
            lang_menu.add_command(label="  " + name, command=lambda c=code: self.apply_look(lang=c), **extra)
        lang_btn.configure(menu=lang_menu)
        lang_btn.pack(side="right", padx=(0, 8))

        # toolbar
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=14, pady=(12, 8))
        ttk.Button(bar, text=t("btn.add_files"), command=self.pick_files).pack(side="left")
        ttk.Button(bar, text=t("btn.add_folder"), command=self.pick_folder).pack(side="left", padx=(6, 18))
        self.btn_up = ttk.Button(bar, text=t("btn.move_up"), command=lambda: self.move(-1))
        self.btn_up.pack(side="left")
        self.btn_down = ttk.Button(bar, text=t("btn.move_down"), command=lambda: self.move(1))
        self.btn_down.pack(side="left", padx=6)
        self.btn_remove = ttk.Button(bar, text=t("btn.remove"), command=self.remove_selected)
        self.btn_remove.pack(side="left")
        ttk.Button(bar, text=t("btn.clear_done"), command=self.clear_done).pack(side="left", padx=6)
        ttk.Button(bar, text=t("btn.about"), command=self.about).pack(side="right")
        ttk.Button(bar, text=t("btn.options"), command=self.options).pack(side="right", padx=6)

        # The bottom block is packed first (side=bottom) so the table takes what is left
        # and never pushes the controls out of a small window.
        bottom = ttk.Frame(self.root)
        bottom.pack(side="bottom", fill="x")

        # queue table inside a bordered card
        card = tk.Frame(self.root, bg=C["line"], bd=0)
        card.pack(fill="both", expand=True, padx=14)
        inner = ttk.Frame(card, style="Card.TFrame")
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        cols = ("num", "file", "peers", "length", "before", "after", "dest", "status")
        self.tree = ttk.Treeview(inner, columns=cols, show="headings", selectmode="extended")
        for c, wd, anchor, stretch in (("num", 40, "e", False), ("file", 250, "w", True),
                                       ("peers", 150, "w", False), ("length", 70, "e", False),
                                       ("before", 84, "e", False), ("after", 150, "e", False),
                                       ("dest", 200, "w", True), ("status", 180, "w", True)):
            self.tree.heading(c, text=t("col." + c), anchor=anchor)
            self.tree.column(c, width=wd, minwidth=36, anchor=anchor, stretch=stretch)
        sb = ttk.Scrollbar(inner, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("odd", background=C["alt"])
        self.tree.tag_configure("done", foreground=C["good"])
        self.tree.tag_configure("failed", foreground=C["bad"])
        self.tree.tag_configure("running", foreground=C["accent"])
        self.tree.tag_configure("muted", foreground=C["soft"])
        self.tree.bind("<Configure>", lambda e: self._place_watermark())
        self.tree.bind("<Double-1>", lambda e: self.open_video())
        self.tree.bind("<Button-3>", self._context)
        self.tree.bind("<Delete>", lambda e: self.remove_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._refresh_buttons())

        self.empty = tk.Frame(inner, bg=C["card"])
        tk.Label(self.empty, text="⇣", bg=C["card"], fg=C["accent"], font=(FONT, 30)).pack()
        tk.Label(self.empty, text=t("empty.title"), bg=C["card"], fg=C["text"],
                 font=(FONT, 14, "bold")).pack(pady=(2, 4))
        tk.Label(self.empty, text=t("empty.sub"), bg=C["card"], fg=C["soft"], font=(FONT, 10),
                 wraplength=560, justify="center").pack()

        # faint brand mark in the unused part of the list; hidden once rows would reach it
        self.watermark = None
        mark = paths.resource("assets", f"watermark_{self.cfg['theme']}.png")
        if os.path.isfile(mark):
            try:
                self._mark_img = tk.PhotoImage(file=mark)
                self.watermark = tk.Label(self.tree, image=self._mark_img, bg=C["card"], bd=0)
            except tk.TclError:
                self.watermark = None

        # output settings
        out = ttk.LabelFrame(bottom, text=t("out.title"), padding=(12, 8))
        out.pack(fill="x", padx=14, pady=(10, 0))
        self.fmt_labels = {k: t("fmt." + k) for k in capture.FORMATS}
        self.res_labels = {h: (t("res.original") if h == 0 else t("res.p", n=h)) for h in RESOLUTIONS}
        self.q_labels = {k: t("opt.quality." + k) for k in QUALITY_CQ}
        self.v_fmt = tk.StringVar(value=self.fmt_labels[self.cfg["format"]])
        self.v_res = tk.StringVar(value=self.res_labels[self.cfg["max_height"]])
        self.v_q = tk.StringVar(value=self.q_labels[self.cfg["quality"]])
        row = ttk.Frame(out)
        row.pack(fill="x")
        for label, var, values, width in ((t("out.format"), self.v_fmt, list(self.fmt_labels.values()), 44),
                                          (t("out.resolution"), self.v_res, list(self.res_labels.values()), 12),
                                          (t("out.quality"), self.v_q, list(self.q_labels.values()), 12)):
            ttk.Label(row, text=label).pack(side="left")
            box = ttk.Combobox(row, textvariable=var, values=values, width=width, state="readonly")
            box.pack(side="left", padx=(6, 18))
            box.bind("<<ComboboxSelected>>", lambda e: self._save_cfg())
        row = ttk.Frame(out)
        row.pack(fill="x", pady=(8, 0))
        self.out_mode = tk.StringVar(value=self.cfg["out_mode"])
        self.out_dir = tk.StringVar(value=self.cfg["out_dir"])
        self._out = (self.cfg["out_mode"], self.cfg["out_dir"])
        ttk.Label(row, text=t("save.label")).pack(side="left")
        ttk.Radiobutton(row, text=t("save.next_to_source"), value="source", variable=self.out_mode,
                        command=self._save_cfg).pack(side="left", padx=(8, 0))
        ttk.Radiobutton(row, text=t("save.folder"), value="folder", variable=self.out_mode,
                        command=self._save_cfg).pack(side="left", padx=(12, 0))
        ttk.Entry(row, textvariable=self.out_dir, state="readonly").pack(side="left", padx=6, fill="x", expand=True)
        ttk.Button(row, text=t("btn.browse"), command=self.pick_out).pack(side="left")

        # actions
        act = ttk.Frame(bottom)
        act.pack(fill="x", padx=14, pady=(12, 4))
        self.btn_start = PrimaryButton(act, text=t("btn.start"), command=self.start)
        self.btn_start.pack(side="left")
        self.btn_sched = ttk.Button(act, text=t("btn.start_at"), command=self.schedule)
        self.btn_sched.pack(side="left", padx=(8, 18))
        self.btn_pause = ttk.Button(act, text=t("btn.pause_after"), command=self.toggle_pause, state="disabled")
        self.btn_pause.pack(side="left")
        self.btn_stop = ttk.Button(act, text=t("btn.stop"), command=self.stop, state="disabled")
        self.btn_stop.pack(side="left", padx=6)
        self.usage = ttk.Label(act, text="", style="Muted.TLabel")
        self.usage.pack(side="right")

        self.progress = ttk.Progressbar(bottom, maximum=1000)
        self.progress.pack(fill="x", padx=14, pady=(6, 0))
        line = ttk.Frame(bottom)
        line.pack(fill="x", padx=14, pady=(6, 0))
        self.status = ttk.Label(line, text=t("bar.idle"), font=(FONT, 10, "bold"))
        self.status.pack(side="left")
        self.space = ttk.Label(line, text="", style="Muted.TLabel")
        self.space.pack(side="right")
        ttk.Label(bottom, text=t("bar.realtime"), style="Muted.TLabel", wraplength=1040,
                  justify="left").pack(fill="x", padx=14, pady=(2, 10))

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label=t("menu.open_video"), command=self.open_video)
        self.menu.add_command(label=t("menu.open_folder"), command=self.open_folder)
        self.menu.add_separator()
        self.menu.add_command(label=t("menu.save_to"), command=self.save_selected_to)
        self.menu.add_command(label=t("menu.save_source"), command=lambda: self.save_selected_to(""))
        self.menu.add_separator()
        self.menu.add_command(label=t("menu.retry"), command=self.retry_selected)
        self.menu.add_command(label=t("menu.remove"), command=self.remove_selected)


    def _check_requirements(self) -> None:
        if not any(os.path.isfile(p) for p in ANYDESK_PATHS):
            messagebox.showwarning(t("app.title"), t("err.no_anydesk"))
            return
        try:
            capture.tool("ffmpeg")
            capture.tool("ffprobe")
        except FileNotFoundError:
            messagebox.showwarning(t("app.title"), t("err.no_ffmpeg"))

    # ----------------------------------------------------------------- items
    def add_paths(self, paths, dests: dict | None = None) -> None:
        known = {it["path"].lower() for it in self.items.values()}
        for p in expand_paths(paths):
            if p.lower() in known:
                continue
            known.add(p.lower())
            item = {"path": p, "state": "reading", "duration": None, "out": None, "peers": "",
                    "dest": (dests or {}).get(p) or None, "status": ("status.reading", {}),
                    "src_size": None, "out_size": None}
            iid = self.tree.insert("", "end", values=self._row(item))
            self.items[iid] = item
            self._to_read.put((iid, p))
        self._refresh()

    def _reader(self) -> None:
        """Reads recording headers off the Tk thread - one worker, however many files are added."""
        while True:
            iid, path = self._to_read.get()
            try:
                self.ui.put(("info", iid, adrec.read_info(path)))
            except (OSError, ValueError):
                self.ui.put(("info", iid, None))

    def _set(self, iid: str, state: str, key: str, **params) -> None:
        """Status is kept as (string key, params) so it can be re-rendered in another language."""
        if iid in self.items:
            self.items[iid]["state"] = state
            self.items[iid]["status"] = (key, params)
            self.tree.set(iid, "status", t(key, **params))
            self._retag(iid)

    def _row(self, item: dict, num: int | str = "") -> tuple:
        key, params = item["status"]
        length = fmt_clock(item["duration"]) if item["duration"] else ("" if item["state"] == "reading" else "?")
        before = fmt_size(item["src_size"]) if item["src_size"] is not None else ""
        return (num, os.path.basename(item["path"]), item["peers"], length, before,
                self._after_label(item), self._dest_label(item), t(key, **params))

    def estimate(self, item: dict) -> float | None:
        """Expected size of the result in bytes, from length, picture size and the output settings."""
        if not item.get("duration"):
            return None
        fmt = capture.FORMATS[self.cfg["format"]]
        w, h = capture.output_size(item.get("w") or 1920, item.get("h") or 1080,
                                   fmt.max_width, self.cfg["max_height"] or None)
        d = item["duration"]
        mbits = (min(d, 30) * EST_HEAD_MBPS + max(0.0, d - 30) * EST_TAIL_MBPS) * (w * h / 1e6)
        return mbits * 1e6 / 8 * EST_QUALITY[self.cfg["quality"]] * EST_FORMAT.get(self.cfg["format"], 1.0)

    def _after_label(self, item: dict) -> str:
        if item["out_size"] is not None and item["src_size"]:
            change = (item["out_size"] - item["src_size"]) / item["src_size"] * 100
            return f"{fmt_size(item['out_size'])}  ({change:+.0f}%)"
        if item["out_size"] is not None:
            return fmt_size(item["out_size"])
        est = self.estimate(item)
        return "≈ " + fmt_size(est) if est else ""

    def _place_watermark(self) -> None:
        if not self.watermark:
            return
        rows_bottom = 30 + 30 * len(self.tree.get_children())  # heading + rows
        free = self.tree.winfo_height() - rows_bottom
        if free >= self._mark_img.height() + 16 and self.tree.winfo_width() > 500:
            self.watermark.place(relx=1.0, rely=1.0, anchor="se", x=-26, y=-14)
        else:
            self.watermark.place_forget()

    def _retag(self, iid: str, index: int | None = None) -> None:
        if index is None:
            index = self.tree.index(iid)
        state = self.items[iid]["state"]
        tags = ["odd"] if index % 2 else []
        tags.append({"done": "done", "failed": "failed", "invalid": "failed", "running": "running",
                     "reading": "muted"}.get(state, ""))
        self.tree.item(iid, tags=[x for x in tags if x])

    def _refresh(self) -> None:
        """Ask for a refresh; many requests in one burst of events become a single redraw."""
        if not self._refresh_pending:
            self._refresh_pending = True
            self.root.after(30, self._refresh_now)

    def _refresh_now(self) -> None:
        """Row numbers, zebra, destination column, empty state, saved queue, buttons."""
        self._refresh_pending = False
        if self.closing:
            return
        self._sync_out()
        self._order = list(self.tree.get_children())
        for n, iid in enumerate(self.tree.get_children()):
            self.tree.item(iid, values=self._row(self.items[iid], n + 1))
            self._retag(iid, n)
        self._place_watermark()
        if self.items:
            self.empty.place_forget()
        else:
            self.empty.place(relx=0.5, rely=0.5, anchor="center")
        save_json(QUEUE_FILE, [{"path": it["path"], "dest": it["dest"]} for iid in self.tree.get_children()
                               for it in (self.items[iid],) if it["state"] not in ("done", "invalid")])
        self._refresh_buttons()
        self._update_bar()

    def _refresh_buttons(self) -> None:
        sel = bool(self._selected())
        for b in (self.btn_up, self.btn_down, self.btn_remove):
            b.configure(state="normal" if sel else "disabled")
        queued = any(it["state"] == "queued" for it in self.items.values())
        self.btn_start.enable(queued and not self.running)
        self.btn_sched.configure(
            state="normal" if (queued or self.scheduled_at) and not self.running else "disabled",
            text=t("btn.cancel_schedule", clock=time.strftime("%H:%M", time.localtime(self.scheduled_at)))
            if self.scheduled_at else t("btn.start_at"))

    def _restore_queue(self) -> None:
        try:
            with open(QUEUE_FILE, encoding="utf-8") as f:
                saved = json.load(f)
            rows = [r for r in saved if isinstance(r, dict) and isinstance(r.get("path"), str)]
        except (OSError, ValueError, TypeError):
            return
        dests = {os.path.normpath(r["path"]): r.get("dest") for r in rows if isinstance(r.get("dest"), str)}
        self.add_paths([r["path"] for r in rows], dests)

    def _sync_out(self) -> None:
        """Copy the output choice out of the Tk variables for the worker thread."""
        self._out = (self.out_mode.get(), self.out_dir.get())

    def _dest_label(self, item: dict) -> str:
        """Where the result goes - the real folder, and the full file once it exists."""
        if item["state"] == "done" and item.get("out"):
            return item["out"]
        return os.path.dirname(self.out_path(item))

    def out_path(self, item: dict) -> str:
        mode, out_dir = self._out
        folder = item["dest"] or (out_dir if mode == "folder" else "") or os.path.dirname(item["path"])
        ext = capture.FORMATS[self.cfg["format"]].ext
        return os.path.join(folder, os.path.splitext(os.path.basename(item["path"]))[0] + "." + ext)

    # ----------------------------------------------------------------- queue
    def start(self) -> None:
        if self.running or not any(it["state"] == "queued" for it in self.items.values()):
            return
        self.scheduled_at = None
        self.running, self.pause_after = True, False
        self._order = list(self.tree.get_children())
        self._sync_out()
        self.counts = {"ok": 0, "failed": 0}
        self.btn_pause.configure(state="normal", text=t("btn.pause_after"))
        self.btn_stop.configure(state="normal")
        self._keep_awake(True)
        self._refresh_buttons()
        threading.Thread(target=self._work, daemon=True).start()

    def toggle_pause(self) -> None:
        if not self.running:
            return
        self.pause_after = not self.pause_after
        self.btn_pause.configure(text=t("btn.resume") if self.pause_after else t("btn.pause_after"))

    def stop(self) -> None:
        """Stop now: the running file keeps what was recorded, the rest stays queued."""
        if not self.running:
            return
        self.pause_after = True
        try:
            open(self.stop_file, "w").close()
        except OSError:
            pass

    def schedule(self) -> None:
        if self.scheduled_at:
            self.scheduled_at = None
            self._refresh_buttons()
            self._update_bar()
            return
        win = self._dialog(t("sched.title"))
        now = time.localtime(time.time() + 3600)
        hh, mm = tk.StringVar(value=f"{now.tm_hour:02d}"), tk.StringVar(value="00")
        ttk.Label(win.body, text=t("sched.prompt")).pack(anchor="w")
        row = ttk.Frame(win.body)
        row.pack(anchor="w", pady=8)
        ttk.Spinbox(row, from_=0, to=23, textvariable=hh, width=4, format="%02.0f", wrap=True).pack(side="left")
        ttk.Label(row, text=" : ").pack(side="left")
        ttk.Spinbox(row, from_=0, to=59, textvariable=mm, width=4, format="%02.0f", wrap=True).pack(side="left")
        ttk.Label(win.body, text=t("sched.note"), style="Muted.TLabel", wraplength=340).pack(anchor="w")

        def ok() -> None:
            try:
                h, m = int(float(hh.get())), int(float(mm.get()))
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError
            except ValueError:
                return
            lt = time.localtime()
            target = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))
            if target <= time.time() + 5:
                target += 86400  # that time has passed today: tomorrow
            self.scheduled_at = target
            win.destroy()
            self._refresh_buttons()
            self._update_bar()

        self._dialog_buttons(win, ok)

    def _next_queued(self) -> str | None:
        """Called from the worker thread: reads the mirrored order, never the widget."""
        for iid in list(self._order):
            if self.items.get(iid, {}).get("state") == "queued":
                return iid
        return None

    def _work(self) -> None:
        while not self.closing:
            iid = None if self.pause_after else self._next_queued()
            if iid is None:
                break
            item = self.items[iid]
            out = self.out_path(item)
            item["out"] = out
            self.current = iid
            self.ui.put(("state", iid, "running", "status.opening"))
            cmd = paths.worker_command() + ["--json", "--stop-file", self.stop_file,
                   "--format", self.cfg["format"], "--fps", str(self.cfg["fps"]),
                   "--cq", str(QUALITY_CQ[self.cfg["quality"]]), "-o", os.path.dirname(out)]
            if self.cfg["max_height"]:
                cmd += ["--max-height", str(self.cfg["max_height"])]
            if not self.cfg["rewind"]:
                cmd.append("--no-rewind")
            if not self.cfg["skip_existing"]:
                cmd.append("--overwrite")
            if not self.cfg["stealth"]:
                cmd.append("--visible")
            if not self.cfg["wait_busy"]:
                cmd.append("--ignore-busy")
            cmd.append(item["path"])
            try:
                os.remove(self.stop_file)
            except OSError:
                pass
            finished, code = False, None
            try:
                self.child = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                              text=True, encoding="utf-8", errors="replace",
                                              creationflags=subprocess.CREATE_NO_WINDOW)
                for line in self.child.stdout:
                    if line.startswith("{"):
                        try:
                            ev = json.loads(line)
                        except ValueError:
                            continue
                        finished |= ev.get("event") in ("done", "failed", "skipped")
                        self.ui.put(("event", iid, ev))
                self.child.wait()
                code = self.child.returncode
            except OSError as e:
                self.ui.put(("event", iid, {"event": "failed", "error": str(e)}))
                finished = True
            if not finished:
                self.ui.put(("event", iid, {"event": "failed", "error": f"converter exited ({code})"}))
            self.child = None
        self.current = None
        self.ui.put(("idle",))

    # ------------------------------------------------------------ Tk thread
    def _pump(self) -> None:
        try:
            while True:
                msg = self.ui.get_nowait()
                getattr(self, "_on_" + msg[0])(*msg[1:])
        except queue.Empty:
            pass
        if not self.closing:
            self._timers['pump'] = self.root.after(100, self._pump)

    def _on_add(self, names) -> None:
        self.add_paths(names)
        self.show()

    def _on_show(self) -> None:
        if not self.closing:
            self.show()

    def _on_tray_menu(self) -> None:
        if self.closing or not self.tray:
            return
        queued = any(it["state"] == "queued" for it in self.items.values())
        items = [(t("tray.open"), self.show), ("-", None)]
        if self.running:
            items += [(t("btn.resume") if self.pause_after else t("btn.pause_after"), self.toggle_pause),
                      (t("btn.stop"), self.stop)]
        else:
            items += [(t("btn.start"), self.start if queued else None)]
        items += [("-", None), (t("tray.quit"), self.on_close)]
        tray.popup_menu(self.tray.hwnd, items)

    def _on_info(self, iid: str, info) -> None:
        if iid not in self.items:
            return
        if info is None:
            self._set(iid, "invalid", "status.invalid")
        else:
            item = self.items[iid]
            item["duration"], item["src_size"] = info.duration, info.size
            item["w"], item["h"] = info.width, info.height
            item["peers"] = " → ".join(n for n, _ in info.peers)
            self._set(iid, "queued", "status.queued")
        self._refresh()

    def _on_state(self, iid: str, state: str, key: str) -> None:
        self._set(iid, state, key)
        if iid in self.items:
            self.tree.see(iid)

    def _on_event(self, iid: str, ev: dict) -> None:
        kind = ev.get("event")
        item = self.items.get(iid)
        if item is None:
            return
        if kind == "queue_wait":
            self._set(iid, "running", "status.waiting")
        elif kind == "busy_wait":
            self._set(iid, "running", "status.busy_wait")
        elif kind == "busy_over":
            self._set(iid, "running", "status.opening")
        elif kind == "progress":
            total = ev.get("total") or item.get("duration") or 0
            done = min(ev["done"], total) if total else ev["done"]
            item["done"] = done
            item["pct"] = int(done / total * 100) if total else 0
            self.progress["value"] = item["pct"] * 10
            self._set(iid, "running", "status.recording", done=fmt_clock(done),
                      total=fmt_clock(total) if total else "?", pct=item["pct"])
            self._update_bar()
        elif kind == "stage" and ev.get("name") == "finishing":
            self._set(iid, "running", "status.finishing")
        elif kind == "stage" and ev.get("name") == "transcoding":
            self._set(iid, "running", "status.transcoding", fmt=capture.FORMATS[self.cfg["format"]].ext.upper())
        elif kind == "retry":
            self._set(iid, "running", "status.retry", attempt=ev["attempt"], of=ev["of"])
        elif kind in ("done", "skipped"):
            item["out"] = ev["out"]
            try:
                item["out_size"] = ev.get("size") or os.path.getsize(ev["out"])
            except OSError:
                item["out_size"] = None
            if kind == "skipped":
                self._set(iid, "done", "status.skipped")
            else:
                self._set(iid, "done", "status.partial" if ev.get("partial") else "status.done")
            self.counts["ok"] += 1
            self.progress["value"] = 0
            self._refresh()
        elif kind == "failed":
            self._set(iid, "failed", "status.failed", error=(ev.get("error") or "?").splitlines()[0])
            self.counts["failed"] += 1
            self.progress["value"] = 0
            self._refresh()

    def _on_idle(self) -> None:
        self.running = False
        self._keep_awake(False)
        self.btn_pause.configure(state="disabled", text=t("btn.pause_after"))
        self.btn_stop.configure(state="disabled")
        self.usage.configure(text="")
        self._refresh()
        left = sum(1 for it in self.items.values() if it["state"] == "queued")
        if left:
            self.status.configure(text=t("bar.paused", n=left))
            return
        summary = t("bar.finished", ok=self.counts["ok"], failed=self.counts["failed"])
        self.status.configure(text=summary)
        if self.tray and self.root.state() == "withdrawn":
            self.tray.notify(t("tray.done_title"), summary)
        if self.cfg["shutdown"] and self.counts["ok"]:
            shutdown = system_tool("System32", "shutdown.exe")
            subprocess.run([shutdown, "/s", "/t", "60"], creationflags=subprocess.CREATE_NO_WINDOW)
            self.show()
            if messagebox.askokcancel(t("app.title"), t("dlg.shutdown") + "\n\n" + t("dlg.shutdown_cancel") + "?",
                                      default="cancel"):
                subprocess.run([shutdown, "/a"], creationflags=subprocess.CREATE_NO_WINDOW)

    def _update_space(self) -> None:
        """Totals of the rows still to convert, and whether the target drives have room."""
        before = after = 0.0
        need: dict[str, float] = {}
        for it in self.items.values():
            if it["state"] not in ("queued", "running") or not it["src_size"]:
                continue
            est = self.estimate(it) or 0.0
            before += it["src_size"]
            after += est
            drive = os.path.splitdrive(os.path.abspath(self.out_path(it)))[0] or "C:"
            need[drive] = need.get(drive, 0.0) + est
        if not before:
            self.space.configure(text="", foreground=C["soft"])
            return
        text = t("bar.space", before=fmt_size(before), after=fmt_size(after))
        short = False
        for drive, amount in need.items():
            try:
                free = shutil.disk_usage(drive + os.sep).free
            except OSError:
                continue
            text += "  ·  " + t("bar.free", drive=drive, free=fmt_size(free))
            short |= amount * 1.3 > free
        if short:
            text += "  ·  " + t("bar.space_low")
        self.space.configure(text=text, foreground=C["bad"] if short else C["soft"])

    def _update_bar(self) -> None:
        self._update_space()
        left, secs, pct = 0, 0.0, 0
        for it in self.items.values():
            if it["state"] == "queued":
                left += 1
                secs += (it["duration"] or 0) + PER_FILE_OVERHEAD
            elif it["state"] == "running":
                left += 1
                secs += max(0.0, (it["duration"] or 0) - it.get("done", 0))
                pct = it.get("pct", 0)
        tip = t("tray.tip_idle")
        if self.scheduled_at and not self.running:
            clock = time.strftime("%H:%M", time.localtime(self.scheduled_at))
            self.status.configure(text=t("bar.scheduled", clock=clock, eta=fmt_eta(self.scheduled_at - time.time())))
            tip = t("tray.tip_scheduled", clock=clock)
        elif left:
            clock = time.strftime("%H:%M", time.localtime(time.time() + secs))
            self.status.configure(text=t("bar.queue", n=left, eta=fmt_eta(secs), clock=clock))
            if self.running:
                tip = t("tray.tip_running", pct=pct, n=left)
        elif not self.running and not self.counts["ok"] and not self.counts["failed"]:
            self.status.configure(text=t("bar.idle"))
        if self.tray:
            self.tray.set_tip(tip)

    def _tick(self) -> None:
        if self.closing:
            return
        if self.scheduled_at and not self.running:
            if time.time() >= self.scheduled_at:
                self.start()
            else:
                self._update_bar()
        if self.running:
            try:
                cpu, ram = self.meter.read()
                self.usage.configure(text=t("bar.usage", cpu=f"{cpu:.0f}", ram=fmt_size(ram)))
            except OSError:
                pass
        self._timers['tick'] = self.root.after(2000 if self.running else 1000, self._tick)

    def _keep_awake(self, on: bool) -> None:
        flags = ES_CONTINUOUS
        if on and self.cfg["keep_awake"]:
            flags |= ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        sysdll("kernel32").SetThreadExecutionState(ctypes.c_uint(flags))

    # ------------------------------------------------------------- window
    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _on_unmap(self, event) -> None:
        if event.widget is self.root and self.cfg["tray"] and self.tray and self.root.state() == "iconic":
            self.root.withdraw()
            if not self.cfg["tray_hint"]:  # say once where the window went
                self.cfg["tray_hint"] = True
                save_settings(self.cfg)
                self.tray.notify(t("app.title"), t("tray.hidden"))

    # --------------------------------------------------------------- actions
    def pick_files(self) -> None:
        names = filedialog.askopenfilenames(
            title=t("dlg.pick_files"), initialdir=self.cfg["last_dir"] or None,
            filetypes=[(t("dlg.filetype"), "*.anydesk"), ("*", "*.*")])
        if names:
            self.cfg["last_dir"] = os.path.dirname(names[0])
            self._save_cfg()
            self.add_paths(names)

    def pick_folder(self) -> None:
        d = filedialog.askdirectory(title=t("dlg.pick_folder"), initialdir=self.cfg["last_dir"] or None)
        if d:
            self.cfg["last_dir"] = d
            self._save_cfg()
            self.add_paths([d])

    def pick_out(self) -> None:
        d = filedialog.askdirectory(title=t("dlg.pick_out"), initialdir=self.out_dir.get() or None)
        if d:
            self.out_dir.set(os.path.normpath(d))
            self.out_mode.set("folder")
            self._save_cfg()

    def _save_cfg(self) -> None:
        def pick(labels: dict, var: tk.StringVar, default):
            return next((k for k, v in labels.items() if v == var.get()), default)
        self.cfg["format"] = pick(self.fmt_labels, self.v_fmt, "mp4")
        self.cfg["max_height"] = pick(self.res_labels, self.v_res, 0)
        self.cfg["quality"] = pick(self.q_labels, self.v_q, "balanced")
        self.cfg["out_mode"], self.cfg["out_dir"] = self.out_mode.get(), self.out_dir.get()
        self._sync_out()
        save_settings(self.cfg)
        self._refresh()

    def _selected(self) -> list[str]:
        return [i for i in self.tree.selection() if i in self.items]

    def _context(self, e) -> None:
        iid = self.tree.identify_row(e.y)
        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            try:
                self.menu.tk_popup(e.x_root, e.y_root)
            finally:
                self.menu.grab_release()

    def move(self, step: int) -> None:
        sel = self._selected()
        order = list(self.tree.get_children())
        for iid in (sel if step < 0 else list(reversed(sel))):
            i = order.index(iid)
            j = i + step
            if 0 <= j < len(order) and order[j] not in sel:
                order[i], order[j] = order[j], order[i]
                self.tree.move(iid, "", j)
        self._refresh()

    def save_selected_to(self, folder: str | None = None) -> None:
        if folder is None:
            folder = filedialog.askdirectory(title=t("dlg.pick_out"), initialdir=self.out_dir.get() or None)
            if not folder:
                return
            folder = os.path.normpath(folder)
        for iid in self._selected():
            if self.items[iid]["state"] != "running":
                self.items[iid]["dest"] = folder or None
        self._refresh()

    def open_video(self) -> None:
        for iid in self._selected():
            out = self.items[iid].get("out")
            if out and os.path.isfile(out):
                os.startfile(out)

    def open_folder(self) -> None:
        for iid in self._selected()[:1]:
            it = self.items[iid]
            target = it["out"] if it.get("out") and os.path.exists(it["out"]) else it["path"]
            subprocess.Popen([system_tool("explorer.exe"), "/select,", os.path.normpath(target)])

    def retry_selected(self) -> None:
        for iid in self._selected():
            if self.items[iid]["state"] in ("failed", "done"):
                self.items[iid]["out_size"] = None
                self._set(iid, "queued", "status.queued")
        self._refresh()

    def remove_selected(self) -> None:
        for iid in self._selected():
            if self.items[iid]["state"] != "running":
                del self.items[iid]
                self.tree.delete(iid)
        self._refresh()

    def clear_done(self) -> None:
        for iid in list(self.items):
            if self.items[iid]["state"] == "done":
                del self.items[iid]
                self.tree.delete(iid)
        self._refresh()

    # --------------------------------------------------------------- dialogs
    def _dialog(self, title: str) -> tk.Toplevel:
        win = tk.Toplevel(self.root, bg=C["paper"])
        win.title(title)
        win.transient(self.root)
        win.resizable(False, False)
        win.body = ttk.Frame(win, padding=18)
        win.body.pack(fill="both", expand=True)
        win.geometry(f"+{self.root.winfo_rootx() + 120}+{self.root.winfo_rooty() + 90}")
        win.after(10, lambda: (win.grab_set(), self._dark_titlebar(win)))
        return win

    def _dialog_buttons(self, win: tk.Toplevel, on_ok) -> None:
        row = ttk.Frame(win.body)
        row.pack(fill="x", pady=(14, 0))
        ttk.Button(row, text=t("btn.cancel"), command=win.destroy).pack(side="right")
        ttk.Button(row, text=t("btn.ok"), command=on_ok).pack(side="right", padx=6)
        win.bind("<Return>", lambda e: on_ok())
        win.bind("<Escape>", lambda e: win.destroy())

    def options(self) -> None:
        win = self._dialog(t("opt.title"))
        fps = tk.StringVar(value=str(self.cfg["fps"]))
        flags = {k: tk.BooleanVar(value=self.cfg[k])
                 for k in ("stealth", "wait_busy", "rewind", "skip_existing", "keep_awake", "tray", "shutdown")}
        row = ttk.Frame(win.body)
        row.pack(anchor="w", pady=(0, 6))
        ttk.Label(row, text=t("opt.fps"), width=14).pack(side="left")
        ttk.Combobox(row, textvariable=fps, values=[str(x) for x in FPS_CHOICES], width=6,
                     state="readonly").pack(side="left")
        for k in flags:
            ttk.Checkbutton(win.body, text=t("opt." + k), variable=flags[k]).pack(anchor="w", pady=3)

        def ok() -> None:
            self.cfg["fps"] = int(fps.get())
            for k, v in flags.items():
                self.cfg[k] = v.get()
            save_settings(self.cfg)
            win.destroy()

        self._dialog_buttons(win, ok)

    def about(self) -> None:
        win = self._dialog(t("about.title"))
        top = ttk.Frame(win.body)
        top.pack(anchor="w")
        if os.path.isfile(ICON_PNG):
            try:
                win.logo = tk.PhotoImage(file=ICON_PNG).subsample(4)
                ttk.Label(top, image=win.logo).pack(side="left", padx=(0, 14))
            except tk.TclError:
                pass
        col = ttk.Frame(top)
        col.pack(side="left")
        ttk.Label(col, text=t("app.title"), font=(FONT, 14, "bold")).pack(anchor="w")
        ttk.Label(col, text=f"v{APP_VERSION}", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(win.body, text=t("about.made"), wraplength=460).pack(anchor="w", pady=(14, 2))
        ttk.Label(win.body, text=t("about.license"), wraplength=460).pack(anchor="w")
        ttk.Label(win.body, text=t("about.disclaimer"), wraplength=460, style="Muted.TLabel").pack(anchor="w", pady=(8, 12))
        for label, url in ((t("about.product"), PRODUCT_URL), (t("about.privacy"), PRIVACY_URL),
                           (t("about.source"), SOURCE_URL),
                           (t("about.report"), SOURCE_URL + "/issues")):
            lk = tk.Label(win.body, text=label + "  ↗", fg=C["accent"], bg=C["paper"], cursor="hand2",
                          font=(FONT, 10, "underline"))
            lk.pack(anchor="w", pady=1)
            lk.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
        row = ttk.Frame(win.body)
        row.pack(fill="x", pady=(14, 0))
        ttk.Button(row, text=t("btn.close"), command=win.destroy).pack(side="right")
        win.bind("<Escape>", lambda e: win.destroy())

    def on_close(self) -> None:
        if self.running and self.child is not None:
            self.show()
            if not messagebox.askyesno(t("app.title"), t("dlg.quit_running")):
                return
            self.stop()
            deadline = time.time() + 25
            while self.child is not None and time.time() < deadline:
                self.root.update()
                time.sleep(0.1)
        self.closing = True
        for tid in self._timers.values():  # or a pending callback fires on a dead interpreter
            try:
                self.root.after_cancel(tid)
            except tk.TclError:
                pass
        self._keep_awake(False)
        if self.tray:
            self.tray.remove()
        if self.drop:
            self.drop.close()
        self.root.destroy()


# ------------------------------------------------------------ single instance
def serve_other_instances(app: App, listener: Listener) -> None:
    """Later launches (e.g. from Explorer's right-click) hand their files to this window."""
    def loop() -> None:
        while True:
            try:
                with listener.accept() as conn:
                    # bytes + JSON rather than conn.recv(): that would unpickle whatever a
                    # local process chose to send
                    names = json.loads(conn.recv_bytes(1 << 20).decode("utf-8"))
                if isinstance(names, list):
                    app.ui.put(("add", [n for n in names if isinstance(n, str)]))
            except (OSError, EOFError, ValueError):
                continue

    threading.Thread(target=loop, daemon=True).start()


def main() -> int:
    if "--worker" in sys.argv[1:]:
        # the packaged program is its own conversion worker (see paths.worker_command)
        return anydesk2mp4.main()
    files = [a for a in sys.argv[1:] if not a.startswith("-")]
    # Explorer starts one process per selected file, all at once: exactly one of them
    # wins the pipe and becomes the window, the others hand over their file and leave.
    listener = None
    for _ in range(20):
        try:
            with Client(PIPE, family="AF_PIPE", authkey=PIPE_KEY) as conn:
                conn.send_bytes(json.dumps(files).encode("utf-8"))
            return 0
        except (OSError, EOFError):
            pass
        try:
            listener = Listener(PIPE, family="AF_PIPE", authkey=PIPE_KEY)
            break
        except OSError:
            time.sleep(0.3)  # somebody else is just becoming the window

    try:
        sysdll("shcore").SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    cfg = load_settings()
    cfg["lang"] = cfg["lang"] if cfg["lang"] in i18n.available() else None
    i18n.load(cfg["lang"])
    root = tk.Tk()
    app = App(root, cfg, files)
    if listener is not None:
        serve_other_instances(app, listener)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
