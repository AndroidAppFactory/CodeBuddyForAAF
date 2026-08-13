"""adb-replay CLI 工具函数"""

from __future__ import annotations

import json
import socket
from datetime import datetime
from pathlib import Path

from adb_core.config import REPLAY_DIR, TASK_RECORD_DIR


def ensure_replay_dir() -> Path:
    """确保存储目录存在"""
    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    return REPLAY_DIR


def generate_dirname(name: str | None = None) -> str:
    """生成带时间戳的目录名"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if name:
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        return f"{ts}_{safe_name}"
    return ts


def list_recordings() -> list[dict]:
    """列出所有录制目录"""
    recordings = []
    skip = {"flows", "flow_runs", "tasks", "task_groups", "group_runs",
            "groups", "favorites", "screenshots"}

    def _scan(dir_path: Path):
        if not dir_path.exists():
            return
        for d in sorted(dir_path.iterdir(), reverse=True):
            if not d.is_dir():
                continue
            if d.name in skip:
                continue
            data_file = d / "data.json"
            if not data_file.exists():
                continue
            try:
                data = json.loads(data_file.read_text(encoding="utf-8"))
                recordings.append({
                    "path": str(d),
                    "name": d.name,
                    "device": data.get("device", "unknown"),
                    "event_count": len(data.get("events", [])),
                    "resolution": data.get("resolution", [0, 0]),
                })
            except (json.JSONDecodeError, OSError):
                recordings.append({"path": str(d), "name": d.name, "device": "?", "event_count": -1})

    _scan(TASK_RECORD_DIR)
    _scan(REPLAY_DIR)
    return recordings


def ensure_port_free(port: int) -> bool:
    """检查端口是否空闲"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False
