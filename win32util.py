"""Minimal Win32 helpers (ctypes only) for locating and sampling a window."""
from __future__ import annotations

import ctypes
import zlib
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True, winmode=0x800)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True, winmode=0x800)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True, winmode=0x800)

try:  # real pixel coordinates regardless of display scaling
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass

WM_CLOSE = 0x0010
SW_RESTORE, SW_MAXIMIZE = 9, 3
HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_NOSIZE, SWP_NOMOVE, SWP_SHOWWINDOW = 0x1, 0x2, 0x40
PW_RENDERFULLCONTENT = 0x2
MONITOR_DEFAULTTONEAREST = 2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [_EnumProc, wintypes.LPARAM]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HANDLE
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.GetBitmapBits.argtypes = [wintypes.HBITMAP, wintypes.LONG, ctypes.c_void_p]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]


def _process_name(pid: int) -> str:
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return buf.value.rsplit("\\", 1)[-1].lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


def window_title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, len(buf))
    return buf.value


def window_class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, len(buf))
    return buf.value


def list_windows(process_name: str) -> dict[int, str]:
    """Visible top-level windows owned by `process_name` -> title."""
    found: dict[int, str] = {}
    names: dict[int, str] = {}

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value not in names:
                names[pid.value] = _process_name(pid.value)
            if names[pid.value] == process_name.lower():
                found[hwnd] = window_title(hwnd)
        return True

    user32.EnumWindows(_EnumProc(cb), 0)
    return found


def is_alive(hwnd: int) -> bool:
    return bool(user32.IsWindow(hwnd)) and bool(user32.IsWindowVisible(hwnd))


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def client_rect_on_screen(hwnd: int) -> tuple[int, int, int, int]:
    """(x, y, w, h) of the client area in virtual-screen pixels."""
    r = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, r.right, r.bottom


def monitor_rect(hwnd: int) -> tuple[int, int, int, int]:
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(mi)
    user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST),
                           ctypes.byref(mi))
    m = mi.rcMonitor
    return m.left, m.top, m.right - m.left, m.bottom - m.top


def bring_to_front(hwnd: int, maximize: bool = False, topmost: bool = False) -> None:
    user32.ShowWindow(hwnd, SW_MAXIMIZE if maximize else SW_RESTORE)
    user32.SetWindowPos(hwnd, HWND_TOPMOST if topmost else HWND_NOTOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    user32.SetForegroundWindow(hwnd)


def close_window(hwnd: int) -> None:
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


def grab_window(hwnd: int) -> tuple[int, int, bytes]:
    """Snapshot of the whole window as raw BGRA (w, h, pixels) via PrintWindow."""
    _, _, w, h = window_rect(hwnd)
    if w <= 0 or h <= 0:
        return 0, 0, b""
    wdc = user32.GetDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(wdc)
    bmp = gdi32.CreateCompatibleBitmap(wdc, w, h)
    old = gdi32.SelectObject(mdc, bmp)
    try:
        user32.PrintWindow(hwnd, mdc, PW_RENDERFULLCONTENT)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetBitmapBits(bmp, len(buf), buf)
        return w, h, buf.raw
    finally:
        gdi32.SelectObject(mdc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(hwnd, wdc)


def window_hash(hwnd: int) -> int:
    return zlib.crc32(grab_window(hwnd)[2])


SW_SHOWNOACTIVATE = 4
SWP_NOZORDER, SWP_NOACTIVATE = 0x4, 0x10
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x2, 0x4

user32.EnumChildWindows.argtypes = [wintypes.HWND, _EnumProc, wintypes.LPARAM]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsZoomed.argtypes = [wintypes.HWND]
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]


user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND


def root_window(hwnd: int) -> int:
    return user32.GetAncestor(hwnd, 2) or hwnd  # GA_ROOT


def child_windows(hwnd: int) -> list[int]:
    kids: list[int] = []

    def cb(child, _):
        kids.append(child)
        return True

    user32.EnumChildWindows(hwnd, _EnumProc(cb), 0)
    return kids


def is_visible(hwnd: int) -> bool:
    return bool(user32.IsWindowVisible(hwnd))


def is_minimized(hwnd: int) -> bool:
    return bool(user32.IsIconic(hwnd))


def is_maximized(hwnd: int) -> bool:
    return bool(user32.IsZoomed(hwnd))


def work_area(hwnd: int) -> tuple[int, int, int, int]:
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(mi)
    user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST),
                           ctypes.byref(mi))
    r = mi.rcWork
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def restore_no_activate(hwnd: int) -> None:
    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)


def place_window(hwnd: int, x: int, y: int, w: int, h: int) -> None:
    """Move/resize without stealing focus or changing z-order."""
    user32.SetWindowPos(hwnd, 0, x, y, w, h, SWP_NOACTIVATE | SWP_NOZORDER)


def click_window(hwnd: int, dx: int, dy: int) -> bool:
    """Real left click at client (dx, dy) of `hwnd`; cursor is put back afterwards.

    The window is raised topmost for the moment of the click, and the click is
    skipped (returns False) unless that exact window is under the target point,
    so a covering application never receives it.
    """
    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
    top = root_window(hwnd)  # `hwnd` may be a child: only top-level windows can be raised
    user32.SetWindowPos(top, HWND_TOPMOST, 0, 0, 0, 0, flags)
    try:
        import time
        time.sleep(0.2)
        x, y, _, _ = client_rect_on_screen(hwnd)
        hit = user32.WindowFromPoint(wintypes.POINT(x + dx, y + dy))
        # a click may land on a child control of the same window; what matters is that
        # no *other* application is covering the spot
        if hit != hwnd and root_window(hit) != top:
            return False
        saved = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(saved))
        user32.SetCursorPos(x + dx, y + dy)
        time.sleep(0.12)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.06)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.08)
        user32.SetCursorPos(saved.x, saved.y)
        return True
    finally:
        user32.SetWindowPos(top, HWND_NOTOPMOST, 0, 0, 0, 0, flags)


HWND_BOTTOM = 1
user32.GetForegroundWindow.restype = wintypes.HWND
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


def foreground_window() -> int:
    return user32.GetForegroundWindow() or 0


def send_to_back(hwnd: int) -> None:
    """Put the window behind every other window without activating it."""
    user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def give_focus(hwnd: int) -> bool:
    """Best-effort: hand keyboard focus back to `hwnd` (another process's window)."""
    if not hwnd or not user32.IsWindow(hwnd) or foreground_window() == hwnd:
        return True
    me = kernel32.GetCurrentThreadId()
    holder = user32.GetWindowThreadProcessId(foreground_window(), None)
    attached = bool(holder) and holder != me and user32.AttachThreadInput(me, holder, True)
    try:
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(me, holder, False)
    if foreground_window() != hwnd:
        # Windows refuses focus changes from background processes unless the caller
        # just produced input; a bare Alt tap is the documented way to qualify
        user32.keybd_event(0x12, 0, 0, 0)
        user32.SetForegroundWindow(hwnd)
        user32.keybd_event(0x12, 0, 2, 0)
    return foreground_window() == hwnd


GWL_EXSTYLE = -20
WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_APPWINDOW = 0x20, 0x80, 0x40000
WS_EX_LAYERED, WS_EX_NOACTIVATE = 0x80000, 0x08000000
LWA_ALPHA = 0x2
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_ubyte, wintypes.DWORD]
shell32 = ctypes.WinDLL("shell32", use_last_error=True, winmode=0x800)


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def make_stealth(hwnd: int) -> bool:
    """Keep a window alive and drawn but out of the user's way: all but transparent
    (alpha 1/255 - Windows stops drawing fully hidden or minimized windows, this it still
    draws), click-through, never activated, and absent from the taskbar and Alt+Tab."""
    ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    ex = (ex | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE) & ~WS_EX_APPWINDOW
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex)
    return bool(user32.SetLayeredWindowAttributes(hwnd, 0, 1, LWA_ALPHA))


def set_click_through(hwnd: int, on: bool) -> None:
    ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    ex = (ex | WS_EX_TRANSPARENT) if on else (ex & ~WS_EX_TRANSPARENT)
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex)


def is_stealth(hwnd: int) -> bool:
    return bool(user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE) & WS_EX_LAYERED)


def user_is_busy() -> bool:
    """True while a game, another full-screen application or a presentation is running -
    the states in which Windows itself holds back notifications."""
    state = ctypes.c_int(0)
    if shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
        return False
    return state.value in (2, 3, 4)  # QUNS_BUSY, QUNS_RUNNING_D3D_FULL_SCREEN, QUNS_PRESENTATION_MODE


def idle_seconds() -> float:
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return max(0.0, (kernel32.GetTickCount() - info.dwTime) / 1000.0)
