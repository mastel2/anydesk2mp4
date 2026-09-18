"""CPU and memory used by the processes that take part in a conversion (ctypes only)."""
from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True, winmode=0x800)
psapi = ctypes.WinDLL("psapi", use_last_error=True, winmode=0x800)

TH32CS_SNAPPROCESS = 0x2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
INVALID_HANDLE = ctypes.c_void_p(-1).value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                                       wintypes.DWORD]


def _processes() -> list[tuple[int, int, str]]:
    """(pid, parent pid, exe name) of every process."""
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE:
        return []
    out = []
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            out.append((entry.th32ProcessID, entry.th32ParentProcessID, entry.szExeFile.lower()))
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return out


def _usage(pid: int) -> tuple[float, int] | None:
    """(cpu seconds so far, working set bytes)."""
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        if not k32.GetProcessTimes(h, *[ctypes.byref(x) for x in times]):
            return None
        cpu = sum(((x.dwHighDateTime << 32) | x.dwLowDateTime) for x in times[2:]) / 1e7
        mem = PROCESS_MEMORY_COUNTERS()
        mem.cb = ctypes.sizeof(mem)
        psapi.GetProcessMemoryInfo(h, ctypes.byref(mem), mem.cb)
        return cpu, mem.WorkingSetSize
    finally:
        k32.CloseHandle(h)


class Meter:
    """Usage of this process, its descendants and every AnyDesk process, since the last read."""

    def __init__(self, extra_names: tuple[str, ...] = ("anydesk.exe",)):
        self.extra = extra_names
        self._last: dict[int, float] = {}
        self._at = time.time()

    def read(self) -> tuple[float, int]:
        """(% of the whole machine's CPU, bytes of RAM)."""
        procs = _processes()
        children: dict[int, list[int]] = {}
        for pid, parent, _ in procs:
            children.setdefault(parent, []).append(pid)
        wanted, stack = set(), [os.getpid()]
        while stack:
            pid = stack.pop()
            if pid not in wanted:
                wanted.add(pid)
                stack += children.get(pid, [])
        wanted |= {pid for pid, _, name in procs if name in self.extra}

        now, cpu_delta, ram, seen = time.time(), 0.0, 0, {}
        for pid in wanted:
            u = _usage(pid)
            if u is None:
                continue
            seen[pid] = u[0]
            if pid in self._last:
                cpu_delta += max(0.0, u[0] - self._last[pid])
            ram += u[1]
        elapsed = max(1e-3, now - self._at)
        self._last, self._at = seen, now
        return cpu_delta / elapsed * 100 / (os.cpu_count() or 1), ram
