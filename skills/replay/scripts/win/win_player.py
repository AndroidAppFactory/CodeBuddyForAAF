#!/usr/bin/env python3
"""Windows 桌面操作回放引擎

读取 events.json，通过 pynput Controller 按坐标回放事件。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# DPI 感知必须在 pynput 导入前设置
if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per Monitor
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# 将 scripts/ 目录加入 import 路径
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from bridge import wininput
from bridge.screenshot import capture_fullscreen
from bridge import window


class WinPlayer:
    """Windows 桌面操作回放器。"""

    def play(self, path: Path, delay_ms: int = 500):
        with open(str(path), "r", encoding="utf-8") as f:
            data = json.load(f)

        events = data.get("events", [])
        print(f"回放: {data.get('name', 'unnamed')} ({len(events)} 个事件)")

        self._output_dir = path.parent
        self._ss_dir = self._output_dir / "screenshots"
        self._ss_dir.mkdir(parents=True, exist_ok=True)

        for i, event in enumerate(events):
            event_type = event.get("type", "")
            delay_before = event.get("delay_before_ms", delay_ms)

            if delay_before > 0:
                time.sleep(delay_before / 1000.0)

            seq = i + 1
            print(f"  [{seq}/{len(events)}] {event_type}")

            try:
                self._execute_event(event, seq)
            except Exception as e:
                print(f"    ⚠ 执行失败: {e}")

        print(f"\n💡 后续命令:")
        print(f"  ✏️  编辑:   python scripts/cli/main.py edit {path.parent}")
        print(f"  📊 导出报告: python scripts/cli/main.py export {path.parent}")

        # 自动生成报告
        try:
            from win_report import generate_report
            report_path = generate_report(path.parent, path.parent)
            print(f"\n📊 报告已自动生成: {report_path}")
        except Exception as e:
            print(f"\n⚠️  报告生成失败: {e}")

    def _execute_event(self, event: dict, seq: int):
        event_type = event.get("type", "")
        x, y = event.get("x", 0), event.get("y", 0)

        before_path = self._ss_dir / f"event_{seq:03d}_0_before.jpg"
        capture_fullscreen(str(before_path), mark_pos=(x, y))

        self._do_execute(event_type, event, x, y)

        after_path = self._ss_dir / f"event_{seq:03d}_1_after.jpg"
        capture_fullscreen(str(after_path), mark_pos=(x, y))

    def _do_execute(self, event_type: str, event: dict, x: float, y: float):
        if event_type == "click":
            wininput.click(x, y, button="left")

        elif event_type == "dblclick":
            wininput.double_click(x, y)

        elif event_type == "rightclick":
            wininput.click(x, y, button="right")

        elif event_type == "type":
            content = event.get("content", "")
            wininput.type_text(content)

        elif event_type == "keyboard":
            keys = event.get("keys", [])
            wininput.send_combo(keys)

        elif event_type == "scroll":
            dx = event.get("delta_x", 0)
            dy = event.get("delta_y", 0)
            wininput.scroll(x, y, dx=dx, dy=dy)

        elif event_type == "drag":
            x1 = event.get("x1", x)
            y1 = event.get("y1", y)
            x2 = event.get("x2", event.get("x", 0))
            y2 = event.get("y2", event.get("y", 0))
            duration_ms = event.get("duration_ms", 500)
            wininput.drag(x1, y1, x2, y2, duration_ms=duration_ms)

        elif event_type == "hover":
            duration_ms = event.get("duration_ms", 500)
            wininput.hover(x, y, duration_ms=duration_ms)

        elif event_type == "wait":
            duration = event.get("duration_ms", 1000)
            time.sleep(duration / 1000.0)

        elif event_type == "tips":
            content = event.get("content", "按 Enter 继续...")
            input(f"\n  💬 {content}")

        elif event_type == "action":
            self._execute_action(event)

    def _execute_action(self, event: dict):
        """执行 Windows 应用动作。

        action:
        - launch:   启动 target（可执行路径或 PATH 命令）
        - activate: 按 target（窗口标题子串）聚焦窗口
        - close:    关闭当前前台窗口（Alt+F4）
        - maximize: 最大化当前前台窗口（Win+Up）
        """
        action = event.get("action", "")
        target = event.get("target", "")

        if action == "launch":
            import subprocess
            try:
                if target:
                    subprocess.Popen(target, shell=True)
                    delay = event.get("delay_after_ms", 2000)
                    time.sleep(delay / 1000.0)
            except Exception as e:
                print(f"    ⚠ 启动失败: {e}")

        elif action == "activate":
            if target:
                window.focus_window(target)

        elif action == "close":
            window.close_foreground()

        elif action == "maximize":
            window.maximize_foreground()

        elif action == "resize":
            w = int(event.get("width", 800))
            h = int(event.get("height", 600))
            window.resize_window(target, w, h)
