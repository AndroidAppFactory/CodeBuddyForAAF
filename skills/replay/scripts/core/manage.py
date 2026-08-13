"""flow manage 全局入口 — 跨平台 Flow 管理器 UI"""

from __future__ import annotations

import http.server
import socket
import subprocess
import sys
import time

from core.config import HTML_DIR
from core.hsrv.flow_handler import make_flow_create_handler, _flows_summary


def _ensure_port_free(port: int) -> bool:
    """检测端口是否被占用；若占用则询问用户。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return True
        except OSError:
            pass

    # 端口被占用，查找 PID
    pids = []
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"],
            capture_output=True, text=True, timeout=5,
        )
        pids = [p for p in result.stdout.strip().splitlines() if p.strip()]
    except Exception:
        pass

    if pids:
        print(f"⚠️  端口 {port} 被占用（PID: {', '.join(pids)}）")
    else:
        print(f"⚠️  端口 {port} 被占用")
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


def cmd_flow_manage(port: int = 8090) -> int:
    """启动 Flow 管理器 HTTP 服务"""
    if not _ensure_port_free(port):
        return 1

    empty_flow = {"name": "", "steps": []}
    Handler = make_flow_create_handler(empty_flow, _flows_summary, port)
    try:
        server = http.server.HTTPServer(('127.0.0.1', port), Handler)
    except OSError:
        print(f"❌ 端口 {port} 无法绑定", file=sys.stderr)
        return 1

    print(f"🖥️  Flow 管理器")
    print(f"   http://localhost:{port}")
    print(f"   按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  已关闭")
        server.shutdown()

    from core.cli import tips_after_flow_manage
    tips_after_flow_manage("flow", script_path="")
    return 0
