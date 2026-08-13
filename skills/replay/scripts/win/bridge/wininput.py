"""Windows 输入封装 — 基于 pynput Controller

对 win_player 暴露与平台无关的鼠标/键盘操作接口。
坐标使用 Windows 虚拟屏幕坐标（与 pynput 监听器一致）。
"""

from __future__ import annotations

import time

from pynput import keyboard as p_keyboard
from pynput import mouse as p_mouse
from pynput.keyboard import Key, KeyCode

# 修饰键名称 → pynput Key
_MODIFIER_MAP = {
    "ctrl": Key.ctrl,
    "control": Key.ctrl,
    "alt": Key.alt,
    "shift": Key.shift,
    "win": Key.cmd,
    "cmd": Key.cmd,
    "super": Key.cmd,
}

# 特殊按键名称 → pynput Key（getattr 兼容不同平台/版本的 pynput API）
_SPECIAL_MAP = {}
for _name, _attr in {
    "enter": "enter", "return": "enter", "tab": "tab", "space": "space",
    "backspace": "backspace", "delete": "delete", "esc": "esc", "escape": "esc",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "home": "home", "end": "end", "pageup": "page_up", "pagedown": "page_down",
    "insert": "insert",
    "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
    "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
    "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
}.items():
    _key = getattr(Key, _attr, None)
    if _key is not None:
        _SPECIAL_MAP[_name] = _key


def _resolve_key(name: str):
    """将按键名称解析为 pynput Key / KeyCode 对象。"""
    n = (name or "").lower()
    if n in _MODIFIER_MAP:
        return _MODIFIER_MAP[n]
    if n in _SPECIAL_MAP:
        return _SPECIAL_MAP[n]
    if len(n) == 1:
        return KeyCode.from_char(n)
    # 未知按键：尝试按单字符处理
    try:
        return KeyCode.from_char(name)
    except Exception:
        return None


_mouse = p_mouse.Controller()
_kb = p_keyboard.Controller()


def move_to(x: float, y: float):
    _mouse.position = (int(x), int(y))


def click(x: float, y: float, button: str = "left"):
    btn = p_mouse.Button.right if button == "right" else p_mouse.Button.left
    move_to(x, y)
    time.sleep(0.02)
    _mouse.click(btn)


def double_click(x: float, y: float):
    move_to(x, y)
    time.sleep(0.02)
    _mouse.click(p_mouse.Button.left)
    time.sleep(0.06)
    _mouse.click(p_mouse.Button.left)


def right_click(x: float, y: float):
    click(x, y, button="right")


def drag(x1: float, y1: float, x2: float, y2: float, duration_ms: int = 500):
    steps = max(2, duration_ms // 20)
    move_to(x1, y1)
    time.sleep(0.05)
    _mouse.press(p_mouse.Button.left)
    for step in range(1, steps + 1):
        t = step / steps
        cx = x1 + (x2 - x1) * t
        cy = y1 + (y2 - y1) * t
        _mouse.move(int(cx), int(cy))
        time.sleep(0.02)
    _mouse.release(p_mouse.Button.left)


def hover(x: float, y: float, duration_ms: int = 500):
    move_to(x, y)
    if duration_ms > 0:
        time.sleep(duration_ms / 1000.0)


def scroll(x: float, y: float, dx: int = 0, dy: int = 0):
    """滚动。pynput 语义：dy>0 向上，dx>0 向右。"""
    move_to(x, y)
    time.sleep(0.02)
    _mouse.scroll(int(dx), int(dy))


def type_text(text: str):
    """输入文本（剪贴板 + Ctrl+V，支持 Unicode / 中文）。

    pynput Controller.type() 在 Windows 上逐字符发送键盘事件，
    不经过输入法，中文等 Unicode 字符会被直接丢弃。
    改为复制到剪贴板后自动粘贴。
    """
    if not text:
        return
    import pyperclip
    pyperclip.copy(text)
    time.sleep(0.05)
    send_combo(["ctrl", "v"])


def send_combo(keys: list[str]):
    """发送组合键，如 ['ctrl', 'c']。"""
    pressed = []
    try:
        for k in keys:
            obj = _resolve_key(k)
            if obj is None:
                continue
            _kb.press(obj)
            pressed.append(obj)
            time.sleep(0.02)
    finally:
        for obj in reversed(pressed):
            _kb.release(obj)
            time.sleep(0.02)


def hold_key(name: str, down: bool):
    """单独按下/释放一个键（用于 keyboard 事件中已拆好的单键）。"""
    obj = _resolve_key(name)
    if obj is None:
        return
    if down:
        _kb.press(obj)
    else:
        _kb.release(obj)
