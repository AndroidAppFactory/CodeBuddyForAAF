"""win-replay 路径常量

统一管理录制、回放、Flow、导出的文件路径。
"""

from __future__ import annotations

import os
from pathlib import Path

ZIXIEKIT_TMP = Path(os.environ.get("ZIXIEKIT_TMP", str(Path.home() / ".zixiekit")))

REPLAY_DIR = ZIXIEKIT_TMP / "skill" / "win-replay"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent

RECORDINGS_DIR = REPLAY_DIR / "recordings"
# Flow 编排：全局统一仓库（replay/flows/）
_REPLAY_CORE = Path(__file__).resolve().parents[3] / "scripts"
FLOWS_DIR = _REPLAY_CORE.parent / "flows"
# 所有平台统一：~/.zixiekit/skill/replay/
FLOW_RUNS_DIR = ZIXIEKIT_TMP / "skill" / "replay" / "flow_runs"
FLOW_EXPORTS_DIR = ZIXIEKIT_TMP / "skill" / "replay" / "flow_exports"
