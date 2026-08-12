#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unused_resource_scanner.py
解析 Android Lint 的 XML 报告，提取 UnusedResources 条目。

策略：
- **脚本只读取 lint 报告，不执行任何 gradle 命令**。用户负责跑 lint，
  脚本负责解析与聚合。
- **多 module 聚合**：Android Lint 默认只报告「当前 module 内定义的未用资源」，
  library module 的自扫描结果落在各自的 `*/build/reports/lint-results-*.xml`。
  本扫描会在工程根下搜集**所有** module 的 lint 报告并合并去重，让 APK 瘦身看得到
  library 里的未用资源（而不只是 app module 那一份）。
- 查找优先级：具名 module > app > 根工程的报告排在最前；继续扫全工程的其他
  `*/build/reports/lint-results-*.xml` 并追加。
- 去重规则：同一 `(res_type, res_name, defined_at, line)` 视为同一条。
- 找不到任何报告时：输出多行指引，列出推荐命令与完成后的"重放本命令"，
  让用户自行在终端执行。
- 未用资源的体积通过 APK 条目倒推估算（资源名在 res/ 下匹配）

Lint XML 报告格式示例：
    <issue id="UnusedResources" severity="Warning"
           message="The resource R.drawable.ic_old is unused"
           category="Performance" ...>
        <location file="/.../res/drawable/ic_old.png" line="1" column="1"/>
    </issue>
"""

import os
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from models import FileEntry, UnusedResource


# ============================================================================
# 查找 Lint 报告
# ============================================================================

# 深度搜索的最大层级（避免全盘遍历）
_MAX_GLOB_DEPTH = 4


def _candidate_paths(app_module: str = "") -> List[str]:
    """按优先级返回候选 lint 报告相对路径。

    优先级：具名 module > 'app' 默认 > 根工程 > AGP 8+ SARIF 产物
    """
    modules: List[str] = []
    if app_module:
        modules.append(app_module)
    if 'app' not in modules:
        modules.append('app')

    suffixes = [
        'build/reports/lint-results-release.xml',
        'build/reports/lint-results-debug.xml',
        'build/reports/lint-results.xml',
    ]

    candidates: List[str] = []
    for m in modules:
        for s in suffixes:
            candidates.append(f'{m}/{s}')
    # 根工程兜底
    for s in suffixes:
        candidates.append(s)
    return candidates


def find_lint_report(project_root: str,
                     app_module: str = "") -> Optional[str]:
    """在项目根下查找 **主 lint XML 报告**（兼容旧接口）

    查找顺序：
        1. 优先 {app_module}/build/reports/...
        2. 退化到常见 app/build/reports/... 与根工程路径
        3. 退化到 glob 搜索（仅限 4 层内，避免慢）

    :return: 报告绝对路径或 None

    注意：如果需要聚合所有 module 的 lint 报告，请使用 `find_all_lint_reports`。
    """
    if not project_root or not os.path.isdir(project_root):
        return None

    root_abs = os.path.abspath(project_root)

    # 1. 按优先级尝试固定路径
    for rel in _candidate_paths(app_module):
        path = os.path.join(root_abs, rel)
        if os.path.isfile(path):
            return path

    # 2. glob 搜索（限制深度，跳过黑名单目录）
    return _glob_lint_xml(root_abs, depth=0)


def find_all_lint_reports(project_root: str,
                          app_module: str = "") -> List[str]:
    """搜集工程根下**所有 module**的 lint XML 报告（多 module 聚合用）

    扫描路径：任何 `{project_root}/*/build/reports/lint-results-*.xml`
    以及根工程下的同名文件。

    返回顺序：
        1. 主 module 的报告（app_module 指定的 > 'app' > 根工程）排在最前
        2. 其他 module 按路径字典序

    :return: 报告绝对路径列表，按上述顺序排序；无报告时返回空列表
    """
    if not project_root or not os.path.isdir(project_root):
        return []

    root_abs = os.path.abspath(project_root)
    found: List[str] = []
    seen: set = set()

    def _add(p: str) -> None:
        """按绝对路径去重后追加"""
        ap = os.path.abspath(p)
        if ap in seen:
            return
        if os.path.isfile(ap):
            seen.add(ap)
            found.append(ap)

    # 1. 按优先级追加主报告（保证排在最前）
    for rel in _candidate_paths(app_module):
        _add(os.path.join(root_abs, rel))

    # 2. 扫描 {root}/*/build/reports/lint-results-*.xml
    try:
        with os.scandir(root_abs) as it:
            for entry in it:
                if not entry.is_dir():
                    continue
                if entry.name.startswith('.') or entry.name in (
                        'build', 'node_modules', 'out', 'gradle'):
                    continue
                reports_dir = os.path.join(entry.path, 'build', 'reports')
                if not os.path.isdir(reports_dir):
                    continue
                try:
                    with os.scandir(reports_dir) as rit:
                        # 收集同一 module 下的所有 lint-results*.xml，然后按文件名排序后加入
                        xmls = [
                            r.path for r in rit
                            if r.is_file()
                            and r.name.startswith('lint-results')
                            and r.name.endswith('.xml')
                        ]
                        for x in sorted(xmls):
                            _add(x)
                except OSError:
                    pass
    except OSError:
        pass

    # 3. 根工程兜底：{root}/build/reports/lint-results-*.xml
    root_reports = os.path.join(root_abs, 'build', 'reports')
    if os.path.isdir(root_reports):
        try:
            with os.scandir(root_reports) as rit:
                xmls = [
                    r.path for r in rit
                    if r.is_file()
                    and r.name.startswith('lint-results')
                    and r.name.endswith('.xml')
                ]
                for x in sorted(xmls):
                    _add(x)
        except OSError:
            pass

    return found


def _module_from_report_path(report_path: str, project_root: str) -> str:
    """从 lint 报告路径推断所属 Gradle module 名

    典型路径：{project_root}/APPTest/build/reports/lint-results-debug.xml
                             ^^^^^^^
    取 project_root 之后的第一段目录名即 module 名。
    根工程（{project_root}/build/reports/...）返回空串。
    """
    if not report_path or not project_root:
        return ''
    try:
        rel = os.path.relpath(os.path.abspath(report_path),
                              os.path.abspath(project_root))
    except ValueError:
        return ''
    if rel.startswith('..'):
        return ''
    parts = rel.replace(os.sep, '/').split('/')
    if len(parts) < 2:
        return ''
    first = parts[0]
    # 根工程下的 build/reports/... 第一段就是 'build'
    if first == 'build':
        return ''
    return first


def _module_from_defined_at(defined_at: str) -> str:
    """从资源定义路径推断真实所属 Gradle module 名。

    `defined_at` 是 lint 解析后经 `_relativize` 处理过的短路径，形如：
        LibBase/src/main/res/drawable/ic_xxx.png
        app/src/main/res/values/strings.xml
    取第一段目录即 module 名。

    与 `_module_from_report_path` 的区别：
    - report_path 基于 lint 报告文件所在目录（开了 checkDependencies 后
      所有资源都汇总到一个报告里，无法区分）
    - defined_at 基于资源源文件路径，能精确反映资源真实归属 module

    无法推断（绝对路径/空路径/仅文件名）时返回空串。
    """
    if not defined_at:
        return ''
    path = defined_at.replace(os.sep, '/').lstrip('/')
    # 已是绝对路径或盘符开头（未相对化成功）——不可推断
    if not path or path.startswith(('/', '.')) or ':' in path.split('/', 1)[0]:
        return ''
    parts = path.split('/')
    if len(parts) < 2:
        return ''
    first = parts[0]
    # 根工程资源或临时构建目录下的资源——不归属具体 module
    if first in ('build', 'src'):
        return ''
    return first


def _glob_lint_xml(start: str, depth: int) -> Optional[str]:
    """递归查找 lint-results*.xml，限制深度避免慢"""
    if depth > _MAX_GLOB_DEPTH:
        return None
    try:
        with os.scandir(start) as it:
            subdirs: List[str] = []
            for entry in it:
                if entry.is_file() and entry.name.startswith('lint-results') \
                        and entry.name.endswith('.xml'):
                    return entry.path
                if entry.is_dir() and not entry.name.startswith('.') \
                        and entry.name not in ('build', 'node_modules', 'out'):
                    subdirs.append(entry.path)
            # 先优先 build/reports 目录
            subdirs.sort(key=lambda p: (0 if 'reports' in p else 1, p))
            for sd in subdirs:
                result = _glob_lint_xml(sd, depth + 1)
                if result:
                    return result
    except OSError:
        pass
    return None


# ============================================================================
# 解析 Lint XML
# ============================================================================

# 从 message 中抽取 "R.xxx.yyy" 资源引用；lint 的常见格式：
#   "The resource R.drawable.ic_old is unused"
#   "The resource R.string.old_title appears to be unused"
_RES_REF_RE = re.compile(r'R\.([a-zA-Z_]+)\.([a-zA-Z0-9_]+)')


def _parse_res_from_location(location: str) -> Tuple[str, str]:
    """从文件路径反推 (res_type, res_name)

    示例：
        /proj/app/src/main/res/drawable-hdpi/ic_old.png -> ('drawable', 'ic_old')
        /proj/app/src/main/res/layout/activity_old.xml -> ('layout', 'activity_old')
        /proj/app/src/main/res/values/colors.xml       -> ('values', 'colors')（较特殊，需结合 message 判断）
    """
    path = location.replace('\\', '/')
    parts = path.split('/')
    # 找到 "res" 段
    try:
        idx = len(parts) - 1 - list(reversed(parts)).index('res')
    except ValueError:
        return '', ''
    if idx + 2 >= len(parts):
        return '', ''
    folder = parts[idx + 1]
    # drawable-hdpi -> drawable
    res_type = folder.split('-')[0]
    fname = parts[idx + 2]
    stem = fname.rsplit('.', 1)[0]
    if stem.endswith('.9'):  # 9-patch
        stem = stem[:-2]
    return res_type, stem


def _parse_res_from_message(msg: str) -> Tuple[str, str]:
    """从 lint message 抽取 R.type.name"""
    m = _RES_REF_RE.search(msg or '')
    if m:
        return m.group(1), m.group(2)
    return '', ''


def _to_relative_path(path: str, project_root: str) -> str:
    """把 lint 给出的 location 路径规整为「相对工程根」的短路径。

    Lint XML 的 `<location file="..."/>` 在不同 AGP 版本下可能是：
    - 绝对路径（常见）：/Users/x/projects/demo/app/src/main/res/drawable/ic.png
    - 相对 module 根：res/drawable/ic.png
    - 相对工程根：app/src/main/res/drawable/ic.png（较少见）

    本函数目标：
    - 绝对路径且落在 project_root 内 → 转成相对 project_root 的路径
    - 绝对路径但不在 project_root 内 → 保持原绝对路径（避免丢信息）
    - 本就是相对路径 → 原样返回（已经够短）
    """
    if not path:
        return ''
    if not project_root:
        return path
    if not os.path.isabs(path):
        return path  # 已是相对路径
    try:
        root_abs = os.path.abspath(project_root)
        rel = os.path.relpath(os.path.abspath(path), root_abs)
        # 若 relpath 产出 ../../.. 这种跳出工程根的路径，说明 lint 报告来自外部，
        # 放弃相对化，保留原绝对路径以便用户溯源。
        if rel.startswith('..'):
            return path
        # 统一用正斜杠（HTML/跨平台显示更友好）
        return rel.replace(os.sep, '/')
    except ValueError:
        # Windows 跨盘符等场景 relpath 会抛 ValueError
        return path


def parse_lint_report(report_path: str,
                      project_root: str = '',
                      module: str = '') -> List[UnusedResource]:
    """解析 lint XML 报告，返回所有 UnusedResources 条目。

    :param project_root: 工程根目录；提供后会把 location 的绝对路径
                         相对化为「相对工程根」的短路径。
    :param module: 该报告所属的 Gradle module 名（用于 UnusedResource.module 字段）
    """
    if not report_path or not os.path.isfile(report_path):
        return []

    try:
        tree = ET.parse(report_path)
    except ET.ParseError:
        return []

    root = tree.getroot()
    results: List[UnusedResource] = []

    for issue in root.iter('issue'):
        if issue.get('id') != 'UnusedResources':
            continue
        message = issue.get('message', '')

        # 先从 message 抽 R.type.name，再用 location 补充 defined_at
        res_type, res_name = _parse_res_from_message(message)
        location_file = ''
        location_line = 0
        for loc in issue.iter('location'):
            location_file = loc.get('file', '')
            try:
                location_line = int(loc.get('line', '0') or 0)
            except ValueError:
                location_line = 0
            break  # 只取第一个 location

        # message 未能抽出时，从 location 反推（此时仍使用原始路径，
        # 便于正则匹配出 res/<type>/<name> 等结构）
        if not res_type or not res_name:
            rt, rn = _parse_res_from_location(location_file)
            res_type = res_type or rt
            res_name = res_name or rn

        if not res_name:
            continue  # 信息不足，跳过

        # 相对化后再落入 UnusedResource，确保 HTML 展示的是相对路径
        location_file_rel = _to_relative_path(location_file, project_root)

        # 若未显式传入 module，尝试从 location 路径中推断（取 project_root 后第一段）
        res_module = module
        if not res_module and location_file_rel \
                and not os.path.isabs(location_file_rel):
            parts = location_file_rel.replace(os.sep, '/').split('/')
            if parts and parts[0] and parts[0] != 'build':
                res_module = parts[0]

        results.append(UnusedResource(
            res_type=res_type or 'unknown',
            res_name=res_name,
            defined_at=location_file_rel,
            line=location_line,
            message=message,
            estimated_size=0,  # 稍后在 enrich 阶段填充
            module=res_module,
        ))

    return results


def _dedupe_unused(unused_list: List[UnusedResource]) -> List[UnusedResource]:
    """按 (module, res_type, res_name, defined_at, line) 去重。

    多个 module 的 lint 报告可能对同一资源都有条目（尤其是 app 开启
    checkDependencies 后既在 app 报告里也在 library 报告里出现）。
    去重时保留 module 非空的那条；若都非空，保留排序最靠前的。
    """
    seen: dict = {}
    for u in unused_list:
        key = (u.res_type, u.res_name, u.defined_at, u.line)
        if key not in seen:
            seen[key] = u
            continue
        # 已存在：优先保留 module 非空者
        old = seen[key]
        if not old.module and u.module:
            seen[key] = u
    return list(seen.values())


# ============================================================================
# 体积估算：从 APK 条目倒推
# ============================================================================

def enrich_with_apk_size(unused: List[UnusedResource],
                         apk_entries: List[FileEntry]) -> int:
    """为每个 UnusedResource 匹配 APK 内条目，估算体积。

    匹配规则：res_type 对应目录 + 资源名匹配（允许密度后缀，如 drawable-xxhdpi/ic_old.png）
    同一资源名多密度变体的体积会累加。

    :return: 所有未用资源的总可回收体积（字节）
    """
    # 构建索引：type -> name -> total_size
    by_type_name: Dict[Tuple[str, str], int] = {}
    for e in apk_entries:
        path = e.path.replace('\\', '/')
        if not path.startswith('res/'):
            continue
        parts = path.split('/')
        if len(parts) < 3:
            continue
        folder = parts[1]
        res_type = folder.split('-')[0]  # drawable-hdpi -> drawable
        fname = parts[2]
        stem = fname.rsplit('.', 1)[0]
        if stem.endswith('.9'):
            stem = stem[:-2]
        key = (res_type, stem)
        by_type_name[key] = by_type_name.get(key, 0) + e.compressed_size

    total = 0
    for u in unused:
        size = by_type_name.get((u.res_type, u.res_name), 0)
        u.estimated_size = size
        total += size
    return total


# ============================================================================
# 主入口
# ============================================================================

def _build_missing_report_note(project_root: str,
                               app_module: str,
                               replay_cmd: str = "") -> str:
    """构造「未找到 lint 报告」的引导文本

    脚本不会自动触发任何 gradle 命令，只负责给出用户可以直接复制的指引：
        1) cd 到工程根并执行 `./gradlew lintReportRelease`（推荐：会同时
           跑 Analyze + 产出 HTML/XML 报告，兼容性最好）
        2) 产出 XML 后直接重放本分析命令，即可拿到未用资源结果

    改进：推荐 `lintReportRelease` 而非 `lint` / `lintAnalyzeRelease`：
        - `lint` 会对所有 variant 跑一遍，耗时更长
        - `lintAnalyzeRelease` 只跑分析阶段，不保证产出 XML（依赖 AGP 版本）
        - `lintReportRelease` 会自动依赖 Analyze 任务，且**稳定产出 XML**，
          这是本工具解析所依赖的产物
        - **不带冒号前缀**：`:lintReportRelease` 只在 root project 执行，而
          root project 通常没有 AGP 插件，这个 task 根本不存在；去掉冒号后
          Gradle 会把 task 名派发到所有启用 AGP 的 subproject，这样本工具
          的多报告聚合能看到所有 library 的未用资源
    """
    report_dir = "*/build/reports/lint-results-*.xml"

    lines = [
        "未找到 Lint XML 报告，已跳过未用资源扫描。",
        "    请手动执行 lint 分析（通常耗时数分钟）：",
        f"      cd {project_root} && ./gradlew lintReportRelease",
        f"    报告位置：{report_dir}（本工具会聚合所有 module 的报告）",
    ]
    if app_module:
        lines.append(
            f"    仅想扫单 module 可用：./gradlew :{app_module}:lintReportRelease")
    if replay_cmd:
        lines.append("    完成后直接重放本命令即可拿到结果：")
        lines.append(f"      {replay_cmd}")
    else:
        lines.append("    完成后重新运行本分析命令即可。")
    return "\n".join(lines)


def scan_unused_resources(
        project_root: str,
        apk_entries: List[FileEntry],
        app_module: str = "",
        replay_cmd: str = "",
) -> Tuple[List[UnusedResource], str, str, List[str]]:
    """扫描未使用资源（**多 module 聚合**）

    本函数**只读取**已存在的 lint XML 报告，**不会执行任何 gradle 命令**。
    跑 lint 是用户的责任，本工具负责解析与聚合。

    :param project_root: Android 工程根目录
    :param apk_entries: APK 的所有条目（用于体积估算）
    :param app_module: 目标 Gradle module 名（影响候选路径优先级）
    :param replay_cmd: 重放命令字符串，拼到「找不到报告」的引导文本里，方便
                      用户在手动跑完 lint 后直接复制重放
    :return: (UnusedResource 列表, 主 lint_report_path, note, all_report_paths)
        - 主 lint_report_path: 用作"来源"在 HTML 单行展示（兼容旧字段）
        - all_report_paths: 所有参与聚合的报告路径
        - note: 扫描过程说明（找不到报告时的引导文本），成功解析时为空
    """
    if not project_root or not os.path.isdir(project_root):
        return [], '', '', []

    report_paths = find_all_lint_reports(project_root, app_module)

    if not report_paths:
        return ([], '',
                _build_missing_report_note(
                    project_root, app_module, replay_cmd),
                [])

    # 多报告聚合：逐份解析，按 (type, name, defined_at, line) 去重
    all_unused: List[UnusedResource] = []
    for rp in report_paths:
        module_name = _module_from_report_path(rp, project_root)
        all_unused.extend(parse_lint_report(
            rp, project_root=project_root, module=module_name))

    unused = _dedupe_unused(all_unused)

    # 按 defined_at 纠正 module 字段——
    # 原本 u.module 记录的是「lint 报告文件所在的 module」，但 app 开启
    # checkDependencies 后所有跨 module 的未用资源都汇总到 app 的报告里，
    # 导致 u.module 统一变成 app module，无法反映资源的真实归属。
    # defined_at 是相对工程根的路径（如 "LibBase/src/main/res/drawable/x.png"），
    # 第一段目录即真实所属 module；取不到时保留原值作 fallback。
    for u in unused:
        real_mod = _module_from_defined_at(u.defined_at)
        if real_mod:
            u.module = real_mod

    if unused:
        enrich_with_apk_size(unused, apk_entries)
        # 先按 module 字典序，再按体积降序
        unused.sort(key=lambda u: (u.module or '~', -u.estimated_size))

    primary = report_paths[0]
    return unused, primary, '', report_paths
