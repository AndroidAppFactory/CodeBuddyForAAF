#!/usr/bin/env python3
"""一次性改写四端 examples/flows 为新统一契约（S0 任务 1.6）。

改写规则（不做历史兼容，直接产出新结构）：
- 顶层补 platform（按所在端目录推断：adb/web/win/mac）。
- 平台专属元数据（device/resolution/profiles/default_profile）下沉 meta。
- 步骤：Flow 步骤 type=="adb_cmd" → "shell_cmd"；事件步骤已是双层 {type:"event",action}，保留。
- 截图字段命名交由录制/回放期的 screenshot 工具产出，flow 定义本身通常不含截图路径，无需改。

用法：
    python3 tools/rewrite_examples.py            # 改写并写回
    python3 tools/rewrite_examples.py --dry-run  # 仅打印将改动的文件，不写
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 定位 replay-core/scripts 以 import core
_SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPTS))

from core.schema import normalize_flow  # noqa: E402

# skills/test 根目录（replay-core/scripts/tools -> skills/test）
_TEST_ROOT = _SCRIPTS.parent.parent

# 端目录 → platform 映射
END_PLATFORM = {
    "adb-replay": "adb",
    "web-replay": "web",
    "win-replay": "win",
    "mac-replay": "mac",
}

_META_KEYS = ("device", "resolution", "profiles", "default_profile")


def rewrite_flow(data: dict, platform: str) -> dict:
    """把单个 flow dict 改写为新契约（补 platform、meta 下沉、adb_cmd→shell_cmd）。"""
    out = dict(data)
    out["platform"] = platform

    # 平台专属元数据下沉 meta
    meta = dict(out.get("meta", {}))
    for k in _META_KEYS:
        if k in out:
            meta.setdefault(k, out.pop(k))
    if meta:
        out["meta"] = meta

    # 步骤：adb_cmd → shell_cmd
    steps = []
    for s in out.get("steps", []):
        s = dict(s)
        if s.get("type") == "adb_cmd":
            s["type"] = "shell_cmd"
        steps.append(s)
    out["steps"] = steps

    # 用 core 契约校验并补默认值（幂等），失败会抛错暴露问题
    return normalize_flow(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    changed = 0
    errors = 0
    for end, platform in END_PLATFORM.items():
        flows_dir = _TEST_ROOT / end / "examples" / "flows"
        if not flows_dir.is_dir():
            continue
        for f in sorted(flows_dir.glob("flow_*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                new_data = rewrite_flow(data, platform)
            except Exception as e:  # noqa: BLE001
                print(f"  [ERR] {f.relative_to(_TEST_ROOT)}: {e}", file=sys.stderr)
                errors += 1
                continue
            new_text = json.dumps(new_data, ensure_ascii=False, indent=2) + "\n"
            if new_text == f.read_text(encoding="utf-8"):
                continue
            changed += 1
            if args.dry_run:
                print(f"  [DRY] would rewrite {f.relative_to(_TEST_ROOT)} (platform={platform})")
            else:
                f.write_text(new_text, encoding="utf-8")
                print(f"  [OK]  {f.relative_to(_TEST_ROOT)} (platform={platform})")

    print(f"\n改写完成：{changed} 个文件{'（dry-run）' if args.dry_run else ''}，{errors} 个错误")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
