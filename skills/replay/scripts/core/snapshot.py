#!/usr/bin/env python3
"""公共关键事件截图拼接模块

三端（adb/web/win）共用的拼图渲染逻辑。各端只需组装 cards 列表和 info_text，
调用 render_critical_snapshot() 即可生成统一样式的汇总图。
"""

from __future__ import annotations

import socket
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── 常量 ────────────────────────────────────────────────────────────────────

SNAPSHOT_COLORS = ["#4fc3f7", "#66bb6a", "#ffa726", "#ef5350", "#ab47bc", "#26c6da"]


# ─── 工具函数 ─────────────────────────────────────────────────────────────────


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def snapshot_font(size: int, bold: bool = False):
    """跨平台中文字体加载"""
    from PIL import ImageFont
    candidates: list[str] = []
    if bold:
        candidates = [
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/noto/NotoSansCJK-Bold.ttc",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyhl.ttc",
            "C:/Windows/Fonts/simsun.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc",
        ]
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def get_local_hostname() -> str:
    """获取本机名，去除 .local 后缀"""
    host = socket.gethostname()
    if host.endswith(".local"):
        host = host[: -len(".local")]
    return host


def format_started_at(summary: dict) -> str:
    raw = summary.get("started_at", "")
    try:
        return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return raw or "-"


def wrap_text(draw, text: str, font, max_width: int, max_lines: int = 2) -> list[str]:
    """按字符宽度换行，超过 max_lines 时截断"""
    lines: list[str] = []
    cur = ""
    for ch in text:
        test = cur + ch
        if cur and draw.textlength(test, font=font) > max_width:
            lines.append(cur)
            cur = ch
            if len(lines) >= max_lines:
                break
        else:
            cur = test
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines[:max_lines]


# ─── 公共拼图函数 ─────────────────────────────────────────────────────────────


def render_critical_snapshot(
    cards: list[dict],
    info_text: str,
    out_path: Path,
    max_cols: int = 4,
    max_card_width: int = 0,
) -> Optional[Path]:
    """将 cards 列表渲染为统一样式的关键事件拼图。

    Args:
        cards: [{"title": str, "image": Path}, ...]，已筛选好的关键截图
        info_text: 顶部信息栏文案（如 "执行时间：... 执行机器：..."）
        out_path: 输出 PNG 路径
        max_cols: 最大列数，默认 4
        max_card_width: 单卡片最大宽度（像素），0=不限制。多平台合并时建议 1600

    Returns:
        成功返回 out_path，cards 为空返回 None
    """
    if not cards:
        return None

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    PAD = 20
    GAP = 16
    COLS = min(max_cols, len(cards))
    BG = (10, 10, 26)
    TITLE_COLOR = (79, 195, 247)

    # 不做固定缩略图宽度，保持原始分辨率，列宽取所有图片最大宽度
    thumbs = []
    for c in cards:
        img = Image.open(c["image"]).convert("RGB")
        thumbs.append(img)

    col_w = max(t.width for t in thumbs)

    # 限制单卡片最大宽度（防止多平台合并时画布过大）
    if max_card_width and col_w > max_card_width:
        col_w = max_card_width
        thumbs = [
            t.resize((col_w, int(t.height * col_w / t.width)), Image.LANCZOS)
            for t in thumbs
        ]

    # 字体大小按截图宽度自适应，加上限避免桌面截图字过大
    # 1080px → info 24 / header 18；1920px → info 34 / header 32
    header_size = max(18, min(col_w // 55, 36))
    info_size = max(24, min(col_w // 50, 42))
    header_font = snapshot_font(header_size, bold=True)
    info_font = snapshot_font(info_size, bold=True)

    probe = Image.new("RGB", (10, 10))
    probe_draw = ImageDraw.Draw(probe)
    header_lines_list = [wrap_text(probe_draw, c["title"], header_font, col_w - 16) for c in cards]
    max_lines = max(len(lines) for lines in header_lines_list)
    line_h = header_font.size + 6
    HEADER_H = max(40, line_h * max_lines + 14)

    card_h = max(t.height for t in thumbs) + HEADER_H
    rows = (len(cards) + COLS - 1) // COLS
    title_h = 64

    canvas_w = PAD * 2 + COLS * col_w + (COLS - 1) * GAP
    canvas_h = title_h + PAD * 2 + rows * card_h + (rows - 1) * GAP

    canvas = Image.new("RGB", (canvas_w, canvas_h), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((PAD, (title_h - info_font.size) // 2), info_text, font=info_font, fill=TITLE_COLOR)

    for i, (card, thumb, header_lines) in enumerate(zip(cards, thumbs, header_lines_list)):
        row, col = divmod(i, COLS)
        x = PAD + col * (col_w + GAP)
        y = title_h + PAD + row * (card_h + GAP)
        color = hex_to_rgb(SNAPSHOT_COLORS[i % len(SNAPSHOT_COLORS)])

        draw.rounded_rectangle([x - 3, y - 3, x + col_w + 3, y + card_h + 3], radius=10, outline=color, width=3)
        draw.rectangle([x, y, x + col_w, y + HEADER_H], fill=color)

        ty = y + (HEADER_H - line_h * len(header_lines)) // 2
        for line in header_lines:
            tw = draw.textlength(line, font=header_font)
            draw.text((x + (col_w - tw) / 2, ty), line, font=header_font, fill=(255, 255, 255))
            ty += line_h

        # 等比缩放至列宽后贴入
        scale = col_w / thumb.width
        resized = thumb.resize((col_w, int(thumb.height * scale)), Image.LANCZOS)
        canvas.paste(resized, (x, y + HEADER_H))

    canvas.save(str(out_path), format="PNG", optimize=True)
    print(f"  快照已保存: {out_path} ({out_path.stat().st_size / 1024 / 1024:.1f}MB)", file=sys.stderr)
    return out_path


# ─── Mixed 流程专用：把每个子流程的 critical_after_snapshot.png 竖向堆叠 ─────────

def render_mixed_critical_snapshot(
    groups: list[dict],
    info_text: str,
    out_path: Path,
    max_card_width: int = 1600,
) -> Optional[Path]:
    """Mixed 流程专用拼图：把各子流程已渲染的 critical_after_snapshot.png 竖向堆叠。

    Args:
        groups: [{"label": "[web] 浏览器 IP 查看", "image": Path 至已渲染的 PNG}]
        info_text: 顶部信息栏文案
        out_path: 输出 PNG 路径
        max_card_width: 每个子流程图最大宽度（像素），超过则缩放

    Returns:
        成功返回 out_path，无 image 返回 None
    """
    from PIL import Image, ImageDraw

    if not groups:
        return None

    PAD = 20
    GAP = 12
    BG = (10, 10, 26)
    TITLE_H = 64

    # 字体
    info_font = snapshot_font(26, bold=True)
    ldr = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    max_label_w = max(ldr.textlength(g["label"], font=snapshot_font(18, bold=True)) for g in groups)
    label_w = max(160, int(max_label_w) + 24)

    # 加载并缩放每个子流程的截图
    rows: list[dict] = []
    for g in groups:
        try:
            img = Image.open(g["image"]).convert("RGB")
        except Exception:
            continue
        if max_card_width and img.width > max_card_width:
            img = img.resize(
                (max_card_width, int(img.height * max_card_width / img.width)),
                Image.LANCZOS,
            )
        rows.append({"label": g["label"], "img": img, "h": img.height, "w": img.width})

    if not rows:
        return None

    # 计算画布尺寸
    max_row_w = max(label_w + 16 + r["w"] for r in rows)
    canvas_w = PAD * 2 + max_row_w
    row_gap = 16
    canvas_h = TITLE_H + PAD * 2 + sum(r["h"] for r in rows) + row_gap * (len(rows) - 1)

    canvas = Image.new("RGB", (canvas_w, canvas_h), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((PAD, (TITLE_H - info_font.size) // 2), info_text, font=info_font,
              fill=(79, 195, 247))

    label_font = snapshot_font(18, bold=True)
    cur_y = TITLE_H + PAD
    for ri, row in enumerate(rows):
        color = hex_to_rgb(SNAPSHOT_COLORS[ri % len(SNAPSHOT_COLORS)])
        # 左侧标签
        draw.rounded_rectangle(
            [PAD, cur_y, PAD + label_w, cur_y + row["h"]], radius=8, fill=color,
        )
        lw = draw.textlength(row["label"], font=label_font)
        draw.text(
            (PAD + (label_w - lw) / 2, cur_y + (row["h"] - label_font.size) / 2),
            row["label"], font=label_font, fill=(255, 255, 255),
        )
        # 右侧子流程截图
        canvas.paste(row["img"], (PAD + label_w + 16, cur_y))
        cur_y += row["h"] + row_gap

    canvas.save(str(out_path), format="PNG", optimize=True)
    print(f"  快照已保存: {out_path} ({out_path.stat().st_size / 1024 / 1024:.1f}MB)", file=sys.stderr)
    return out_path
