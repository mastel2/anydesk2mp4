"""Desktop integration: Explorer right-click entry, desktop shortcut, file picker,
and a cross-process queue so several launches convert one after another."""
from __future__ import annotations

import ctypes
import os
import subprocess
import winreg

import paths

MENU_KEY = r"Software\Classes\SystemFileAssociations\.anydesk\shell\anydesk2mp4"
MENU_LABEL = "Convert to MP4"
SHORTCUT_NAME = "Recording Converter for AnyDesk.lnk"
OLD_SHORTCUTS = ("AnyDesk to MP4.lnk",)
_MUTEX_NAME = "Local\\anydesk2mp4-queue"
_WAIT_TIMEOUT = 0x102

_mutex = None  # kept referenced for the life of the process


def _icon() -> str:
    ico = paths.resource("assets", "app.ico")
    return ico if os.path.isfile(ico) else "imageres.dll,-5205"


def _launch_command(arg: str) -> str:
    # every selected file starts this once; the first becomes the window and the
    # others hand their file over to it (see gui.serve_other_instances)
    parts = " ".join(f'"{p}"' for p in paths.launch_command())
    return f"{parts} {arg}".rstrip()


def _desktop() -> str:
    buf = ctypes.create_unicode_buffer(260)
    ctypes.WinDLL("shell32", winmode=0x800).SHGetFolderPathW(None, 0x10, None, 0, buf)  # desktop dir
    return buf.value


def _ps_quote(value: str) -> str:
    """Make a value safe inside a single-quoted PowerShell string (paths may contain ')."""
    return value.replace("'", "''")


def _system_tool(*parts: str) -> str:
    """Absolute path of a Windows tool, so PATH cannot substitute another program."""
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), *parts)


def _powershell(script: str) -> None:
    exe = _system_tool("System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    subprocess.run([exe, "-NoProfile", "-NonInteractive", "-Command", script], check=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def install() -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, MENU_KEY) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, MENU_LABEL)
        winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, _icon())
        # one process per selected file is fine: they queue on the mutex below
        winreg.SetValueEx(k, "MultiSelectModel", 0, winreg.REG_SZ, "Player")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, MENU_KEY + r"\command") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, _launch_command('"%1"'))
    for name in OLD_SHORTCUTS:
        old = os.path.join(_desktop(), name)
        if os.path.exists(old):
            os.remove(old)
    print(f'right-click menu added: "{MENU_LABEL}" on .anydesk files')

    lnk = os.path.join(_desktop(), SHORTCUT_NAME)
    launch = paths.launch_command()
    target, args = launch[0], " ".join(f'"{p}"' for p in launch[1:])
    _powershell(
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
        "$s.TargetPath = '%s'; $s.Arguments = '%s';"
        "$s.WorkingDirectory = '%s'; $s.IconLocation = '%s';"
        "$s.Description = 'Convert AnyDesk recordings to MP4'; $s.Save()"
        % tuple(_ps_quote(v) for v in (lnk, target, args, os.path.dirname(target), _icon())))
    print(f"desktop shortcut created: {lnk}")
    print("  double-click it to pick files, or drop .anydesk files onto it")


def uninstall() -> None:
    for sub in (MENU_KEY + r"\command", MENU_KEY):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
        except FileNotFoundError:
            pass
    for name in (SHORTCUT_NAME,) + OLD_SHORTCUTS:
        lnk = os.path.join(_desktop(), name)
        if os.path.exists(lnk):
            os.remove(lnk)
    print("right-click menu and desktop shortcut removed")


def pick_files() -> list[str]:
    """Standard Open dialog, multi-select."""
    import tkinter
    from tkinter import filedialog
    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    names = filedialog.askopenfilenames(
        parent=root, title="Select AnyDesk recordings to convert",
        filetypes=[("AnyDesk recordings", "*.anydesk"), ("All files", "*.*")])
    root.destroy()
    return [os.path.normpath(n) for n in names]


def wait_for_turn(on_wait=None) -> None:
    """Only one conversion can drive AnyDesk at a time; later launches wait here."""
    global _mutex
    k32 = ctypes.WinDLL("kernel32", use_last_error=True, winmode=0x800)
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    _mutex = k32.CreateMutexW(None, False, _MUTEX_NAME)
    if k32.WaitForSingleObject(_mutex, 0) == _WAIT_TIMEOUT:
        print("another conversion is running - waiting for it to finish...", flush=True)
        if on_wait:
            on_wait()
        k32.WaitForSingleObject(_mutex, 0xFFFFFFFF)
    # released by the OS when this process exits


def pause_before_exit(ok: bool) -> None:
    """Keep the console readable when launched from Explorer."""
    try:
        if ok:
            print("\nthis window closes in 10 seconds")
            import time
            time.sleep(10)
        else:
            input("\nsomething failed - press Enter to close")
    except (KeyboardInterrupt, EOFError):
        pass
