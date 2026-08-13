"""win-replay CLI：Flow 子命令（D21 统一入口）"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from flowcore.config import SCRIPTS_DIR, FLOW_RUNS_DIR

# 注入 replay-core 路径
_replay_core_dir = SCRIPTS_DIR.parent.parent / "scripts"
if _replay_core_dir.exists() and str(_replay_core_dir) not in sys.path:
    sys.path.insert(0, str(_replay_core_dir))


def _get_flow_module():
    import core.flow
    return core.flow


# ── D21 统一入口（由 cli/main.py 调用）──


def cmd_flow_run(args) -> int:
    """flow run <id>"""
    if getattr(args, "no_notify", False):
        os.environ["REPLAY_NO_NOTIFY"] = "1"
    flow_module = _get_flow_module()
    flow = flow_module.load_flow(args.id)
    if not flow:
        from core.cli import log_error
        log_error(f"Flow「{args.id}」不存在")
        return 1

    if not flow.get("steps"):
        from core.cli import log_error
        log_error(f"Flow「{flow['name']}」没有步骤")
        return 1

    from win_flow_runner import run_flow_by_name

    step_indices = None
    step = getattr(args, "step", None)
    if step:
        try:
            a, b = step.split("-")
            step_indices = list(range(int(a), int(b) + 1))
        except ValueError:
            print("❌ --step 格式应为 1-5")
            return 1

    speed = getattr(args, "speed", 1.0)
    fail_fast = getattr(args, "fail_fast", False)
    rerun = getattr(args, "rerun", False)

    run_dir, summary, report = run_flow_by_name(
        args.id,
        step_indices=step_indices,
        rerun=rerun,
        fail_fast=fail_fast,
        speed=speed,
    )

    fid = (flow.get("id", "") or "")[:4]
    from core.cli import tips_after_flow_run
    tips_after_flow_run("win", fid, script_path="", report_path=str(report) if report else "")
    return 0 if summary.get("failed_steps", 0) == 0 else 1


def cmd_flow_report(args) -> int:
    """flow report <id>"""
    from cli.flow_report import generate_flow_report, generate_critical_snapshot

    flow_module = _get_flow_module()
    flow = flow_module.load_flow(args.id)
    if not flow:
        from core.cli import log_error
        log_error(f"Flow「{args.id}」不存在")
        return 1

    fid = flow.get("id", "")
    runs = sorted([d for d in FLOW_RUNS_DIR.iterdir() if d.is_dir() and fid in d.name], reverse=True) if FLOW_RUNS_DIR.exists() else []
    if not runs:
        from core.cli import log_error
        log_error(f"Flow「{flow['name']}」没有运行记录")
        return 1
    run_dir = runs[0]
    sf = run_dir / "summary.json"
    if not sf.exists():
        from core.cli import log_error
        log_error("目录中没有 summary.json")
        return 1
    summary = json.loads(sf.read_text(encoding="utf-8"))
    report = generate_flow_report(run_dir, summary)
    snapshot = generate_critical_snapshot(run_dir, summary)
    from core.cli import log_success
    log_success(f"报告已生成: {report}")
    if snapshot:
        print(f"   🖼  关键截图: {snapshot}")
    return 0


def cmd_report_rerun(args) -> int:
    """report <run_dir>"""
    from cli.flow_report import generate_flow_report, generate_critical_snapshot

    run_dir = Path(args.run_dir).resolve()
    sf = run_dir / "summary.json"
    if not sf.exists():
        from core.cli import log_error
        log_error(f"{run_dir} 中没有 summary.json")
        return 1
    summary = json.loads(sf.read_text(encoding="utf-8"))
    report = generate_flow_report(run_dir, summary)
    from core.cli import log_success
    log_success(f"报告已生成: {report}")
    return 0
