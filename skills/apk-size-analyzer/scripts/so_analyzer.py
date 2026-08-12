#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
so_analyzer.py
Native SO 分析器：按 ABI 统计 + 压缩存储状态检测
"""

from pathlib import Path
from typing import List

from models import (
    ApkSizeResult, SoInfo, AbiStats, FileCategory, COMPRESS_STORED,
)


# 已知 ABI（用于校验路径段）
_KNOWN_ABIS = {
    'arm64-v8a', 'armeabi-v7a', 'armeabi',
    'x86', 'x86_64', 'mips', 'mips64', 'riscv64',
}


def _extract_abi(path: str) -> str:
    """从 lib/{abi}/xxx.so 提取 abi 段"""
    parts = path.replace('\\', '/').split('/')
    if len(parts) >= 3 and parts[0].lower() == 'lib':
        return parts[1]
    return 'unknown'


def analyze_so(result: ApkSizeResult) -> List[SoInfo]:
    """分析 APK 中所有 .so 文件

    :param result: apk_parser 产出的 ApkSizeResult
    :return: SoInfo 列表（同时写入 result.so_infos / result.abi_stats）
    """
    so_entries = [e for e in result.entries if e.category == FileCategory.NATIVE]

    so_infos: List[SoInfo] = []
    abi_stats: dict = {}

    for entry in so_entries:
        abi = _extract_abi(entry.path)
        info = SoInfo(
            path=entry.path,
            name=Path(entry.path).name,
            abi=abi,
            compressed_size=entry.compressed_size,
            uncompressed_size=entry.uncompressed_size,
            is_stored=(entry.compress_type == COMPRESS_STORED),
        )
        so_infos.append(info)

        stats = abi_stats.get(abi)
        if stats is None:
            stats = AbiStats(abi=abi)
            abi_stats[abi] = stats
        stats.file_count += 1
        stats.total_compressed += info.compressed_size
        stats.total_uncompressed += info.uncompressed_size

    # 排序：先按 abi 归组，再按压缩后大小降序
    so_infos.sort(key=lambda s: (s.abi, -s.compressed_size))

    result.so_infos = so_infos
    result.abi_stats = abi_stats
    return so_infos


def is_known_abi(abi: str) -> bool:
    """是否为已知 ABI"""
    return abi in _KNOWN_ABIS
