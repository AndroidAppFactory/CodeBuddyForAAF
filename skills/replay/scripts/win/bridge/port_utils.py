"""端口占用检测与交互式释放（Windows）"""

from __future__ import annotations

import subprocess
import time


def _find_pids(port: int) -> list[str]:
    """用 netstat 找出占用端口的 PID 列表。"""
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return []

    pids = []
    target = f":{port}"
    for line in result.stdout.splitlines():
        cols = line.split()
        if len(cols) < 5:
            continue
        local = cols[1]
        state = cols[3] if len(cols) > 4 and cols[3] == "LISTENING" else ""
        pid = cols[-1]
        if target in local and (state == "LISTENING" or len(cols) < 5):
            if pid.isdigit():
                pids.append(pid)
    # 去重
    return list(dict.fromkeys(pids))


def ensure_port_free(port: int) -> bool:
    """检测端口是否被占用；若占用则询问用户是否关闭进程。"""
    pids = _find_pids(port)
    if not pids:
        return True

    print(f"⚠️  端口 {port} 被占用（PID: {', '.join(pids)}）")
    print("   1. 跳过")
    print("   2. 杀掉")
    try:
        answer = input("   请选择 [1/2]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return False

    if answer != "2":
        return False

    ok = True
    for pid in pids:
        try:
            subprocess.run(["taskkill", "/F", "/PID", pid], check=True, capture_output=True)
            print(f"  ✅ 已关闭进程 PID {pid}")
        except subprocess.CalledProcessError:
            print(f"  ❌ 关闭进程 PID {pid} 失败（可能需要管理员权限）")
            ok = False

    time.sleep(0.5)
    return ok
