#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compress_script_generator.py
生成批量图片压缩清单（TinyPNG 版）：
  - 根据 optimizable_images 反查每张图在工程中的真实源路径，生成 compress_images.list
  - 未找到源路径的图以注释行 "# SKIPPED: ..." 记录
  - 脚本本体（compress_images.sh）常驻 skill 目录，不再复制到报告产物中
    用户通过 `bash {skill_script} --list {生成的 list}` 调用

清单格式（第 1 列 = 工程源文件真实绝对路径，脚本据此原地替换）：

    /abs/src_main_res_drawable_xxxhdpi/ic_launcher.png | res/drawable-xxxhdpi/ic_launcher.png | 245678

触发条件（由调用方把控）：
  - 仅 APK（非 AAB/AAR）
  - 有有效的 project_root
  - optimizable_images 非空

设计原则：
  - 尊重现有 image_extractor 的副本目录结构（共用 {report}_assets/），不另起目录
  - 不做 WebP 转换：所有候选图都是同格式压缩（PNG→PNG、JPG→JPG）
  - 9-patch（*.9.png）直接标 SKIPPED，脚本内也再兜一层
  - 源路径反查：按 APK 内路径后缀在工程内匹配，命中多个（flavor）则全部写入
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from models import FileEntry


# 不支持 TinyPNG 压缩的扩展名（提前过滤）
_SUPPORTED_EXTS = {'.png', '.jpg', '.jpeg'}

# 源文件反查时跳过的目录（与 resource_usage_finder 保持一致）
_SKIP_DIRS = {
    'build', '.gradle', '.idea', '.git', '.svn', '.hg',
    'node_modules', 'out', '.cxx', 'captures', '.externalNativeBuild',
    'bin', 'gen', 'dist', '.kotlin', '.dart_tool',
}


# ============================================================================
# 工具函数
# ============================================================================

def _is_9_patch(apk_path: str) -> bool:
    return apk_path.lower().endswith('.9.png')


def _apk_path_suffix(apk_path: str) -> str:
    """从 APK 内路径构造工程内可能的尾部匹配片段。

    APK 内: `res/drawable-xxxhdpi/ic_launcher.png`
       → 工程内应匹配 `src/main/res/drawable-xxxhdpi/ic_launcher.png`
                或 `src/debug/res/drawable-xxxhdpi/ic_launcher.png`
                等。所以我们用 `res/.../xxx` 作为尾部匹配即可。

    APK 内: `assets/splash.jpg`
       → 工程内 `src/main/assets/splash.jpg`

    这里返回归一化后、使用 `/` 分隔的尾部片段（不含前导分隔符）。
    """
    p = apk_path.replace('\\', '/').lstrip('/')
    return p


def _build_project_index(project_root: str) -> Dict[str, List[str]]:
    """遍历 project_root，建立 basename -> [绝对路径列表] 的索引。

    只索引扩展名为 png/jpg/jpeg 的文件，跳过构建产物目录。
    """
    index: Dict[str, List[str]] = {}
    root_abs = os.path.abspath(project_root)
    for dirpath, dirnames, filenames in os.walk(root_abs):
        # 就地修改 dirnames 以阻止 os.walk 进入黑名单目录
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in _SUPPORTED_EXTS:
                continue
            abs_path = os.path.join(dirpath, fn)
            index.setdefault(fn, []).append(abs_path)
    return index


def _resolve_sources(apk_path: str,
                     project_index: Dict[str, List[str]]) -> List[str]:
    """为一条 APK 内路径找出工程内的真实源文件路径（可能多个，对应多 flavor）。

    匹配策略：
      1. 用 basename 查索引拿到候选集合
      2. 过滤出「绝对路径以 APK 内路径为结尾」的候选（用 `/` 归一化对比）
         - 例如 APK 内 `res/drawable-xxxhdpi/ic.png`
           对应候选路径 `<root>/app/src/main/res/drawable-xxxhdpi/ic.png`（命中）
           `<root>/libX/src/main/res/drawable-xxxhdpi/ic.png`（也命中，多 flavor/module）
      3. 若 2 无命中，退化到仅按 basename 命中的候选（避免路径结构不规则的工程漏掉）
         但此时要求 basename 的候选唯一，否则无法确定是哪一张，返回空。
    """
    suffix = _apk_path_suffix(apk_path)
    basename = os.path.basename(suffix)

    candidates = project_index.get(basename, [])
    if not candidates:
        return []

    # 严格匹配：归一化后以 suffix 结尾
    suffix_norm = '/' + suffix  # 确保是路径片段边界
    strict = []
    for c in candidates:
        c_norm = c.replace('\\', '/')
        if c_norm.endswith(suffix_norm) or c_norm.endswith(suffix):
            strict.append(c)
    if strict:
        return sorted(strict)

    # 宽松匹配（basename 唯一才使用，避免误伤）
    if len(candidates) == 1:
        return list(candidates)
    return []


# ============================================================================
# 主入口
# ============================================================================

def generate_compress_assets(
    result_images: List[FileEntry],
    project_root: str,
    output_dir: str,
) -> Optional[Dict[str, object]]:
    """生成 compress_images.list 到 output_dir（不复制 shell 本体）。

    :param result_images: ApkSizeResult.optimizable_images
    :param project_root: Android 工程根目录
    :param output_dir: 输出目录（通常是 `{report}_assets/`）
    :return: 生成统计（dict）；未生成时返回 None
                {
                  'script_path': str,      # skill 内通用 shell 的绝对路径（用于提示/命令）
                  'list_path': str,        # 本次生成的 list 绝对路径
                  'resolvable': int,       # 可定位源路径的条目数
                  'unresolved': int,       # 无法定位的条目数（写入 # SKIPPED）
                  'total': int,            # 清单总条目数（resolvable + unresolved）
                }
             None 的情况：
                - project_root 不存在 / 不是目录
                - result_images 为空
                - 过滤后没有任何 PNG/JPG（全是 WebP 或 9-patch）
    """
    if not project_root or not os.path.isdir(project_root):
        return None
    if not result_images:
        return None

    # 1. 过滤：只保留 png/jpg/jpeg，9-patch 标注但不压缩
    candidates: List[Tuple[FileEntry, bool]] = []  # (entry, is_9patch)
    for entry in result_images:
        ext = os.path.splitext(entry.path)[1].lower()
        if ext not in _SUPPORTED_EXTS:
            continue
        candidates.append((entry, _is_9_patch(entry.path)))

    if not candidates:
        return None

    # 2. 建立工程文件索引
    project_index = _build_project_index(project_root)

    # 3. 反查每个候选的源路径
    resolvable_lines: List[str] = []
    unresolved_lines: List[str] = []
    skipped_9patch_lines: List[str] = []

    resolvable = 0
    unresolved = 0
    resolvable_sizes: List[int] = []  # 每个生成行对应的原字节数（供 HTML 阈值过滤统计）

    for entry, is_9p in candidates:
        if is_9p:
            skipped_9patch_lines.append(
                f"# SKIPPED: {entry.path} | 9-patch 资源不压缩 "
                f"| {entry.compressed_size}"
            )
            continue

        sources = _resolve_sources(entry.path, project_index)
        if not sources:
            unresolved += 1
            unresolved_lines.append(
                f"# SKIPPED: {entry.path} | not_found_in_project "
                f"| {entry.compressed_size}"
            )
            continue

        for src_abs in sources:
            resolvable += 1
            resolvable_lines.append(
                f"{src_abs} | {entry.path} | {entry.compressed_size}"
            )
            resolvable_sizes.append(int(entry.compressed_size or 0))

    # 4. 准备 skill 内通用 shell 路径（始终返回，便于提示打印）
    template_path = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'templates', 'compress_images.sh'))

    # 5. 若没有任何可定位的条目，跳过生成 list（脚本无事可做）
    if resolvable == 0:
        return {
            'script_path': template_path,
            'list_path': '',
            'resolvable': 0,
            'unresolved': unresolved,
            'total': 0,
            'sizes': [],
        }

    # 6. 准备输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 7. 生成清单文件
    list_path = os.path.join(output_dir, 'compress_images.list')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    header = [
        f"# compress_images.list",
        f"# 由 apk-size-analyzer 生成于 {now}",
        f"# 项目根: {os.path.abspath(project_root)}",
        f"#",
        f"# 格式: <source_real_path> | <apk_internal_path> | <size_bytes>",
        f"# 说明: 第 1 列为工程源文件的真实路径，脚本 --apply 时将原地替换",
        f"#       同格式压缩（PNG→PNG / JPG→JPG），不做 WebP 转换",
        f"#       压缩前会把源文件备份到 .backup/，可用 --restore 回滚",
        f"#",
        f"# 可压缩条目: {resolvable}，未找到源路径: {unresolved}"
        + (f"，9-patch 跳过: {len(skipped_9patch_lines)}"
           if skipped_9patch_lines else ""),
        "",
    ]

    body = list(resolvable_lines)

    skipped_block: List[str] = []
    if unresolved_lines or skipped_9patch_lines:
        skipped_block.append("")
        skipped_block.append("# ========== 以下条目不参与压缩 ==========")
        if unresolved_lines:
            skipped_block.append("# 工程中未找到源文件（可能来自 AAR/生成资源）：")
            skipped_block.extend(unresolved_lines)
        if skipped_9patch_lines:
            skipped_block.append("# 9-patch 资源（压缩会破坏拉伸区域，跳过）：")
            skipped_block.extend(skipped_9patch_lines)

    with open(list_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(header + body + skipped_block) + '\n')

    return {
        'script_path': template_path,
        'list_path': list_path,
        'resolvable': resolvable,
        'unresolved': unresolved,
        'total': resolvable + unresolved,
        'sizes': resolvable_sizes,
    }
