"""ZixieKit 脚本引导模块（零外部依赖）

为独立脚本提供：
  - find_repo_root(): 定位 ZixieKit 仓库根目录
  - load_env(): 加载 ~/.zixiekit/.env 环境变量

~/.zixiekit/scripts/ 由 install/init 自动同步。

用法：
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path.home() / ".zixiekit" / "scripts"))
    from bootstrap import find_repo_root, load_env
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# find_repo_root
# ---------------------------------------------------------------------------

def find_repo_root() -> Path:
    """定位 ZixieKit 仓库根目录。

    查找策略：
    1. 先 load_env() 确保环境变量已加载
    2. 从 ZIXIEKIT_HOME 环境变量获取路径
    3. 报错退出

    返回：仓库根目录的绝对路径
    """
    # 确保 .env 已加载
    load_env()

    zk_home = os.environ.get("ZIXIEKIT_HOME", "")
    if zk_home:
        p = Path(os.path.expandvars(os.path.expanduser(zk_home))).resolve()
        if p.exists():
            return p

    # 报错
    print(
        "❌ 无法定位 ZixieKit 仓库。请在 ~/.zixiekit/.env 中配置：\n"
        "  ZIXIEKIT_HOME=<ZixieKit 仓库路径>",
        file=sys.stderr,
    )
    sys.exit(3)


# ---------------------------------------------------------------------------
# load_env
# ---------------------------------------------------------------------------

_GLOBAL_ENV_PATH = Path.home() / ".zixiekit" / ".env"


def load_env() -> None:
    """加载 ~/.zixiekit/.env 到 os.environ（不覆盖已存在的变量）。

    支持值中的 $VAR / ${VAR} 引用展开（基于 os.path.expandvars）。
    """
    if not _GLOBAL_ENV_PATH.is_file():
        return
    for line in _GLOBAL_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        value = os.path.expanduser(os.path.expandvars(value))
        os.environ.setdefault(key.strip(), value)



