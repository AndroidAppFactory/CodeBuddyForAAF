"""win-replay record 子命令"""

def cmd_record(args) -> int:
    """启动 win 录制"""
    from win_recorder import start_recording
    from core.cli import tips_after_record, log_info
    from pathlib import Path

    log_info("启动 Windows 录制...")
    try:
        record_dir = start_recording()
    except KeyboardInterrupt:
        print("\n⏹️  录制结束")
        record_dir = None
    except Exception as e:
        from core.cli import log_error
        log_error("录制失败", str(e))
        return 1

    if record_dir:
        script = str(Path(__file__).resolve().parents[1] / "win_replay.py")
        tips_after_record("win", str(record_dir), script_path=script)
    return 0
