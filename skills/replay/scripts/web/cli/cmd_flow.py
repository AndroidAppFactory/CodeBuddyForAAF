"""web-replay CLI：Flow 子命令（D21 统一入口）"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# 注入 notify 模块路径（~/.zixiekit/scripts/）
sys.path.insert(0, str(Path.home() / ".zixiekit" / "scripts"))
_zk_home = os.environ.get("ZIXIEKIT_HOME")
if _zk_home:
    sys.path.insert(0, str(Path(_zk_home) / "scripts"))

# replay-core 路径
_replay_core = Path(__file__).resolve().parents[3] / "scripts"
if str(_replay_core) not in sys.path:
    sys.path.insert(0, str(_replay_core))
from core.notify import notify_safe as _notify_safe, notify_image_safe as _notify_image_safe  # noqa: E402


def _run_flow_impl(flow: dict) -> int:
    """运行 Flow：展开为事件级步骤列表，整个运行期间共享同一浏览器"""
    from web_player import run_flow_events
    from flowcore.flow import resolve_flow_steps
    from core.config import FLOW_RUNS_DIR
    from datetime import datetime
    from flow_report import (generate_flow_report, generate_critical_snapshot,
                             _get_local_hostname, _format_started_at)

    try:
        steps = resolve_flow_steps(flow)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    if not steps:
        print(f"❌ Flow「{flow['name']}」没有可执行步骤", file=sys.stderr)
        return 1

    total = len(steps)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in flow["name"])
    FLOW_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = FLOW_RUNS_DIR / f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now().isoformat(timespec="seconds")
    print(f"\n{'='*50}")
    print(f"🚀 运行 Flow: {flow['name']}")
    if flow.get("description"):
        print(f"   {flow['description']}")
    print(f"   步骤数（展开后）: {total}")
    print(f"   产物目录: {run_dir}")
    print(f"{'='*50}\n")

    host = _get_local_hostname()
    ts = _format_started_at({"started_at": started_at})
    fid = (flow.get("id", "") or "")[:4] or flow["name"]
    _skip_notify = os.environ.get("REPLAY_MIXED_MODE") == "1" or os.environ.get("REPLAY_NO_NOTIFY") == "1"
    if not _skip_notify:
        _notify_safe(f"🚀 【开始 - WEB】{flow['name']} · 执行时间：{ts}    执行机器：{host}",
                     f"共 {total} 步\nzk replay web flow run {fid}")

    step_results = run_flow_events(steps, run_dir, headless=False, timeout=30, speed=1.0)

    finished_at = datetime.now().isoformat(timespec="seconds")
    passed = sum(1 for r in step_results if r.get("status") == "success")
    failed = sum(1 for r in step_results if r.get("status") == "failed")

    summary = {
        "flow": flow["name"], "flow_id": flow.get("id", ""),
        "description": flow.get("description", ""),
        "started_at": started_at, "finished_at": finished_at,
        "total_steps": total, "completed_steps": passed, "failed_steps": failed,
        "steps": step_results,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report_file = generate_flow_report(run_dir, summary)
    snapshot_file = generate_critical_snapshot(run_dir, summary, max_cols=2)

    print(f"\n{'='*50}")
    print(f"{'✅' if failed == 0 else '⚠️'} 完成: {passed}/{total} 成功")
    print(f"   报告: {report_file}")
    if snapshot_file:
        print(f"   关键截图: {snapshot_file}")
    print(f"{'='*50}")

    from core.cli import tips_after_flow_run
    tips_after_flow_run("web", fid, script_path="")

    status = "完成" if failed == 0 else "失败"
    if not _skip_notify:
        _notify_safe(
            f"{'✅' if failed == 0 else '⚠️'} 【{status} - WEB】{flow['name']} · 执行时间：{ts}    执行机器：{host}",
            f"{passed}/{total} 成功\n报告: {report_file}\nzk replay web flow run {fid}",
            level="info" if failed == 0 else "warning",
        )
        _notify_image_safe(snapshot_file)

    return 0 if failed == 0 else 1


# ── D21 统一入口（由 cli/main.py 调用）──


def cmd_flow_run(args) -> int:
    """flow run <id>"""
    if getattr(args, "no_notify", False):
        os.environ["REPLAY_NO_NOTIFY"] = "1"
    from flowcore.flow import load_flow
    flow = load_flow(args.id)
    if not flow:
        from core.cli import log_error
        log_error(f"Flow「{args.id}」不存在")
        return 1
    return _run_flow_impl(flow)


def cmd_flow_report(args) -> int:
    """flow report <id>"""
    from flowcore.flow import load_flow
    from core.config import FLOW_RUNS_DIR
    from flow_report import generate_flow_report, generate_critical_snapshot

    flow = load_flow(args.id)
    if not flow:
        from core.cli import log_error
        log_error(f"Flow「{args.id}」不存在")
        return 1

    if not FLOW_RUNS_DIR.exists():
        from core.cli import log_error
        log_error("没有运行记录")
        return 1
    fid = flow.get("id", "")
    runs = sorted([d for d in FLOW_RUNS_DIR.iterdir() if d.is_dir() and fid in d.name], reverse=True)
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
    from flow_report import generate_flow_report, generate_critical_snapshot

    run_dir = Path(args.run_dir).resolve()
    sf = run_dir / "summary.json"
    if not sf.exists():
        from core.cli import log_error
        log_error(f"{run_dir} 中没有 summary.json")
        return 1
    summary = json.loads(sf.read_text(encoding="utf-8"))
    report = generate_flow_report(run_dir, summary)
    snapshot = generate_critical_snapshot(run_dir, summary)
    from core.cli import log_success
    log_success(f"报告已生成: {report}")
    if snapshot:
        print(f"   🖼  关键截图: {snapshot}")
    return 0
