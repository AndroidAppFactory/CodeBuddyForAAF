#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apk_parser.py
APK 解析器：遍历 ZIP 条目，按类型分类统计，构建 ApkSizeResult 骨架
"""

import os
import zipfile
from pathlib import Path
from typing import List

from models import (
    ApkSizeResult, FileEntry, CategoryStats, FileCategory,
    LARGE_FILE_THRESHOLD, LARGE_IMAGE_THRESHOLD,
)


# ============================================================================
# 文件分类规则
# ============================================================================

# 图片后缀
_IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.9.png'}


def _classify_entry(name: str) -> str:
    """根据 ZIP 内路径 + 文件名判断类别"""
    lower = name.lower()

    # 目录优先
    if lower.startswith('lib/') and lower.endswith('.so'):
        return FileCategory.NATIVE
    if lower.startswith('meta-inf/'):
        return FileCategory.SIGNATURE
    if lower.startswith('assets/'):
        return FileCategory.ASSETS
    if lower.startswith('kotlin/') or lower.endswith('.kotlin_module') or lower.endswith('.kotlin_builtins'):
        return FileCategory.KOTLIN

    # 特定文件
    if lower == 'androidmanifest.xml':
        return FileCategory.MANIFEST
    if lower == 'resources.arsc':
        return FileCategory.RES_TABLE

    # DEX
    if lower.endswith('.dex'):
        return FileCategory.DEX

    # res/ 下的资源
    if lower.startswith('res/'):
        return FileCategory.RESOURCE

    return FileCategory.OTHER


def _is_image(name: str) -> bool:
    """是否为图片文件"""
    lower = name.lower()
    # 处理 .9.png
    if lower.endswith('.9.png'):
        return True
    return Path(lower).suffix in _IMAGE_EXTS


# ============================================================================
# 核心解析流程
# ============================================================================

def parse_apk(apk_path: str) -> ApkSizeResult:
    """解析 APK，构建完整的 FileEntry 列表和分类统计

    :param apk_path: APK / AAB / AAR 等 ZIP 格式文件路径
    :return: ApkSizeResult（尚未填充 dex_infos / so_infos / tips 等）
    """
    apk_path = os.path.abspath(apk_path)
    file_size = os.path.getsize(apk_path)

    result = ApkSizeResult(file_path=apk_path, file_size=file_size)
    stats: dict = {}  # category -> CategoryStats

    with zipfile.ZipFile(apk_path, 'r') as zf:
        for info in zf.infolist():
            # 跳过目录条目
            if info.is_dir():
                continue

            category = _classify_entry(info.filename)
            entry = FileEntry(
                path=info.filename,
                category=category,
                compressed_size=info.compress_size,
                uncompressed_size=info.file_size,
                compress_type=info.compress_type,
            )
            result.entries.append(entry)

            # 累加分类统计
            cs = stats.get(category)
            if cs is None:
                cs = CategoryStats(category=category)
                stats[category] = cs
            cs.file_count += 1
            cs.total_compressed += entry.compressed_size
            cs.total_uncompressed += entry.uncompressed_size

    result.category_stats = stats

    # 提取大文件 / 可优化图片
    result.large_files = _collect_large_files(result.entries)
    result.optimizable_images = _collect_optimizable_images(result.entries)

    return result


def _collect_large_files(entries: List[FileEntry],
                         top_n: int = 30) -> List[FileEntry]:
    """按压缩后大小降序提取大文件"""
    candidates = [e for e in entries if e.compressed_size >= LARGE_FILE_THRESHOLD]
    candidates.sort(key=lambda e: e.compressed_size, reverse=True)
    return candidates[:top_n]


def _collect_optimizable_images(entries: List[FileEntry]) -> List[FileEntry]:
    """识别可优化图片：
    - PNG/JPG/GIF 且压缩后 >= LARGE_IMAGE_THRESHOLD，可考虑转 WebP 或压缩
    - WebP 不视为可优化候选
    - 返回所有命中项（不截断 Top N），按压缩后大小降序
    """
    results: List[FileEntry] = []
    for e in entries:
        if e.category != FileCategory.RESOURCE and not e.path.lower().startswith('assets/'):
            continue
        lower = e.path.lower()
        # 已经是 webp 的不需要进一步优化
        if lower.endswith('.webp'):
            continue
        if not _is_image(lower):
            continue
        if e.compressed_size < LARGE_IMAGE_THRESHOLD:
            continue
        results.append(e)

    results.sort(key=lambda e: e.compressed_size, reverse=True)
    return results
