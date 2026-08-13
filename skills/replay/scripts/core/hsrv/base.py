"""BaseEditHandler — HTTP 处理器基类

消除 EditHandler、_CreateHandler、_GroupEditHandler 的重复代码。
子类只需实现 do_GET() / do_POST() 路由。
"""

from __future__ import annotations

import http.server
import json
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, urlparse


SCRIPTS_DIR = Path(__file__).resolve().parent.parent


class BaseEditHandler(http.server.BaseHTTPRequestHandler):
    """HTTP 处理器基类"""

    def log_message(self, format, *args):
        """请求日志（输出到 stderr）"""
        import sys
        msg = format % args
        print(f"  [HTTP] {self.address_string()} {msg}", file=sys.stderr)

    # ─── 公共响应方法 ───────────────────────────────────

    def _no_cache(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")

    def _json(self, data: dict, status: int = 200):
        import json
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._no_cache()
        self.end_headers()
        self._safe_write(json.dumps(data, ensure_ascii=False).encode())

    def _safe_write(self, content: bytes) -> bool:
        """写入响应体，客户端断连时静默忽略（如浏览器刷新）。"""
        try:
            self.wfile.write(content)
            return True
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return False

    # ─── 静态文件服务 ────────────────────────────────────

    def _serve_static(self, path: str, extra_dirs: list[Path] | None = None) -> bool:
        """尝试提供静态文件。返回 True 表示已响应。"""
        import mimetypes
        from core.config import HTML_DIR, SCRIPTS_DIR
        # 搜索顺序：extra_dirs → HTML_DIR → SCRIPTS_DIR → 同级平台 JS 目录
        candidates = list(extra_dirs or []) + [HTML_DIR, SCRIPTS_DIR]
        # 各端的 JS 目录作为 fallback（editor JS 暂未移到 core）
        scripts_root = SCRIPTS_DIR.parent  # scripts/
        for plat in ("adb", "web", "win", "mac"):
            p = scripts_root / plat
            if p.exists():
                candidates.append(p)
        for base in candidates:
            f = base / path.lstrip("/")
            if f.is_file() and f.suffix in (".js", ".css", ".png", ".svg", ".html"):
                ct, _ = mimetypes.guess_type(str(f))
                self.send_response(200)
                self.send_header("Content-Type", ct or "application/octet-stream")
                self._no_cache()
                self.end_headers()
                self._safe_write(f.read_bytes())
                return True
        return False

    # ─── 编辑目录查找 ────────────────────────────────────

    def _find_edit_dir(self) -> Path | None:
        """从查询参数 fav（或 server._current_fav）中查找临时编辑目录"""
        qs = parse_qs(urlparse(self.path).query)
        name = qs.get("fav", [None])[0]
        if not name and hasattr(self.server, "_current_fav"):
            name = self.server._current_fav
        if name and hasattr(self.server, "_fav_edit_dirs") and name in self.server._fav_edit_dirs:
            return Path(self.server._fav_edit_dirs[name])
        return None

    # ─── 简单 HTML 响应 ─────────────────────────────────

    def _html(self, content: str | bytes, status: int = 200):
        if isinstance(content, str):
            content = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self._no_cache()
        self.end_headers()
        self._safe_write(content)
