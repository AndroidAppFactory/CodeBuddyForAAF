"""web-replay Flow 数据模型（代理层）

所有 Flow CRUD 和解析能力统一由 replay-core 提供。
本模块仅做 re-export，保持现有调用方 import 路径不变。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 确保 replay-core/scripts 在 sys.path 上
_replay_core = Path(__file__).resolve().parents[3] / "scripts"
if str(_replay_core) not in sys.path:
    sys.path.insert(0, str(_replay_core))

# ─── 从 core.flow 统一 re-export ──────────────────────
from core.flow import (  # noqa: E402, F401
    save_flow,
    load_flow,
    list_flows,
    delete_flow,
    resolve_flow_ref,
    get_flow_id_by_name,
    resolve_steps_recursive,
    resolve_flow_steps,
    is_atomic,
    flows_summary,
    invalidate_flows_cache,
    find_flows_by_name,
    ensure_dir,
)

# ─── web 兼容：collect_events（去掉 recording 分支后的版本）───
from core.schema import normalize_step  # noqa: E402


def collect_events(steps: list[dict], depth: int = 0) -> list[dict]:
    """递归展开 Flow 步骤为扁平的浏览器事件列表。

    flow 引用递归展开；recording 类型（已废弃，D16）仍尝试读取兼容旧测试；
    pause/shell_cmd 跳过。
    """
    if depth > 10:
        return []
    from flowcore.config import RECORDINGS_DIR

    events: list[dict] = []
    for s in steps:
        stype = s.get("type", "")
        if stype == "flow":
            ref = resolve_flow_ref(s)
            if ref:
                events.extend(collect_events(ref.get("steps", []), depth + 1))
        elif stype == "recording":
            # 废弃路径：现网无 recording 步骤，保留兼容旧测试
            rec_name = s.get("name", "")
            ef = RECORDINGS_DIR / rec_name / "events.json"
            if ef.exists():
                try:
                    data = json.loads(ef.read_text(encoding="utf-8"))
                    events.extend(normalize_step(e) for e in data.get("events", []))
                except (json.JSONDecodeError, OSError):
                    pass
        elif stype not in ("pause", "adb_cmd", "shell_cmd"):
            events.append(normalize_step(s))
    return events
