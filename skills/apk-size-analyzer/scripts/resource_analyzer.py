#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resource_analyzer.py
资源分析器：res/ 目录下资源按类型分组、检测大图/可转 WebP 候选
"""

from pathlib import Path
from typing import Dict, List

from models import (
    ApkSizeResult, FileEntry, FileCategory, LARGE_IMAGE_THRESHOLD,
)


# 资源子类型（用于 UI 展示）
RES_SUBTYPE_DRAWABLE = "drawable"    # drawable*/, mipmap*/
RES_SUBTYPE_LAYOUT = "layout"        # layout*/
RES_SUBTYPE_ANIM = "anim"            # anim*/, animator*/
RES_SUBTYPE_RAW = "raw"              # raw*/
RES_SUBTYPE_XML = "xml"              # xml*/
RES_SUBTYPE_FONT = "font"            # font*/
RES_SUBTYPE_VALUES = "values"        # values*/（通常已被合并进 resources.arsc）
RES_SUBTYPE_OTHER = "other"


_IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}


def _subtype_of_res(path: str) -> str:
    """从 res/{folder}/xxx 识别资源子类型"""
    lower = path.lower().replace('\\', '/')
    if not lower.startswith('res/'):
        return RES_SUBTYPE_OTHER

    parts = lower.split('/')
    if len(parts) < 3:
        return RES_SUBTYPE_OTHER

    folder = parts[1]  # res/<folder>/<file>
    if folder.startswith('drawable') or folder.startswith('mipmap'):
        return RES_SUBTYPE_DRAWABLE
    if folder.startswith('layout'):
        return RES_SUBTYPE_LAYOUT
    if folder.startswith('anim'):
        return RES_SUBTYPE_ANIM
    if folder.startswith('raw'):
        return RES_SUBTYPE_RAW
    if folder.startswith('xml'):
        return RES_SUBTYPE_XML
    if folder.startswith('font'):
        return RES_SUBTYPE_FONT
    if folder.startswith('values'):
        return RES_SUBTYPE_VALUES
    return RES_SUBTYPE_OTHER


def _is_image(path: str) -> bool:
    lower = path.lower()
    if lower.endswith('.9.png'):
        return True
    return Path(lower).suffix in _IMAGE_EXTS


def group_by_subtype(result: ApkSizeResult) -> Dict[str, Dict]:
    """按资源子类型汇总 res/ 下资源

    :return: {subtype: {'count': int, 'compressed': int, 'uncompressed': int,
                        'entries': List[FileEntry]}}
    """
    groups: Dict[str, Dict] = {}
    for e in result.entries:
        if e.category != FileCategory.RESOURCE:
            continue
        sub = _subtype_of_res(e.path)
        g = groups.get(sub)
        if g is None:
            g = {'count': 0, 'compressed': 0, 'uncompressed': 0, 'entries': []}
            groups[sub] = g
        g['count'] += 1
        g['compressed'] += e.compressed_size
        g['uncompressed'] += e.uncompressed_size
        g['entries'].append(e)
    return groups


def find_large_images(result: ApkSizeResult,
                      threshold: int = LARGE_IMAGE_THRESHOLD,
                      top_n: int = 50) -> List[FileEntry]:
    """找出 res/ 和 assets/ 下的大图片（非 WebP）"""
    candidates: List[FileEntry] = []
    for e in result.entries:
        lower = e.path.lower()
        if not _is_image(lower):
            continue
        if lower.endswith('.webp'):
            continue  # 已经是 WebP
        if e.compressed_size < threshold:
            continue
        candidates.append(e)

    candidates.sort(key=lambda x: x.compressed_size, reverse=True)
    return candidates[:top_n]


def count_density_variants(result: ApkSizeResult) -> Dict[str, int]:
    """统计各密度 drawable/mipmap 目录的文件数

    返回 {density_folder: file_count}，如 {'drawable-hdpi': 120}
    """
    counts: Dict[str, int] = {}
    for e in result.entries:
        if e.category != FileCategory.RESOURCE:
            continue
        parts = e.path.replace('\\', '/').split('/')
        if len(parts) < 3:
            continue
        folder = parts[1]
        if folder.startswith('drawable') or folder.startswith('mipmap'):
            counts[folder] = counts.get(folder, 0) + 1
    return counts
