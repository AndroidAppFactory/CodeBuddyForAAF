#!/usr/bin/env python3
"""把四端 examples/flows 合并迁移到全局仓库 replay/flows/（S1 任务 3.7）。

方案 C：唯一标识是 id，name 可重复。迁移时：
- 逐端读取 examples/flows/*.json（已是新契约，含 platform）。
- 检测跨端 8 位 hex id 冲突：冲突则为后来者重新分配 id，并更新引用它的
  {type:"flow", flow_id} 父步骤。
- 写入全局 FLOWS_DIR（replay/flows/），文件名 flow_<id>.json。

用法：
    python3 tools/migrate_flows_to_global.py --dry-run
    python3 tools/migrate_flows_to_global.py
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPTS))

from core.config import FLOWS_DIR  # noqa: E402
from core.schema import normalize_flow  # noqa: E402

_TEST_ROOT = _SCRIPTS.parent.parent
_ENDS = ("adb-replay", "web-replay", "win-replay", "mac-replay")


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # 收集所有端的 flow
    collected: list[dict] = []
    for end in _ENDS:
        d = _TEST_ROOT / end / "examples" / "flows"
        if not d.is_dir():
            continue
        for f in sorted(d.glob("flow_*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            collected.append(data)

    # id 去重（方案 C：id 唯一）
    used_ids: set[str] = set()
    id_remap: dict[str, str] = {}  # old_id -> new_id（冲突重分配）
    for data in collected:
        fid = data.get("id") or _new_id()
        if fid in used_ids:
            new_fid = _new_id()
            while new_fid in used_ids:
                new_fid = _new_id()
            id_remap[fid] = new_fid
            data["id"] = new_fid
            fid = new_fid
        else:
            data["id"] = fid
        used_ids.add(fid)

    # 更新被重分配 id 的子 flow 引用
    if id_remap:
        for data in collected:
            for s in data.get("steps", []):
                if s.get("type") == "flow" and s.get("flow_id") in id_remap:
                    s["flow_id"] = id_remap[s["flow_id"]]

    # 写入全局仓库
    if not args.dry_run:
        FLOWS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for data in collected:
        data = normalize_flow(data)  # 再校验一次
        out = FLOWS_DIR / f"flow_{data['id']}.json"
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if args.dry_run:
            print(f"  [DRY] -> {out.relative_to(_TEST_ROOT)} ({data['platform']}/{data['name']})")
        else:
            out.write_text(text, encoding="utf-8")
        written += 1

    print(f"\n迁移 {written} 个 flow 到 {FLOWS_DIR.relative_to(_TEST_ROOT)}"
          f"{'（dry-run）' if args.dry_run else ''}；重分配 id: {len(id_remap)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
