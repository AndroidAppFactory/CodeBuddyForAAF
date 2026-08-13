"""web-replay Flow 展开与 rerun 合并逻辑单元测试"""
import json
import sys
import tempfile
from pathlib import Path

_scripts = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_scripts))
_replay_core = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(_replay_core))

import flowcore.config as config  # noqa: E402
import core.config as core_config  # noqa: E402

_orig_flows = config.FLOWS_DIR
_orig_core_flows = core_config.FLOWS_DIR
_orig_recordings = config.RECORDINGS_DIR
_tmp = tempfile.TemporaryDirectory()


def setup_module():
    base = Path(_tmp.name)
    config.FLOWS_DIR = base / "flows"
    core_config.FLOWS_DIR = base / "flows"  # core.flow 实际使用的路径
    config.RECORDINGS_DIR = base / "recordings"
    config.FLOWS_DIR.mkdir(parents=True, exist_ok=True)
    config.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


def teardown_module():
    config.FLOWS_DIR = _orig_flows
    core_config.FLOWS_DIR = _orig_core_flows
    config.RECORDINGS_DIR = _orig_recordings
    _tmp.cleanup()


def _clean():
    for d in (config.FLOWS_DIR, config.RECORDINGS_DIR):
        if d.exists():
            for f in d.iterdir():
                if f.is_file():
                    f.unlink()
                elif f.is_dir():
                    import shutil
                    shutil.rmtree(f)


# ── 6.3 局部执行与 rerun ───────────────────────────


def test_collect_events_skips_aux_steps():
    """collect_events 跳过 pause/adb_cmd 辅助步骤"""
    _clean()
    from flowcore.flow import save_flow, collect_events

    flow = {
        "name": "辅助步骤测试",
        "platform": "web",
        "steps": [
            {"type": "event", "action": "click", "selectors": []},
            {"type": "pause", "hint": "等待"},
            {"type": "event", "action": "click", "selectors": []},
            {"type": "shell_cmd", "command": "echo test"},
        ],
    }
    save_flow(dict(flow))

    events = collect_events(flow["steps"])
    # pause 和 adb_cmd 被跳过，只剩 2 个 click（统一 adb 模式：type=event + action=click）
    assert len(events) == 2
    assert all(e["type"] == "event" and e["action"] == "click" for e in events)


def test_is_atomic():
    """原子 Flow 判定"""
    _clean()
    from flowcore.flow import save_flow, is_atomic, load_flow

    save_flow({
        "name": "原子",
        "platform": "web",
        "steps": [
            {"type": "event", "action": "click", "selectors": []},
            {"type": "pause", "hint": "等"},
        ],
    })
    f = load_flow("原子")
    assert is_atomic(f) is True

    save_flow({
        "name": "非原子",
        "platform": "web",
        "steps": [
            {"type": "flow", "flow_id": "原子"},
        ],
    })
    f2 = load_flow("非原子")
    assert is_atomic(f2) is False


def test_resolve_depth_limit():
    """Flow 引用超过 10 层时报错"""
    _clean()
    from flowcore.flow import save_flow, resolve_flow_steps
    import pytest

    save_flow({"name": "自引用", "platform": "web", "steps": [{"type": "flow", "flow_id": "自引用"}]})

    with pytest.raises(ValueError):
        resolve_flow_steps({"name": "触发", "steps": [{"type": "flow", "flow_id": "自引用"}]})
