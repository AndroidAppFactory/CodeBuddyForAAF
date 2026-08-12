#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
report_terminal.py
终端输出（极简模式 — 对齐 apk-16kb-check 风格）

设计理念：
- 终端只输出「结论摘要」：文件大小、条目数、高优先级建议数
- 详情全部由 HTML 报告承载，不在终端重复
- 保留颜色，方便一眼识别警告
"""

from models import ApkSizeResult, Colors

# ============================================================================
# 工具方法
# ============================================================================

def format_bytes(n: int) -> str:
    """人类友好的字节数格式化"""
    if n is None:
        return "-"
    units = ['B', 'KB', 'MB', 'GB']
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            if u == 'B':
                return f"{int(f)} B"
            return f"{f:.2f} {u}"
        f /= 1024
    return f"{n} B"

# ============================================================================
# 主输出函数
# ============================================================================

def print_header(result: ApkSizeResult) -> None:
    """打印分析标题块（文件路径 + 大小）。在 analyze() 之前调用。"""
    c = Colors
    print()
    print(f"{c.BOLD}{c.CYAN}═══════ 📦 APK 体积分析 ═══════{c.NC}")
    print(f"  文件: {result.file_path}")
    print(f"  大小: {c.BOLD}{format_bytes(result.file_size)}{c.NC}"
          f"（原始 {format_bytes(result.total_uncompressed)}，"
          f"{result.total_files} 条目）")


def print_tip_summary(result: ApkSizeResult) -> None:
    """打印末尾的建议统计行（高优先级 / 普通）。详情见 HTML。"""
    c = Colors
    high_tips = [t for t in result.tips if t.severity == 'high']
    if high_tips:
        print(f"{c.YELLOW}⚠️  {len(high_tips)} 条高优先级建议"
              f"{c.NC} {c.CYAN}（详情见 HTML）{c.NC}")
    elif result.tips:
        print(f"{c.GREEN}✅ {len(result.tips)} 条优化建议"
              f"{c.NC} {c.CYAN}（详情见 HTML）{c.NC}")
