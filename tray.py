"""Notification-area (system tray) icon via Shell_NotifyIconW - ctypes only.

The icon owns a hidden window. Create it on the GUI thread: that thread's message loop
(Tk's, here) then delivers the clicks.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True, winmode=0x800)
shell32 = ctypes.WinDLL("shell32", use_last_error=True, winmode=0x800)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True, winmode=0x800)

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
NIIF_INFO = 0x1
WM_APP_TRAY = 0x8000 + 1
WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP = 0x0202, 0x0203, 0x0205
IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x10, 0x40

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT),
                ("hIcon", wintypes.HICON), ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wintypes.HICON)]


user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]

_CLASS = "anydesk2mp4.tray"
_registered = None  # keeps the window procedure alive for the life of the process


class TrayIcon:
    def __init__(self, icon_path: str, tip: str, on_activate, on_menu):
        """on_activate(): left click / double click. on_menu(): right click."""
        global _registered
        self.on_activate, self.on_menu = on_activate, on_menu
        self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
        self._proc = WNDPROC(self._wndproc)
        hinst = kernel32.GetModuleHandleW(None)
        if _registered is None:
            cls = WNDCLASSW()
            cls.lpfnWndProc, cls.hInstance, cls.lpszClassName = self._proc, hinst, _CLASS
            user32.RegisterClassW(ctypes.byref(cls))
            _registered = self._proc
        self.hwnd = user32.CreateWindowExW(0, _CLASS, _CLASS, 0, 0, 0, 0, 0, None, None, hinst, None)
        self._icon = user32.LoadImageW(None, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        self._tip = tip
        self.visible = False
        self.show()

    def _data(self, flags: int) -> NOTIFYICONDATAW:
        d = NOTIFYICONDATAW()
        d.cbSize = ctypes.sizeof(d)
        d.hWnd, d.uID, d.uFlags = self.hwnd, 1, flags
        d.uCallbackMessage, d.hIcon, d.szTip = WM_APP_TRAY, self._icon, self._tip[:127]
        return d

    def show(self) -> None:
        self.visible = bool(shell32.Shell_NotifyIconW(
            NIM_ADD, ctypes.byref(self._data(NIF_MESSAGE | NIF_ICON | NIF_TIP))))

    def set_tip(self, tip: str) -> None:
        if tip != self._tip:
            self._tip = tip
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._data(NIF_TIP)))

    def notify(self, title: str, text: str) -> None:
        d = self._data(NIF_INFO)
        d.szInfoTitle, d.szInfo, d.dwInfoFlags = title[:63], text[:255], NIIF_INFO
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(d))

    def remove(self) -> None:
        if self.visible:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._data(0)))
            self.visible = False
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_APP_TRAY:
                if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self.on_activate()
                elif lparam == WM_RBUTTONUP:
                    user32.SetForegroundWindow(hwnd)  # lets the popup menu close on click-away
                    self.on_menu()
                return 0
            if msg == self._taskbar_created:  # Explorer restarted: put the icon back
                self.show()
                return 0
        except Exception:  # an exception must never unwind into the window procedure
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


# --- native pop-up menu -------------------------------------------------------
# Tk's tk_popup takes a global grab that only a real click releases; if the menu is left
# open the whole window stops responding. The shell's own menu is what tray icons use.
MF_STRING, MF_SEPARATOR, MF_GRAYED = 0x0, 0x800, 0x1
TPM_RIGHTBUTTON, TPM_RETURNCMD, TPM_RIGHTALIGN, TPM_BOTTOMALIGN = 0x2, 0x100, 0x8, 0x20

user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_void_p, wintypes.LPCWSTR]
user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, wintypes.HWND, ctypes.c_void_p]
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


def popup_menu(owner: int, items: list[tuple[str, object]]) -> None:
    """Show `items` at the cursor and run the chosen callback.

    items: (label, callback) pairs; ("-", None) draws a separator and a callback of
    None greys the entry out.
    """
    menu = user32.CreatePopupMenu()
    if not menu:
        return
    actions: dict[int, object] = {}
    try:
        for i, (label, action) in enumerate(items, start=1):
            if label == "-":
                user32.AppendMenuW(menu, MF_SEPARATOR, None, None)
                continue
            flags = MF_STRING | (0 if action else MF_GRAYED)
            user32.AppendMenuW(menu, flags, ctypes.c_void_p(i), label)
            actions[i] = action
        pos = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pos))
        # the shell requires this pair around a tray menu, or it never closes on click-away
        user32.SetForegroundWindow(owner)
        chosen = user32.TrackPopupMenu(
            menu, TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_RIGHTALIGN | TPM_BOTTOMALIGN,
            pos.x, pos.y, 0, owner, None)
        user32.PostMessageW(owner, 0, 0, 0)  # WM_NULL
    finally:
        user32.DestroyMenu(menu)
    action = actions.get(chosen)
    if action:
        action()
