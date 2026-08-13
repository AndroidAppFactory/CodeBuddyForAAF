"""win-replay Flow 报告（代理层）

所有报告生成能力统一由 replay-core 提供。
本模块仅做 re-export，保持现有调用方 import 路径不变。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保 replay-core/scripts 在 sys.path 上
_replay_core = Path(__file__).resolve().parents[3] / "scripts"
if str(_replay_core) not in sys.path:
    sys.path.insert(0, str(_replay_core))

from core.report import (  # noqa: E402, F401
    generate_flow_report,
    generate_critical_snapshot,
    recover_missing_steps,
    _get_local_hostname,
    _format_started_at,
)
