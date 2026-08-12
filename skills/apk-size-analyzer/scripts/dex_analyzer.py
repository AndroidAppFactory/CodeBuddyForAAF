#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dex_analyzer.py
DEX 分析器：读取 DEX 文件头，解析方法数 / 类数 / 字符串数

DEX header (standard dex-035..040) layout (little endian):
  offset 0    : 8 bytes   magic "dex\n035\0"
  offset 8    : 4 bytes   checksum
  offset 12   : 20 bytes  sha1 signature
  offset 32   : 4 bytes   file_size
  offset 36   : 4 bytes   header_size  (0x70)
  offset 40   : 4 bytes   endian_tag
  offset 44   : 4 bytes   link_size
  offset 48   : 4 bytes   link_off
  offset 52   : 4 bytes   map_off
  offset 56   : 4 bytes   string_ids_size
  offset 60   : 4 bytes   string_ids_off
  offset 64   : 4 bytes   type_ids_size
  offset 68   : 4 bytes   type_ids_off
  offset 72   : 4 bytes   proto_ids_size
  offset 76   : 4 bytes   proto_ids_off
  offset 80   : 4 bytes   field_ids_size
  offset 84   : 4 bytes   field_ids_off
  offset 88   : 4 bytes   method_ids_size   <-- 方法数
  offset 92   : 4 bytes   method_ids_off
  offset 96   : 4 bytes   class_defs_size   <-- 类数
"""

import struct
import zipfile
from typing import List

from models import ApkSizeResult, DexInfo, FileCategory


DEX_HEADER_SIZE = 112
DEX_MAGIC_PREFIX = b'dex\n'


def analyze_dex(apk_path: str, result: ApkSizeResult) -> List[DexInfo]:
    """分析 APK 中所有 .dex 文件

    :param apk_path: APK 路径
    :param result: apk_parser 产出的 ApkSizeResult
    :return: DexInfo 列表（同时写入 result.dex_infos）
    """
    dex_entries = [e for e in result.entries if e.category == FileCategory.DEX]
    if not dex_entries:
        result.dex_infos = []
        return []

    infos: List[DexInfo] = []
    with zipfile.ZipFile(apk_path, 'r') as zf:
        for entry in dex_entries:
            info = _parse_dex_entry(zf, entry.path,
                                    entry.compressed_size,
                                    entry.uncompressed_size)
            infos.append(info)

    # 按文件名排序（classes.dex, classes2.dex, classes3.dex ...）
    infos.sort(key=lambda d: d.path)
    result.dex_infos = infos
    return infos


def _parse_dex_entry(zf: zipfile.ZipFile, path: str,
                     compressed_size: int, uncompressed_size: int) -> DexInfo:
    """读取单个 dex 文件头并解析"""
    info = DexInfo(
        path=path,
        compressed_size=compressed_size,
        uncompressed_size=uncompressed_size,
    )

    try:
        with zf.open(path, 'r') as f:
            header = f.read(DEX_HEADER_SIZE)
    except Exception as e:
        info.magic_valid = False
        info.error = f"读取 DEX 头失败: {e}"
        return info

    if len(header) < DEX_HEADER_SIZE:
        info.magic_valid = False
        info.error = f"DEX 头长度不足（{len(header)}/{DEX_HEADER_SIZE}）"
        return info

    if not header.startswith(DEX_MAGIC_PREFIX):
        info.magic_valid = False
        info.error = f"DEX magic 错误: {header[:8]!r}"
        return info

    try:
        # 一次性解出 string / type / proto / field / method_ids_size + method_ids_off + class_defs_size
        # 从 offset 56 起，共 11 个 uint32（直到 offset 100）
        values = struct.unpack_from('<11I', header, 56)
        string_ids_size = values[0]
        # type_ids_size    = values[2]
        # proto_ids_size   = values[4]
        # field_ids_size   = values[6]
        method_ids_size = values[8]
        class_defs_size = values[10]

        info.string_count = string_ids_size
        info.method_count = method_ids_size
        info.class_count = class_defs_size
    except struct.error as e:
        info.magic_valid = False
        info.error = f"DEX 头解析失败: {e}"

    return info
