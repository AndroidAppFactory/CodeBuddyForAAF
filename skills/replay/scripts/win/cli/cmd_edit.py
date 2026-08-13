"""win-replay edit 子命令 — 打开录制素材编辑器"""

import http.server
import sys
import webbrowser
from pathlib import Path

from bridge.port_utils import ensure_port_free
from core.config import HTML_DIR
from core.hsrv.flow_handler import make_flow_create_handler, _flows_summary


def cmd_edit(args) -> int:
    """打开录制素材编辑器（Web UI）"""
    target = getattr(args, "target", None)
    port = 8090

    if not ensure_port_free(port):
        return 1

    empty_flow = {"name": "", "steps": []}
    Handler = make_flow_create_handler(empty_flow, _flows_summary, port)

    try:
        server = http.server.HTTPServer(('127.0.0.1', port), Handler)
    except OSError:
        print(f"❌ 端口 {port} 无法绑定", file=sys.stderr)
        return 1

    if target:
        target_path = Path(target)
        if not target_path.exists():
            print(f"❌ 录制目录不存在: {target}", file=sys.stderr)
            return 1
        url = f"http://localhost:{port}/replay/?dir={target_path.resolve()}"
    else:
        url = f"http://localhost:{port}/"

    print(f"🖥️  录制素材编辑器")
    print(f"   {url}")
    print(f"   按 Ctrl+C 停止")
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  已关闭")
        server.shutdown()

    return 0
