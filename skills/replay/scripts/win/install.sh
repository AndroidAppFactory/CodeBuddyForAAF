#!/usr/bin/env bash
# win-replay 依赖安装脚本（Git Bash / WSL 下可用；Windows 原生建议用 install.ps1）
set -euo pipefail
echo "安装 win-replay 依赖..."
PYTHON="${PYTHON:-python3}"
"$PYTHON" -m pip install --quiet pynput Pillow pywin32
echo "✅ 依赖安装完成"
echo ""
echo "💡 测试命令:"
echo "   python scripts/cli/main.py record --name smoke"
echo "   python scripts/cli/main.py play <events.json>"
