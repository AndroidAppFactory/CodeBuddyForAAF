"""adb-replay CLI：录制命令"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from adb_core.config import REPLAY_DIR, SCRIPTS_DIR, TASK_RECORD_DIR
from adb_core.recorder import record
from cli.utils import ensure_replay_dir, generate_dirname
from core.cli import tips_after_record


def cmd_record(args: argparse.Namespace) -> int:
    """录制操作 — 直接调用 core.recorder.record()"""
    name = getattr(args, "name", None)
    if name and os.path.isabs(name):
        record_dir = Path(name)
    elif name:
        TASK_RECORD_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        record_dir = TASK_RECORD_DIR / safe_name
    else:
        TASK_RECORD_DIR.mkdir(parents=True, exist_ok=True)
        dirname = generate_dirname(None)
        record_dir = TASK_RECORD_DIR / dirname

    record_dir.mkdir(parents=True, exist_ok=True)

    output_path = record_dir / "data.json"

    print(f"📁 录制目录: {record_dir}")
    print(f"📄 数据文件: {output_path}")
    print()

    try:
        record(str(output_path), device=args.device, verbose=getattr(args, "verbose", False), enable_screenshot=not args.no_screenshot)
        returncode = 0
    except KeyboardInterrupt:
        returncode = 0
    except SystemExit as e:
        returncode = e.code if e.code is not None else 1
    except Exception as e:
        print(f"❌ 录制异常: {e}")
        returncode = 1

    script_path = SCRIPTS_DIR / "adb_replay.py"
    if returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
        print()
        print("=" * 50)
        tips_after_record("adb", str(record_dir), str(script_path))
        print("=" * 50)

    return returncode
