"""replay-core 统一截图保存与转码工具

四端录制/回放的截图统一经此模块产出：任意输入（PNG/JPEG 字节流、源文件、PIL Image）
转码为 JPG，按统一命名规范存入 screenshots/ 子目录。

命名规范（见 replay-event-contract）：
    event_{index:03d}_{0_before|1_after}.jpg

依赖 Pillow（各端 Python 均可用）。
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Union

# 相位常量
PHASE_BEFORE = "before"
PHASE_AFTER = "after"

# JPG 转码质量
JPG_QUALITY = 85

ImageInput = Union[bytes, str, Path, "object"]


def screenshot_name(index: int, phase: str) -> str:
    """生成统一截图文件名。

    Args:
        index: 事件序号（从 0 开始）
        phase: "before" 或 "after"

    Returns:
        形如 event_000_0_before.jpg / event_000_1_after.jpg
    """
    if phase == PHASE_BEFORE:
        slot = 0
    elif phase == PHASE_AFTER:
        slot = 1
    else:
        raise ValueError(f"phase 必须为 'before' 或 'after'，实际: {phase!r}")
    return f"event_{index:03d}_{slot}_{phase}.jpg"


def _to_pil_image(src: ImageInput):
    """把任意输入转为 RGB 的 PIL Image。"""
    from PIL import Image

    if isinstance(src, (bytes, bytearray)):
        img = Image.open(io.BytesIO(bytes(src)))
    elif isinstance(src, (str, Path)):
        img = Image.open(str(src))
    elif isinstance(src, Image.Image):
        img = src
    else:
        raise TypeError(f"不支持的截图输入类型: {type(src)!r}")
    # JPG 不支持 alpha，统一转 RGB
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def save_screenshot(
    src: ImageInput,
    screenshots_dir: Union[str, Path],
    index: int,
    phase: str,
    *,
    quality: int = JPG_QUALITY,
) -> str:
    """把截图转码为 JPG 并按统一命名存入 screenshots_dir。

    Args:
        src: 截图输入（PNG/JPEG 字节流、源文件路径、或 PIL Image）
        screenshots_dir: 目标 screenshots/ 目录（不存在则创建）
        index: 事件序号（从 0 开始）
        phase: "before" 或 "after"
        quality: JPG 质量（默认 85）

    Returns:
        相对于 screenshots_dir 父目录的相对路径，形如 "screenshots/event_000_0_before.jpg"
    """
    screenshots_dir = Path(screenshots_dir)
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    name = screenshot_name(index, phase)
    out_path = screenshots_dir / name

    img = _to_pil_image(src)
    img.save(str(out_path), format="JPEG", quality=quality, optimize=True)

    # 返回相对路径（screenshots/xxx.jpg），供写入事件的 screenshots 字段
    return f"{screenshots_dir.name}/{name}"
