"""web-replay record 子命令"""

from __future__ import annotations


def cmd_record(args) -> int:
    """启动 web 录制"""
    from web_recorder import start_recording
    from core.cli import tips_after_record, log_info

    url = getattr(args, "url", None)
    profile = getattr(args, "profile", None)

    log_info("启动 Web 录制...")
    if url:
        log_info(f"起始 URL: {url}")

    try:
        record_dir = start_recording(url=url, profile=profile)
    except KeyboardInterrupt:
        print("\n⏹️  录制结束")
        record_dir = None
    except Exception as e:
        from core.cli import log_error
        log_error("录制失败", str(e))
        return 1

    if record_dir:
        from pathlib import Path
        script = str(Path(__file__).resolve().parents[1] / "web_replay.py")
        tips_after_record("web", str(record_dir), script_path=script)

    return 0
