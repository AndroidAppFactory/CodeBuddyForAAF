#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
module_attributor.py
SO 模块归因：复用 apk-16kb-check/scripts/so_source_analyzer.py 的
Gradle transforms 缓存反查能力，为每个 SO 标注来源模块。

策略：
  1. 通过 sys.path 动态注入 apk-16kb-check/scripts/ 目录
  2. 调用 analyze_so_sources(apk_path) 获取 (project_root, so_source_map, agp_info)
  3. 将映射写回 SoInfo 的 source_module / source_type 字段
"""

import os
import sys
from typing import Tuple, Dict

from models import ApkSizeResult, Colors


# 计算 apk-16kb-check/scripts 的绝对路径（相对于本文件）
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_SIBLING_SCRIPTS = os.path.abspath(os.path.join(
    _CURRENT_DIR, '..', '..', 'apk-16kb-check', 'scripts'
))


def _ensure_importable() -> bool:
    """确保可以 import 兄弟 Skill 的 so_source_analyzer"""
    if not os.path.isdir(_SIBLING_SCRIPTS):
        return False
    if _SIBLING_SCRIPTS not in sys.path:
        sys.path.insert(0, _SIBLING_SCRIPTS)
    return True


def attribute_so_sources(result: ApkSizeResult) -> Tuple[str, Dict[str, Dict]]:
    """为 result 中的 SO 标注来源模块

    :return: (project_root, so_source_map)
      - project_root 为空表示 APK 非项目构建产物，未做归因
    """
    c = Colors
    if not result.so_infos:
        return "", {}

    if not _ensure_importable():
        print(f"{c.YELLOW}⚠️  未找到 apk-16kb-check/scripts，跳过 SO 模块归因{c.NC}")
        return "", {}

    try:
        # 延迟 import，避免 sys.path 未就绪时 import 失败
        from so_source_analyzer import analyze_so_sources  # type: ignore
    except Exception as e:
        print(f"{c.YELLOW}⚠️  import so_source_analyzer 失败: {e}{c.NC}")
        return "", {}

    try:
        project_root, so_source_map, agp_info = analyze_so_sources(result.file_path)
    except Exception as e:
        print(f"{c.YELLOW}⚠️  SO 来源分析失败: {e}{c.NC}")
        return "", {}

    # 写回结果
    # 注意：只在 result.project_root 为空时才用 so_source_analyzer 推断值填充，
    # 避免覆盖上游通过 --project 显式传入或 _detect_project_root 自动推断的值
    # （so_source_analyzer 只识别标准构建产物路径，误判场景会返回空串）
    if not result.project_root:
        result.project_root = project_root or ""
    result.so_source_map = so_source_map or {}

    if so_source_map:
        for so in result.so_infos:
            info = so_source_map.get(so.name)
            if not info:
                continue
            so.source_module = info.get('module', '')
            so.source_type = info.get('type', '')

    return result.project_root, result.so_source_map
