# win-replay 依赖安装脚本 (PowerShell)
# 在 Windows 上安装 pynput / Pillow / pywin32

$ErrorActionPreference = "Stop"

Write-Host "安装 win-replay 依赖..."

# 选择 pip
$pip = $null
if (Get-Command pip -ErrorAction SilentlyContinue) { $pip = "pip" }
elseif (Get-Command pip3 -ErrorAction SilentlyContinue) { $pip = "pip3" }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $pip = "python -m pip" }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $pip = "py -m pip" }

if (-not $pip) {
    Write-Host "❌ 未找到 pip，请先安装 Python" -ForegroundColor Red
    exit 1
}

Write-Host "  使用 pip: $pip"
Write-Host "  安装 pynput / Pillow / pywin32 ..."
Invoke-Expression "$pip install --quiet pynput Pillow pywin32"

Write-Host "✅ 依赖安装完成" -ForegroundColor Green
Write-Host ""
Write-Host "💡 测试命令:" -ForegroundColor Cyan
Write-Host "   python scripts/cli/main.py record --name smoke"
Write-Host "   python scripts/cli/main.py play <events.json>"
