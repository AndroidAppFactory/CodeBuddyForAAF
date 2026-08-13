"""端口占用检测与交互式释放"""

from __future__ import annotations

import subprocess
import time


def ensure_port_free(port: int) -> bool:
    """检测端口是否被占用；若占用则询问用户是否关闭进程。"""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return True

    pids = [p for p in result.stdout.strip().splitlines() if p.strip()]
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
            subprocess.run(["kill", "-9", pid], check=True, capture_output=True)
            print(f"  ✅ 已关闭进程 PID {pid}")
        except subprocess.CalledProcessError:
            print(f"  ❌ 关闭进程 PID {pid} 失败")
            ok = False

    time.sleep(0.5)
    return ok
