#!/usr/bin/env python3
"""macOS 桌面操作回放引擎

读取 events.json，通过 CGEventPost 按坐标回放事件。
"""

from __future__ import annotations

import json
import time
import sys
from pathlib import Path

# 将 scripts/ 目录加入 import 路径
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

import Quartz
from bridge import cgevent
from bridge.screenshot import capture_fullscreen


class MacPlayer:
    """macOS 桌面操作回放器。"""

    def play(self, path: Path, delay_ms: int = 500):
        """回放 events.json。

        Args:
            path: events.json 文件路径
            delay_ms: 默认步骤间隔（毫秒）
        """
        with open(str(path), "r", encoding="utf-8") as f:
            data = json.load(f)

        events = data.get("events", [])
        print(f"回放: {data.get('name', 'unnamed')} ({len(events)} 个事件)")

        # 截图输出目录（同录制产物目录）
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

        work_dir = str(path.parent) if path.parent.name != "recordings" else str(path.parent)
        print(f"\n💡 后续命令:")
        print(f"  ✏️  编辑:   python3 scripts/cli/main.py edit {work_dir}")
        print(f"  📊 导出报告: python3 scripts/cli/main.py export {work_dir}")

        # 自动生成报告
        try:
            from mac_report import generate_report
            report_path = generate_report(path.parent, path.parent)
            print(f"\n📊 报告已自动生成: {report_path}")
        except Exception as e:
            print(f"\n⚠️  报告生成失败: {e}")

    def _execute_event(self, event: dict, seq: int):
        """执行单个事件（含 before/after 截图）。"""
        event_type = event.get("type", "")
        x, y = event.get("x", 0), event.get("y", 0)

        # before 截图
        before_path = self._ss_dir / f"event_{seq:03d}_0_before.jpg"
        capture_fullscreen(str(before_path), mark_pos=(x, y))

        # 执行事件
        self._do_execute(event_type, event, x, y)

        # after 截图
        after_path = self._ss_dir / f"event_{seq:03d}_1_after.jpg"
        capture_fullscreen(str(after_path), mark_pos=(x, y))

    def _do_execute(self, event_type: str, event: dict, x: float, y: float):
        """执行事件（不含截图，截图在 _execute_event 中处理）。"""

        if event_type == "click":
            cgevent.post_mouse_event(Quartz.kCGEventLeftMouseDown, x, y)
            time.sleep(0.05)
            cgevent.post_mouse_event(Quartz.kCGEventLeftMouseUp, x, y)

        elif event_type == "dblclick":
            for i in range(2):
                click_state = i + 1  # 1=第一次单击 2=第二次(触发双击)
                cgevent.post_mouse_event(Quartz.kCGEventLeftMouseDown, x, y, click_state=click_state)
                time.sleep(0.05)
                cgevent.post_mouse_event(Quartz.kCGEventLeftMouseUp, x, y, click_state=click_state)
                time.sleep(0.1)

        elif event_type == "rightclick":
            cgevent.post_mouse_event(Quartz.kCGEventRightMouseDown, x, y)
            time.sleep(0.05)
            cgevent.post_mouse_event(Quartz.kCGEventRightMouseUp, x, y)

        elif event_type == "type":
            content = event.get("content", "")
            for char in content:
                self._type_char(char)

        elif event_type == "keyboard":
            keys = event.get("keys", [])
            for key in keys:
                if key in ("cmd", "command"):
                    self._key_down(55, True)
                elif key in ("shift",):
                    self._key_down(56, True)
                elif key in ("ctrl", "control"):
                    self._key_down(59, True)
                elif key in ("option", "alt"):
                    self._key_down(58, True)
            time.sleep(0.1)
            for key in reversed(keys):
                if key in ("cmd", "command"):
                    self._key_down(55, False)
                elif key in ("shift",):
                    self._key_down(56, False)
                elif key in ("ctrl", "control"):
                    self._key_down(59, False)
                elif key in ("option", "alt"):
                    self._key_down(58, False)

        elif event_type == "scroll":
            dx = event.get("delta_x", 0)
            dy = event.get("delta_y", 0)
            cgevent.post_scroll_event(x, y, dx, dy)

        elif event_type == "drag":
            x1 = event.get("x1", x)
            y1 = event.get("y1", y)
            x2 = event.get("x2", event.get("x", 0))
            y2 = event.get("y2", event.get("y", 0))
            duration_ms = event.get("duration_ms", 500)
            steps = max(1, duration_ms // 20)
            cgevent.post_mouse_event(Quartz.kCGEventLeftMouseDown, x1, y1)
            for step in range(1, steps + 1):
                t = step / steps
                cx = x1 + (x2 - x1) * t
                cy = y1 + (y2 - y1) * t
                cgevent.post_mouse_event(Quartz.kCGEventMouseMoved, cx, cy)
                time.sleep(0.02)
            cgevent.post_mouse_event(Quartz.kCGEventLeftMouseUp, x2, y2)

        elif event_type == "hover":
            cgevent.post_mouse_event(Quartz.kCGEventMouseMoved, x, y)

        elif event_type == "action":
            self._execute_action(event)

        elif event_type == "wait":
            duration = event.get("duration_ms", 1000)
            time.sleep(duration / 1000.0)

        elif event_type == "tips":
            content = event.get("content", "按 Enter 继续...")
            input(f"\n  💬 {content}")

    def _type_char(self, char: str):
        """输入单个字符（Unicode）。"""
        ev = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
        Quartz.CGEventKeyboardSetUnicodeString(ev, len(char.encode("utf-16-le")) // 2, char)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(0.02)
        ev = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def _key_down(self, key_code: int, down: bool):
        """发送按键事件。"""
        ev = Quartz.CGEventCreateKeyboardEvent(None, key_code, down)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def _execute_action(self, event: dict):
        """执行 action 控制命令。

        支持的操作：
        - launch: 启动应用，可选全屏
        - activate: 激活应用（切到前台）
        - fullscreen: 切换全屏（Cmd+Ctrl+F）
        - quit: 退出应用（Cmd+Q）
        """
        action = event.get("action", "")
        bundle_id = event.get("bundle_id", "")

        if action == "launch":
            import Cocoa
            ws = Cocoa.NSWorkspace.sharedWorkspace()
            ws.launchApplicationWithBundleIdentifier_(bundle_id)
            delay = event.get("delay_after_ms", 2000)
            time.sleep(delay / 1000.0)
            if event.get("fullscreen"):
                self._send_app_shortcut(bundle_id, (3,), cmd=True, ctrl=True)

        elif action == "activate":
            import Cocoa
            apps = Cocoa.NSRunningApplication.runningApplicationsWithBundleIdentifier_(bundle_id)
            if apps and len(apps) > 0:
                apps[0].activateWithOptions_(Cocoa.NSApplicationActivateIgnoringOtherApps)
                time.sleep(0.5)

        elif action == "fullscreen":
            self._send_app_shortcut(bundle_id, (3,), cmd=True, ctrl=True)

        elif action == "quit":
            self._send_app_shortcut(bundle_id, (12,), cmd=True)

    def _send_app_shortcut(self, bundle_id: str, key_codes: tuple, cmd=False, ctrl=False, option=False, shift=False):
        """向指定应用发送快捷键。

        先激活目标应用，再发送按键。
        """
        # 激活
        if bundle_id:
            import Cocoa
            apps = Cocoa.NSRunningApplication.runningApplicationsWithBundleIdentifier_(bundle_id)
            if apps and len(apps) > 0:
                apps[0].activateWithOptions_(Cocoa.NSApplicationActivateIgnoringOtherApps)
                time.sleep(0.3)

        self._send_hotkey(key_codes, cmd=cmd, ctrl=ctrl, option=option, shift=shift)

    def _send_hotkey(self, key_codes: tuple, cmd=False, ctrl=False, option=False, shift=False):
        """发送组合键。

        Args:
            key_codes: 键码元组，如 (3,) 表示 F 键
            cmd, ctrl, option, shift: 修饰键
        """
        import Quartz as Qz

        flags = 0
        if cmd:
            flags |= Qz.kCGEventFlagMaskCommand
            cgevent.post_key_event(0x37, True)  # Cmd
        if ctrl:
            flags |= Qz.kCGEventFlagMaskControl
            cgevent.post_key_event(0x3B, True)  # Ctrl
        if option:
            flags |= Qz.kCGEventFlagMaskAlternate
            cgevent.post_key_event(0x3A, True)  # Option
        if shift:
            flags |= Qz.kCGEventFlagMaskShift
            cgevent.post_key_event(0x38, True)  # Shift

        time.sleep(0.05)

        for key_code in key_codes:
            ev_down = Qz.CGEventCreateKeyboardEvent(None, key_code, True)
            Qz.CGEventSetFlags(ev_down, flags)
            Qz.CGEventPost(Qz.kCGHIDEventTap, ev_down)
            time.sleep(0.05)

            ev_up = Qz.CGEventCreateKeyboardEvent(None, key_code, False)
            Qz.CGEventSetFlags(ev_up, flags)
            Qz.CGEventPost(Qz.kCGHIDEventTap, ev_up)
            time.sleep(0.05)

        # 释放修饰键
        if cmd:
            cgevent.post_key_event(0x37, False)
        if ctrl:
            cgevent.post_key_event(0x3B, False)
        if option:
            cgevent.post_key_event(0x3A, False)
        if shift:
            cgevent.post_key_event(0x38, False)

        time.sleep(0.3)
