"""web-replay 公共常量和配置"""

from __future__ import annotations

import os
from pathlib import Path

ZIXIEKIT_TMP = Path(os.environ.get("ZIXIEKIT_TMP", str(Path.home() / ".zixiekit")))
REPLAY_DIR = ZIXIEKIT_TMP / "skill" / "web-replay"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent

# 录制产物目录
RECORDINGS_DIR = REPLAY_DIR / "recordings"

# replay-core 共享资源
_REPLAY_CORE = Path(__file__).resolve().parents[3] / "scripts"
FLOWS_DIR = _REPLAY_CORE.parent / "flows"
HTML_DIR = _REPLAY_CORE.parent / "edit"
# 所有平台统一：~/.zixiekit/skill/replay/flow_runs/
FLOW_RUNS_DIR = ZIXIEKIT_TMP / "skill" / "replay" / "flow_runs"
FLOW_EXPORTS_DIR = REPLAY_DIR / "flow_exports"
