#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image_extractor.py
从 APK/AAB/AAR 解压可优化图片（>=100KB）到 HTML 同目录的 assets 子目录，
供 HTML 报告做缩略图预览。

设计原则：
- 全量解压（不截断 Top N），列表来自 apk_parser._collect_optimizable_images
- 设一个极大兜底值避免极端项目撑爆磁盘
- 文件名加序号前缀避免冲突（001_splash.png、002_ic_launcher.png）
- 目录结构：{html_stem}_assets/images/
- 失败单张跳过，不影响整体报告
"""

import os
import re
import struct
import zipfile
from pathlib import Path
from typing import List, Tuple, Optional

from models import FileEntry


# 极端情况下的兜底上限（正常项目不会触达）
MAX_EXTRACT = 1000


def _safe_filename(name: str) -> str:
    """把 APK 内路径转成安全的文件名片段（去斜杠、特殊字符）"""
    basename = os.path.basename(name)
    # 替换可能引起问题的字符
    safe = re.sub(r'[^\w\.\-]+', '_', basename)
    # 防止空名
    return safe or 'image'


def extract_optimizable_images(
    archive_path: str,
    images: List[FileEntry],
    output_dir: str,
    max_count: int = MAX_EXTRACT,
) -> List[Tuple[FileEntry, Optional[str], Optional[Tuple[int, int]]]]:
    """从 APK 中解压命中的可优化图片到 output_dir（默认全量，不截断）。

    :param archive_path: APK/AAB/AAR 路径
    :param images: 候选图片列表（已按大小降序）
    :param output_dir: 输出目录（如 `{report}_assets/images/`）
    :param max_count: 最大解压张数
    :return: List[(entry, local_name 或 None, (w,h) 或 None)]
             local_name 为 None 表示解压失败；(w,h) 为 None 表示读分辨率失败
    """
    if not images:
        return []

    os.makedirs(output_dir, exist_ok=True)

    picked = images[:max_count]
    results: List[Tuple[FileEntry, Optional[str], Optional[Tuple[int, int]]]] = []

    try:
        with zipfile.ZipFile(archive_path, 'r') as zf:
            for idx, entry in enumerate(picked, 1):
                local_name = _extract_one(zf, entry, output_dir, idx)
                size_wh: Optional[Tuple[int, int]] = None
                if local_name:
                    size_wh = read_image_size(
                        os.path.join(output_dir, local_name))
                results.append((entry, local_name, size_wh))
    except (zipfile.BadZipFile, OSError) as e:
        # 整个 zip 打不开，直接退化：所有图片 local_path=None
        for entry in picked:
            results.append((entry, None, None))
        print(f"⚠️  图片解压失败（zip 异常）：{e}")

    return results


def _extract_one(zf: zipfile.ZipFile, entry: FileEntry,
                 output_dir: str, idx: int) -> Optional[str]:
    """解压单张图片，返回相对 output_dir 的文件名（失败返回 None）"""
    try:
        safe_name = _safe_filename(entry.path)
        # 序号前缀：确保与表格顺序一致，且避免重名
        local_name = f"{idx:03d}_{safe_name}"
        local_path = os.path.join(output_dir, local_name)

        with zf.open(entry.path) as src, open(local_path, 'wb') as dst:
            dst.write(src.read())

        return local_name
    except Exception:
        return None


def read_image_size(path: str) -> Optional[Tuple[int, int]]:
    """纯 stdlib 读图片宽高（零依赖），支持 PNG / JPG / WebP / GIF / BMP。

    失败（格式未知、文件损坏、IO 异常）一律返回 None，调用方需做兜底。
    只读前 ~64 字节，不加载像素数据，对几百张图无性能压力。
    """
    try:
        with open(path, 'rb') as f:
            head = f.read(32)
            if len(head) < 16:
                return None

            # PNG：8B 签名 + IHDR 块；宽高在偏移 16/20（big-endian u32）
            if head[:8] == b'\x89PNG\r\n\x1a\n':
                w, h = struct.unpack('>II', head[16:24])
                return (w, h)

            # GIF：'GIF87a'/'GIF89a' + width(u16 LE) + height(u16 LE)
            if head[:6] in (b'GIF87a', b'GIF89a'):
                w, h = struct.unpack('<HH', head[6:10])
                return (w, h)

            # BMP：'BM' + ...宽高在偏移 18/22（u32 LE）
            if head[:2] == b'BM':
                w, h = struct.unpack('<ii', head[18:26])
                return (abs(w), abs(h))

            # WebP：'RIFF' + size + 'WEBP' + chunk
            if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
                chunk = head[12:16]
                if chunk == b'VP8 ':
                    # Simple lossy：宽高在 frame tag 之后（偏移 26/28，14bit）
                    f.seek(26)
                    wh = f.read(4)
                    if len(wh) == 4:
                        w = struct.unpack('<H', wh[0:2])[0] & 0x3FFF
                        h = struct.unpack('<H', wh[2:4])[0] & 0x3FFF
                        return (w, h)
                elif chunk == b'VP8L':
                    # Lossless：偏移 21 起 4 字节打包 14bit(w-1)+14bit(h-1)
                    f.seek(21)
                    b = f.read(4)
                    if len(b) == 4:
                        b0, b1, b2, b3 = b[0], b[1], b[2], b[3]
                        w = 1 + (((b1 & 0x3F) << 8) | b0)
                        h = 1 + (((b3 & 0x0F) << 10) | (b2 << 2)
                                 | ((b1 & 0xC0) >> 6))
                        return (w, h)
                elif chunk == b'VP8X':
                    # Extended：偏移 24 起 3 字节(w-1) + 3 字节(h-1)，小端
                    f.seek(24)
                    b = f.read(6)
                    if len(b) == 6:
                        w = 1 + (b[0] | (b[1] << 8) | (b[2] << 16))
                        h = 1 + (b[3] | (b[4] << 8) | (b[5] << 16))
                        return (w, h)
                return None

            # JPEG：扫描 SOF0/SOF2 帧段（FFC0/FFC2 等），取高/宽
            if head[:2] == b'\xff\xd8':
                f.seek(2)
                while True:
                    b = f.read(1)
                    if not b:
                        return None
                    if b != b'\xff':
                        continue
                    # 跳过填充的 0xFF
                    while b == b'\xff':
                        b = f.read(1)
                        if not b:
                            return None
                    marker = b[0]
                    # SOF0..SOF15（排除 DHT=C4/JPG=C8/DAC=CC）
                    if (0xC0 <= marker <= 0xCF
                            and marker not in (0xC4, 0xC8, 0xCC)):
                        f.read(3)  # segment length(2) + precision(1)
                        hw = f.read(4)
                        if len(hw) == 4:
                            h, w = struct.unpack('>HH', hw)
                            return (w, h)
                        return None
                    # 其他段：读长度跳过
                    seg_len_raw = f.read(2)
                    if len(seg_len_raw) < 2:
                        return None
                    seg_len = struct.unpack('>H', seg_len_raw)[0]
                    if seg_len < 2:
                        return None
                    f.seek(seg_len - 2, os.SEEK_CUR)
                return None

            return None
    except Exception:
        return None
