"""Convert AnyDesk session recordings (.anydesk) to MP4.

The picture codec is proprietary, so the recording is played back by AnyDesk
itself (`AnyDesk.exe --play`) while ffmpeg captures the playback view.
Conversion therefore runs in real time.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

import adrec
import capture
import shellmenu
import win32util as w

ANYDESK_CANDIDATES = [
    r"C:\Program Files (x86)\AnyDesk\AnyDesk.exe",
    r"C:\Program Files\AnyDesk\AnyDesk.exe",
]
PROCESS = "AnyDesk.exe"
TRACE_FILE = os.path.join(os.environ.get("APPDATA", ""), "AnyDesk", "ad.trace")
RESTART_MARK = b"Restarting playback from beginning"
TAIL_PAD = 1.0         # seconds kept after the nominal end
RESTART_SETTLE = 0.35  # seek-to-start latency after the click (AnyDesk 9 is slower)
# AnyDesk 5.4 dies with an access violation when asked to restart before it has
# decoded the first picture, so the rewind waits this long past that point.
FIRST_PICTURE_MARGIN = 2.0
SETTLE = 4.0           # AnyDesk shuffles focus/minimizes during its first seconds
SCREEN_MARGIN = 48     # a playback window filling the work area minimizes itself
ATTEMPTS = 3           # AnyDesk 5.4's player crashes now and then; just try again


JSON_EVENTS = False    # --json: one JSON object per line for a front end to follow


def event(kind: str, **fields) -> None:
    if JSON_EVENTS:
        print(json.dumps({"event": kind, **fields}), flush=True)


class ConvertError(RuntimeError):
    pass


class PlayerError(ConvertError):
    """AnyDesk misbehaved (crash, vanished window, dead button): worth a retry."""


def find_anydesk(explicit: str | None) -> str:
    for p in ([explicit] if explicit else []) + ANYDESK_CANDIDATES:
        if p and os.path.isfile(p):
            return p
    raise ConvertError("AnyDesk.exe not found; pass --anydesk PATH")


def hide_behind(win: int, bar: int, user_fg: int) -> None:
    """Keep the player out of the way: behind every window, focus back to the user."""
    if w.root_window(bar) == bar:  # AnyDesk 5: the bar is a window of its own
        w.send_to_back(bar)
    w.send_to_back(win)
    # 0 = nobody has focus: happens when the buried player was the foreground window
    if w.foreground_window() in (win, bar, 0):
        w.give_focus(user_fg)


def wait_until_free(args) -> None:
    """The one moment a conversion can disturb the user is the start of a file (the player
    opens, the mouse clicks once). Hold that back while a game, another full-screen
    application or a presentation is running."""
    if args.ignore_busy or not w.user_is_busy():
        return
    print("  a full-screen app is running - waiting for it to end before starting this file")
    event("busy_wait")
    while w.user_is_busy():
        if args.stop_file and os.path.exists(args.stop_file):
            raise KeyboardInterrupt
        time.sleep(5)
    time.sleep(10)  # let the user settle back on the desktop first
    event("busy_over")


def open_playback(exe: str, path: str, timeout: float = 30.0, stealth: bool = True,
                  user_fg: int = 0) -> tuple[int, int]:
    """Start playback; returns (playback window, control bar)."""
    close_stale_players()
    before = set(w.list_windows(PROCESS))
    subprocess.Popen([exe, "--play", path])
    win = bar = None
    end = time.time() + timeout
    while time.time() < end and not (win and bar):
        for h in w.list_windows(PROCESS):
            if h in before:
                continue
            cls = w.window_class(h)
            if cls.startswith("ad.playback_bar"):
                bar = h
            elif cls.startswith("ad_win") and not w.is_minimized(h):
                win = h
                w.send_to_back(h)  # it pops up over the user's work: bury it at once
                if stealth:
                    w.make_stealth(h)
                if user_fg and w.foreground_window() == h:
                    w.give_focus(user_fg)  # AnyDesk grabs the keyboard as it opens: hand it back now
        if win and not bar:  # AnyDesk 7+: the bar is a child laid over the view
            bar = next((c for c in w.child_windows(win)
                        if w.window_class(c).startswith("ad.playback_bar")), None)
        time.sleep(0.05)
    if not (win and bar):
        raise ConvertError("playback window did not appear")
    return win, bar


def close_stale_players() -> None:
    """A hidden player can outlive a converter that was killed; nobody could see it to close it.
    Only one conversion runs at a time (see shellmenu.wait_for_turn), so any hidden player
    found here is a leftover."""
    for h in w.list_windows(PROCESS):
        if w.is_stealth(h) and any(w.window_class(c).startswith("ad.playback_bar")
                                   for c in [h] + w.child_windows(h)):
            w.close_window(h)


def crash_dialogs() -> list[int]:
    return [h for h in w.list_windows(PROCESS) if w.window_class(h).startswith("ad_crash")]


def _trace_size() -> int:
    try:
        return os.path.getsize(TRACE_FILE)
    except OSError:
        return -1


def _restart_logged(since: int, timeout: float = 1.5) -> bool | None:
    """Did AnyDesk log the restart after offset `since`? None if the trace is unreadable."""
    if since < 0:
        return None
    end = time.time() + timeout
    while time.time() < end:
        try:
            with open(TRACE_FILE, "rb") as f:
                # AnyDesk trims its log from the top now and then; a shorter file means the
                # remembered offset is meaningless, so look at the tail instead
                size = f.seek(0, 2)
                f.seek(since if since <= size else max(0, size - 4096))
                if RESTART_MARK in f.read():
                    return True
        except OSError:
            return None
        time.sleep(0.1)
    return False


def rewind(win: int, bar: int) -> None:
    """Click the bar's restart button, confirming through AnyDesk's trace log."""
    for _ in range(3):
        if w.is_minimized(win):
            w.restore_no_activate(win)
            time.sleep(0.7)
        if not w.is_alive(bar) or w.window_rect(bar)[0] <= -30000:
            raise PlayerError("playback bar is not on screen")
        _, _, _, bar_h = w.window_rect(bar)
        mark = _trace_size()
        stealth = w.is_stealth(win)
        if stealth:
            w.set_click_through(win, False)  # or the click would fall through to what is behind
        try:
            clicked = w.click_window(bar, int(bar_h * 0.45), int(bar_h * 0.55))
        finally:
            if stealth:
                w.set_click_through(win, True)
        if not clicked:
            raise ConvertError("could not reach the playback bar to rewind "
                               "(is another always-on-top window covering it?)")
        if _restart_logged(mark) is not False:
            return
    raise PlayerError("AnyDesk did not react to the restart button")


def find_view(win: int) -> int:
    for c in w.child_windows(win):
        if w.window_class(c).startswith("gui.tabbar_panel") and w.is_visible(c):
            return c
    raise ConvertError("playback view not found inside the AnyDesk window")


def fit_window(win: int, view: int, vw: int, vh: int, bar: int = 0,
               max_width: int = 4096) -> None:
    """Size the window so the view shows the video 1:1 (AnyDesk never upscales),
    or at the largest size worth capturing when it is wider than the codec allows."""
    scale = min(1.0, max_width / vw)
    vw, vh = int(vw * scale), int(vh * scale)
    if w.is_maximized(win):  # a maximized window snaps back when it gets activated
        w.restore_no_activate(win)
        time.sleep(0.5)
    if bar and w.root_window(bar) != bar:
        # an overlaid bar hides the bottom of the view; the picture is centred, so
        # twice the bar's height keeps it clear of the bar
        vh += 2 * w.window_rect(bar)[3]
    _, _, ww, wh = w.window_rect(win)
    _, _, pw, ph = w.window_rect(view)
    ax, ay, aw, ah = w.work_area(win)
    w.place_window(win, ax, ay, min(aw - SCREEN_MARGIN, vw + (ww - pw)),
                   min(ah - SCREEN_MARGIN, vh + (wh - ph)))


def video_rect(view: int, vw: int, vh: int) -> tuple[int, int, int, int]:
    """(w, h, x, y) of the picture inside the view: aspect-fit, centred, max 1:1."""
    _, _, pw, ph = w.window_rect(view)
    scale = min(1.0, pw / vw, ph / vh)
    sw, sh = int(vw * scale) & ~1, int(vh * scale) & ~1
    return sw, sh, (pw - sw) // 2, (ph - sh) // 2


def progress_line(done: float, total: float | None, speed: str) -> None:
    if JSON_EVENTS:
        event("progress", done=round(done, 1), total=total, speed=speed)
        return
    def mmss(s: float) -> str:
        return f"{int(s) // 60}:{int(s) % 60:02d}"
    tot = mmss(total) if total else "?"
    sys.stdout.write(f"\r  recording {mmss(done)} / {tot}  (ffmpeg speed {speed or '-'})   ")
    sys.stdout.flush()


def convert(path: str, out_path: str, args) -> None:
    info = adrec.read_info(path)
    print(info.describe())
    event("start", file=path, duration=info.duration, width=info.width, height=info.height,
          peers=[n for n, _ in info.peers])
    duration = args.duration if args.duration else info.duration
    if duration is not None and duration <= 0:
        raise ConvertError("recording is empty")

    fmt = capture.FORMATS[args.format]
    exe = find_anydesk(args.anydesk)
    tmp = out_path + ".part.mkv"
    stale_crashes = set(crash_dialogs())
    wait_until_free(args)
    user_fg = w.foreground_window()
    win, bar = open_playback(exe, path, stealth=not args.visible, user_fg=user_fg)
    hide_behind(win, bar, user_fg)
    opened_at = time.time()
    rec = None
    interrupted = False
    try:
        time.sleep(0.5)
        view = find_view(win)
        crop = None
        if info.width and not args.no_crop:
            fit_window(win, view, info.width, info.height, bar, fmt.max_width)
            time.sleep(0.8)
            crop = video_rect(view, info.width, info.height)
            if crop[0] < info.width:
                event("warning", code="downscaled", width=crop[0], height=crop[1])
                print(f"  note: {info.width}x{info.height} does not fit (screen size / "
                      f"H.264 width limit), capturing at {crop[0]}x{crop[1]}")

        # Without a rewind the recording plays on while we set up, so every second spent
        # here is a second of it lost - start as soon as the window is laid out.
        wait = 1.2 if args.no_rewind else max(SETTLE, (info.first_picture or 0.0) + FIRST_PICTURE_MARGIN)
        time.sleep(max(0.0, wait - (time.time() - opened_at)))
        if not w.is_alive(win):
            raise PlayerError("AnyDesk player died while starting")
        if w.is_minimized(win):
            w.restore_no_activate(win)
            time.sleep(0.7)
        hide_behind(win, bar, user_fg)
        if crop:  # the view may have been laid out again meanwhile
            crop = video_rect(view, info.width, info.height)
            if w.root_window(bar) != bar:
                hidden = crop[3] + crop[1] - (w.window_rect(view)[3] - w.window_rect(bar)[3])
                if hidden > 0:
                    event("warning", code="bar_overlap", pixels=hidden)
                    print(f"  warning: the playback bar covers the bottom {hidden}px of the picture")

        event("stage", name="recording")
        rec = capture.Recorder(view, tmp, args.fps, args.cq, crop, fmt,
                               max_height=args.max_height, dense_until=30.0)
        if not rec.wait_started():
            raise ConvertError("ffmpeg failed to start:\n" + rec.errors())

        if args.no_rewind:
            head = 0.0
            duration = None if duration is None else max(1.0, duration - (time.time() - opened_at))
        else:
            # rewind so the capture contains the recording from its first frame
            user_fg = w.foreground_window() or user_fg
            try:
                rewind(win, bar)
            finally:
                hide_behind(win, bar, user_fg)
            head = time.time() - rec.started_at + RESTART_SETTLE

        t0 = time.time()
        idle_since, last_hash = t0, None
        try:
            while rec.running():
                elapsed = time.time() - t0
                if args.stop_file and os.path.exists(args.stop_file):
                    raise KeyboardInterrupt  # the front end asked to stop: keep what we have
                if duration is not None:
                    if elapsed >= duration + TAIL_PAD:
                        break
                else:  # unknown length: stop once the picture stays frozen
                    hsh = w.window_hash(view)
                    if hsh != last_hash:
                        last_hash, idle_since = hsh, time.time()
                    elif time.time() - idle_since >= args.idle_stop:
                        duration = max(1.0, idle_since - t0)
                        break
                if not w.is_alive(win):
                    if set(crash_dialogs()) - stale_crashes:
                        raise PlayerError("AnyDesk crashed during playback")
                    raise PlayerError("playback window was closed")
                if w.is_minimized(win):  # a minimized window cannot be captured
                    w.restore_no_activate(win)
                    hide_behind(win, bar, w.foreground_window())
                    event("warning", code="was_minimized")
                    print("\n  warning: playback window was minimized; restored "
                          "(that stretch of the video is frozen)")
                progress_line(elapsed, duration, rec.speed)
                time.sleep(1.0 if duration is not None else 2.0)
        except KeyboardInterrupt:
            interrupted = True
            duration = time.time() - t0
            print("\n  interrupted - finalizing what was captured")
        print()
        if not rec.running() and not interrupted:
            # ffmpeg only ends on its own when the capture broke (exit code is still 0)
            kind = ConvertError if w.is_alive(win) else PlayerError
            raise kind(f"ffmpeg stopped early at {rec.out_time:.1f}s "
                               f"(exit {rec.proc.returncode}):\n" + rec.errors())
        rec.stop()
        event("stage", name="finishing")

        start = capture.cut_point(tmp, head)
        length = None if duration is None else max(0.5, duration + TAIL_PAD + (head - start))
        if fmt.transcode:
            event("stage", name="transcoding")
        capture.finalize(tmp, out_path, start, length, fmt)
    finally:
        if rec is not None:
            rec.stop()
        if w.is_alive(win):
            w.close_window(win)
        for dlg in set(crash_dialogs()) - stale_crashes:
            w.close_window(dlg)
        if os.path.exists(tmp) and (os.path.exists(out_path) or not args.keep_temp):
            try:
                os.remove(tmp)
            except OSError:
                pass

    p = capture.probe(out_path)
    event("done", out=out_path, duration=float(p.get("duration", 0)), size=int(p.get("size", 0)),
          width=p.get("width"), height=p.get("height"), partial=interrupted)
    print(f"  -> {out_path}\n     {p.get('codec_name')} {p.get('width')}x{p.get('height')} "
          f"{float(p.get('duration', 0)):.1f}s  {int(p.get('size', 0)) / 1e6:.1f} MB")
    if interrupted:
        raise KeyboardInterrupt


def expand(patterns: list[str]) -> list[str]:
    files: list[str] = []
    for pat in patterns:
        if os.path.isfile(pat):  # names contain "(" ")" etc: try literal first
            files.append(pat)
            continue
        if os.path.isdir(pat):  # a folder means every recording in it
            files += sorted(os.path.join(pat, n) for n in os.listdir(pat)
                            if n.lower().endswith(".anydesk"))
            continue
        hits = sorted(glob.glob(pat))
        if not hits:
            print(f"no match: {pat}", file=sys.stderr)
        files += [h for h in hits if h.lower().endswith(".anydesk")]
    return list(dict.fromkeys(os.path.abspath(f) for f in files))


def run() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*",
                    help=".anydesk files or glob patterns (none: choose in a dialog)")
    ap.add_argument("-o", "--outdir", help="output folder (default: next to the source)")
    ap.add_argument("--format", choices=sorted(capture.FORMATS), default="mp4",
                    help="container/codec of the result (default mp4)")
    ap.add_argument("--max-height", type=int, metavar="PX",
                    help="scale down to at most this many lines, e.g. 1080 or 720")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--cq", type=int, default=23, help="quality, lower = better (default 23)")
    ap.add_argument("--duration", type=float, help="override recording length in seconds")
    ap.add_argument("--idle-stop", type=float, default=120,
                    help="when the length is unknown, stop after this many frozen seconds")
    ap.add_argument("--no-rewind", action="store_true",
                    help="never touch the mouse; the first seconds of the recording are lost")
    ap.add_argument("--visible", action="store_true",
                    help="leave the AnyDesk player visible instead of transparent and click-through")
    ap.add_argument("--ignore-busy", action="store_true",
                    help="start files even while a game or full-screen app is running")
    ap.add_argument("--no-crop", action="store_true", help="keep the whole playback view")
    ap.add_argument("--info", action="store_true", help="print metadata only")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--keep-temp", action="store_true", help="keep the .mkv if remux fails")
    ap.add_argument("--anydesk", help="path to AnyDesk.exe")
    ap.add_argument("--install", action="store_true",
                    help="add the Explorer right-click entry and a desktop shortcut")
    ap.add_argument("--uninstall", action="store_true", help="remove them again")
    ap.add_argument("--json", action="store_true", help="also print JSON progress events")
    ap.add_argument("--stop-file", help="stop gracefully as soon as this file exists")
    ap.add_argument("--pause", action="store_true",
                    help="keep the console open at the end (used by the shortcuts)")
    args = ap.parse_args()
    global JSON_EVENTS
    JSON_EVENTS = args.json

    if args.install or args.uninstall:
        (shellmenu.install if args.install else shellmenu.uninstall)()
        return 0
    files = expand(args.files) if args.files else shellmenu.pick_files()
    if not files:
        print("no files selected")
        return 2
    if args.info:
        bad = 0
        for f in files:
            try:
                print(adrec.read_info(f).describe())
            except (adrec.NotAnAnyDeskRecording, OSError, ValueError) as e:
                print(f"{f}\n  not an AnyDesk recording ({type(e).__name__})")
                bad += 1
        return 1 if bad else 0
    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)
    def out_for(f: str) -> str:
        return os.path.join(args.outdir or os.path.dirname(f),
                            os.path.splitext(os.path.basename(f))[0]
                            + "." + capture.FORMATS[args.format].ext)

    if len(files) > 1:  # conversion is real time, so say how long the queue will take
        todo = [f for f in files if args.overwrite or not os.path.exists(out_for(f))]
        total = 0.0
        for f in todo:
            try:
                total += (adrec.read_info(f).duration or 0.0) + 15  # + per-file overhead
            except (OSError, ValueError):
                pass
        done_at = time.strftime("%H:%M", time.localtime(time.time() + total))
        print(f"queue: {len(todo)} to convert ({len(files) - len(todo)} already done), "
              f"about {int(total // 3600)}h{int(total % 3600 // 60):02d}m - finishes around {done_at}")
        print()

    shellmenu.wait_for_turn(lambda: event("queue_wait"))

    failed = []
    for i, f in enumerate(files, 1):
        out = out_for(f)
        print(f"[{i}/{len(files)}] ", end="")
        if os.path.exists(out) and not args.overwrite:
            print(f"skip (exists): {out}")
            event("skipped", file=f, out=out)
            continue
        try:
            for attempt in range(1, ATTEMPTS + 1):
                try:
                    convert(f, out, args)
                    break
                except PlayerError as e:
                    if attempt == ATTEMPTS:
                        raise
                    event("retry", attempt=attempt + 1, of=ATTEMPTS, reason=str(e))
                    print(f"  AnyDesk problem ({e}); retrying {attempt + 1}/{ATTEMPTS}")
                    time.sleep(3)
        except KeyboardInterrupt:
            print("stopped by user")
            return 130
        except (ConvertError, adrec.NotAnAnyDeskRecording, RuntimeError, OSError) as e:
            print(f"  FAILED: {e}")
            event("failed", file=f, error=str(e))
            failed.append(f)
    print(f"\ndone: {len(files) - len(failed)} ok, {len(failed)} failed")
    for f in failed:
        print("  failed:", f)
    return 1 if failed else 0


def _restore_streams() -> None:
    """A windowed build starts with no stdout, but the parent gave us a pipe on fd 1;
    wrap it again so progress events reach the window."""
    import io
    for fd, name in ((1, "stdout"), (2, "stderr")):
        if getattr(sys, name, None) is None:
            try:
                stream = io.TextIOWrapper(io.FileIO(fd, "w"), encoding="utf-8",
                                          errors="replace", line_buffering=True)
            except OSError:
                stream = io.StringIO()
            setattr(sys, name, stream)


def main() -> int:
    if "--worker" in sys.argv[1:]:   # packaged: the same .exe is its own conversion worker
        sys.argv.remove("--worker")
        _restore_streams()
    code = 1
    try:
        code = run()
    finally:
        if "--pause" in sys.argv:
            shellmenu.pause_before_exit(code in (0, 2))
    return code


if __name__ == "__main__":
    sys.exit(main())
