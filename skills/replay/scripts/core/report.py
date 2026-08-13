#!/usr/bin/env python3
"""ADB-Replay Flow 瀑布流汇总报告生成器

从 group_report.py 适配，路径引用更新为 Flow 体系。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from core.config import FLOW_RUNS_DIR


def _step_desc_html(ev: dict, flow_name: str = "") -> str:
    """从事件数据生成可读的步骤描述（跨平台统一）

    同时兼容新契约 {type:"event", action:"tap"} 和旧格式 {type:"tap"}。
    """
    # 新契约：action 字段；旧格式：type 本身就是动作
    action = ev.get("action", ev.get("type", "?"))

    # ── 坐标类（adb/win/mac）──
    if action == "tap":
        return f"tap ({ev.get('x', '?')},{ev.get('y', '?')})"
    if action == "swipe":
        x1, y1 = ev.get("x1", ev.get("x", "?")), ev.get("y1", ev.get("y", "?"))
        x2, y2 = ev.get("x2", ev.get("to", {}).get("x", "?")), ev.get("y2", ev.get("to", {}).get("y", "?"))
        return f"swipe ({x1},{y1})→({x2},{y2})"
    if action == "keyevent":
        return f"keyevent {ev.get('code', '?')}"

    # ── 选择器类（web）──
    if action == "click":
        sel = ev.get("selectors", [])
        target = sel[0].get("value", "") if sel else ev.get("value", "")
        return f"点击 {target}" if target else "点击"
    if action == "navigate":
        url = ev.get("value", ev.get("url", "?"))
        # 截断长 URL
        if len(str(url)) > 40:
            url = str(url)[:37] + "..."
        return f"导航 {url}"
    if action in ("input", "text"):
        val = ev.get("value", ev.get("content", ""))
        if len(str(val)) > 20:
            val = str(val)[:17] + "..."
        return f"输入 \"{val}\""
    if action == "scroll":
        return "滚动"
    if action == "select":
        return f"选择 {ev.get('value', '?')}"

    # ── 系统命令类 ──
    if action == "adb":
        act = ev.get("adb_action", "?")
        if act == "open-schema":
            return f"Schema: {ev.get('content', ev.get('value', '?'))}"
        return f"adb {act}"

    # ── 兜底 ──
    return action


# 兼容旧名称
_desc_report = _step_desc_html


def recover_missing_steps(run_dir: Path, summary: dict) -> dict:
    """从磁盘 step 目录恢复 summary 中缺失的步骤，并用 flow 定义补全元数据"""
    steps = summary.get("steps", [])
    existing = {s.get("index", 0) for s in steps}
    dir_indices = []
    for d in sorted(run_dir.iterdir()):
        if d.is_dir() and d.name.isdigit():
            dir_indices.append(int(d.name))
    missing = [i for i in dir_indices if i not in existing]
    # 从 flow 定义获取完整步骤元数据（用 flow_id 定位）
    from core.flow import load_flow, resolve_flow_steps
    target = summary.get("flow_id", "")
    flow = load_flow(target) if target else None
    resolved = resolve_flow_steps(flow) if flow else []
    step_map = {}       # 全局序号兜底：仅用于恢复真正缺失的步骤（顶层原子步骤/无 flow_id 场景）
    flow_step_map = {}  # (flow_id, sub_index) 精确匹配：不受上游 flow 结构调整导致的全局序号错位影响
    for si, s in enumerate(resolved):
        step_map[si + 1] = s
        fid, sub_idx = s.get("_flow_id"), s.get("_sub_index")
        if fid and sub_idx:
            flow_step_map[(fid, sub_idx)] = s

    # 修补已有步骤的 flow_name、is_critical：优先按 (flow_id, sub_index) 精确匹配子 flow 内部步骤，
    # 避免同一 flow 的上游其他子 flow 被编辑（增删步骤）后，全局序号整体偏移污染无关步骤的关键事件标记
    for s in steps:
        fid = s.get("flow_id")
        ref = flow_step_map.get((fid, s.get("sub_index"))) if fid else step_map.get(s["index"])
        if ref:
            if ref.get("_flow_name"):
                s["flow_name"] = ref["_flow_name"]
            # 双向同步：flow 定义中已取消的关键标记也要在历史报告中降级，避免一次性错误提升后永久无法纠正
            s["is_critical"] = bool(ref.get("is_critical", False))
        if s.get("is_critical"):
            # 对关键步骤，扫描截屏目录填充 critical_screenshots
            if not s.get("critical_screenshots"):
                ss_dir = run_dir / s.get("dir", "") / "screenshots"
                if ss_dir.exists():
                    scrn = []
                    for img in sorted(ss_dir.glob("*.png")) + sorted(ss_dir.glob("*.mp4")):
                        scrn.append(f"{s['dir']}/screenshots/{img.name}")
                    s["critical_screenshots"] = scrn
        else:
            s["critical_screenshots"] = []

    if not missing:
        summary["steps"] = steps
        return summary

    for idx in missing:
        d = run_dir / f"{idx:04d}"
        df = d / "data.json"
        ref = step_map.get(idx, {})
        if df.exists():
            try:
                ev_data = json.loads(df.read_text(encoding="utf-8"))
                _evs = ev_data.get("events", [{}])
                _ev = _evs[0] if _evs else {}
                steps.append({
                    "name": _desc_report(_ev), "type": "event", "index": idx,
                    "status": "success", "event_count": 1,
                    "is_critical": ref.get("is_critical", False),
                    "dir": d.name, "critical_screenshots": [],
                    "flow_name": ref.get("_flow_name", ""),
                })
            except (json.JSONDecodeError, OSError):
                pass
    steps.sort(key=lambda x: x["index"])
    summary["steps"] = steps
    summary["total_steps"] = max(len(steps), dir_indices[-1] if dir_indices else len(steps))
    summary["completed_steps"] = sum(1 for s in steps if s.get("status") == "success")
    summary["failed_steps"] = sum(1 for s in steps if s.get("status") == "failed")
    return summary


def _cv_block_width(n_cols: int, max_cols: int = 3) -> int:
    """按 cv-col 列数计算 cv-block 应有的宽度（px），使卡片宽度贴合图片区域而非被标题撑宽。

    单个对比组内每行最多 max_cols 列，超过换行（不横向滚动），故宽度按 min(n_cols, max_cols) 换算：
    单列宽由 max_cols 决定（col_width = 100% / max_cols），gap 8px*(display_cols-1) + cv-grid padding 24px + cv-block 边框 4px。
    """
    display_cols = min(n_cols, max_cols)
    col_w = max(180, 600 // max_cols)
    return display_cols * col_w + max(display_cols - 1, 0) * 8 + 24 + 4


def _media_tag(src: str, extra_attrs: str = "", step_view: bool = False) -> str:
    if src.endswith(".mp4"):
        if step_view:
            return f'''<div class="video-wrapper" onclick="playStepVideo(this)">
                <video src="{src}" muted preload="metadata" style="width:100%;max-height:270px;border-radius:6px;display:block;background:#000"></video>
                <div class="play-overlay"><div class="play-btn">▶</div></div>
            </div>'''
        return f'''<div class="cv-video-wrap" onclick="cvPlay(this)" style="position:relative;display:inline-block;cursor:pointer">
                <video src="{src}" preload="metadata" style="width:100%;max-height:270px;border-radius:6px;display:block;background:#000"></video>
                <div class="cv-play-overlay"><div class="play-btn">▶</div></div>
            </div>'''
    return f'<img src="{src}" style="width:100%;max-height:270px;object-fit:contain;background:#000;border-radius:6px;cursor:pointer" {extra_attrs}>'


_CP_COLORS = ["#4fc3f7", "#66bb6a", "#ffa726", "#ef5350", "#ab47bc", "#26c6da"]


def _render_cv_block(header: str, items: list[dict], color: str, max_cols: int = 3) -> str:
    """公共 block 渲染函数：全对比面板按 label 分组调用，关键事件面板按 phase 分组调用。

    items: [{"idx": int, "img": {...}}]，已按 idx 排序。
    entries>=2 时每列显示 `#执行序号` 标签，entries==1 时不显示。
    """
    n_cols = len(items)
    cols = ""
    for it in items:
        idx_label = f'<div class="cv-step">#{it["idx"]:02d}</div>' if n_cols >= 2 else ""
        img = it["img"]
        _cr = "true" if img.get("critical") else "false"
        cols += f'''<div class="cv-col" data-critical="{_cr}">
                    {idx_label}
                    {_media_tag(img["src"], f'onclick="showFullscreen(this)" data-phase="{img.get("phase", "")}"')}
                </div>'''
    return f'''
            <div class="cv-block" style="border-color:{color};width:{_cv_block_width(n_cols, max_cols)}px">
                <div class="cv-block-header" style="background:{color}">{header}</div>
                <div class="cv-grid" style="--cv-max-cols:{max_cols}">{cols}</div>
            </div>'''


def _render_critical_panel(compare_data: dict, max_cols: int = 3) -> tuple[str, int]:
    """从 compare_data 构建关键事件面板：按 phase 拆分 block，header 编号取组内最小 idx，
    block 排序按各组最小 idx 升序。返回 (blocks_html, block_count)。
    """
    groups = []
    for cdata in compare_data.values():
        entries = cdata["entries"]
        if not entries or not entries[0].get("is_critical"):
            continue
        min_idx = min(e["idx"] for e in entries)
        step_name = entries[0].get("step_name", "")
        flow_name = entries[0].get("flow_name", "")
        sub_index = entries[0].get("sub_index", 0)
        by_phase: dict[str, list] = {}
        for entry in entries:
            for img in entry["images"]:
                by_phase.setdefault(img.get("phase", ""), []).append({"idx": entry["idx"], "img": img})
        groups.append((min_idx, step_name, flow_name, sub_index, by_phase))
    groups.sort(key=lambda g: g[0])

    blocks = ""
    block_count = 0
    for i, (min_idx, step_name, flow_name, sub_index, by_phase) in enumerate(groups):
        color = _CP_COLORS[i % len(_CP_COLORS)]
        # 标注所属 Flow 及其在该 Flow 内的序号；顶层原子步骤 sub_index=0，不显示"第几步"
        if flow_name and sub_index:
            fn_prefix = f"[{flow_name} 第{sub_index}步] "
        elif flow_name:
            fn_prefix = f"[{flow_name}] "
        else:
            fn_prefix = ""
        for phase in ("before", "after"):
            items = sorted(by_phase.get(phase, []), key=lambda x: x["idx"])
            if not items:
                continue
            header = f"#{min_idx:02d} {fn_prefix}{step_name} · {phase}"
            blocks += _render_cv_block(header, items, color, max_cols)
            block_count += 1
    return blocks, block_count


def generate_flow_report(run_dir: Path, summary: dict, screenshot_cols: int = 3) -> Path:
    """生成瀑布流汇总页（对比网格 + 历史数据融合）。

    screenshot_cols: 步骤视图和对比面板每行最大列数（默认 3）。
    """
    flow_name = summary.get("flow", "未命名")
    description = summary.get("description", "")
    device = summary.get("device", "unknown")
    resolution = summary.get("resolution", [0, 0])
    started_at = summary.get("started_at", "")
    finished_at = summary.get("finished_at", "")
    total_steps = summary.get("total_steps", 0)
    completed_steps = summary.get("completed_steps", 0)
    failed_steps = summary.get("failed_steps", 0)
    steps = summary.get("steps", [])
    summary = recover_missing_steps(run_dir, summary)
    steps = summary["steps"]
    # 写回修复后的 summary（如果有变化）
    sf = run_dir / "summary.json"
    if sf.exists():
        try:
            old_data = json.loads(sf.read_text(encoding="utf-8"))
            old_str = json.dumps(old_data, ensure_ascii=False, sort_keys=True)
            new_str = json.dumps(summary, ensure_ascii=False, sort_keys=True)
            if old_str != new_str:
                json.dump(summary, open(str(sf), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        except (OSError, json.JSONDecodeError):
            pass

    duration_str = ""
    if started_at and finished_at:
        try:
            from datetime import datetime
            start = datetime.fromisoformat(started_at)
            end = datetime.fromisoformat(finished_at)
            delta = end - start
            minutes = int(delta.total_seconds() // 60)
            seconds = int(delta.total_seconds() % 60)
            duration_str = f"{minutes}m{seconds}s" if minutes > 0 else f"{seconds}s"
        except (ValueError, TypeError):
            pass

    compare_data: dict[str, dict] = {}

    def _add_compare_entry(sname: str, entry: dict) -> None:
        if sname not in compare_data:
            compare_data[sname] = {"name": sname, "entries": []}
        compare_data[sname]["entries"].append(entry)

    def _gather_images(step: dict, base_dir: Path) -> list[dict]:
        sdir = base_dir / step.get("dir", "") / "screenshots"
        fn = step.get("flow_name", "")
        fp = f"[{fn}] " if fn else ""
        images = []
        if sdir.exists():
            critical_screenshots = step.get("critical_screenshots", []) or []
            for img in sorted(sdir.glob("*.png")) + sorted(sdir.glob("*.mp4")):
                parts = img.stem.split("_")
                label = ""
                phase = ""
                if len(parts) >= 4:
                    ev_num = int(parts[1]) + 1
                    phase = parts[3]
                    label = f"{fp}#{ev_num} {phase}"
                rel_dir = step.get("dir", "")
                src = f"{rel_dir}/screenshots/{img.name}"
                images.append({
                    "label": label, "src": src, "phase": phase,
                    "critical": src in critical_screenshots,
                })
        return images

    def _compare_key(step: dict) -> str:
        fid = step.get("flow_id", "")
        if not fid:
            # 老数据无 flow_id，回退到 flow_name
            fid = step.get("flow_name", "")
        if not fid:
            return step.get("name", "?")
        si = step.get("sub_index", 0)
        if si:
            return f"{fid}|{si}"
        # 老数据无 sub_index，用步骤描述兜底匹配
        return f"{fid}|{step.get('name', '?')}"

    # 所有步骤参与对比（含顶层直接事件），仅在同一次 run 内比较，不做跨 run 历史匹配
    for step in steps:
        ck = _compare_key(step)
        images = _gather_images(step, run_dir)
        _add_compare_entry(ck, {
            "idx": step.get("index", 0),
            "sub_index": step.get("sub_index", 0),
            "images": images,
            "step_name": step.get("name", ""),
            "flow_name": step.get("flow_name", ""),
            "is_critical": step.get("is_critical", False),
        })

    all_compare_html = ""

    for si, (sname, cdata) in enumerate(sorted(compare_data.items())):
        entries = cdata["entries"]
        if len(entries) < 2:
            continue

        # 提取可读的标题：flow_name + 步骤序号 + 描述
        _key_suffix = sname.rsplit("|", 1)[-1]
        _fn = entries[0].get("flow_name", sname)
        _step_desc = entries[0].get("step_name", "")
        if _key_suffix and _key_suffix.isdigit():
            display_name = _fn
            display_sub = f" 步骤{_key_suffix} — {_step_desc}" if _step_desc else f" 步骤{_key_suffix}"
        else:
            display_name = _fn
            display_sub = f" — {_step_desc}" if _step_desc else ""

        all_labels = sorted(set(
            img["label"] for entry in entries for img in entry["images"]
        ), key=lambda x: (int(re.search(r'#(\d+)', x).group(1)) if re.search(r'#(\d+)', x) else 0, 0 if "before" in x else 1))

        blocks = ""
        for li, label in enumerate(all_labels):
            color = _CP_COLORS[li % len(_CP_COLORS)]
            items = [
                {"idx": entry["idx"], "img": img}
                for entry in entries
                for img in entry["images"]
                if img["label"] == label
            ]
            blocks += _render_cv_block(label, items, color, screenshot_cols)

        run_count = len(entries)
        all_compare_html += f'''
        <div class="compare-panel" id="compare-{si}">
            <div class="compare-header" onclick="toggleCompare(this)">
                <h3>📋 {display_name}{display_sub} <span class="collapse-icon">▾</span></h3>
                <span class="badge">{run_count} 次运行</span>
            </div>
            <div class="cv-wrapper">{blocks}</div>
        </div>'''

    # ── 关键事件面板（复用 compare_data，与全对比面板同源）──
    # 按 phase 拆分 block：同一 compare_key 的 before/after 各生成一个独立 cv-block，
    # header 编号取组内最小 idx，block 排序按各组最小 idx 升序（详见设计文档 3.1 节）。
    flat_compare_html = ""
    critical_blocks, critical_item_count = _render_critical_panel(compare_data, screenshot_cols)
    if critical_blocks:
        flat_compare_html = f'''
        <div class="compare-panel flat-panel" id="flat-all" style="display:none">
            <div class="compare-header flat-header" onclick="toggleFlat(this)">
                <h3>⭐ 关键事件 <span class="collapse-icon">▾</span></h3>
                <span class="badge">{critical_item_count} 组</span>
            </div>
            <div class="cv-wrapper">{critical_blocks}</div>
        </div>'''

    critical_step_count = sum(1 for s in steps if s.get("is_critical"))
    compare_count = sum(1 for v in compare_data.values() if len(v['entries']) >= 2)
    # 默认模式：有对比数据→对比，有关键步骤→关键事件，否则→步骤视图
    _default_mode = 'compare' if compare_count > 0 else ('critical' if critical_step_count > 0 else 'normal')

    # ── 预计算 f-string 表达式（Python < 3.12 不允许反斜杠在 { } 内）──
    _duration_cell = f'<div class="meta-item">⏱ <span class="meta-value">{duration_str}</span></div>' if duration_str else ""
    _failed_cell = f'<div class="meta-item"><span class="meta-value" style="color:var(--danger)">❌ {failed_steps} 失败</span></div>' if failed_steps > 0 else ""
    _compare_tab = f'<span class="control-btn{" active" if _default_mode == "compare" else ""}" onclick="switchMode(\'compare\', this)" id="mode-compare">🔍 全对比（{compare_count} 组）</span>' if compare_count > 0 else ""
    _critical_tab = f'<span class="control-btn{" active" if _default_mode == "critical" else ""}" onclick="switchMode(\'critical\', this)" id="mode-critical">⭐ 关键事件（{critical_step_count} 步）</span>' if critical_step_count > 0 else ""
    _empty_state = '<div class="empty-state">📭 暂无对比数据 — 至少需要 2 次运行才能生成对比视图</div>'
    _compare_section = _empty_state if not all_compare_html.strip() and not flat_compare_html.strip() else all_compare_html + "\n" + flat_compare_html

    # ── 屏幕录制视频（平台可选）──
    _video_html = ""
    for vname in ("screen_recording.mp4", "recording.mp4", "screen_recording.webm"):
        vpath = run_dir / vname
        if vpath.exists():
            _video_html = f'''<div style="max-width:1400px;margin:0 auto 16px;text-align:center">
    <details open><summary style="cursor:pointer;color:var(--accent);font-size:14px;margin-bottom:8px">🎬 屏幕录制</summary>
    <video src="{vname}" controls style="max-width:100%;max-height:400px;border-radius:8px;background:#000"></video>
    </details></div>'''
            break

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{flow_name} — 运行报告</title>
<style>
:root {{
    --bg: #0a0a1a;
    --surface: #1a1a2e;
    --surface-hover: #252545;
    --border: #2a2a4a;
    --text: #e0e0e0;
    --text-dim: #8899aa;
    --accent: #4fc3f7;
    --success: #66bb6a;
    --danger: #ef5350;
    --critical-border: #f39c12;
    --critical-bg: rgba(243, 156, 18, 0.08);
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; padding: 24px; overflow-x: hidden; }}
.header {{ max-width: 1400px; margin: 0 auto 32px; padding: 24px 32px; background: var(--surface); border-radius: 16px; border: 1px solid var(--border); }}
.header h1 {{ font-size: 24px; margin-bottom: 8px; color: var(--accent); }}
.header .description {{ color: var(--text-dim); font-size: 14px; margin-bottom: 16px; }}
.meta-row {{ display: flex; gap: 24px; flex-wrap: wrap; font-size: 13px; color: var(--text-dim); }}
.meta-row .meta-item {{ display: flex; align-items: center; gap: 6px; }}
.meta-row .meta-value {{ color: var(--text); font-weight: 500; }}
.controls {{ max-width: 1400px; margin: 0 auto 16px; display: flex; gap: 8px; flex-wrap: wrap; }}
.control-btn {{ padding: 6px 14px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); color: var(--text); font-size: 13px; cursor: pointer; transition: all 0.15s; }}
.control-btn:hover {{ border-color: var(--accent); }}
.control-btn.active {{ background: var(--accent); color: #000; border-color: var(--accent); font-weight: 600; }}
.container {{ max-width: 1400px; margin: 0 auto; }}
.empty-state {{ max-width: 1400px; margin: 0 auto 24px; padding: 40px 24px; text-align: center; color: var(--text-dim); font-size: 15px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; }}

/* ── 对比面板 ── */
.compare-panel {{ max-width: 1400px; margin: 0 auto 24px; background: var(--surface); border: 2px solid var(--accent); border-radius: 12px; padding: 20px; }}
.compare-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px; cursor: pointer; user-select: none; }}
.compare-header h3 {{ font-size: 16px; color: var(--accent); }}
.compare-header .collapse-icon {{ display: inline-block; transition: transform 0.2s; font-size: 20px; color: var(--text-dim); }}
.compare-panel.collapsed .cv-wrapper {{ display: none; }}
.compare-panel.collapsed .collapse-icon {{ transform: rotate(-90deg); }}

/* ── 关键事件面板 ── */
.flat-header {{ cursor: pointer; user-select: none; }}
.flat-panel.collapsed .cv-wrapper {{ display: none; }}
.cv-wrapper {{ display: block; }}
.cv-block {{ display: inline-block; vertical-align: top; max-width: 100%; border: 2px solid; border-radius: 12px; overflow: hidden; background: rgba(255,255,255,0.02); margin-bottom: 12px; margin-right: 12px; }}
.cv-block-header {{ padding: 10px 14px; font-size: 16px; font-weight: 700; color: #fff; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.cv-grid {{ display: flex; flex-wrap: wrap; gap: 8px; padding: 12px; justify-content: flex-start; }}
.cv-col {{ width: calc((100% - {(screenshot_cols - 1) * 8}px) / {screenshot_cols}); flex-shrink: 0; text-align: center; position: relative; }}
.cv-col[data-critical="true"]::after {{ content: "⭐"; position: absolute; top: 4px; right: 4px; font-size: 14px; z-index: 2; }}
.cv-col img, .cv-col video {{ width: 100%; height: auto; max-height: 360px; object-fit: contain; background: #000; border-radius: 6px; cursor: pointer; }}
.cv-col img:hover, .cv-col video:hover {{ opacity: 0.8; }}

/* ── 扁平对比面板 ── */
.flat-panel {{ border-color: #f39c12 !important; }}
.history-badge {{ background: rgba(79, 195, 247, 0.12); color: var(--accent); border: 1px solid rgba(79, 195, 247, 0.3); }}

/* ── 步骤卡片 ── */
.step-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; margin-bottom: 24px; overflow: hidden; transition: border-color 0.2s; }}
.step-card:hover {{ border-color: var(--accent); }}
.step-card.critical {{ border-color: var(--critical-border); background: var(--critical-bg); }}
.step-card .collapse-icon {{ display: inline-block; transition: transform 0.2s; font-size: 20px; margin-right: 6px; color: var(--text-dim); }}
.step-card.collapsed .collapse-icon {{ transform: rotate(-90deg); }}
.step-card.collapsed .screenshot-grid {{ display: none; }}
.step-header {{ display: flex; align-items: center; gap: 12px; padding: 16px 20px; border-bottom: 1px solid var(--border); cursor: pointer; user-select: none; }}
.step-number {{ font-size: 18px; font-weight: 700; color: var(--accent); min-width: 32px; }}
.step-name {{ font-size: 16px; font-weight: 600; flex: 1; }}
.step-meta {{ font-size: 12px; color: var(--text-dim); }}
.badge {{ font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }}
.critical-badge {{ background: rgba(243, 156, 18, 0.15); color: #f39c12; border: 1px solid rgba(243, 156, 18, 0.3); }}
.flow-badge {{ background: rgba(79, 195, 247, 0.12); color: #4fc3f7; border: 1px solid rgba(79, 195, 247, 0.25); }}
.status-success {{ background: rgba(102, 187, 106, 0.15); color: var(--success); }}
.status-failed {{ background: rgba(239, 83, 80, 0.15); color: var(--danger); }}
.status-interrupted {{ background: rgba(255, 152, 0, 0.15); color: #ff9800; }}
.screenshot-grid {{ display: grid; grid-template-columns: repeat({screenshot_cols}, 1fr); gap: 12px; padding: 16px 20px; }}
.screenshot-item {{ position: relative; border-radius: 8px; overflow: hidden; border: 1px solid var(--border); transition: transform 0.2s, box-shadow 0.2s; cursor: pointer; }}
.screenshot-item:hover {{ transform: scale(1.02); box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4); }}
.screenshot-item img, .screenshot-item video {{ display: block; height: 240px; width: 100%; object-fit: contain; background: #000; }}
.screenshot-label {{ position: absolute; bottom: 0; left: 0; right: 0; padding: 4px 8px; background: rgba(0, 0, 0, 0.75); font-size: 11px; color: #ccc; text-align: center; }}

.video-wrapper, .cv-video-wrap {{ position: relative; display: inline-block; }}
.video-wrapper .video-controlbar, .cv-video-wrap .video-controlbar {{ position: absolute; bottom: 0; left: 0; right: 0; height: 36px; background: rgba(0,0,0,0.78); display: flex; align-items: center; padding: 0 8px; gap: 6px; z-index: 5; border-radius: 0 0 6px 6px; }}
.video-wrapper .vc-btn, .cv-video-wrap .vc-btn {{ background: none; border: none; color: #fff; font-size: 14px; cursor: pointer; padding: 4px 6px; flex-shrink: 0; line-height: 1; }}
.video-wrapper .vc-time, .cv-video-wrap .vc-time {{ color: #ccc; font-size: 11px; white-space: nowrap; font-variant-numeric: tabular-nums; }}
.video-wrapper .vc-sep, .cv-video-wrap .vc-sep {{ color: #666; font-size: 11px; margin: 0 2px; }}

.play-overlay {{ position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.2); transition: background 0.2s; cursor: pointer; }}
.play-overlay:hover {{ background: rgba(0,0,0,0.35); }}
.cv-play-overlay {{ position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.25); transition: background 0.2s; }}
.cv-video-wrap:hover .cv-play-overlay {{ background: rgba(0,0,0,0.35); }}
.play-btn {{ width: 52px; height: 52px; border-radius: 50%; background: rgba(0,0,0,0.65); border: 3px solid rgba(255,255,255,0.85); display: flex; align-items: center; justify-content: center; font-size: 22px; color: #fff; transition: transform 0.15s, background 0.15s; }}
.video-wrapper:hover .play-btn {{ transform: scale(1.08); background: rgba(0,0,0,0.8); }}

video::-webkit-media-controls {{ display: none !important; }}
video::-webkit-media-controls-enclosure {{ display: none !important; }}

.fullscreen-overlay {{ display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.92); z-index: 9999; justify-content: center; align-items: center; cursor: pointer; }}
.fullscreen-overlay.show {{ display: flex; }}
.fullscreen-overlay img, .fullscreen-overlay video {{ max-width: 90vw; max-height: 90vh; object-fit: contain; border-radius: 8px; }}

@media (max-width: 768px) {{ body {{ padding: 12px; }} .screenshot-item img, .screenshot-item video {{ height: 170px; }} .meta-row {{ gap: 12px; }} }}
</style>
</head>
<body>

<div class="header">
    <h1>📋 {flow_name}</h1>
    {"<div class='description'>" + description + "</div>" if description else ""}
    <div class="meta-row">
        <div class="meta-item">📱 <span class="meta-value">{device}</span></div>
        <div class="meta-item">📐 <span class="meta-value">{resolution[0]}x{resolution[1]}</span></div>
        {_duration_cell}
        <div class="meta-item">📊 <span class="meta-value">{completed_steps}/{total_steps} 步骤完成</span></div>
        {_failed_cell}
    </div>
</div>

{_video_html}

<div class="controls">
    <span class="control-btn{(' active' if _default_mode == 'normal' else '')}" onclick="switchMode('normal', this)" id="mode-normal">📋 步骤视图</span>
    {_compare_tab}
    {_critical_tab}
    <span style="flex:1"></span>
    <span class="control-btn active" onclick="filterPhase('all', this)" data-phase-filter="true">🖼 全部</span>
    <span class="control-btn" onclick="filterPhase('before', this)" data-phase-filter="true">◀ before</span>
    <span class="control-btn" onclick="filterPhase('after', this)" data-phase-filter="true">after ▶</span>
</div>

<div id="compare-section">
{_compare_section}
</div>

<div class="container" id="steps-section" style="display:none">
    {_build_steps_html(steps, run_dir)}
</div>

<div class="fullscreen-overlay" id="fullscreen" onclick="hideFullscreen()">
    <img id="fullscreen-img" src="" alt="" style="display:none">
    <video id="fullscreen-video" src="" controls style="display:none"></video>
</div>

<script>
let currentMode = '{_default_mode}';

function showFullscreen(el) {{
    const isVideo = el.tagName === 'VIDEO';
    document.getElementById('fullscreen-img').style.display = isVideo ? 'none' : '';
    document.getElementById('fullscreen-video').style.display = isVideo ? '' : 'none';
    if (isVideo) {{
        const vid = document.getElementById('fullscreen-video');
        vid.src = el.querySelector('source') ? el.querySelector('source').src : el.currentSrc || el.src;
        vid.play();
    }} else {{
        document.getElementById('fullscreen-img').src = el.src;
    }}
    document.getElementById('fullscreen').classList.add('show');
}}
function hideFullscreen() {{
    const vid = document.getElementById('fullscreen-video');
    // 注意：不要用 vid.src = ''，空字符串会被浏览器解析为"当前文档自身的 URL"，
    // 在 file:// 协议下会触发跨 origin 安全拦截报错。用 removeAttribute + load() 代替。
    vid.pause();
    vid.removeAttribute('src');
    vid.load();
    document.getElementById('fullscreen').classList.remove('show');
}}
document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape') hideFullscreen(); }});

function switchMode(mode, btn) {{
    currentMode = mode;
    document.querySelectorAll('.control-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');

    const comparePanels = document.querySelectorAll('#compare-section > .compare-panel');
    const flatPanels = document.querySelectorAll('.flat-panel');
    const stepsSection = document.getElementById('steps-section');

    if (mode === 'normal') {{
        stepsSection.style.display = '';
        comparePanels.forEach(p => p.style.display = 'none');
        flatPanels.forEach(p => p.style.display = 'none');
    }} else if (mode === 'compare') {{
        stepsSection.style.display = 'none';
        comparePanels.forEach(p => p.style.display = 'block');
        flatPanels.forEach(p => p.style.display = 'none');
    }} else if (mode === 'critical') {{
        stepsSection.style.display = 'none';
        comparePanels.forEach(p => p.style.display = 'none');
        flatPanels.forEach(p => p.style.display = 'block');
    }}

    applyPhaseFilter();
}}

let currentPhase = 'all';
function filterPhase(mode, btn) {{
    currentPhase = mode;
    document.querySelectorAll('[data-phase-filter="true"]').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    applyPhaseFilter();
}}

function applyPhaseFilter() {{
    document.querySelectorAll('.cv-block').forEach(b => b.style.display = '');
    document.querySelectorAll('.screenshot-item').forEach(item => item.style.display = '');
    if (currentPhase === 'all') return;

    // 全对比面板 + 关键事件面板共用：cv-block-header 文本本身含 phase 标签（如 "#1 before"），按整块隐藏
    document.querySelectorAll('.cv-block').forEach(block => {{
        const header = block.querySelector('.cv-block-header');
        const blockLabel = header ? header.textContent : '';
        if (!blockLabel.toLowerCase().includes(currentPhase)) {{
            block.style.display = 'none';
        }}
    }});

    document.querySelectorAll('.screenshot-item').forEach(item => {{
        if (item.dataset.phase !== currentPhase) {{
            item.style.display = 'none';
        }}
    }});
}}

function toggleCompare(header) {{
    header.parentElement.classList.toggle('collapsed');
}}

function toggleFlat(header) {{
    header.parentElement.classList.toggle('collapsed');
}}

function cvPlay(wrap) {{
    const video = wrap.querySelector('video');
    if (!video || !video.paused) return;
    video.play();
    wrap.querySelector('.cv-play-overlay')?.remove();
}}

function addCustomControls(video) {{
    if (video._customBar) return;
    video._customBar = true;
    video.controls = false;

    video.closest('.video-wrapper')?.querySelector('.play-overlay')?.remove();
    video.closest('.cv-video-wrap')?.querySelector('.cv-play-overlay')?.remove();

    let wrap = video.closest('.video-wrapper, .cv-video-wrap');
    if (!wrap) {{
        wrap = video.parentElement;
        const nw = document.createElement('div');
        nw.className = 'video-wrapper-inline';
        nw.style.cssText = 'position:relative;display:inline-block';
        video.parentElement.insertBefore(nw, video);
        nw.appendChild(video);
        wrap = nw;
    }}

    const bar = document.createElement('div');
    bar.className = 'video-controlbar';
    bar.innerHTML = '' +
        '<button class="vc-btn" onclick="togglePlay(this)">⏸</button>' +
        '<span class="vc-time">0:00</span>' +
        '<span class="vc-sep">/</span>' +
        '<span class="vc-time">0:00</span>';
    wrap.appendChild(bar);

    const times = bar.querySelectorAll('.vc-time');
    const btn = bar.querySelector('.vc-btn');

    const fmt = (s) => {{
        const m = Math.floor(s / 60), sec = Math.floor(s % 60);
        return m + ':' + (sec < 10 ? '0' : '') + sec;
    }};
    const update = () => {{
        if (video.duration) {{
            times[0].textContent = fmt(video.currentTime);
            times[1].textContent = fmt(video.duration);
        }}
    }};
    video.addEventListener('timeupdate', update);
    video.addEventListener('loadedmetadata', update);
    video.addEventListener('ended', () => {{ btn.textContent = '▶'; }});
}}

function togglePlay(btn) {{
    const video = btn.closest('.video-wrapper,.cv-video-wrap').querySelector('video');
    if (!video) return;
    if (video.paused) {{ video.play(); btn.textContent = '⏸'; }}
    else {{ video.pause(); btn.textContent = '▶'; }}
}}

function playStepVideo(wrapper) {{
    const video = wrapper.querySelector('video');
    if (!video) return;
    video.muted = false;
    video.play();
    addCustomControls(video);
    wrapper.querySelector('.play-overlay')?.remove();
}}

document.addEventListener('play', function(e) {{
    const video = e.target;
    if (video.tagName !== 'VIDEO') return;
    addCustomControls(video);
    const block = video.closest('.cv-block');
    if (!block) return;
    block.querySelectorAll('video').forEach(v => {{
        if (v !== video) {{ v.currentTime = 0; v.play(); }}
    }});
}}, true);
window.addEventListener("DOMContentLoaded",function(){{switchMode("{_default_mode}",document.getElementById("mode-{_default_mode}"));}});</script>

</body>
</html>'''

    report_file = run_dir / "index.html"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(html)
    return report_file


def _build_steps_html(steps: list[dict], run_dir: Path) -> str:
    """构建步骤卡片 HTML（常规模式）"""
    from collections import Counter
    step_names = [s.get("flow_name", s.get("name", "?")) for s in steps if s.get("status") != "interrupted"]
    name_counts = Counter(step_names)
    dup_names = {n for n, c in name_counts.items() if c > 1}
    dup_to_idx = {n: i for i, n in enumerate(sorted(dup_names))}

    compare_data: dict = {}
    for step in steps:
        sname = step.get("flow_name", step.get("name", "?"))
        cidx = dup_to_idx.get(sname)
        if cidx is None:
            continue
        critical_screenshots = step.get("critical_screenshots", []) or []
        sdir = run_dir / step.get("dir", "") / "screenshots"
        fn = step.get("flow_name", "")
        fp = f"[{fn}] " if fn else ""
        images = []
        if sdir.exists():
            for img in sorted(sdir.glob("*.png")) + sorted(sdir.glob("*.mp4")):
                parts = img.stem.split("_")
                label = ""
                phase = ""
                if len(parts) >= 4:
                    ev_num = int(parts[1]) + 1
                    phase = parts[3]
                    label = f"{fp}#{ev_num} {phase}"
                src = f"{step.get('dir', '')}/screenshots/{img.name}"
                images.append({"label": label, "src": src, "phase": phase, "critical": src in critical_screenshots})
        compare_data.setdefault(cidx, {"name": sname, "entries": []})["entries"].append({
            "idx": step.get("index", 0),
            "images": images,
        })

    steps_html = ""
    # 按 flow_name 分组：同一 flow 内的连续步骤合并为一张卡片
    from itertools import groupby
    grouped_steps = []
    for k, g in groupby(steps, lambda s: s.get("flow_name", "")):
        grouped_steps.append((k, list(g)))

    for gn, g_steps in grouped_steps:
        # 取第一步骤的信息作为组头
        first = g_steps[0]
        flow_name = gn
        step_name = flow_name if flow_name else first.get("name", "?")
        step_idx = first.get("index", 0)
        multi_step = len(g_steps) > 1
        status = "success" if all(s.get("status") == "success" for s in g_steps) else "failed"
        is_critical = any(s.get("is_critical") for s in g_steps)

        status_icon = "✅" if status == "success" else "❌"
        critical_class = "critical" if is_critical else ""
        critical_badge = '<span class="badge critical-badge">⭐ 关键步骤</span>' if is_critical else ""
        # 多步骤卡片显示步骤范围，单步骤显示具体序号
        step_number_html = f"{step_idx:02d}" if not multi_step else f"{step_idx:02d}-{g_steps[-1].get('index', step_idx):02d}"

        # 收集所有截图
        screenshots_html = ""
        for step in g_steps:
            dir_name = step.get("dir", "")
            critical_screenshots = step.get("critical_screenshots", []) or []
            step_dir = run_dir / dir_name / "screenshots"
            if step_dir.exists():
                for img in sorted(list(step_dir.glob("*.png")) + list(step_dir.glob("*.mp4"))):
                    rel_path = f"{dir_name}/screenshots/{img.name}"
                    parts = img.stem.split("_")
                    label = ""
                    phase = ""
                    if len(parts) >= 4:
                        ev_num = int(parts[1]) + 1
                        phase = parts[3]
                        si = step.get("sub_index", step.get("index", 0))
                        label = f"#{si:02d} #{ev_num} {phase}"
                    _sc = 'true' if rel_path in critical_screenshots else 'false'
                    is_mp4 = rel_path.endswith(".mp4")
                    screenshots_html += f'''
                <div class="screenshot-item" data-phase="{phase}" data-critical="{_sc}">
                    {_media_tag(rel_path, f'onclick="showFullscreen(this)"', step_view=is_mp4)}
                    <div class="screenshot-label">{label}</div>
                </div>'''

        steps_html += f'''
        <div class="step-card {critical_class}" data-critical="{str(is_critical).lower()}">
            <div class="step-header" onclick="this.parentElement.classList.toggle('collapsed')">
                <span class="step-number">{step_number_html}</span>
                <span class="step-name"><span class="collapse-icon">▾</span> {step_name}</span>
                {critical_badge}
                <span class="badge flow-badge">{len(g_steps)} 事件</span>
                <span class="badge status-{status}">{status_icon}</span>
            </div>
            <div class="screenshot-grid">
                {screenshots_html if screenshots_html else '<div class="no-screenshots" style="color:var(--text-dim);padding:12px 0;font-size:13px">暂无截图</div>'}
            </div>
        </div>'''

    return steps_html


# ─── 关键事件截图拼接（复用 replay-core 公共模块）──────────────

from core.snapshot import render_critical_snapshot, get_local_hostname, format_started_at


def _get_local_hostname() -> str:
    return get_local_hostname()


def _format_started_at(summary: dict) -> str:
    return format_started_at(summary)





def generate_critical_snapshot(run_dir: Path, summary: dict, phase: str = "after", max_cols: int = 4,
                                display_name: str = "", device_label: str = "") -> Path | None:
    """将本次运行的关键事件截图拼接为一张汇总 PNG。

    display_name: 自定义顶部信息栏左侧标题（不传则取 summary.flow）。
    device_label: 设备型号，不为空时追加在 执行机器 之后。
    """
    steps = summary.get("steps", [])
    cards: list[dict] = []
    for step in steps:
        if not step.get("is_critical"):
            continue
        # 匹配两种格式：_before.png (ADB) / _before.jpg (Web 统一命名)
        shots = [s for s in (step.get("critical_screenshots") or []) if f"_{phase}." in s]
        if not shots and phase == "after":
            # after 截图缺失时回退到 before（ADB 截屏偶发失败）
            shots = [s for s in (step.get("critical_screenshots") or []) if "_before." in s]
        if not shots:
            continue
        img_path = run_dir / shots[0]
        if not img_path.exists():
            continue
        fn = step.get("flow_name", "") or step.get("name", "")
        si = step.get("sub_index", 0)
        if fn:
            title = f"{fn} 步骤{si} [{fn}]" if si else fn
        else:
            title = f"步骤{si}" if si else step.get("name", "?")
        cards.append({"title": title, "image": img_path})

    name = display_name or summary.get("flow", "")
    info_text = f"{name} · 执行时间：{_format_started_at(summary)}    执行机器：{_get_local_hostname()}"
    if device_label:
        info_text += f"    手机型号：{device_label}"
    out_path = run_dir / f"critical_{phase}_snapshot.png"
    return render_critical_snapshot(cards, info_text, out_path, max_cols=max_cols)


def generate_mixed_critical_snapshot(
    results: list[dict],
    flow_name: str,
    output_dir: Path,
    phase: str = "after",
) -> Path | None:
    """把各子流程的 critical_{phase}_snapshot.png 竖向堆叠为一张汇总 PNG。

    Args:
        results: [{plat, name, run_dir, summary}]
        flow_name: mixed 流程名称
        output_dir: 输出目录
    """
    from core.snapshot import render_mixed_critical_snapshot

    groups: list[dict] = []
    for r in results:
        run_dir = Path(r.get("run_dir", ""))
        plat = r.get("plat", "")
        name = r.get("name", "")
        if not run_dir.exists():
            continue
        # 直接复用子流程已渲染的 critical_after_snapshot.png
        snap = run_dir / f"critical_{phase}_snapshot.png"
        if not snap.exists():
            continue
        label = f"[{plat}] {name}" if plat else name
        groups.append({"label": label, "image": snap})

    if not groups:
        return None
    info_text = f"[mixed] {flow_name} · 执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}    执行机器：{get_local_hostname()}"
    out_path = output_dir / f"mixed_critical_{phase}_snapshot.png"
    return render_mixed_critical_snapshot(groups, info_text, out_path, max_card_width=1600)



