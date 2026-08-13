#!/usr/bin/env bash
# mac-replay 依赖安装脚本
# 自动检测 Python 环境并安装 pyobjc 框架依赖

set -euo pipefail

echo "安装 mac-replay 依赖..."

PYTHON="${PYTHON:-python3}"

# 检测 Python 版本
PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python: $PY_VER"

# 检测 pyobjc 是否已安装
check_pyobjc() {
    "$PYTHON" -c "import Quartz; import Cocoa; import ApplicationServices" 2>/dev/null
}

if check_pyobjc; then
    echo "  pyobjc 已安装，跳过"
else
    echo "  安装 pyobjc 框架..."
    "$PYTHON" -m pip install --break-system-packages --quiet \
        pyobjc-framework-Quartz \
        pyobjc-framework-Cocoa \
        pyobjc-framework-ApplicationServices
    echo "  pyobjc 框架安装完成"
fi

echo "依赖安装完成"
