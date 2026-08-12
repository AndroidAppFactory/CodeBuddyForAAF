#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_apk.py
APK 瘦身分析主入口

工作流程：
  1. apk_parser: 遍历 ZIP，按类别分类统计
  2. dex_analyzer: 解析各 DEX 头（方法数/类数）
  3. so_analyzer: 统计各 ABI 分布、检测 STORED 存储
  4. module_attributor: 复用 apk-16kb-check/so_source_analyzer 做 SO 归因
  5. optimization_advisor: 根据规则生成优化建议
  6. report_terminal / report_html: 输出终端和 HTML 报告

用法:
    python3 analyze_apk.py <APK/AAB/AAR 路径> [HTML输出路径] [--project <工程根>]
    python3 analyze_apk.py --batch <目录> [--project <工程根>]

依赖: Python 3.6+（仅标准库）
"""

import os
import sys
import subprocess
import platform
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from models import Colors, ApkSizeResult
from apk_parser import parse_apk
from dex_analyzer import analyze_dex
from so_analyzer import analyze_so
from module_attributor import attribute_so_sources
from optimization_advisor import advise
from report_terminal import (
    print_header, print_tip_summary, format_bytes,
)
from report_html import generate_html_report
from image_extractor import extract_optimizable_images
from compress_script_generator import generate_compress_assets
from resource_usage_finder import find_image_usages
from unused_resource_scanner import scan_unused_resources
from project_resolver import (
    detect_app_module as _detect_app_module,
    resolve_project_root as _resolve_project_root,
)


SUPPORTED_EXTS = {'.apk', '.aab', '.aar'}


# ============================================================================
# 核心分析流程
# ============================================================================

def analyze(apk_path: str, project_root: str = "",
            project_auto_detected: bool = False,
            app_module: str = "",
            app_module_auto_detected: bool = False,
            replay_cmd: str = "") -> ApkSizeResult:
    """执行完整的 APK 体积分析流程

    :param apk_path: APK/AAB/AAR 路径
    :param project_root: 关联的 Android 工程根（空串表示跳过源码关联）
    :param project_auto_detected: 工程根是否为自动推断（影响输出提示）
    :param app_module: 关联的 Gradle module 名（如 'app' / 'APPTest'）
    :param app_module_auto_detected: module 是否为自动推断
    :param replay_cmd: 当前分析的重放命令字符串，透传给 unused_resource_scanner
                      用于拼接"手动 lint 后可直接重放"的引导文本

    本脚本只读取现有的 Lint XML 报告，**不会执行任何 gradle 命令**。
    找不到 lint 报告时，会在扫描说明里打印手动命令 + 重放命令，让用户自行决定。
    """
    c = Colors

    print(f"{c.CYAN}🔍 解析 APK 条目...{c.NC}")
    result = parse_apk(apk_path)
    result.check_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    result.project_root = project_root
    result.project_auto_detected = project_auto_detected
    result.app_module = app_module
    result.app_module_auto_detected = app_module_auto_detected

    # 标题块（文件+大小）在 parse 完成后立即输出，语义优先：
    # 🔍 在前（动作开始），标题在后（动作结果）
    print_header(result)

    print(f"{c.CYAN}🧬 分析 DEX 文件头...{c.NC}")
    analyze_dex(apk_path, result)

    print(f"{c.CYAN}⚙️  分析 Native SO...{c.NC}")
    analyze_so(result)

    # SO 模块归因：仅 APK 支持（AAR/AAB 没有项目构建产物路径）
    ext = Path(apk_path).suffix.lower()
    if ext == '.apk' and result.so_infos:
        attribute_so_sources(result)

    # 源码关联分析：仅当有有效 project_root 且为 APK 时执行
    if project_root and ext == '.apk':
        _run_source_linked_analysis(result, replay_cmd=replay_cmd)

    print(f"{c.CYAN}💡 生成优化建议...{c.NC}")
    advise(result)

    return result


def _run_source_linked_analysis(result: ApkSizeResult,
                                replay_cmd: str = "") -> None:
    """基于 project_root 执行源码关联分析（图片使用位置 + 未用资源）"""
    c = Colors

    # 1. 图片使用位置反查（基于可优化图片清单）
    if result.optimizable_images:
        print(f"{c.CYAN}🖼️  反查图片使用位置 "
              f"({len(result.optimizable_images)} 张)...{c.NC}")
        try:
            result.image_usages = find_image_usages(
                result.project_root, result.optimizable_images)
        except Exception as e:
            print(f"{c.YELLOW}⚠️  图片反查失败: {e}{c.NC}")

    # 2. 未使用资源扫描（只读现有 Lint 报告，不会自动执行 gradle）
    #    **多 module 聚合**：会收集 {root}/*/build/reports/lint-results-*.xml
    #    合并所有 module 的未用资源，而不只是 app_module 那一份
    print(f"{c.CYAN}🧹 扫描未使用资源（Lint 报告，多 module 聚合）{c.NC}")
    try:
        unused_list, report_path, note, report_paths = \
            scan_unused_resources(
                result.project_root, result.entries,
                app_module=result.app_module,
                replay_cmd=replay_cmd,
            )
        result.unused_resources = unused_list
        result.lint_report_path = report_path
        result.lint_report_paths = report_paths
        result.unused_res_scan_note = note
    except Exception as e:
        result.unused_res_scan_note = f"扫描异常: {e}"


# ============================================================================
# 批量模式
# ============================================================================

def batch_analyze(directory: str,
                  project_root_override: str = "") -> List[ApkSizeResult]:
    """批量分析目录下的所有 APK/AAB/AAR

    :param project_root_override: 显式指定的工程根（对所有文件共用）；
        为空时对每个 APK 尝试自动推断
    """
    c = Colors
    results: List[ApkSizeResult] = []

    apk_files = []
    for root, _, files in os.walk(directory):
        for f in files:
            ext = Path(f).suffix.lower()
            if ext in SUPPORTED_EXTS:
                apk_files.append(os.path.join(root, f))

    if not apk_files:
        print(f"{c.YELLOW}⚠️  目录下未找到 APK/AAB/AAR 文件{c.NC}")
        return results

    print(f"{c.CYAN}📦 批量分析 {len(apk_files)} 个文件...{c.NC}")
    for i, p in enumerate(apk_files, 1):
        print(f"\n{c.BOLD}[{i}/{len(apk_files)}] {p}{c.NC}")
        try:
            proj, auto = _resolve_project_root(p, project_root_override)
            module, module_auto = "", False
            if proj:
                module = _detect_app_module(p, proj)
                module_auto = bool(module)
            # 计算当前 APK 的重放命令（给 scanner 拼到引导文本里）
            per_replay = build_replay_command(
                p, is_batch=False, project_root=proj)
            _t0 = time.perf_counter()
            _r = analyze(p, proj, auto,
                         app_module=module,
                         app_module_auto_detected=module_auto,
                         replay_cmd=per_replay)
            _r.analyze_duration = time.perf_counter() - _t0
            results.append(_r)
        except Exception as e:
            print(f"{c.RED}❌ 分析失败: {e}{c.NC}")
    return results


def print_batch_summary(results: List[ApkSizeResult]) -> None:
    c = Colors
    if not results:
        return
    print()
    print(f"{c.BOLD}{c.CYAN}═══════════════ 批量分析汇总 ═══════════════{c.NC}")
    print(f"  {'文件':<40} {'大小':>10}  建议数")
    print(f"  {'-'*40} {'-'*10}  -----")
    for r in results:
        name = Path(r.file_path).name
        if len(name) > 40:
            name = name[:37] + '...'
        tip_count = len(r.tips)
        print(f"  {name:<40} {format_bytes(r.file_size):>10}  {tip_count:>5}")


# ============================================================================
# 工具方法
# ============================================================================

def _open_html(path: str) -> None:
    """尝试在系统默认浏览器中打开 HTML 报告"""
    c = Colors
    try:
        system = platform.system()
        if system == 'Darwin':
            subprocess.Popen(['open', path])
        elif system == 'Windows':
            os.startfile(path)  # type: ignore[attr-defined]
        elif system == 'Linux':
            subprocess.Popen(['xdg-open', path],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"{c.YELLOW}⚠️  无法自动打开报告: {e}{c.NC}")


def _script_path() -> str:
    """返回 analyze_apk.py 的绝对路径（用于重放命令）"""
    return os.path.abspath(__file__)


def _prepare_image_assets(apk_path: str, html_output: str,
                          result: ApkSizeResult):
    """解压可优化图片到 {html_stem}_assets/images/，返回 (assets_list, rel_dir)

    rel_dir: 相对 HTML 文件的目录（HTML 里 <img src> 用）
    """
    if not result.optimizable_images:
        return [], ''

    abs_html = os.path.abspath(html_output)
    html_dir = os.path.dirname(abs_html)
    html_stem = os.path.splitext(os.path.basename(abs_html))[0]
    rel_dir = f"{html_stem}_assets/images"
    abs_assets_dir = os.path.join(html_dir, rel_dir)

    assets = extract_optimizable_images(
        apk_path, result.optimizable_images, abs_assets_dir)
    return assets, rel_dir


def _generate_compress_script(html_output: str,
                              result: ApkSizeResult) -> Optional[dict]:
    """在 {report}_assets/ 下生成批量压缩脚本 + 清单。

    仅当同时满足以下条件时才生成：
      1. 有有效的 project_root（能反查到工程源文件）
      2. optimizable_images 非空
      3. 生成器成功反查到至少 1 张图的源路径

    其他情况返回 None，由调用方决定是否打印提示。
    """
    if not result.project_root:
        return None
    if not result.optimizable_images:
        return None

    abs_html = os.path.abspath(html_output)
    html_dir = os.path.dirname(abs_html)
    html_stem = os.path.splitext(os.path.basename(abs_html))[0]
    output_dir = os.path.join(html_dir, f"{html_stem}_assets")

    try:
        return generate_compress_assets(
            result.optimizable_images, result.project_root, output_dir)
    except Exception as e:
        print(f"{Colors.YELLOW}⚠️  生成压缩脚本失败: {e}{Colors.NC}")
        return None


def _package_share_zip(html_output: str, assets_rel_dir: str) -> Optional[str]:
    """把 HTML + 资源目录打成 {html_stem}.zip 方便分享

    :param html_output: HTML 文件路径
    :param assets_rel_dir: 资源相对目录（空则不打包）
    :return: zip 绝对路径（成功）或 None
    """
    if not assets_rel_dir:
        return None  # 无资源目录，HTML 单文件即可直接分享，不需要打包

    abs_html = os.path.abspath(html_output)
    html_dir = os.path.dirname(abs_html)
    html_name = os.path.basename(abs_html)
    html_stem = os.path.splitext(html_name)[0]
    # 资源目录的顶层（如 "{stem}_assets"，不含末尾的 /images）
    assets_top = assets_rel_dir.split('/', 1)[0]
    abs_assets_top = os.path.join(html_dir, assets_top)

    zip_path = os.path.join(html_dir, f"{html_stem}.zip")
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED,
                             compresslevel=6) as zf:
            # 1. HTML 本体（zip 内放在根目录）
            zf.write(abs_html, arcname=html_name)

            # 2. 资源目录（保持相对结构）
            if os.path.isdir(abs_assets_top):
                for root, _, files in os.walk(abs_assets_top):
                    for name in files:
                        abs_file = os.path.join(root, name)
                        rel = os.path.relpath(abs_file, html_dir)
                        zf.write(abs_file, arcname=rel)
        return zip_path
    except (OSError, zipfile.BadZipFile) as e:
        print(f"⚠️  zip 打包失败: {e}")
        # 失败时清掉残文件避免误导
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
        except OSError:
            pass
        return None


def _quote(path: str) -> str:
    """路径仅在含空格或 shell 特殊字符时才加引号，普通路径裸写，方便复制/点击。

    中文字符本身对 shell 是安全的，无需引号；真正需要引号的是空格、引号、括号、
    反斜杠、$、`、*、?、&、|、;、<、>、#、! 等。
    """
    if not path:
        return '""'
    unsafe = set(' \t\n"\'\\()[]{}<>|&;*?$`#!~')
    if any(ch in unsafe for ch in path):
        return f'"{path}"'
    return path


def _print_compress_script_hint(info: Optional[dict]) -> None:
    """根据压缩脚本生成器的结果打印使用提示。

    info 由 _generate_compress_script 返回：
      - None：未生成（无 project_root / 无可优化图片 / 生成器异常） → 不打印
      - resolvable == 0：全部未定位 → 打轻提示
      - resolvable > 0：打路径提示 + 一键命令
    """
    c = Colors
    if not info:
        return

    resolvable = int(info.get('resolvable', 0) or 0)
    unresolved = int(info.get('unresolved', 0) or 0)
    script_path = info.get('script_path') or ''
    list_path = info.get('list_path') or ''

    if resolvable == 0:
        if unresolved > 0:
            print(f"{c.YELLOW}     ⚠️  {unresolved} 张图片未在工程内定位到源路径，"
                  f"未生成压缩清单{c.NC}")
        return

    print(f"{c.CYAN}     └─ 压缩清单 ({resolvable} 条可压缩"
          + (f", {unresolved} 条未定位" if unresolved else "")
          + f"): {list_path}{c.NC}")
    print(f"{c.YELLOW}     💡 一键批量压缩（原地替换工程源文件，自动备份）:{c.NC}")
    print(f"        export tinypng_api_key=your_key")
    print(f"        bash {_quote(script_path)} --list {_quote(list_path)}          # dry-run 预览")
    print(f"        bash {_quote(script_path)} --list {_quote(list_path)} --apply  # 真执行")
    print(f"        bash {_quote(script_path)} --list {_quote(list_path)} --restore  # 一键回滚")


def build_replay_command(file_path: str, is_batch: bool = False,
                         project_root: str = "") -> str:
    """构造重放命令字符串，供终端与 HTML 共用。

    始终使用默认 HTML 输出路径（同名 `_size_report.html`），不暴露指定 HTML 路径的变体。
    当 project_root 有效时追加 `--project <abs_path>`，保证重放能复现源码关联分析。
    """
    script = _script_path()
    abs_input = os.path.abspath(file_path)

    if is_batch:
        cmd = f"python3 {_quote(script)} --batch {_quote(abs_input)}"
    else:
        cmd = f"python3 {_quote(script)} {_quote(abs_input)}"

    if project_root:
        cmd += f" --project {_quote(os.path.abspath(project_root))}"
    return cmd


def print_replay(file_path: str, is_batch: bool = False,
                 project_root: str = "") -> None:
    """打印重放命令块到终端（简化版：不再使用超宽边框）"""
    c = Colors
    cmd = build_replay_command(file_path, is_batch, project_root)

    print()
    print(f"{c.BOLD}{c.YELLOW}🔄 重放命令（可复制）{c.NC}")
    print(f"  {c.GREEN}{cmd}{c.NC}")
    print()


def _print_usage() -> None:
    prog = sys.argv[0]
    print("用法:")
    print(f"  {prog} <APK/AAB/AAR 路径> [HTML输出路径] [--project <工程根>]")
    print(f"  {prog} --batch <目录路径> [--project <工程根>]")
    print()
    print("示例:")
    print(f"  {prog} app-release.apk")
    print(f"  {prog} app-release.apk ./report.html")
    print(f"  {prog} app-release.apk --project /path/to/android-project")
    print(f"  {prog} --batch ./apks/")
    print()
    print("说明:")
    print("  APK: 完整分析（构成 + DEX + SO + 资源 + 模块归因 + 建议）")
    print("  AAB/AAR: 完整分析（无 SO 模块归因，缺少项目构建产物路径）")
    print("  --project: 关联 Android 工程源码（可选）")
    print("    - 显式传入：按指定路径执行源码关联分析")
    print("    - 未传入且 APK 位于 build/{outputs,intermediates}/apk/ 下：自动向上查找工程根")
    print("    - 启用后追加两项能力：图片使用位置反查、Lint 未使用资源扫描")
    print()
    print("关于 Lint 未使用资源扫描：")
    print("  脚本只读取现有的 Lint XML 报告，不会自动执行任何 gradle 命令。")
    print("  需要用户自行在工程根下执行（推荐）：")
    print("    ./gradlew lintReportRelease")
    print("  脚本会自动聚合所有 module 的 lint 报告。")
    print()
    print("依赖: Python 3.6+（仅标准库）")


def _parse_flags(argv: List[str]) -> Tuple[List[str], str]:
    """从 argv 中抽取 `--project <path>`，并兼容历史遗留的 `--run-lint`/`--no-lint`

    - `--project`：支持 `--project <path>` 或 `--project=<path>`
    - `--run-lint` / `--no-lint`：脚本已不再自动执行 gradle，这两个 flag 保留仅为
      兼容旧重放命令，检测到时打印一条提示并忽略

    :return: (清理后的 argv, project)
    """
    cleaned: List[str] = []
    project = ""
    i = 0
    while i < len(argv):
        token = argv[i]
        if token == '--project':
            if i + 1 >= len(argv):
                print(f"{Colors.RED}错误: --project 缺少路径参数{Colors.NC}")
                sys.exit(1)
            project = argv[i + 1]
            i += 2
            continue
        if token.startswith('--project='):
            project = token[len('--project='):]
            i += 1
            continue
        if token in ('--run-lint', '--no-lint'):
            # 历史兼容：脚本现在**不会自动触发 lint**，这两个 flag 被忽略
            print(f"{Colors.YELLOW}ℹ️  {token} 已废弃——脚本不再自动执行 gradle，"
                  f"需要用户自行运行 ./gradlew lintReportRelease{Colors.NC}")
            i += 1
            continue
        cleaned.append(token)
        i += 1
    return cleaned, project


# 保留旧名以兼容任何外部引用（主要是测试与 doc 示例）
def _parse_project_arg(argv: List[str]) -> Tuple[List[str], str]:
    return _parse_flags(argv)


# ============================================================================
# 入口
# ============================================================================

def main() -> int:
    c = Colors
    if len(sys.argv) < 2:
        _print_usage()
        return 1

    # 先剥离 --project（以及兼容性的 --run-lint/--no-lint）
    argv, project_override = _parse_flags(sys.argv[1:])
    if not argv:
        _print_usage()
        return 1

    # 批量模式
    if argv[0] == '--batch':
        if len(argv) < 2:
            print(f"{c.RED}错误: 请指定目录路径{c.NC}")
            return 1
        directory = argv[1]
        if not os.path.isdir(directory):
            print(f"{c.RED}错误: 目录不存在: {directory}{c.NC}")
            return 1

        results = batch_analyze(directory, project_override)
        for r in results:
            html_path = r.file_path.rsplit('.', 1)[0] + '_size_report.html'
            # 每个 APK 的重放命令（以单文件形式给出）
            # 重放时使用 result 实际关联的 project_root（自动推断时也能复现）
            cmd_def = build_replay_command(
                r.file_path, is_batch=False,
                project_root=r.project_root)
            # 解压可优化图片到 HTML 同级 assets 目录（仅 APK）
            image_assets, assets_rel = [], ''
            if Path(r.file_path).suffix.lower() == '.apk':
                image_assets, assets_rel = _prepare_image_assets(
                    r.file_path, html_path, r)
            generate_html_report(r, html_path, replay_cmd=cmd_def,
                                 image_assets=image_assets,
                                 assets_rel_dir=assets_rel,
                                 compress_info=None)  # 先占位，下面生成后再补渲染
            print()
            print(f"{c.CYAN}📄 HTML 报告: {html_path}{c.NC}")
            if assets_rel:
                extracted = sum(1 for _, n, _wh in image_assets if n)
                abs_assets = os.path.join(
                    os.path.dirname(os.path.abspath(html_path)), assets_rel)
                print(f"{c.CYAN}     └─ 图片资源 ({extracted} 张): "
                      f"{abs_assets}{c.NC}")
                # 先生成压缩清单，再重生 HTML（让图片 Tab 能显示一键命令）
                compress_info = _generate_compress_script(html_path, r)
                if compress_info:
                    generate_html_report(r, html_path, replay_cmd=cmd_def,
                                         image_assets=image_assets,
                                         assets_rel_dir=assets_rel,
                                         compress_info=compress_info)
                zip_path = _package_share_zip(html_path, assets_rel)
                if zip_path:
                    zip_size = format_bytes(os.path.getsize(zip_path))
                    print(f"{c.CYAN}     └─ 分享包 ({zip_size}): "
                          f"{zip_path}{c.NC}")
                    print(f"{c.YELLOW}     💡 单独分享 HTML 请发 .zip 文件{c.NC}")
                _print_compress_script_hint(compress_info)
            print_tip_summary(r)
        print_batch_summary(results)
        # 批量模式重放命令（project_override 存在则透传，否则留空让各文件各自推断）
        print_replay(directory, is_batch=True, project_root=project_override)
        return 0 if results else 1

    # 单文件模式
    file_path = argv[0]
    if not os.path.isfile(file_path):
        print(f"{c.RED}错误: 文件不存在: {file_path}{c.NC}")
        return 1

    ext = Path(file_path).suffix.lower()
    if ext not in SUPPORTED_EXTS:
        print(f"{c.RED}错误: 不支持的文件格式: {ext}{c.NC}")
        print(f"支持的格式: {', '.join(sorted(SUPPORTED_EXTS))}")
        return 1

    html_output = argv[1] if len(argv) > 1 \
        else file_path.rsplit('.', 1)[0] + '_size_report.html'

    # 决策 project_root + 推断 module
    proj, auto = _resolve_project_root(file_path, project_override)
    module, module_auto = "", False
    if proj:
        module = _detect_app_module(file_path, proj)
        module_auto = bool(module)

    # 预先构造一个临时 result 用于打标题（在 analyze 之前显示文件+大小）
    # 实际分析后的 result 会替换它，标题依然准确。
    # —— 为了做到先打标题再跑流程，这里巧利用 parse_apk 先把基础信息拿出来。
    # 但考虑 parse_apk 会在 analyze() 内再跑一次有重复开销，此处改为：
    # 直接先打一行精简标题占位，analyze() 跳过自己的标题打印。
    # (最终实现采用：analyze 内部不打标题，标题在 analyze 完成后从 result 再补打不可行——
    #  所以我们将 print_header 放在 analyze() 内部的最前面。)

    # 预先算出"当前次"的重放命令，传给 analyze → scanner 拼接到引导文本里
    pre_replay = build_replay_command(
        file_path, is_batch=False, project_root=proj)

    # 执行分析
    try:
        _t0 = time.perf_counter()
        result = analyze(file_path, proj, auto,
                         app_module=module,
                         app_module_auto_detected=module_auto,
                         replay_cmd=pre_replay)
        result.analyze_duration = time.perf_counter() - _t0
    except Exception as e:
        print(f"{c.RED}❌ 分析失败: {e}{c.NC}")
        import traceback
        traceback.print_exc()
        return 2

    # 生成 HTML 报告（附带重放命令 + 可选的图片缩略图）
    cmd_def = build_replay_command(file_path, is_batch=False,
                                   project_root=result.project_root)

    # 解压可优化图片（仅 APK；AAB/AAR 跳过）
    image_assets, assets_rel = [], ''
    if ext == '.apk':
        image_assets, assets_rel = _prepare_image_assets(
            file_path, html_output, result)

    generate_html_report(result, html_output,
                         replay_cmd=cmd_def,
                         image_assets=image_assets,
                         assets_rel_dir=assets_rel,
                         compress_info=None)  # 先占位
    print()
    print(f"{c.CYAN}📄 HTML 报告: {os.path.abspath(html_output)}{c.NC}")
    if assets_rel:
        extracted = sum(1 for _, n, _wh in image_assets if n)
        abs_assets = os.path.join(
            os.path.dirname(os.path.abspath(html_output)), assets_rel)
        print(f"{c.CYAN}     └─ 图片资源 ({extracted} 张): {abs_assets}{c.NC}")
        # 先生成压缩清单，再重生 HTML（让图片 Tab 能显示一键命令）
        compress_info = _generate_compress_script(html_output, result)
        if compress_info:
            generate_html_report(result, html_output,
                                 replay_cmd=cmd_def,
                                 image_assets=image_assets,
                                 assets_rel_dir=assets_rel,
                                 compress_info=compress_info)
        zip_path = _package_share_zip(html_output, assets_rel)
        if zip_path:
            zip_size = format_bytes(os.path.getsize(zip_path))
            print(f"{c.CYAN}     └─ 分享包 ({zip_size}): {zip_path}{c.NC}")
            print(f"{c.YELLOW}     💡 单独分享 HTML 请发 .zip 文件{c.NC}")
        # 批量压缩脚本使用提示
        _print_compress_script_hint(compress_info)

    # 建议统计（顶格：⌢⿴⿴⿴ ... / ✔ ...）
    print_tip_summary(result)

    # 自动打开
    _open_html(html_output)

    # 重放命令
    print_replay(file_path, is_batch=False,
                 project_root=result.project_root)

    # 退出码：有 high 建议时返回 1
    high_tips = [t for t in result.tips if t.severity == 'high']
    return 1 if high_tips else 0


if __name__ == '__main__':
    sys.exit(main())
