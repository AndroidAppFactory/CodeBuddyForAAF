#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resource_usage_finder.py
图片资源源码反查：对每张可优化图片的资源名，扫描 Android 工程源码找出引用位置。

按 APK 内路径对图片分为 4 类，分别使用不同的反查策略：

| 类别        | APK 路径特征           | 静态引用（static）                                              | 动态引用（dynamic）                              |
|-------------|-----------------------|----------------------------------------------------------------|------------------------------------------------|
| assets      | assets/...            | "rel_path" / file:///android_asset/rel / "android_asset/rel"  | "basename.ext" / "basename"                    |
| res/raw     | res/raw*/...          | @raw/name / R.raw.name                                         | "name"                                         |
| drawable    | res/drawable*/... 或   | @drawable/name / @mipmap/name / R.drawable.name / R.mipmap.name | "name" / "name.ext"                           |
|             | res/mipmap*/...        |                                                                |                                                |
| generic res | res/{type}*/...       | @{type}/name / R.{type}.name                                   | "name"                                         |

可信度三档：
- 🟢 static  — 明确的资源引用语法
- 🟡 dynamic — 字符串字面量（可能是 getIdentifier / AssetManager.open / WebView url 等）
- 🔴 none    — 未找到任何引用

仅依赖 Python 3.6+ 标准库，使用 os.walk 扫描源码，不依赖 ripgrep。
对大工程做了路径过滤（跳过 build / .gradle / .idea / node_modules 等目录）避免慢。
"""

import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from models import FileEntry, ImageUsage, ImageUsageRef


# ============================================================================
# 常量
# ============================================================================

# 扫描源码时需要跳过的目录（相对路径片段）
_SKIP_DIRS = {
    'build', '.gradle', '.idea', '.git', '.svn', '.hg',
    'node_modules', 'out', '.cxx', 'captures', '.externalNativeBuild',
    # 产物 / 中间目录
    'bin', 'gen', 'dist', '.kotlin', '.dart_tool',
}

# XML 源文件扩展名
_XML_EXTS = {'.xml'}
# Kotlin/Java 源文件扩展名
_CODE_EXTS = {'.kt', '.kts', '.java'}
# Web / 配置 / 纯文本类扩展名（主要为 assets 动态引用兜底）
_TEXT_EXTS = {
    '.html', '.htm', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx',
    '.json', '.json5', '.css', '.scss', '.less',
    '.md', '.txt', '.properties', '.yaml', '.yml', '.toml',
}

# 单行代码片段最长截断长度（避免超长行撑破 HTML）
_SNIPPET_MAX = 160

# 单张图片最多收集的引用条目（截断，避免 UI 爆炸）
_MAX_REFS_PER_IMAGE = 50

# 单张图片名称长度下限（< 4 的名字不做 dynamic 字符串匹配，避免噪声，如 "a"、"ic"）
_DYNAMIC_MIN_NAME_LEN = 4


# ============================================================================
# 工具：图片分类 + 名称推断
# ============================================================================

# APK 内路径前缀识别
_RE_ASSETS = re.compile(r'^assets/', re.IGNORECASE)
_RE_RES_RAW = re.compile(r'^res/raw[^/]*/', re.IGNORECASE)
_RE_RES_DRAWABLE = re.compile(r'^res/(?:drawable|mipmap)[^/]*/', re.IGNORECASE)
_RE_RES_GENERIC = re.compile(r'^res/([a-z]+)[^/]*/', re.IGNORECASE)


def _categorize_image(apk_path: str) -> str:
    """按 APK 内路径对图片分类。

    返回：'assets' / 'raw' / 'drawable' / 'generic' / 'unknown'
    """
    p = apk_path.replace('\\', '/').lstrip('/')
    if _RE_ASSETS.match(p):
        return 'assets'
    if _RE_RES_RAW.match(p):
        return 'raw'
    if _RE_RES_DRAWABLE.match(p):
        return 'drawable'
    if _RE_RES_GENERIC.match(p):
        return 'generic'
    return 'unknown'


def _strip_extension(name: str) -> str:
    """去 .9.png / .png / .webp 等扩展名"""
    if name.lower().endswith('.9.png'):
        return name[:-6]
    dot = name.rfind('.')
    if dot > 0:
        return name[:dot]
    return name


def _extract_res_type(apk_path: str) -> str:
    """从 res/{type}.../name.ext 提取资源类型（drawable/mipmap/raw/xml/...）

    找不到返回空串。
    """
    p = apk_path.replace('\\', '/').lstrip('/')
    m = _RE_RES_GENERIC.match(p)
    if m:
        return m.group(1).lower()
    return ''


def _assets_rel_path(apk_path: str) -> str:
    """从 assets/xxx/yyy.png 提取相对 assets 的子路径 xxx/yyy.png"""
    p = apk_path.replace('\\', '/').lstrip('/')
    if p.lower().startswith('assets/'):
        return p[len('assets/'):]
    return ''


def _resource_key_from_apk_path(apk_path: str) -> Tuple[str, str]:
    """从 APK 内路径反推「资源 key」和「展示名」。

    返回 (key, display_name)：
    - assets：key = 相对路径 (如 img/banner.png)，display_name = 基础名
    - res/*：key = 资源名（去扩展名），display_name = 资源名
    """
    category = _categorize_image(apk_path)
    basename = os.path.basename(apk_path)
    if category == 'assets':
        rel = _assets_rel_path(apk_path)
        return rel, basename
    # res/* 统一去扩展名
    stem = _strip_extension(basename)
    return stem, stem


def _ui_hint_from_refs(refs: List[ImageUsageRef]) -> str:
    """从引用文件路径推断界面归属（如 activity_login.xml -> LoginActivity）

    只基于 XML 布局文件名的约定俗成规则，找不到就返回空串。
    """
    activity_names = []
    fragment_names = []
    dialog_names = []
    for r in refs:
        fn = os.path.basename(r.file).lower()
        if not fn.endswith('.xml'):
            continue
        stem = fn[:-4]
        if stem.startswith('activity_'):
            activity_names.append(_snake_to_camel(stem[len('activity_'):]) + 'Activity')
        elif stem.startswith('fragment_'):
            fragment_names.append(_snake_to_camel(stem[len('fragment_'):]) + 'Fragment')
        elif stem.startswith('dialog_'):
            dialog_names.append(_snake_to_camel(stem[len('dialog_'):]) + 'Dialog')
    # 去重并拼接
    result_parts = []
    seen: Set[str] = set()
    for name in activity_names + fragment_names + dialog_names:
        if name not in seen:
            seen.add(name)
            result_parts.append(name)
    return ', '.join(result_parts[:3])


def _snake_to_camel(s: str) -> str:
    parts = [p for p in s.split('_') if p]
    return ''.join(p[:1].upper() + p[1:] for p in parts)


# ============================================================================
# 工具：源码扫描
# ============================================================================

def _iter_source_files(project_root: str,
                       include_text: bool) -> Iterable[Tuple[str, str]]:
    """遍历项目源码文件，yield (abs_path, kind)

    kind: 'xml' / 'code' / 'text'
    include_text: 是否包含 html/js/json/... 等纯文本类（assets 场景需要）
    """
    root_abs = os.path.abspath(project_root)
    for dirpath, dirnames, filenames in os.walk(root_abs):
        # 跳过黑名单目录（就地修改 dirnames 生效于后续遍历）
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in _XML_EXTS:
                yield os.path.join(dirpath, fn), 'xml'
            elif ext in _CODE_EXTS:
                yield os.path.join(dirpath, fn), 'code'
            elif include_text and ext in _TEXT_EXTS:
                yield os.path.join(dirpath, fn), 'text'


class _ImagePatterns:
    """单张图片的所有正则策略集合。

    按类别不同，填充不同的 pattern：
    - static_xml / static_code：明确的资源引用语法
    - dynamic：字符串字面量
    """
    __slots__ = ('category', 'static_xml', 'static_code', 'dynamic')

    def __init__(self, category: str):
        self.category: str = category
        self.static_xml: List[re.Pattern] = []
        self.static_code: List[re.Pattern] = []
        self.dynamic: List[re.Pattern] = []


def _compile_one(apk_path: str, key: str) -> _ImagePatterns:
    """为一张图片按类别编译正则集。"""
    pats = _ImagePatterns(category=_categorize_image(apk_path))
    basename = os.path.basename(apk_path)
    basename_stem = _strip_extension(basename)

    if pats.category == 'assets':
        rel = key  # key 已经是 assets 相对路径 (如 img/desert.jpg)
        rel_esc = re.escape(rel)
        base_esc = re.escape(basename)
        stem_esc = re.escape(basename_stem)
        # static 1：完整相对路径作为字面量（"img/desert.jpg"）
        pats.static_xml.append(re.compile(rf'["\'(]{rel_esc}["\')]'))
        pats.static_code.append(re.compile(rf'["\'(]{rel_esc}["\')]'))
        # static 2：以 basename 结尾的 URL 路径（支持 "../img/desert.jpg"、"/assets/img/desert.jpg" 等）
        #          前置必须是路径分隔符，后置必须是非资源名字符，避免误匹配 xxxdesert.jpg
        pats.static_xml.append(re.compile(rf'[/\\]{base_esc}(?![A-Za-z0-9_.])'))
        pats.static_code.append(re.compile(rf'[/\\]{base_esc}(?![A-Za-z0-9_.])'))
        # static 3：file:///android_asset/xxx 或 android_asset/xxx 前缀
        pats.static_xml.append(re.compile(rf'android_asset/{rel_esc}(?![A-Za-z0-9_/])'))
        pats.static_code.append(re.compile(rf'android_asset/{rel_esc}(?![A-Za-z0-9_/])'))
        # dynamic：纯字符串字面量 "basename.ext" / "basename"
        if len(basename) >= _DYNAMIC_MIN_NAME_LEN:
            pats.dynamic.append(re.compile(rf'["\']{base_esc}["\']'))
        if len(basename_stem) >= _DYNAMIC_MIN_NAME_LEN and basename_stem != basename:
            pats.dynamic.append(re.compile(rf'["\']{stem_esc}["\']'))

    elif pats.category == 'raw':
        name_esc = re.escape(key)
        pats.static_xml.append(re.compile(rf'@raw/{name_esc}(?![A-Za-z0-9_])'))
        pats.static_code.append(re.compile(rf'\bR\.raw\.{name_esc}(?![A-Za-z0-9_])'))
        if len(key) >= _DYNAMIC_MIN_NAME_LEN:
            pats.dynamic.append(re.compile(rf'["\']{name_esc}["\']'))

    elif pats.category == 'drawable':
        name_esc = re.escape(key)
        base_esc = re.escape(basename)
        # XML：@drawable/xxx 或 @mipmap/xxx
        pats.static_xml.append(
            re.compile(rf'@(?:drawable|mipmap)/{name_esc}(?![A-Za-z0-9_])'))
        # 代码：R.drawable.xxx / R.mipmap.xxx
        pats.static_code.append(
            re.compile(rf'\bR\.(?:drawable|mipmap)\.{name_esc}(?![A-Za-z0-9_])'))
        # dynamic：资源名 / 带扩展名的基础名（有些框架按 "xxx.png" 用）
        if len(key) >= _DYNAMIC_MIN_NAME_LEN:
            pats.dynamic.append(re.compile(rf'["\']{name_esc}["\']'))
        if basename != key and len(basename) >= _DYNAMIC_MIN_NAME_LEN:
            pats.dynamic.append(re.compile(rf'["\']{base_esc}["\']'))

    elif pats.category == 'generic':
        name_esc = re.escape(key)
        res_type = _extract_res_type(apk_path)
        if res_type:
            type_esc = re.escape(res_type)
            pats.static_xml.append(
                re.compile(rf'@{type_esc}/{name_esc}(?![A-Za-z0-9_])'))
            pats.static_code.append(
                re.compile(rf'\bR\.{type_esc}\.{name_esc}(?![A-Za-z0-9_])'))
        if len(key) >= _DYNAMIC_MIN_NAME_LEN:
            pats.dynamic.append(re.compile(rf'["\']{name_esc}["\']'))

    # unknown 类别：不填任何正则（扫描时会被跳过）
    return pats


def _compile_patterns(images: List[FileEntry]) -> Dict[str, _ImagePatterns]:
    """为所有待查图片预编译正则集合，key 是该图片的资源 key。

    注意：不同 APK 路径可能映射到同一个 key（比如多密度 drawable），
    这里取第一个路径编译的结果；若后续出现冲突会以先到者为准。
    """
    compiled: Dict[str, _ImagePatterns] = {}
    for entry in images:
        key, _ = _resource_key_from_apk_path(entry.path)
        if not key or key in compiled:
            continue
        compiled[key] = _compile_one(entry.path, key)
    return compiled


def _truncate_snippet(line: str) -> str:
    line = line.rstrip('\n').rstrip('\r').strip()
    if len(line) > _SNIPPET_MAX:
        return line[:_SNIPPET_MAX] + '…'
    return line


# ============================================================================
# 主入口
# ============================================================================

def find_image_usages(project_root: str,
                      images: List[FileEntry]) -> List[ImageUsage]:
    """扫描项目源码，为每张图片找出引用位置。

    :param project_root: Android 工程根目录（包含 settings.gradle）
    :param images: 待查的图片条目（通常是 result.optimizable_images）
    :return: ImageUsage 列表，顺序与 images 一致；未找到引用的也会包含（confidence=red）
    """
    if not project_root or not os.path.isdir(project_root) or not images:
        return []

    # 1. 建立 key -> ImageUsage 索引，保留原始顺序
    #    对 res/* 类图片，同一资源名的多密度变体共用同一份 refs
    usages_by_key: Dict[str, ImageUsage] = {}
    order: List[Tuple[str, FileEntry]] = []
    for entry in images:
        key, display_name = _resource_key_from_apk_path(entry.path)
        if not key:
            continue
        if key not in usages_by_key:
            usages_by_key[key] = ImageUsage(
                resource_name=display_name, apk_path=entry.path, refs=[])
        order.append((key, entry))

    if not usages_by_key:
        return []

    # 2. 预编译正则；同时判断是否需要扫描 text 类文件
    #    只要存在 assets 类图片就启用 text 扫描（html/js/json 中的 url 引用）
    patterns_by_key = _compile_patterns(images)
    need_text_scan = any(p.category == 'assets' for p in patterns_by_key.values())

    # 3. 遍历源码文件，逐行扫描
    root_abs = os.path.abspath(project_root)
    for abs_path, kind in _iter_source_files(project_root, include_text=need_text_scan):
        rel_path = os.path.relpath(abs_path, root_abs)
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_no, line in enumerate(f, 1):
                    _scan_line(line, line_no, rel_path, kind,
                               usages_by_key, patterns_by_key)
        except (OSError, UnicodeDecodeError):
            continue  # 忽略无法读取的文件

    # 4. 推断界面归属 + 截断 refs 数量 + 去重
    for usage in usages_by_key.values():
        usage.refs = _dedup_refs(usage.refs)
        usage.ui_hint = _ui_hint_from_refs(usage.refs)
        if len(usage.refs) > _MAX_REFS_PER_IMAGE:
            usage.refs = usage.refs[:_MAX_REFS_PER_IMAGE]

    # 5. 按 images 原始顺序返回（同 key 的变体各自一个 ImageUsage，引用信息相同）
    results: List[ImageUsage] = []
    for key, entry in order:
        base = usages_by_key[key]
        results.append(ImageUsage(
            resource_name=base.resource_name,
            apk_path=entry.path,
            refs=list(base.refs),
            ui_hint=base.ui_hint,
        ))
    return results


def _dedup_refs(refs: List[ImageUsageRef]) -> List[ImageUsageRef]:
    """按 (file, line, kind) 去重，保留首次出现顺序。同一行被多个正则匹配时只保留一条。"""
    seen: Set[Tuple[str, int, str]] = set()
    result: List[ImageUsageRef] = []
    # static 优先于 dynamic：先留 static
    for r in refs:
        sig = (r.file, r.line, r.kind)
        if sig in seen:
            continue
        # 如果同位置已经有 static，就不再追加 dynamic
        if r.kind == 'dynamic' and (r.file, r.line, 'static') in seen:
            continue
        seen.add(sig)
        result.append(r)
    return result


def _scan_line(line: str, line_no: int, rel_path: str, kind: str,
               usages_by_key: Dict[str, ImageUsage],
               patterns_by_key: Dict[str, '_ImagePatterns']) -> None:
    """扫描单行，把命中的资源记录到 usages_by_key

    对性能敏感：一行可能同时命中多个资源名，所以要全部遍历。
    """
    # 提前短路：若一行中既没有 @ 也没有 R. 也没有引号也没有 android_asset 则跳过
    if ('@' not in line and 'R.' not in line and
            '"' not in line and "'" not in line and
            'android_asset' not in line):
        return

    snippet_cache: Optional[str] = None
    for key, usage in usages_by_key.items():
        pats = patterns_by_key.get(key)
        if pats is None:
            continue

        # 快速子串预判（正则前置优化）
        # 对 assets 用 basename 或 stem 做子串判断；其他用 key
        basename = os.path.basename(usage.apk_path)
        if pats.category == 'assets':
            stem = _strip_extension(basename)
            # 匹配 key（相对路径）、basename、stem 三者任一都可能命中
            if (key not in line and basename not in line
                    and (not stem or stem not in line)):
                continue
        else:
            if key not in line and (basename == key or basename not in line):
                continue

        # static 匹配（按 kind 选择不同的正则集）
        is_static = False
        if kind == 'xml':
            for pat in pats.static_xml:
                if pat.search(line):
                    is_static = True
                    break
        else:  # 'code' / 'text'
            for pat in pats.static_code:
                if pat.search(line):
                    is_static = True
                    break
            # assets 的 static 正则在 xml/code/text 都适用（url 字面量）
            if not is_static and pats.category == 'assets':
                for pat in pats.static_xml:
                    if pat.search(line):
                        is_static = True
                        break

        if is_static:
            if snippet_cache is None:
                snippet_cache = _truncate_snippet(line)
            usage.refs.append(ImageUsageRef(
                file=rel_path, line=line_no,
                snippet=snippet_cache, kind='static'))
            continue

        # dynamic 匹配（字符串字面量）
        for pat in pats.dynamic:
            if pat.search(line):
                if snippet_cache is None:
                    snippet_cache = _truncate_snippet(line)
                usage.refs.append(ImageUsageRef(
                    file=rel_path, line=line_no,
                    snippet=snippet_cache, kind='dynamic'))
                break
