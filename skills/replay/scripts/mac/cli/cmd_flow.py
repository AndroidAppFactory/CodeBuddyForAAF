"""Flow 子命令 — 复用 replay-core"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_core():
    """注入 replay-core 的 scripts 到 sys.path"""
    core_scripts = Path(__file__).resolve().parent.parent.parent / "scripts"
    if str(core_scripts) not in sys.path:
        sys.path.insert(0, str(core_scripts))


def cmd_flow_run(args):
    """运行 flow"""
    _ensure_core()
    from core.runner import run_flow
    from mac_core.config import PLATFORM
    from mac_core.flow_runner import setup_hook, step_executor

    flow_id = args.flow_id
    run_flow(flow_id, platform=PLATFORM, setup_hook=setup_hook, step_executor=step_executor)


def cmd_flow_report(args):
    """生成 flow 运行报告"""
    _ensure_core()
    from core.report import generate_flow_report

    flow_id = args.flow_id
    generate_flow_report(flow_id)
