"""adb-replay CLI：导出命令"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from adb_core.config import REPLAY_DIR
from cli.main import list_recordings


def cmd_export(args: argparse.Namespace) -> int:
    """打包指定录制目录为 zip"""
    target_dir = args.dir

    if not target_dir:
        recordings = list_recordings()
        if not recordings:
            print("⚠️  没有找到录制文件，无需导出")
            return 1

        print("📂 本地录制：\n")
        for i, rec in enumerate(recordings, 1):
            print(f"  {i}. {rec['name']}（{rec['event_count']} 个事件）")
        print()

        try:
            choice = input("请选择要导出的序号: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n取消")
            return 0

        if not choice.isdigit():
            print("❌ 无效输入")
            return 1

        idx = int(choice)
        if 1 <= idx <= len(recordings):
            target_dir = recordings[idx - 1]["path"]
        else:
            print("❌ 序号超出范围")
            return 1

    target_path = Path(target_dir).resolve()
    if not target_path.exists() or not target_path.is_dir():
        print(f"❌ 目录不存在: {target_dir}")
        return 1

    output_zip = args.output or str(target_path.parent / f"{target_path.name}.zip")

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        file_count = 0
        for f in sorted(target_path.rglob("*")):
            if f.is_file() and f.name != "index.html":
                arcname = f"{target_path.name}/{f.relative_to(target_path)}"
                zf.write(f, arcname)
                file_count += 1

    print(f"📦 已导出 {file_count} 个文件")
    print(f"   路径: {output_zip}")
    return 0
