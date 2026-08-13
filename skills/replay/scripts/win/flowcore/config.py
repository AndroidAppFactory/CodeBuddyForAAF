"""win-replay 路径常量（供 win_recorder / win_player / cli 使用）"""

from __future__ import annotations

import os
from pathlib import Path

ZIXIEKIT_TMP = Path(os.environ.get("ZIXIEKIT_TMP", str(Path.home() / ".zixiekit")))

REPLAY_DIR = ZIXIEKIT_TMP / "skill" / "win-replay"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent

RECORDINGS_DIR = REPLAY_DIR / "recordings"
# replay-core 共享资源
_REPLAY_CORE = Path(__file__).resolve().parents[3] / "scripts"
FLOWS_DIR = _REPLAY_CORE.parent / "flows"
HTML_DIR = _REPLAY_CORE.parent / "edit"
# 所有平台统一：~/.zixiekit/skill/replay/
FLOW_RUNS_DIR = ZIXIEKIT_TMP / "skill" / "replay" / "flow_runs"
FLOW_EXPORTS_DIR = ZIXIEKIT_TMP / "skill" / "replay" / "flow_exports"

__all__ = [
    "ZIXIEKIT_TMP",
    "REPLAY_DIR",
    "SCRIPTS_DIR",
    "RECORDINGS_DIR",
    "FLOWS_DIR",
    "FLOW_RUNS_DIR",
    "FLOW_EXPORTS_DIR",
]
