"""三种典型场景的 summary/截图 fixture 构造器。

对应 `.sdd/designs/adb-replay-report-v2.md` 第4节场景 A/B/C：
- A：原子 Flow（无子 Flow 引用），全部 entries=1
- B：非原子 Flow，子 Flow 无重复引用，全部 entries=1
- C：非原子 Flow，子 Flow 重复引用，出现 entries>=2 的对比组

仅构造 `generate_flow_report` 渲染所需的最小磁盘结构（截图文件内容为空字节，
不依赖真实图片，因为渲染流程只引用路径不打开图片）。
"""

from __future__ import annotations

from pathlib import Path


def _write_step_screenshots(run_dir: Path, dir_name: str) -> None:
    """在 {run_dir}/{dir_name}/screenshots/ 下生成 before/after 空白截图。

    文件名遵循 `_gather_images` 期望的 `event_{ev:03d}_{n}_{phase}.png` 格式。
    """
    sdir = run_dir / dir_name / "screenshots"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "event_000_0_before.png").write_bytes(b"")
    (sdir / "event_000_0_after.png").write_bytes(b"")


def _make_step(
    run_dir: Path, *, index: int, name: str, flow_name: str, flow_id: str,
    sub_index: int, is_critical: bool = False,
) -> dict:
    dir_name = f"{index:04d}"
    _write_step_screenshots(run_dir, dir_name)
    critical_screenshots = []
    if is_critical:
        critical_screenshots = [
            f"{dir_name}/screenshots/event_000_0_before.png",
            f"{dir_name}/screenshots/event_000_0_after.png",
        ]
    return {
        "name": name,
        "type": "event",
        "index": index,
        "status": "success",
        "is_critical": is_critical,
        "dir": dir_name,
        "critical_screenshots": critical_screenshots,
        "flow_name": flow_name,
        "flow_id": flow_id,
        "sub_index": sub_index,
    }


def _base_summary(flow_name: str, steps: list[dict]) -> dict:
    return {
        "flow": flow_name,
        "description": "",
        "device": "test-device",
        "resolution": [1080, 1920],
        "started_at": "",
        "finished_at": "",
        "total_steps": len(steps),
        "completed_steps": len(steps),
        "failed_steps": 0,
        "steps": steps,
    }


def build_scenario(scenario: str, tmp_path: Path) -> tuple[Path, dict]:
    """构造场景 A/B/C 的 (run_dir, summary)。scenario ∈ {"A", "B", "C"}"""
    run_dir = tmp_path / f"run_{scenario}"
    run_dir.mkdir(parents=True, exist_ok=True)

    if scenario == "A":
        # 原子 Flow「快速验证」：#1 tap  #2 swipe⭐  #3 tap
        steps = [
            _make_step(run_dir, index=1, name="tap (10,20)", flow_name="", flow_id="atomicA", sub_index=0),
            _make_step(run_dir, index=2, name="swipe (10,20)->(30,40)", flow_name="", flow_id="atomicA", sub_index=0, is_critical=True),
            _make_step(run_dir, index=3, name="tap (50,60)", flow_name="", flow_id="atomicA", sub_index=0),
        ]
        return run_dir, _base_summary("快速验证", steps)

    if scenario == "B":
        # 非原子 Flow「完整验证」（无重复）：启动App(sub1,sub2)  检查首页(sub1⭐)
        steps = [
            _make_step(run_dir, index=1, name="tap", flow_name="启动App", flow_id="startApp", sub_index=1),
            _make_step(run_dir, index=2, name="swipe", flow_name="启动App", flow_id="startApp", sub_index=2, is_critical=True),
            _make_step(run_dir, index=3, name="tap", flow_name="检查首页", flow_id="checkHome", sub_index=1, is_critical=True),
        ]
        return run_dir, _base_summary("完整验证", steps)

    if scenario == "C":
        # 非原子 Flow「多场景验证」（重复引用 启动App）
        steps = [
            _make_step(run_dir, index=1, name="tap", flow_name="启动App", flow_id="startApp", sub_index=1),
            _make_step(run_dir, index=2, name="swipe", flow_name="启动App", flow_id="startApp", sub_index=2, is_critical=True),
            _make_step(run_dir, index=3, name="tap", flow_name="检查首页", flow_id="checkHome", sub_index=1, is_critical=True),
            _make_step(run_dir, index=4, name="tap", flow_name="启动App", flow_id="startApp", sub_index=1),
            _make_step(run_dir, index=5, name="swipe", flow_name="启动App", flow_id="startApp", sub_index=2, is_critical=True),
        ]
        return run_dir, _base_summary("多场景验证", steps)

    raise ValueError(f"unknown scenario: {scenario}")


def build_wide_compare(tmp_path: Path, n_entries: int = 8) -> tuple[Path, dict]:
    """构造单个对比组内 entries=n_entries 的场景，用于验证 6 列换行布局（AC4）。

    同一 flow_id + sub_index 重复引用 n_entries 次。
    """
    run_dir = tmp_path / "run_wide"
    run_dir.mkdir(parents=True, exist_ok=True)
    steps = [
        _make_step(run_dir, index=i + 1, name="tap", flow_name="重复步骤", flow_id="wideFlow", sub_index=1)
        for i in range(n_entries)
    ]
    return run_dir, _base_summary("宽对比验证", steps)
