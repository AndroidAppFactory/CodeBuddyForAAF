"""replay-core 通知模块

统一的通知发送（企业微信 webhook）。静默容错——任何失败不影响主流程。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    import notify as _notify_impl
except ImportError:
    _notify_impl = None


def _notify_key() -> Optional[str]:
    """从环境变量获取企业微信 webhook key"""
    return os.environ.get("WECOM_KEY_PUBLIC") or None


def notify_safe(title: str, message: str = "", level: str = "info") -> None:
    """静默发送文本通知，任何失败均不影响主流程"""
    if not _notify_impl:
        return
    try:
        _notify_impl.send_notification(title, message, level, key=_notify_key())
    except Exception:
        pass


def notify_image_safe(image_path: Optional[Path] = None) -> None:
    """静默发送图片消息，任何失败均不影响主流程（notify 库内置压缩）"""
    if not _notify_impl or not image_path:
        return
    try:
        _notify_impl.send_image(str(image_path), key=_notify_key())
    except Exception:
        pass


def snapshot_title(
    flow_name: str,
    device: str = "",
    started_at: str = "",
    status: str = "",
    platform: str = "",
) -> str:
    """生成通知标题

    格式：🚀 🤖 【开始 - ADB】{flow} · 执行时间：{ts}    执行机器：{host}    运行设备：{device}
    """
    from core.report import _get_local_hostname, _format_started_at

    ts = _format_started_at({"started_at": started_at}) if started_at else ""
    host = _get_local_hostname()
    plat = platform.upper() or "REPLAY"

    icon = {"开始": "🚀", "结束": "✅", "失败": "⚠️"}.get(status, "ℹ️")
    label = f"{icon} 🤖 【{status} - {plat}】" if status else f"ℹ️ 🤖 {plat}"
    parts = [f"{label}{flow_name}"]
    if ts:
        parts.append(f"执行时间：{ts}")
    parts.append(f"执行机器：{host}")
    if device:
        parts.append(f"运行设备：{device}")
    return " · ".join(parts[:2]) + "    " + "    ".join(parts[2:])
