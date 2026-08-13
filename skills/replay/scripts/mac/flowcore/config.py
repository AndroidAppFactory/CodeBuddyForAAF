"""mac-replay 路径常量

统一管理录制、回放、Flow、导出的文件路径。
"""

from pathlib import Path
import os

ZIXIEKIT_TMP = Path(os.environ.get("ZIXIEKIT_TMP", str(Path.home() / ".zixiekit")))

REPLAY_DIR = ZIXIEKIT_TMP / "skill" / "mac-replay"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent

RECORDINGS_DIR = REPLAY_DIR / "recordings"
# replay-core 共享资源
_REPLAY_CORE = Path(__file__).resolve().parents[3] / "scripts"
FLOWS_DIR = _REPLAY_CORE.parent / "flows"
HTML_DIR = _REPLAY_CORE.parent / "edit"
# 所有平台统一：~/.zixiekit/skill/replay/flow_runs/
FLOW_RUNS_DIR = ZIXIEKIT_TMP / "skill" / "replay" / "flow_runs"
FLOW_EXPORTS_DIR = REPLAY_DIR / "flow_exports"
