"""Windows 窗口信息 / 聚焦 — 基于 ctypes Win32 API

无需 pywin32 依赖，直接使用 user32 接口。
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

WM_CLOSE = 0x0010
SW_MAXIMIZE = 3
GW_OWNER = 4


def get_foreground_info() -> dict:
    """获取当前前台窗口信息。

    Returns:
        {"title": str, "pid": int, "process": str}
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"title": "", "pid": 0, "process": ""}

    length = user32.GetWindowTextLengthW(hwnd) + 1
    buf = ctypes.create_unicode_buffer(length)
    user32.GetWindowTextW(hwnd, buf, length)
    title = buf.value

    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    process = ""
    try:
        import psutil
        p = psutil.Process(pid.value)
        process = p.name()
    except Exception:
        process = ""

    return {"title": title, "pid": pid.value, "process": process}


# EnumWindows 回调原型
_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def find_window(title_substr: str):
    """按标题子串模糊匹配第一个可见顶层窗口句柄。"""
    results = []

    @_WNDENUMPROC
    def _callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd) + 1
        if length <= 1:
            return True
        buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buf, length)
        results.append((hwnd, buf.value))
        return True

    user32.EnumWindows(_callback, 0)

    sub = (title_substr or "").lower()
    for hwnd, title in results:
        if sub and sub in title.lower():
            return hwnd, title
    return None, None


def focus_window(title_substr: str) -> bool:
    """按标题子串聚焦窗口（best-effort，受 UAC 限制）。"""
    hwnd, title = find_window(title_substr)
    if not hwnd:
        print(f"    ⚠ 未找到匹配窗口: {title_substr}")
        return False
    user32.SetForegroundWindow(hwnd)
    time_sleep(0.3)
    return True


def close_foreground():
    """向当前前台窗口发送 WM_CLOSE（等价于 Alt+F4）。"""
    hwnd = user32.GetForegroundWindow()
    if hwnd:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        time_sleep(0.3)


def maximize_foreground():
    """最大化当前前台窗口。"""
    hwnd = user32.GetForegroundWindow()
    if hwnd:
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        time_sleep(0.3)


def resize_window(title_substr: str, width: int, height: int,
                  x: int | None = None, y: int | None = None) -> bool:
    """按标题子串找到窗口并调整大小和位置。"""
    hwnd, title = find_window(title_substr)
    if not hwnd:
        print(f"    ⚠ 未找到匹配窗口: {title_substr}")
        return False
    flags = 0  # SWP_NOSIZE | SWP_NOMOVE 默认都不设
    cx = width
    cy = height
    pos_x = x if x is not None else 0
    pos_y = y if y is not None else 0
    user32.SetWindowPos(hwnd, 0, pos_x, pos_y, cx, cy, 0)
    time_sleep(0.2)
    return True


def time_sleep(sec: float):
    import time
    time.sleep(sec)


def find_all_windows_by_dir(exe_dir: str) -> list[tuple]:
    """按 exe 目录查找所有可见窗口的 (hwnd, title, pid, process_name)。

    遍历所有可见顶层窗口，返回 exe 路径在指定目录下的所有窗口。
    """
    from pathlib import Path as _Path
    target_dir = str(_Path(exe_dir)).lower()
    results: list[tuple] = []

    @_WNDENUMPROC
    def _callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd) + 1
        if length <= 1:
            return True
        buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buf, length)
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        results.append((hwnd, buf.value, pid.value))
        return True

    user32.EnumWindows(_callback, 0)

    windows = []
    try:
        import psutil
        for hwnd, title, pid in results:
            try:
                p = psutil.Process(pid)
                exe_path = p.exe()
                if exe_path and str(_Path(exe_path).parent).lower() == target_dir:
                    windows.append((hwnd, title, pid, p.name()))
            except Exception:
                continue
    except ImportError:
        pass
    return windows


def find_window_by_process(proc_name: str):
    """按进程名（如 'YOUKU.exe'）查找主窗口句柄。

    遍历所有可见顶层窗口，找到匹配进程名的第一个。
    返回 (hwnd, title) 或 (None, None)。
    """
    results = []

    @_WNDENUMPROC
    def _callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        # 跳过无标题窗口
        length = user32.GetWindowTextLengthW(hwnd) + 1
        if length <= 1:
            return True
        buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buf, length)
        # 获取进程 ID
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        results.append((hwnd, buf.value, pid.value))
        return True

    user32.EnumWindows(_callback, 0)

    target = proc_name.lower()
    try:
        import psutil
        for hwnd, title, pid in results:
            try:
                p = psutil.Process(pid)
                if p.name().lower() == target:
                    return hwnd, title
            except Exception:
                continue
    except ImportError:
        pass
    return None, None


def get_window_rect(hwnd) -> tuple[int, int, int, int] | None:
    """获取窗口矩形 (left, top, right, bottom)，返回 None 表示失败。"""
    rect = wintypes.RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return (rect.left, rect.top, rect.right, rect.bottom)
    return None


def find_window_by_exe_dir(exe_dir) -> str | None:
    """通过 exe 所在目录查找拥有可见窗口的进程名。

    遍历所有可见顶层窗口，找到 exe 路径在指定目录下的进程。
    用于解决启动器 exe 和实际 UI 进程名不同的问题。

    Args:
        exe_dir: Path 对象，exe 所在目录

    Returns:
        进程名（如 'mgtv.exe'）或 None
    """
    from pathlib import Path
    target_dir = str(Path(exe_dir)).lower()

    results = []

    @_WNDENUMPROC
    def _callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd) + 1
        if length <= 1:
            return True
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        results.append(pid.value)
        return True

    user32.EnumWindows(_callback, 0)

    try:
        import psutil
        for pid in results:
            try:
                p = psutil.Process(pid)
                exe_path = p.exe()
                if exe_path and str(Path(exe_path).parent).lower() == target_dir:
                    return p.name()
            except Exception:
                continue
    except ImportError:
        pass
    return None
