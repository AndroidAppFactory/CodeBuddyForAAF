#!/usr/bin/env python3
"""macOS 桌面操作录制引擎

通过 CGEventTap 捕获键盘/鼠标事件，状态机推断高层语义事件（click/type/scroll/drag/...），
坐标定位，同步截图，输出 events.json + raw.log。
"""

from __future__ import annotations

import atexit
import json
import queue
import time
import sys
from datetime import datetime
from pathlib import Path
from threading import Event

# 将 scripts/ 目录加入 import 路径
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from bridge import cgevent, screenshot
from bridge.permission import (
    check_accessibility_permission,
    prompt_accessibility_permission,
)
from flowcore.config import RECORDINGS_DIR

# 拖拽触发的最小像素移动
DRAG_THRESHOLD_PX = 5.0
# 双击最大间隔（秒）
DOUBLE_CLICK_INTERVAL = 0.3


class MacRecorder:
    """macOS 桌面操作录制器。"""

    def __init__(self):
        self._stop_event = Event()
        self._events = []  # 语义事件列表
        self._raw_buffer = []  # 原始事件缓冲（延迟写盘）
        self._raw_log = None  # raw.log 文件句柄
        self._output_dir = None
        self._screenshots_dir = None

        # 状态机状态
        self._mouse_down = False
        self._mouse_down_pos = (0.0, 0.0)
        self._mouse_down_time = 0.0
        self._last_click_time = 0.0
        self._last_event_time = 0.0
        self._key_buffer = []  # 文本输入缓冲

        # 截图异步队列 — CGEventTap 回调必须轻量，截图 I/O 绝不能在回调线程同步执行
        # （否则回调超时会被 macOS 自动禁用/降级 tap，导致事件丢失/错乱，如单击误判为右击、幽灵滚动）
        self._screenshot_queue = queue.Queue()
        self._screenshot_thread = None

    def record(self, name: str = None) -> Path:
        """开始录制。

        Args:
            name: 录制名称，默认使用时间戳

        Returns:
            录制输出目录路径
        """
        if not check_accessibility_permission():
            prompt_accessibility_permission()
            sys.exit(1)
        print(f"辅助功能权限: ✓")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if name is None:
            name = timestamp
        self._output_dir = RECORDINGS_DIR / name
        self._screenshots_dir = self._output_dir / "screenshots"
        self._screenshots_dir.mkdir(parents=True, exist_ok=True)

        # 打开 raw.log
        raw_log_path = self._output_dir / "raw.log"
        self._raw_log = open(str(raw_log_path), "w", encoding="utf-8")
        atexit.register(self._cleanup)

        print(f"开始录制 → {self._output_dir}")
        print("按 Esc 停止录制...")

        # 启动截图工作线程（异步处理，避免阻塞 CGEventTap 回调）
        import threading
        self._screenshot_thread = threading.Thread(
            target=self._screenshot_worker, daemon=True
        )
        self._screenshot_thread.start()

        # 创建 CGEventTap
        tap = cgevent.create_event_tap(self._on_event)
        if tap is None:
            print("无法创建 CGEventTap，请检查辅助功能权限。")
            sys.exit(1)

        try:
            # 在独立线程中运行 run loop
            import threading
            loop_thread = threading.Thread(
                target=cgevent.run_event_loop, args=(tap, 0.0), daemon=True
            )
            loop_thread.start()

            # 主线程等待 Esc 按键
            self._wait_for_stop()
        finally:
            self._stop_recording()

        # 保存 events.json
        self._save_events(name)

        events_path = self._output_dir / "events.json"
        work_dir = self._output_dir
        print(f"录制完成，共 {len(self._events)} 个事件")
        print(f" 产物: {events_path}")
        print(f"\n💡 后续命令:")
        print(f"  ▶️  回放:   python3 scripts/cli/main.py play {events_path}")
        print(f"  ✏️  编辑:   python3 scripts/cli/main.py edit {work_dir}")
        print(f"  📊 导出报告: python3 scripts/cli/main.py export {work_dir}")

        # 自动生成报告
        try:
            from mac_report import generate_report
            report_path = generate_report(work_dir, work_dir)
            print(f"\n📊 报告已自动生成: {report_path}")
        except Exception:
            pass
        return self._output_dir

    def _wait_for_stop(self):
        """等待停止信号（Esc 或 Ctrl+C）。"""
        try:
            while not self._stop_event.is_set():
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n收到 Ctrl+C，停止录制...")
            self._stop_event.set()

    def _on_event(self, proxy, event_type, event, refcon):
        """CGEventTap 回调（保持轻量，不阻塞）。"""
        now = time.time()
        loc = cgevent.get_event_location(event)
        type_name = cgevent.get_event_type_name(event)

        # 缓冲原始事件（延迟写盘）
        if self._raw_log is not None:
            raw_entry = {
                "t": now, "type": type_name,
                "loc": [int(loc[0]), int(loc[1])],
                "flags": cgevent.get_event_flags(event),
            }
            if "Key" in type_name:
                raw_entry["keyCode"] = cgevent.get_key_code(event)
            if "Mouse" in type_name and "Moved" not in type_name:
                raw_entry["button"] = cgevent.get_mouse_button(event)
            if "Scroll" in type_name:
                raw_entry["delta"] = list(cgevent.get_scroll_delta(event))
            self._raw_buffer.append(raw_entry)

        # 状态机
        if type_name in ("LMouseDown", "RMouseDown"):
            self._mouse_down = True
            self._mouse_down_pos = loc
            self._mouse_down_time = now

        elif type_name in ("LMouseUp", "RMouseUp"):
            if not self._mouse_down:
                return event

            self._mouse_down = False
            dx = loc[0] - self._mouse_down_pos[0]
            dy = loc[1] - self._mouse_down_pos[1]
            dist = (dx**2 + dy**2) ** 0.5

            if dist > DRAG_THRESHOLD_PX:
                # drag
                self._add_event("drag", {
                    "x1": int(self._mouse_down_pos[0]),
                    "y1": int(self._mouse_down_pos[1]),
                    "x2": int(loc[0]),
                    "y2": int(loc[1]),
                    "duration_ms": int((now - self._mouse_down_time) * 1000),
                }, now)
            elif type_name == "LMouseUp":
                # click
                dbl = (now - self._last_click_time) < DOUBLE_CLICK_INTERVAL
                if dbl:
                    self._events.pop()  # 移除上一个 click
                    self._add_event("dblclick", {"x": int(loc[0]), "y": int(loc[1])}, now)
                else:
                    self._add_event("click", {"x": int(loc[0]), "y": int(loc[1])}, now)
                self._last_click_time = now
            elif type_name == "RMouseUp":
                self._add_event("rightclick", {"x": int(loc[0]), "y": int(loc[1])}, now)

        elif type_name == "ScrollWheel":
            dx, dy = cgevent.get_scroll_delta(event)
            self._add_event("scroll", {
                "x": int(loc[0]), "y": int(loc[1]),
                "delta_x": int(dx), "delta_y": int(dy),
            }, now)

        elif type_name == "KeyDown":
            key_code = cgevent.get_key_code(event)
            flags = cgevent.get_event_flags(event)

            # Esc 键 → 停止录制
            if key_code == 53:
                print("\n检测到 Esc，停止录制...")
                self._stop_event.set()
                cgevent.stop_event_loop()
                return event

            self._key_buffer.append({"keyCode": key_code, "flags": flags})

        elif type_name == "KeyUp":
            pass  # 在 KeyDown 时已处理

        self._last_event_time = now
        return event

    def _add_event(self, event_type: str, extra: dict, timestamp: float):
        """添加语义事件并截图。使用屏幕绝对坐标。"""
        seq = len(self._events)
        x = extra.get("x", extra.get("x1", 0))
        y = extra.get("y", extra.get("y1", 0))

        # 计算 delay_before_ms
        delay_before_ms = 0
        if self._events:
            prev_ts = self._events[-1].get("timestamp", timestamp)
            delay_before_ms = int((timestamp - prev_ts) * 1000)

        event = {
            "type": event_type,
            "timestamp": timestamp,
            "delay_before_ms": max(0, delay_before_ms),
            "delay_after_ms": 0,
        }
        event.update(extra)
        self._events.append(event)

        # 实时输出
        print(f"  #{seq + 1} 🎯 {event_type} 屏幕({x},{y})")

        # 截图交给后台线程异步处理，回调线程不做任何阻塞 I/O
        self._screenshot_queue.put((seq, x, y))

    def _screenshot_worker(self):
        """后台线程：异步执行截图（before + after），不阻塞 CGEventTap 回调线程。"""
        while True:
            item = self._screenshot_queue.get()
            if item is None:
                self._screenshot_queue.task_done()
                break
            seq, x, y = item
            before_path = self._screenshots_dir / f"event_{seq:03d}_0_before.jpg"
            after_path = self._screenshots_dir / f"event_{seq:03d}_1_after.jpg"
            screenshot.capture_fullscreen(str(before_path), mark_pos=(x, y))
            screenshot.capture_fullscreen(str(after_path), mark_pos=(x, y))
            self._screenshot_queue.task_done()

    def _stop_recording(self):
        """停止录制：等待截图队列清空，再写入 raw.log。"""
        # 等待后台线程处理完所有已入队的截图任务
        if self._screenshot_thread is not None:
            self._screenshot_queue.put(None)
            self._screenshot_thread.join(timeout=30)
            self._screenshot_thread = None

        if self._raw_buffer and self._raw_log:
            for entry in self._raw_buffer:
                self._raw_log.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._raw_buffer = []
        if self._raw_log and not self._raw_log.closed:
            self._raw_log.close()

    def _save_events(self, name: str):
        """保存 events.json。"""
        output = {
            "name": name,
            "created_at": datetime.now().isoformat(),
            "platform": "mac",
            "events": self._events,
        }
        events_path = self._output_dir / "events.json"
        with open(str(events_path), "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    def _cleanup(self):
        """退出清理。"""
        self._stop_recording()
