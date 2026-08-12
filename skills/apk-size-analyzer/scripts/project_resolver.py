#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
project_resolver.py
Android 工程根 / Gradle module 推断与校验。

职责：
  - 从 APK 路径向上回溯寻找 Android 工程根（含 settings.gradle[.kts]）
  - 从 APK 相对路径提取 Gradle module 名（如 'app' / 'APPTest'）
  - 校验显式传入的 --project 路径
  - 综合决策 project_root 最终取值与来源（显式 / 自动 / 空）

本模块不依赖其它业务模块，仅依赖 models.Colors 做终端提示输出。
"""

import os
from typing import Tuple

from models import Colors


# 项目根标识文件（任一存在即判定为 Android 工程根）
PROJECT_ROOT_MARKERS = ('settings.gradle', 'settings.gradle.kts')

# 识别为"构建产物路径"的关键段；命中任一即尝试自动推断 project_root / module
_BUILD_PATH_SEGMENTS = (
    'build/outputs/apk/',
    'build/outputs/bundle/',
    'build/intermediates/apk/',
    'build/intermediates/bundle/',
    'build/intermediates/apk_ide/',
)


def detect_project_root(apk_path: str) -> str:
    """从 APK 路径向上回溯查找 Android 工程根。

    触发条件：APK 路径包含典型构建产物段（_BUILD_PATH_SEGMENTS 之一）。
    查找规则：从 APK 所在目录开始向上，遇到含 settings.gradle(.kts) 的目录即返回。

    :return: 工程根绝对路径；未找到时返回空串
    """
    abs_path = os.path.abspath(apk_path)
    norm = abs_path.replace(os.sep, '/')
    if not any(seg in norm for seg in _BUILD_PATH_SEGMENTS):
        return ""

    cur = os.path.dirname(abs_path)
    # 最多向上回溯 10 层，避免极端情况死循环
    for _ in range(10):
        for marker in PROJECT_ROOT_MARKERS:
            if os.path.isfile(os.path.join(cur, marker)):
                return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return ""


def detect_app_module(apk_path: str, project_root: str) -> str:
    """从 APK 路径中提取 Gradle module 名。

    典型结构：
        {project_root}/{module}/build/outputs/apk/.../xxx.apk
        {project_root}/{module}/build/intermediates/apk/debug/xxx.apk
        {project_root}/build/outputs/apk/.../xxx.apk        （根工程即 module，罕见）

    :return: module 名（如 'app' / 'APPTest'）；无法识别时返回空串
    """
    if not project_root or not apk_path:
        return ""
    abs_apk = os.path.abspath(apk_path)
    abs_root = os.path.abspath(project_root)
    try:
        rel = os.path.relpath(abs_apk, abs_root)
    except ValueError:
        return ""
    rel_norm = rel.replace(os.sep, '/')
    if rel_norm.startswith('..'):
        return ""
    parts = rel_norm.split('/')
    # parts[0] 是 module 名（若 parts[0] == 'build'，表示根工程即 module，返回空让上层处理）
    if len(parts) >= 2 and parts[0] != 'build':
        return parts[0]
    return ""


def validate_project_root(path: str) -> bool:
    """校验给定路径是否为有效的 Android 工程根"""
    if not path or not os.path.isdir(path):
        return False
    return any(os.path.isfile(os.path.join(path, m))
               for m in PROJECT_ROOT_MARKERS)


def resolve_project_root(apk_path: str,
                         override: str = "") -> Tuple[str, bool]:
    """决策 project_root 最终取值与来源。

    :return: (project_root, auto_detected)
        - 显式传入且有效：返回 (abs_override, False)
        - 显式传入但无效：返回 ("", False) 并告警
        - 未传入：尝试自动推断，推断成功 (abs_auto, True)，失败 ("", False)
    """
    c = Colors
    if override:
        abs_over = os.path.abspath(override)
        if validate_project_root(abs_over):
            return abs_over, False
        print(f"{c.YELLOW}⚠️  --project 指定的路径不是有效 Android 工程根 "
              f"(缺少 settings.gradle[.kts]): {override}{c.NC}")
        print(f"{c.YELLOW}   跳过源码关联分析{c.NC}")
        return "", False

    auto = detect_project_root(apk_path)
    if auto:
        print(f"{c.CYAN}📂 自动识别工程根: {auto}{c.NC}")
        return auto, True
    return "", False
