#!/usr/bin/env python3
"""mac-replay 录制报告生成器

从 events.json 生成 HTML 步骤报告 + 关键事件截图拼接。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def generate_report(recording_dir: Path, output_dir: Path = None) -> Path:
    """生成 HTML 报告。

    Args:
        recording_dir: 录制产物目录（含 events.json + screenshots/）
        output_dir: 输出目录，默认同 recording_dir

    Returns:
        生成的 index.html 路径
    """
    if output_dir is None:
        output_dir = recording_dir

    events_file = recording_dir / "events.json"
    if not events_file.exists():
        raise FileNotFoundError(f"未找到 events.json: {events_file}")

    data = json.loads(events_file.read_text(encoding="utf-8"))
    events = data.get("events", [])
    name = data.get("name", recording_dir.name)
    created_at = data.get("created_at", "")

    # 构建步骤 HTML
    steps_html = _build_steps_html(events)
    critical_count = sum(1 for e in events if e.get("is_critical"))
    total_events = len(events)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} — mac-replay 报告</title>
<style>
:root {{ --bg: #0a0a1a; --surface: #1a1a2e; --border: #2a2a4a; --text: #e0e0e0; --text-dim: #8899aa; --accent: #4fc3f7; --success: #66bb6a; --danger: #ef5350; --critical-border: #f39c12; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; padding: 24px; }}
.header {{ max-width: 1400px; margin: 0 auto 32px; padding: 24px 32px; background: var(--surface); border-radius: 16px; border: 1px solid var(--border); }}
.header h1 {{ font-size: 24px; margin-bottom: 8px; color: var(--accent); }}
.meta-row {{ display: flex; gap: 24px; flex-wrap: wrap; font-size: 13px; color: var(--text-dim); }}
.meta-row .val {{ color: var(--text); font-weight: 500; }}
.step-card {{ max-width: 1400px; margin: 0 auto 20px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }}
.step-card.critical {{ border-color: var(--critical-border); border-width: 2px; }}
.step-header {{ display: flex; align-items: center; gap: 12px; padding: 14px 20px; border-bottom: 1px solid var(--border); cursor: pointer; user-select: none; }}
.step-number {{ font-size: 18px; font-weight: 700; color: var(--accent); min-width: 36px; }}
.step-name {{ font-size: 15px; font-weight: 600; flex: 1; }}
.badge {{ font-size: 11px; padding: 2px 10px; border-radius: 4px; font-weight: 500; }}
.critical-badge {{ background: rgba(243,156,18,.15); color: #f39c12; border: 1px solid rgba(243,156,18,.3); }}
.screenshot-row {{ display: flex; gap: 1px; background: var(--border); padding: 1px; }}
.screenshot-item {{ flex: 1; position: relative; background: #000; cursor: pointer; }}
.screenshot-item img {{ width: 100%; height: auto; max-height: 400px; object-fit: contain; display: block; }}
.screenshot-label {{ position: absolute; bottom: 0; left: 0; right: 0; padding: 4px 8px; background: rgba(0,0,0,.75); font-size: 11px; color: #ccc; text-align: center; }}
.collapse-icon {{ display: inline-block; transition: transform .2s; margin-right: 4px; }}
.step-card.collapsed .screenshot-grid {{ display: none; }}
.step-card.collapsed .collapse-icon {{ transform: rotate(-90deg); }}
.fullscreen-overlay {{ display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,.92); z-index: 9999; justify-content: center; align-items: center; cursor: pointer; }}
.fullscreen-overlay.show {{ display: flex; }}
.fullscreen-overlay img {{ max-width: 90vw; max-height: 90vh; object-fit: contain; border-radius: 8px; }}
</style>
</head>
<body>

<div class="header">
    <h1>📋 {name}</h1>
    <div class="meta-row">
        <span>📅 <span class="val">{created_at[:19] if created_at else '--'}</span></span>
        <span>📊 <span class="val">{total_events} 个事件</span></span>
        {"<span>⭐ <span class=\"val\" style=\"color:#f39c12\">" + str(critical_count) + " 个关键步骤</span></span>" if critical_count > 0 else ""}
    </div>
</div>

<div id="steps-container">
{steps_html if steps_html else '<div style="max-width:1400px;margin:0 auto;padding:40px;text-align:center;color:var(--text-dim)">📭 暂无事件</div>'}
</div>

<div class="fullscreen-overlay" id="fullscreen" onclick="hideFullscreen()">
    <img id="fullscreen-img" src="" alt="">
</div>

<script>
function showFullscreen(el) {{
    document.getElementById('fullscreen-img').src = el.src;
    document.getElementById('fullscreen').classList.add('show');
}}
function hideFullscreen() {{ document.getElementById('fullscreen').classList.remove('show'); }}
document.addEventListener('keydown', e => {{ if (e.key === 'Escape') hideFullscreen(); }});
</script>

</body>
</html>'''

    report_path = output_dir / "index.html"
    report_path.write_text(html, encoding="utf-8")
    return report_path


def _build_steps_html(events: list[dict]) -> str:
    """构建步骤卡片 HTML。"""
    html_parts = []
    for i, ev in enumerate(events):
        idx = i + 1
        ev_type = ev.get("type", "?")
        is_critical = ev.get("is_critical", False)

        desc = _event_desc(ev)

        before = f"screenshots/event_{i:03d}_0_before.jpg"
        after = f"screenshots/event_{i:03d}_1_after.jpg"

        screenshots_html = '<div class="screenshot-row">'
        for label, path in [("before", before), ("after", after)]:
            screenshots_html += f'<div class="screenshot-item" onclick="showFullscreen(this.querySelector(\'img\'))"><img src="{path}" loading="lazy"><div class="screenshot-label">{label}</div></div>'
        screenshots_html += '</div>'

        critical_class = " critical" if is_critical else ""
        critical_badge = '<span class="badge critical-badge">⭐ 关键</span>' if is_critical else ""

        html_parts.append(f'''
        <div class="step-card{critical_class}">
            <div class="step-header" onclick="this.parentElement.classList.toggle('collapsed')">
                <span class="step-number">#{idx:02d}</span>
                <span class="step-name"><span class="collapse-icon">▾</span> {ev_type} — {desc}</span>
                {critical_badge}
            </div>
            <div class="screenshot-grid">
                {screenshots_html}
            </div>
        </div>''')

    return "\n".join(html_parts)


def _event_desc(ev: dict) -> str:
    """生成事件可读描述。"""
    t = ev.get("type", "?")
    if t in ("click", "dblclick", "rightclick"):
        return f"({ev.get('x', 0)}, {ev.get('y', 0)})"
    if t == "drag":
        return f"({ev.get('x1', 0)},{ev.get('y1', 0)})→({ev.get('x2', 0)},{ev.get('y2', 0)}) {ev.get('duration_ms', 0)}ms"
    if t == "scroll":
        return f"Δ({ev.get('delta_x', 0)}, {ev.get('delta_y', 0)})"
    if t == "type":
        return f'"{str(ev.get("content", ""))[:30]}"'
    if t == "keyboard":
        return ev.get("keys", "")
    if t == "wait":
        return f'{ev.get("duration_ms", 0)}ms'
    if t == "action":
        return f'{ev.get("action", "")} {ev.get("bundle_id", "")}'
    if t == "tips":
        return f'"{str(ev.get("content", ""))[:30]}"'
    return t


def generate_snapshot(recording_dir: Path, phase: str = "after") -> Path | None:
    """将关键事件截图拼接为一张汇总 PNG（不依赖浏览器渲染）。

    Args:
        recording_dir: 录制产物目录
        phase: "before" 或 "after"

    Returns:
        拼接后的 PNG 路径，无关键事件时返回 None
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    events_file = recording_dir / "events.json"
    if not events_file.exists():
        return None

    data = json.loads(events_file.read_text(encoding="utf-8"))
    events = data.get("events", [])

    # 收集关键事件截图
    cards = []
    for i, ev in enumerate(events):
        if not ev.get("is_critical"):
            continue
        path_str = f"screenshots/event_{i:03d}_{'_1' if phase == 'after' else '_0'}_{phase}.jpg"
        img_path = recording_dir / path_str
        if not img_path.exists():
            continue
        cards.append({
            "title": f"#{ev.get('index', 0):02d} {ev.get('type', '')}",
            "image": img_path,
        })

    if not cards:
        return None

    THUMB_W = 400
    PAD = 16
    GAP = 12
    COLS = min(4, len(cards))
    BG = (10, 10, 26)
    COLORS = ["#4fc3f7", "#66bb6a", "#ffa726", "#ef5350", "#ab47bc", "#26c6da"]

    # 字体
    try:
        font_path = "/System/Library/Fonts/STHeiti Medium.ttc"
        header_font = ImageFont.truetype(font_path, 16)
    except Exception:
        header_font = ImageFont.load_default()

    HEADER_H = 36

    # 缩略图
    thumbs = []
    for c in cards:
        img = Image.open(c["image"]).convert("RGB")
        w, h = img.size
        new_h = int(h * THUMB_W / w)
        thumbs.append(img.resize((THUMB_W, new_h), Image.LANCZOS))

    card_h = max(t.height for t in thumbs) + HEADER_H
    rows = (len(cards) + COLS - 1) // COLS
    canvas_w = PAD * 2 + COLS * THUMB_W + (COLS - 1) * GAP
    canvas_h = PAD * 2 + rows * card_h + (rows - 1) * GAP

    canvas = Image.new("RGB", (canvas_w, canvas_h), BG)
    draw = ImageDraw.Draw(canvas)

    for i, (card, thumb) in enumerate(zip(cards, thumbs)):
        row, col = divmod(i, COLS)
        x = PAD + col * (THUMB_W + GAP)
        y = PAD + row * (card_h + GAP)
        color = tuple(int(COLORS[i % len(COLORS)][j:j+2], 16) for j in (1, 3, 5))

        draw.rounded_rectangle([x - 2, y - 2, x + THUMB_W + 2, y + card_h + 2], radius=8, outline=color, width=2)
        draw.rectangle([x, y, x + THUMB_W, y + HEADER_H], fill=color)
        tw = draw.textlength(card["title"], font=header_font)
        draw.text((x + (THUMB_W - tw) / 2, y + (HEADER_H - header_font.size) / 2), card["title"], font=header_font, fill=(255, 255, 255))
        canvas.paste(thumb, (x, y + HEADER_H))

    out_path = recording_dir / f"critical_{phase}_snapshot.png"
    canvas.save(out_path, format="PNG")
    return out_path
