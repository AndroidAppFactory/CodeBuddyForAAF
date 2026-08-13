#!/usr/bin/env python3
"""ADB-Replay Flow 执行引擎

import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".zixiekit" / "scripts"))
from bootstrap import load_env  # noqa: E402

load_env()

每步可以是：
- event: 单个事件（tap/swipe/keyevent/text/adb/...）
- flow: 递归展开引用的 Flow
- pause: 断点等待
- adb_cmd: ADB shell 命令
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

from adb_core.config import SCRIPTS_DIR, FLOW_RUNS_DIR
from adb_core.flow import load_flow
from flow_report import generate_flow_report, _get_local_hostname, _format_started_at

# replay-core 路径注入
_replay_core = Path(__file__).resolve().parents[2] / "scripts"
if str(_replay_core) not in sys.path:
    sys.path.insert(0, str(_replay_core))
from core.flow import resolve_flow_steps as _core_resolve_flow_steps  # noqa: E402

from core.notify import notify_safe as _notify_safe, notify_image_safe as _notify_image_safe, snapshot_title as _snapshot_title_core  # noqa: E402


def _snapshot_title(flow_name: str, device_model: str, started_at: str, status: str = "") -> str:
    return _snapshot_title_core(flow_name, device=device_model, started_at=started_at, status=status, platform="ADB")


def _is_notify_suppressed() -> bool:
    """检查是否应跳过通知（mixed 模式或 --no-notify）"""
    return os.environ.get("REPLAY_MIXED_MODE") == "1" or os.environ.get("REPLAY_NO_NOTIFY") == "1"


def _apply_override(step: dict, res_key: str) -> dict:
    """若 step 有当前分辨率的 override 坐标，返回应用后的副本"""
    overrides = step.get("overrides", {})
    if res_key not in overrides:
        return step
    copy = dict(step)
    for k in ("x", "y", "x1", "y1", "x2", "y2"):
        if k in overrides[res_key]:
            copy[k] = overrides[res_key][k]
    return copy


def _step_to_event(step: dict) -> dict:
    """将 flow 步骤转为 player 可执行的 event 格式"""
    if step["type"] != "event":
        return {}
    ev = {"type": step["action"]}
    for k in ("x", "y", "x1", "y1", "x2", "y2", "duration_ms",
              "code", "content", "adb_action", "package",
              "ssid", "password", "delay_before_ms", "delay_after_ms"):
        if k in step:
            ev[k] = step[k]
    if "adb_action" in step:
        ev["action"] = step["adb_action"]
    return ev


def _desc(step: dict) -> str:
    """生成步骤的可读描述"""
    a = step.get("action", "?")
    if a == "tap":
        return f"tap ({step.get('x','?')},{step.get('y','?')})"
    if a == "swipe":
        return f"swipe ({step.get('x1','?')},{step.get('y1','?')})→({step.get('x2','?')},{step.get('y2','?')})"
    if a == "keyevent":
        code = step.get("code", "?")
        labels = {3: "Home", 4: "Back", 26: "Power", 84: "Search"}
        return f"keyevent {code}" + (f" ({labels[code]})" if code in labels else "")
    if a == "text":
        return f'input "{step.get("content","?")}"'
    if a == "adb":
        return f"adb {step.get('adb_action','?')} {step.get('package','')}"
    if a == "tips":
        return f'💬 "{step.get("content","?")}"'
    return a


def resolve_flow_steps(flow: dict) -> list[dict]:
    """统一使用 core.flow.resolve_flow_steps + 补 _sub_total（adb 报告用）"""
    steps = _core_resolve_flow_steps(flow)
    total = len(steps)
    for s in steps:
        s.setdefault("_sub_total", total)
    return steps


def run_flow(flow_name: str, device: Optional[str] = None,
             speed: float = 1.0, step_indices: list[int] | None = None,
             fail_fast: bool = False, rerun: bool = False) -> int:
    """运行 adb Flow（统一调用 core.runner + setup/executor/teardown hook）"""
    from core.runner import run_flow as core_run_flow

    # ── 环境预检：自动安装缺失依赖 ──
    import shutil, subprocess
    if shutil.which("adb") is None:
        print("❌ ADB 未安装，请安装 Android SDK", file=sys.stderr)
        return 1
    try:
        r = subprocess.run(
            ["adb", "shell", "pm", "path", "com.bihe0832.adb.input"],
            capture_output=True, text=True, timeout=10
        )
        if "package:" not in r.stdout:
            print("📦 ZINPUT 输入法未安装，自动安装中...")
            _install_zinput_auto()
        else:
            print("✅ ZINPUT 输入法已安装，跳过")
    except Exception:
        pass  # 设备未连接，setup_hook 会再报

    # ── setup_hook：设备发现 + 分辨率匹配 + 打印设备信息 ──
    def setup_hook(ctx):
        _self = Path(__file__).resolve().parent
        sys.path.insert(0, str(_self))
        _zk = os.environ.get("ZIXIEKIT_HOME")
        if _zk:
            sys.path.insert(0, str(Path(_zk) / "scripts"))
        import adb_tools

        adb = adb_tools.get_adb_cmd(device)
        device_info = adb_tools.get_device_basic_info(device)
        device_model = device_info["model"]
        dst_res = tuple(device_info["resolution"])
        if dst_res[0] == 0:
            raise RuntimeError("无法获取设备分辨率")

        # 分辨率 + DPI 匹配（D19：统一从 meta.profiles 取）
        density = device_info.get("density", 0)
        res_key = f"{dst_res[0]}x{dst_res[1]}@{density}" if density else f"{dst_res[0]}x{dst_res[1]}"
        flow = ctx.flow
        meta = flow.get("meta", {})
        profiles = meta.get("profiles", flow.get("profiles", {}))
        default_key = meta.get("default_profile", flow.get("default_profile", ""))
        matched_profile = profiles.get(res_key)
        has_exact_match = bool(matched_profile)

        if has_exact_match:
            src_res = tuple(matched_profile.get("resolution", dst_res))
        else:
            if not default_key:
                default_key = next(iter(profiles), "")
            if default_key and default_key in profiles:
                src_res = tuple(profiles[default_key].get("resolution", dst_res))
            else:
                src_res = dst_res

        # 打印 adb 专有设备信息
        if has_exact_match:
            print(f"   ✅ 匹配配置: {res_key} ({matched_profile.get('device', '')})")
        elif default_key and default_key in profiles:
            print(f"   录制设备: {profiles[default_key].get('device', '')} ({default_key})")
        print(f"   当前设备: {device_model} ({res_key})")
        if not has_exact_match and src_res != dst_res and profiles:
            print(f"   ⚠️  未匹配配置，将等比缩放坐标")

        # 存入 ctx.extra 供 step_executor 使用
        ctx.extra["adb"] = adb
        ctx.extra["device_model"] = device_model
        ctx.extra["device_info"] = device_info
        ctx.extra["src_res"] = src_res
        ctx.extra["dst_res"] = dst_res
        ctx.extra["res_key"] = res_key
        # 更新 ctx.device 为真实设备名
        ctx.device = device_model
        # 填充通知状态（供 notify_hook 使用）
        _notify_state["device_model"] = device_model
        _notify_state["started_at"] = ctx.started_at
        _notify_state["flow_name"] = ctx.flow.get("name", flow_name)

    # ── step_executor：只处理 event ──
    def step_executor(ctx, step: dict) -> tuple[bool, dict]:
        from adb_core.player import execute_event

        adb = ctx.extra["adb"]
        src_res = ctx.extra["src_res"]
        dst_res = ctx.extra["dst_res"]
        res_key = ctx.extra["res_key"]
        device_model = ctx.extra["device_model"]

        step = _apply_override(step, res_key)
        ev = _step_to_event(step)
        step_name = _desc(step)
        screenshot_dir = Path(step["_screenshot_dir"])

        captures = execute_event(ev, adb, src_res, dst_res, ctx.speed,
                                 screenshot_dir=screenshot_dir,
                                 event_index=0, total_events=1)

        # 写 data.json
        step_dir = Path(step["_step_dir"])
        step_data = {
            "device": device_model, "resolution": list(dst_res),
            "events": [dict(ev, screenshots=captures)] if captures else [ev],
        }
        with open(step_dir / "data.json", "w", encoding="utf-8") as f:
            json.dump(step_data, f, ensure_ascii=False, indent=2)

        # 关键事件截图
        actual_num = step.get("_actual_num", 0)
        step_dir_name = f"{actual_num:04d}"
        critical_screenshots = []
        if captures and step.get("is_critical"):
            for phase in ("before", "after"):
                mtype = captures.get(f"{phase}_type")
                if mtype:
                    ext = "mp4" if mtype == "video" else "png"
                    slot = "0_before" if phase == "before" else "1_after"
                    critical_screenshots.append(f"{step_dir_name}/screenshots/event_000_{slot}.{ext}")

        return True, {"name": step_name, "critical_screenshots": critical_screenshots}

    # ── notify_hook ──
    # 用闭包变量存设备信息（setup_hook 会填充）
    _notify_state = {"device_model": "", "started_at": ""}

    def notify_hook(title: str, message: str, level: str) -> None:
        # 用 adb 完整格式覆盖 core 的简化标题
        device_model = _notify_state.get("device_model", "?")
        started_at = _notify_state.get("started_at", "")
        fid = flow_name

        if "开始" in title:
            status = "开始"
        elif "中断" in title or "⏹" in title:
            status = "中断"
        elif "失败" in title or "⚠️" in title:
            status = "失败"
        elif "结束" in title or "✅" in title:
            status = "结束"
        else:
            status = ""

        full_title = _snapshot_title(_notify_state.get("flow_name", flow_name), device_model, started_at, status)
        full_msg = f"{message}\nzk replay adb flow run {fid}"
        _notify_safe(full_title, full_msg, level)

    # ── report_hook ──
    def report_hook(run_dir: Path, summary: dict) -> Optional[Path]:
        report_file = generate_flow_report(run_dir, summary)
        from flow_report import generate_critical_snapshot
        device_model = _notify_state.get("device_model", "")
        snapshot_file = generate_critical_snapshot(run_dir, summary, device_label=device_model)
        if snapshot_file and not _is_notify_suppressed():
            _notify_image_safe(snapshot_file)
        return report_file

    # ── tips_hook ──
    def tips_hook(fl: dict, run_dir: Path) -> None:
        from core.cli import tips_after_flow_run, generate_merge_video_script

        # 收集所有步骤的截屏/录屏，生成 merge_video.sh
        media_items = []
        for step_dir in sorted(run_dir.glob("[0-9][0-9][0-9][0-9]")):
            data_file = step_dir / "data.json"
            if not data_file.exists():
                continue
            step_data = json.loads(data_file.read_text(encoding="utf-8"))
            for ev in step_data.get("events", []):
                ss = ev.get("screenshots", {})
                if not ss:
                    continue
                screenshots_dir = step_dir / "screenshots"
                for phase, slot in (("before", "0_before"), ("after", "1_after")):
                    mtype = ss.get(f"{phase}_type")
                    if not mtype:
                        continue
                    ext = "mp4" if mtype == "video" else "png"
                    full_path = str(screenshots_dir / f"event_000_{slot}.{ext}")
                    media_items.append((full_path, mtype == "video"))
        merge_script = generate_merge_video_script(str(run_dir), media_items) if media_items else ""

        script = str(SCRIPTS_DIR / "adb_replay.py")
        fid = fl.get("id", "") if fl.get("id") else flow_name
        report_file = run_dir / "report.html"
        tips_after_flow_run(
            "adb", fid, script_path=script,
            report_path=str(report_file) if report_file.exists() else "",
            merge_script=merge_script,
        )

    # ── 调用 core.runner（一行）──
    summary = core_run_flow(
        flow_name,
        step_executor,
        speed=speed,
        step_indices=step_indices,
        fail_fast=fail_fast,
        rerun=rerun,
        device="adb",
        setup_hook=setup_hook,
        notify_hook=notify_hook,
        report_hook=report_hook,
        tips_hook=tips_hook,
    )

    return summary.get("exit_code", 1)


def list_flow_runs(flow_name: Optional[str] = None) -> list[dict]:
    if not FLOW_RUNS_DIR.exists():
        return []
    # 解析为 flow_id 做精确匹配
    from adb_core.flow import load_flow
    resolved_id = ""
    if flow_name:
        f = load_flow(flow_name)
        if f:
            resolved_id = f.get("id", "")
    runs = []
    for d in sorted(FLOW_RUNS_DIR.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        sf = d / "summary.json"
        if not sf.exists():
            continue
        try:
            with open(sf, "r", encoding="utf-8") as fp:
                s = json.load(fp)
            if resolved_id and s.get("flow_id") != resolved_id:
                continue
            runs.append({"dir": str(d), "name": d.name, "flow": s.get("flow", "?"),
                         "started_at": s.get("started_at", "?"), "total_steps": s.get("total_steps", 0),
                         "failed_steps": s.get("failed_steps", 0)})
        except (json.JSONDecodeError, OSError):
            continue


def _install_zinput_auto():
    """自动下载并安装 ZINPUT 输入法到设备（无 user prompt）"""
    import urllib.request
    import subprocess
    from pathlib import Path

    ZINPUT_URL = "https://android.bihe0832.com/app/release/ZINPUT_official.apk"
    cache_dir = Path.home() / ".zixiekit" / "cache" / "zinput"
    cache_dir.mkdir(parents=True, exist_ok=True)
    apk_path = cache_dir / "ZINPUT_official.apk"

    # 下载
    if not apk_path.exists():
        print(f"  📥 下载 ZINPUT APK...")
        try:
            urllib.request.urlretrieve(ZINPUT_URL, str(apk_path))
        except Exception as e:
            print(f"  ❌ 下载失败: {e}", file=sys.stderr)
            return
    else:
        print(f"  📦 ZINPUT APK 已缓存")

    # 安装
    print(f"  📲 安装到设备...")
    try:
        subprocess.run(
            ["adb", "install", "-r", str(apk_path)],
            check=True, capture_output=True, timeout=60
        )
        print(f"  ✅ ZINPUT 安装完成")
    except Exception as e:
        print(f"  ❌ 安装失败: {e}", file=sys.stderr)
    return runs
