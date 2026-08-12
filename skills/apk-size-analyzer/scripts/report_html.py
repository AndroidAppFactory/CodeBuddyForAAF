#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
report_html.py
HTML 可视化报告：饼图（CSS conic-gradient）+ 分类表格 + Tab 切换
纯 CSS 实现，零外部依赖。
"""

import os
import html
import json
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import quote as _url_quote

from models import ApkSizeResult, FileCategory, OptimizationTip
from image_extractor import read_image_size


# ============================================================================
# 工具方法
# ============================================================================

_CATEGORY_COLORS = {
    FileCategory.DEX: '#3b82f6',        # blue
    FileCategory.NATIVE: '#f59e0b',     # amber
    FileCategory.RESOURCE: '#10b981',   # emerald
    FileCategory.RES_TABLE: '#06b6d4',  # cyan
    FileCategory.ASSETS: '#8b5cf6',     # violet
    FileCategory.SIGNATURE: '#94a3b8',  # slate
    FileCategory.KOTLIN: '#ec4899',     # pink
    FileCategory.MANIFEST: '#22c55e',   # green
    FileCategory.OTHER: '#64748b',      # slate dark
}


def _fmt_bytes(n: int) -> str:
    units = ['B', 'KB', 'MB', 'GB']
    f = float(n or 0)
    for u in units:
        if f < 1024 or u == units[-1]:
            if u == 'B':
                return f"{int(f)} B"
            return f"{f:.2f} {u}"
        f /= 1024
    return f"{n} B"


def _fmt_duration(seconds: float) -> str:
    """格式化耗时：<1s 显示毫秒；<60s 显示 N.Ns；>=60s 显示 Nm Ns"""
    s = float(seconds or 0)
    if s <= 0:
        return "-"
    if s < 1:
        return f"{int(s * 1000)} ms"
    if s < 60:
        return f"{s:.1f} s"
    m = int(s // 60)
    rs = int(s - m * 60)
    return f"{m}m {rs}s"


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _severity_class(sev: str) -> str:
    return {'high': 'sev-high', 'medium': 'sev-mid',
            'low': 'sev-low', 'info': 'sev-info'}.get(sev, 'sev-info')


def _build_conic(stats_list: List[Tuple[str, int, str]]) -> str:
    """根据分类构造 conic-gradient 样式值

    :param stats_list: List[(label, size, color)]
    """
    total = sum(s[1] for s in stats_list) or 1
    segments = []
    acc = 0.0
    for _, size, color in stats_list:
        start = acc / total * 100
        acc += size
        end = acc / total * 100
        segments.append(f"{color} {start:.2f}% {end:.2f}%")
    return ", ".join(segments)


# ============================================================================
# 主生成函数
# ============================================================================

def generate_html_report(result: ApkSizeResult, output_path: str,
                         replay_cmd: str = "",
                         image_assets: List = None,
                         assets_rel_dir: str = '',
                         compress_info: Optional[dict] = None) -> None:
    """生成完整的 HTML 报告

    :param replay_cmd: 重放命令（单条，默认输出路径）
    :param image_assets: 可选，图片解压结果（由 image_extractor 生成）
    :param assets_rel_dir: 图片相对 HTML 的目录（如 'report_assets/images'）
    :param compress_info: 可选，批量压缩脚本生成器的结果
                          {'script_path','list_path','resolvable','unresolved','total'}
    """
    # 各 Tab 的大小 & 占比徽章（相对于 APK 总压缩后大小）
    total_comp = result.total_compressed or 1

    dex_size = result.category_stats.get(FileCategory.DEX)
    dex_bytes = dex_size.total_compressed if dex_size else 0

    so_size = result.category_stats.get(FileCategory.NATIVE)
    so_bytes = so_size.total_compressed if so_size else 0

    large_bytes = sum(e.compressed_size for e in result.large_files)
    image_bytes = sum(e.compressed_size for e in result.optimizable_images)
    tips_saving = sum(t.estimated_saving for t in result.tips)

    ctx = {
        'file_path': _esc(result.file_path),
        'file_name': _esc(Path(result.file_path).name),
        'file_size': _fmt_bytes(result.file_size),
        'total_files': result.total_files,
        'total_uncompressed': _fmt_bytes(result.total_uncompressed),
        'project_root_attr': _esc(
            os.path.abspath(result.project_root)
            if result.project_root else ''),
        'project_banner': _render_project_banner(result),
        'category_section': _render_category_section(result),
        'dex_section': _render_dex_section(result),
        'so_section': _render_so_section(result),
        'large_files_section': _render_large_files_section(result),
        'images_section': _render_images_section(result, image_assets, assets_rel_dir, compress_info),
        'unused_section': _render_unused_section(result),
        'unused_tab_btn': _render_unused_tab_btn(result),
        'unused_panel': _render_unused_panel(result),
        'tips_section': _render_tips_section(result.tips),
        'replay_section': _render_replay_section(replay_cmd),
        'check_time': _esc(result.check_time),
        'analyze_duration': _fmt_duration(result.analyze_duration),
        # Tab 标题徽章
        'badge_overview': _render_size_badge(result.file_size, 100.0, accent=True),
        'badge_dex': _render_size_badge(dex_bytes, dex_bytes / total_comp * 100),
        'badge_so': _render_size_badge(so_bytes, so_bytes / total_comp * 100),
        'badge_largefiles': _render_size_badge(large_bytes, large_bytes / total_comp * 100),
        'badge_images': _render_size_badge(image_bytes, image_bytes / total_comp * 100),
        'badge_tips': _render_saving_badge(tips_saving),
    }

    ctx['styles'] = _STYLES_CSS
    ctx['scripts'] = _SCRIPTS_JS
    html_text = _HTML_TEMPLATE.format(**ctx)

    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_text)


# ============================================================================
# 标题徽章（Tab 标题右侧：大小 + 占比）
# ============================================================================

def _render_size_badge(size_bytes: int, ratio_pct: float, accent: bool = False) -> str:
    """生成 `<h2>` 右侧的「大小 · 占比」徽章

    :param size_bytes: 字节数
    :param ratio_pct: 占 APK 总大小的百分比（0~100）
    :param accent: 是否使用主色强调（用于总览）
    """
    if size_bytes <= 0:
        return ''
    cls = 'h2-badge h2-badge-accent' if accent else 'h2-badge'
    return (
        f'<span class="{cls}">'
        f'<b>{_fmt_bytes(size_bytes)}</b>'
        f'<span class="sep">·</span>'
        f'<span class="ratio">{ratio_pct:.1f}%</span>'
        f'</span>'
    )


def _render_saving_badge(saving_bytes: int) -> str:
    """优化建议 Tab 的徽章：预估可节省"""
    if saving_bytes <= 0:
        return ''
    return (
        f'<span class="h2-badge h2-badge-saving">'
        f'<span class="ratio">预估可节省</span>'
        f'<b>{_fmt_bytes(saving_bytes)}</b>'
        f'</span>'
    )


# ============================================================================
# 重放命令区块
# ============================================================================

def _render_replay_section(replay_cmd: str) -> str:
    """渲染重放命令区块（深色 details 面板，对齐 apk-16kb-check 风格）"""
    if not replay_cmd:
        return ''

    return f"""
    <details class="replay-panel" open>
        <summary>🔄 重放命令</summary>
        <div class="replay-body">
            {_render_replay_row(replay_cmd)}
        </div>
    </details>"""


def _render_replay_row(cmd: str) -> str:
    return f"""
        <div class="replay-cmd">
            <code>{_esc(cmd)}</code>
            <button class="copy-btn" onclick="copyReplayCmd(this)">复制</button>
        </div>"""


def _render_compress_panel(compress_info: Optional[dict]) -> str:
    """渲染「一键批量压缩」命令面板（沿用重放命令面板的深色风格）

    支持按原图大小阈值过滤：顶部按钮组切换后，dry-run/apply/回滚命令自动
    带上 `--min-size`（或移除）。复制按钮直接读 <code> 当前文本，与现有
    copyReplayCmd 无缝兼容。

    仅当 compress_info 有效且 resolvable > 0 时展示。
    """
    if not compress_info:
        return ''
    resolvable = int(compress_info.get('resolvable', 0) or 0)
    unresolved = int(compress_info.get('unresolved', 0) or 0)
    script_path = compress_info.get('script_path') or ''
    list_path = compress_info.get('list_path') or ''
    sizes = compress_info.get('sizes') or []  # list[int]，可压缩条目的原字节数
    if resolvable <= 0 or not script_path or not list_path:
        return ''

    script_q = _shell_quote(script_path)
    list_q = _shell_quote(list_path)

    # 备份目录与日志文件默认落在清单同级目录，直接算出真实路径供 UI 展示
    list_dir = os.path.dirname(os.path.abspath(list_path)) if list_path else ''
    backup_dir = os.path.join(list_dir, '.backup') + os.sep if list_dir else '.backup/'
    log_path = os.path.join(list_dir, 'compress_images.log') if list_dir else 'compress_images.log'

    cmd_export = 'export tinypng_api_key=your_key_here'
    cmd_dry_base = f'bash {script_q} --list {list_q}'
    cmd_apply_base = f'bash {script_q} --list {list_q} --apply'
    cmd_restore = f'bash {script_q} --list {list_q} --restore'

    unresolved_hint = (f' · {unresolved} 条未在工程内定位'
                       if unresolved else '')

    # 预设阈值档位（KB）。0 = 全部
    presets_kb = [0, 200, 500, 1024, 2048]

    def _count_ge(threshold_bytes: int) -> int:
        if threshold_bytes <= 0:
            return len(sizes)
        return sum(1 for s in sizes if s >= threshold_bytes)

    def _label(kb: int) -> str:
        if kb == 0:
            return '全部'
        if kb >= 1024 and kb % 1024 == 0:
            return f'≥{kb // 1024}MB'
        return f'≥{kb}KB'

    def _cli_value(kb: int) -> str:
        """生成传给 --min-size 的字符串（留空表示不加参数）。"""
        if kb == 0:
            return ''
        if kb >= 1024 and kb % 1024 == 0:
            return f'{kb // 1024}M'
        return f'{kb}K'

    # 按钮组（点击后 JS 更新 <code> 内容与命中数）
    btn_items = []
    for kb in presets_kb:
        count = _count_ge(kb * 1024)
        cli = _cli_value(kb)
        active = ' active' if kb == 0 else ''
        btn_items.append(
            f'<button type="button" class="ci-chip{active}" '
            f'data-kb="{kb}" data-cli="{_esc(cli)}" data-count="{count}" '
            f'onclick="updateCompressMinSize(this)">'
            f'{_esc(_label(kb))} <span class="ci-chip-cnt">({count})</span>'
            f'</button>'
        )
    btn_group = ''.join(btn_items)

    # 自定义输入（单位 KB）
    custom_input = (
        '<span class="ci-custom">'
        '自定义：'
        '<input type="number" min="0" step="1" placeholder="KB" '
        'class="ci-custom-input" '
        'oninput="updateCompressMinSizeCustom(this)">'
        '<span class="ci-custom-cnt"></span>'
        '</span>'
    )

    # 用 data-base 保存不带 --min-size 的原始命令，JS 每次重拼
    dry_row = (
        '<div class="replay-cmd">'
        f'<code class="ci-cmd" data-base="{_esc(cmd_dry_base)}">'
        f'{_esc(cmd_dry_base)}</code>'
        '<button class="copy-btn" onclick="copyReplayCmd(this)">复制</button>'
        '</div>'
    )
    apply_row = (
        '<div class="replay-cmd">'
        f'<code class="ci-cmd" data-base="{_esc(cmd_apply_base)}">'
        f'{_esc(cmd_apply_base)}</code>'
        '<button class="copy-btn" onclick="copyReplayCmd(this)">复制</button>'
        '</div>'
    )

    # 内嵌样式（就近收敛，避免污染全局 CSS 文件）
    # 面板底色是深灰（replay-panel），所以所有文字都走显式浅色，避免 color:inherit
    # 被父级降饱和 + opacity 叠加后看不清。
    style = (
        '<style>'
        '.ci-filter{margin:6px 0 10px;display:flex;flex-wrap:wrap;'
        'align-items:center;gap:6px;font-size:13px;color:#e2e8f0;}'
        '.ci-filter-label{color:#cbd5e1;margin-right:4px;}'
        '.ci-chip{background:rgba(255,255,255,.10);color:#f1f5f9;'
        'border:1px solid rgba(255,255,255,.28);border-radius:14px;'
        'padding:3px 10px;cursor:pointer;font-size:12px;line-height:1.4;}'
        '.ci-chip:hover{background:rgba(255,255,255,.20);}'
        '.ci-chip.active{background:#2563eb;border-color:#2563eb;color:#fff;}'
        '.ci-chip-cnt{color:#cbd5e1;margin-left:2px;}'
        '.ci-chip.active .ci-chip-cnt{color:#e0ecff;}'
        '.ci-custom{display:inline-flex;align-items:center;gap:4px;'
        'margin-left:4px;color:#cbd5e1;}'
        '.ci-custom-input{width:90px;padding:3px 8px;border-radius:6px;'
        'border:1px solid rgba(255,255,255,.28);'
        'background:rgba(255,255,255,.12);color:#f8fafc;font-size:12px;}'
        '.ci-custom-input::placeholder{color:#94a3b8;}'
        '.ci-custom-input:focus{outline:none;border-color:#2563eb;'
        'background:rgba(255,255,255,.18);}'
        '.ci-custom-cnt{color:#cbd5e1;font-size:12px;min-width:60px;}'
        '.ci-step-label{color:#cbd5e1;font-size:12px;line-height:1.5;'
        'margin:10px 0 4px;padding-left:2px;letter-spacing:.2px;}'
        '.ci-step-label:first-of-type{margin-top:2px;}'
        '</style>'
    )

    filter_row = (
        '<div class="ci-filter" data-compress-filter>'
        '<span class="ci-filter-label">按原图大小过滤：</span>'
        f'{btn_group}'
        f'{custom_input}'
        '</div>'
    )

    return f"""
    {style}
    <details class="replay-panel" style="margin:12px 0 16px;">
        <summary>🗜️ 一键批量压缩（TinyPNG · 原地替换 · 自动备份 · 可回滚）<span style="opacity:.7;font-weight:normal;"> — 共 {resolvable} 条{unresolved_hint}</span></summary>
        <div class="replay-body">
            {filter_row}
            <div class="ci-step-label">配置 TinyPNG API Key（仅首次，申请见下方）</div>
            {_render_replay_row(cmd_export)}
            <div class="ci-step-label">预览将被压缩的图片（不修改文件）</div>
            {dry_row}
            <div class="ci-step-label">执行批量压缩（原地替换，自动备份）</div>
            {apply_row}
            <div class="ci-step-label">一键回滚（从 .backup/ 恢复原图）</div>
            {_render_replay_row(cmd_restore)}
            <p class="hint" style="margin-top:8px;">
                申请 API Key：<a href="https://tinypng.com/developers" target="_blank" rel="noopener">tinypng.com/developers</a>　·　
                备份目录：<code>{_esc(backup_dir)}</code>　·　
                日志文件：<code>{_esc(log_path)}</code>　·　
                回滚命令不受阈值过滤影响
            </p>
        </div>
    </details>"""


def _shell_quote(path: str) -> str:
    """仅在路径包含 shell 特殊字符时加双引号，普通路径裸写便于复制。"""
    if not path:
        return '""'
    unsafe = set(' \t\n"\'\\()[]{}<>|&;*?$`#!~')
    if any(ch in unsafe for ch in path):
        return f'"{path}"'
    return path


# ============================================================================
# 各区块渲染
# ============================================================================

def _render_category_section(result: ApkSizeResult) -> str:
    stats = sorted(result.category_stats.values(),
                   key=lambda s: s.total_compressed, reverse=True)
    if not stats:
        return '<p class="empty">APK 内没有可统计的条目</p>'

    total = result.total_compressed or 1
    conic_segments = [(s.label, s.total_compressed,
                       _CATEGORY_COLORS.get(s.category, '#94a3b8'))
                      for s in stats]
    conic_value = _build_conic(conic_segments)

    rows = []
    for s in stats:
        ratio = s.total_compressed / total * 100
        color = _CATEGORY_COLORS.get(s.category, '#94a3b8')
        rows.append(f"""
        <tr>
            <td><span class="dot" style="background:{color}"></span>{_esc(s.label)}</td>
            <td class="num">{s.file_count}</td>
            <td class="num">{_fmt_bytes(s.total_compressed)}</td>
            <td class="num">{_fmt_bytes(s.total_uncompressed)}</td>
            <td class="num">{ratio:.1f}%</td>
            <td><div class="progress"><div class="progress-fill" style="width:{ratio:.2f}%;background:{color}"></div></div></td>
        </tr>""")

    return f"""
    <div class="pie-row">
        <div class="pie" style="background:conic-gradient({conic_value})">
            <div class="pie-hole">
                <div class="pie-hole-top">{_fmt_bytes(result.file_size)}</div>
                <div class="pie-hole-sub">APK 大小</div>
            </div>
        </div>
        <div class="pie-legend">
            <table class="data-table sortable">
                <thead>
                    <tr>
                        <th>类别</th>
                        <th data-type="num">文件数</th>
                        <th data-type="num">压缩后</th>
                        <th data-type="num">原始</th>
                        <th data-type="num">占比</th>
                        <th class="no-sort"></th>
                    </tr>
                </thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
        </div>
    </div>
    """


def _render_dex_section(result: ApkSizeResult) -> str:
    if not result.dex_infos:
        return '<p class="empty">无 DEX 文件</p>'

    rows = []
    dex_sorted = sorted(result.dex_infos,
                        key=lambda x: x.compressed_size, reverse=True)
    for d in dex_sorted:
        err = f'<span class="tag err">{_esc(d.error)}</span>' if not d.magic_valid else ''
        rows.append(f"""
        <tr>
            <td>{_esc(d.path)}</td>
            <td class="num">{_fmt_bytes(d.compressed_size)}</td>
            <td class="num">{_fmt_bytes(d.uncompressed_size)}</td>
            <td class="num">{d.method_count}</td>
            <td class="num">{d.class_count}</td>
            <td class="num">{d.string_count}</td>
            <td>{err}</td>
        </tr>""")

    return f"""
    <div class="summary-pills">
        <span class="pill"><b>{len(result.dex_infos)}</b> DEX 文件</span>
        <span class="pill"><b>{result.total_methods}</b> 方法</span>
        <span class="pill"><b>{result.total_classes}</b> 类</span>
    </div>
    <table class="data-table sortable">
        <thead>
            <tr>
                <th>文件</th>
                <th data-type="num">压缩后</th>
                <th data-type="num">原始</th>
                <th data-type="num">方法数</th>
                <th data-type="num">类数</th>
                <th data-type="num">字符串数</th>
                <th class="no-sort"></th>
            </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
    </table>
    """


def _render_so_section(result: ApkSizeResult) -> str:
    if not result.so_infos:
        return '<p class="empty">无 Native SO 文件</p>'

    # ABI 统计表
    abi_total = sum(s.total_compressed for s in result.abi_stats.values()) or 1
    abi_rows = []
    abi_colors = ['#f59e0b', '#3b82f6', '#10b981', '#8b5cf6', '#ec4899', '#06b6d4']
    for i, s in enumerate(sorted(result.abi_stats.values(),
                                 key=lambda x: x.total_compressed, reverse=True)):
        color = abi_colors[i % len(abi_colors)]
        ratio = s.total_compressed / abi_total * 100
        abi_rows.append(f"""
        <tr>
            <td><span class="dot" style="background:{color}"></span>{_esc(s.abi)}</td>
            <td class="num">{s.file_count}</td>
            <td class="num">{_fmt_bytes(s.total_compressed)}</td>
            <td class="num">{ratio:.1f}%</td>
        </tr>""")

    # SO 详情表（按压缩后大小降序）
    so_rows = []
    so_sorted = sorted(result.so_infos,
                       key=lambda x: x.compressed_size, reverse=True)
    for so in so_sorted:
        src = _esc(so.source_module) if so.source_module else '<span class="muted">未识别</span>'
        stored_tag = '<span class="tag warn">STORED</span>' if so.is_stored else ''
        so_rows.append(f"""
        <tr>
            <td>{_esc(so.name)}</td>
            <td>{_esc(so.abi)}</td>
            <td class="num">{_fmt_bytes(so.compressed_size)}</td>
            <td class="num">{_fmt_bytes(so.uncompressed_size)}</td>
            <td>{src}</td>
            <td>{stored_tag}</td>
        </tr>""")

    return f"""
    <h3>ABI 分布</h3>
    <table class="data-table sortable">
        <thead>
            <tr>
                <th>ABI</th>
                <th data-type="num">文件数</th>
                <th data-type="num">压缩后</th>
                <th data-type="num">占比</th>
            </tr>
        </thead>
        <tbody>{''.join(abi_rows)}</tbody>
    </table>
    <h3 style="margin-top:24px">SO 详情（共 {len(result.so_infos)} 个，按大小降序，点击表头可切换排序）</h3>
    <table class="data-table sortable">
        <thead>
            <tr>
                <th>文件名</th>
                <th>ABI</th>
                <th data-type="num">压缩后</th>
                <th data-type="num">原始</th>
                <th>来源模块</th>
                <th>存储方式</th>
            </tr>
        </thead>
        <tbody>{''.join(so_rows)}</tbody>
    </table>
    """


def _render_large_files_section(result: ApkSizeResult) -> str:
    """大文件 Top 表格"""
    if not result.large_files:
        return '<p class="empty">未发现超过 1MB 的大文件</p>'

    rows = []
    for e in result.large_files[:20]:
        label = FileCategory.LABELS.get(e.category, e.category)
        rows.append(f"""
        <tr>
            <td>{_esc(e.path)}</td>
            <td>{_esc(label)}</td>
            <td class="num">{_fmt_bytes(e.compressed_size)}</td>
            <td class="num">{_fmt_bytes(e.uncompressed_size)}</td>
        </tr>""")

    return f"""
    <h3>大文件 Top {min(20, len(result.large_files))}（>1MB，共 {len(result.large_files)} 个，点击表头可切换排序）</h3>
    <table class="data-table sortable">
        <thead>
            <tr>
                <th>路径</th>
                <th>类别</th>
                <th data-type="num">压缩后</th>
                <th data-type="num">原始</th>
            </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
    </table>"""


def _render_images_section(result: ApkSizeResult,
                           image_assets: List = None,
                           assets_rel_dir: str = '',
                           compress_info: Optional[dict] = None) -> str:
    """可优化图片表格（PNG/JPG >100KB）

    :param image_assets: List[(FileEntry, local_filename or None)]
                         由 image_extractor 解压后生成，local_filename 为 None 表示解压失败
    :param assets_rel_dir: 图片相对 HTML 的目录（如 'report_assets/images'）
    :param compress_info: 可选，批量压缩脚本生成结果，有值时展示一键命令面板
    """
    if not result.optimizable_images:
        return '<p class="empty">未发现可优化图片（PNG/JPG >100KB）</p>'

    total_compressed = sum(e.compressed_size for e in result.optimizable_images)
    total_count = len(result.optimizable_images)

    # 建立 APK 路径 → 本地文件名 / 分辨率 映射
    asset_map = {}
    size_map = {}  # entry.path -> (w, h)
    if image_assets:
        for entry, local_name, wh in image_assets:
            if local_name:
                asset_map[entry.path] = local_name
            if wh:
                size_map[entry.path] = wh

    # 建立 APK 路径 → ImageUsage 映射（源码反查结果）
    usage_map = {u.apk_path: u for u in result.image_usages}

    preview_count = len(asset_map)
    overflow_count = max(0, total_count - preview_count)

    # 缩略图视图（全部展示，不截断）
    grid_cards = []
    for idx, entry in enumerate(result.optimizable_images, 1):
        local_name = asset_map.get(entry.path)
        is_9patch = entry.path.lower().endswith('.9.png')
        ext = Path(entry.path).suffix.lower()

        basename = os.path.basename(entry.path)
        size_label = _fmt_bytes(entry.compressed_size)
        # 体积分层标色：>=1MB 红，>=500KB 橙，其他默认深色（阈值 >=100KB 才会进来）
        if entry.compressed_size >= 1024 * 1024:
            size_cls = 'img-size-hot'
        elif entry.compressed_size >= 512 * 1024:
            size_cls = 'img-size-warn'
        else:
            size_cls = ''
        # 分辨率（解压时已读取，零依赖；读不到时不展示）
        _wh = size_map.get(entry.path)
        dim_html = (f' <span class="img-dim">{_wh[0]}×{_wh[1]}</span>'
                    if _wh else '')
        if local_name:
            rel_src = f"{assets_rel_dir}/{local_name}" if assets_rel_dir else local_name
            # 失败占位（hidden 初始），onerror 时交换显示
            fallback_html = (
                f'<div class="img-missing" data-role="fallback" hidden>'
                f'<div class="mi-icon">🖼️</div>'
                f'<div class="mi-name">{_esc(basename)}</div>'
                f'<div class="mi-size">{_esc(size_label)}</div>'
                f'<div class="mi-hint">图片资源丢失</div>'
                f'</div>'
            )
            # 反查引用 payload（灯箱展示完整路径用）
            usage_for_lightbox = usage_map.get(entry.path)
            refs_json = _build_refs_payload(
                usage_for_lightbox, project_root=result.project_root)
            img_html = (
                f'<img src="{_esc(rel_src)}" loading="lazy" alt="{_esc(basename)}" '
                f'onerror="handleImgError(this)" '
                f'onclick="openLightbox(this, {_quote_js(entry.path)}, '
                f'{_quote_js(size_label)}, {_quote_js(refs_json)})">'
                f'{fallback_html}'
            )
        else:
            img_html = (
                f'<div class="img-missing">'
                f'<div class="mi-icon">🚫</div>'
                f'<div class="mi-name">{_esc(basename)}</div>'
                f'<div class="mi-size">{_esc(size_label)}</div>'
                f'<div class="mi-hint">无法预览</div>'
                f'</div>'
            )

        # 左上角：序号 + 使用次数徽章；右上角：9P 等类型标签
        tl_badges = f'<span class="img-idx">#{idx}</span>'
        tr_badges = ''
        if is_9patch:
            tr_badges += '<span class="img-tag img-tag-9p">9P</span>'
        # 源码引用可信度徽章（仅当启用了源码关联时显示）
        usage = usage_map.get(entry.path)
        if usage:
            conf_label = {
                'green': ('✓', 'img-tag-ok', '静态引用'),
                'yellow': ('~', 'img-tag-weak', '仅动态引用'),
                'red': ('✗', 'img-tag-bad', '未找到引用'),
            }.get(usage.confidence, ('', '', ''))
            if conf_label[0]:
                tl_badges += (f'<span class="img-tag {conf_label[1]}" '
                              f'title="{_esc(conf_label[2])}">'
                              f'{conf_label[0]} {len(usage.refs)}</span>')

        # 使用位置提示（缩略图下方紧凑显示）
        usage_html = ''
        if usage:
            if usage.ui_hint:
                usage_html = (f'<div class="img-usage">📍 '
                              f'{_esc(usage.ui_hint)}</div>')
            elif usage.refs:
                first = usage.refs[0]
                usage_html = (f'<div class="img-usage" '
                              f'title="{_esc(first.file)}:{first.line}">'
                              f'📍 {_esc(os.path.basename(first.file))}'
                              f':{first.line}</div>')
            else:
                usage_html = '<div class="img-usage img-usage-none">🚫 未找到引用</div>'

        grid_cards.append(f"""
        <div class="img-card">
            <div class="img-thumb">
                {img_html}
                <div class="img-badges-tl">{tl_badges}</div>
                <div class="img-badges-tr">{tr_badges}</div>
            </div>
            <div class="img-meta" title="{_esc(entry.path)}">
                <div class="img-name">{_esc(basename)}</div>
                <div class="img-size"><strong class="{size_cls}">{_fmt_bytes(entry.compressed_size)}</strong> <span class="img-ext">{_esc(ext)}</span>{dim_html}</div>
                {usage_html}
            </div>
        </div>""")

    # 表格视图（全部展示，不截断）- 有源码关联时多一列
    has_usage = bool(result.image_usages)
    table_rows = []
    for e in result.optimizable_images:
        ext = Path(e.path).suffix.lower()
        usage_cell = ''
        if has_usage:
            u = usage_map.get(e.path)
            if not u:
                usage_cell = '<td><span class="muted">-</span></td>'
            else:
                conf_badge = {
                    'green': '<span class="tag good">✓ 静态</span>',
                    'yellow': '<span class="tag warn">~ 动态</span>',
                    'red': '<span class="tag err">✗ 无</span>',
                }.get(u.confidence, '')
                refs_detail = ''
                if u.refs:
                    items = ''.join(
                        f'<li><code>{_esc(r.file)}:{r.line}</code>'
                        f' <span class="muted">[{r.kind}]</span></li>'
                        for r in u.refs[:10])
                    refs_detail = (f'<details class="ref-list">'
                                   f'<summary>{len(u.refs)} 处</summary>'
                                   f'<ul>{items}</ul></details>')
                ui_hint_html = (f'<div class="muted">→ {_esc(u.ui_hint)}</div>'
                                if u.ui_hint else '')
                usage_cell = (f'<td>{conf_badge}{refs_detail}{ui_hint_html}</td>')

        table_rows.append(f"""
        <tr>
            <td>{_esc(e.path)}</td>
            <td>{_esc(ext)}</td>
            <td class="num">{_fmt_bytes(e.compressed_size)}</td>
            <td class="num">{_fmt_bytes(e.uncompressed_size)}</td>
            {usage_cell}
        </tr>""")

    usage_th = '<th>引用情况</th>' if has_usage else ''

    overflow_note = ''
    if overflow_count > 0:
        overflow_note = (f'<p class="hint">共 {total_count} 张，'
                         f'其中 {overflow_count} 张解压失败仅显示占位。</p>')

    # 源码引用统计胶囊（仅当启用）
    usage_pill = ''
    if has_usage:
        red = sum(1 for u in result.image_usages if u.confidence == "red")
        yellow = sum(1 for u in result.image_usages
                     if u.confidence == "yellow")
        green = sum(1 for u in result.image_usages
                    if u.confidence == "green")
        usage_pill = (f' · 引用 <b style="color:#10b981">{green}</b> 静态 / '
                      f'<b style="color:#f59e0b">{yellow}</b> 动态 / '
                      f'<b style="color:#ef4444">{red}</b> 未找到')

    preview_suffix = (f' · <b>{preview_count}</b> 张已预览'
                      if overflow_count > 0 else '')

    # 批量压缩一键命令面板（仅当生成了清单时展示）
    compress_panel = _render_compress_panel(compress_info)

    return f"""
    <p class="summary-line">共 <b>{total_count}</b> 张可优化图片，合计 <b>{_fmt_bytes(total_compressed)}</b>（压缩后）{usage_pill}{preview_suffix}</p>
    {compress_panel}

    <div class="view-toggle">
        <button class="view-btn active" data-view="grid" data-target="images-view">🖼 缩略图</button>
        <button class="view-btn" data-view="table" data-target="images-view">📊 表格</button>
    </div>
    <p class="hint">建议：转为 WebP 可节省约 25~40%，或使用 pngquant / guetzli 压缩后保留原格式。点击缩略图可放大查看。</p>

    <div class="view-body" data-view-group="images-view">
        <div class="view-pane active" data-view-pane="grid">
            <div class="img-grid">
                {''.join(grid_cards)}
            </div>
            {overflow_note}
        </div>
        <div class="view-pane" data-view-pane="table">
            <table class="data-table sortable">
                <thead>
                    <tr>
                        <th>路径</th>
                        <th>格式</th>
                        <th data-type="num">压缩后</th>
                        <th data-type="num">原始</th>
                        {usage_th}
                    </tr>
                </thead>
                <tbody>{''.join(table_rows)}</tbody>
            </table>
        </div>
    </div>"""


def _quote_js(s: str) -> str:
    """把字符串包装为 JS 字符串字面量（安全转义用于 onclick）"""
    escaped = (s.replace('\\', '\\\\')
                .replace("'", "\\'")
                .replace('"', '&quot;')
                .replace('\n', '\\n')
                .replace('\r', ''))
    return f"'{escaped}'"


def _build_refs_payload(usage, project_root: str = '') -> str:
    """把 ImageUsage 的 refs 序列化为 JSON 字符串，供灯箱 JS 渲染。

    :param project_root: 工程根绝对路径；用于构造 file:// 形式的父目录链接，
                         让用户点击后能直接跳到文件所在目录。
                         空值时不附带 dir 字段，前端降级为纯文本展示。
    空引用返回 '[]'；含 refs 时仅保留前 50 条，按 kind 降序（static 先）。
    """
    if not usage or not usage.refs:
        return '[]'
    kind_rank = {'static': 0, 'dynamic': 1}
    sorted_refs = sorted(
        usage.refs,
        key=lambda r: (kind_rank.get(r.kind, 9), r.file, r.line))
    root_abs = os.path.abspath(project_root) if project_root else ''
    payload = []
    for r in sorted_refs[:50]:
        item = {
            'file': r.file,             # 相对 project_root 的路径
            'line': r.line,
            'kind': r.kind,
            'snippet': (r.snippet or '')[:200],
        }
        if root_abs:
            abs_file = os.path.normpath(os.path.join(root_abs, r.file))
            # 点击定位到文件所在目录（大多数 OS 的文件管理器支持 file:///dir/）
            item['dir'] = os.path.dirname(abs_file)
            item['abs'] = abs_file
        payload.append(item)
    # 顶部附带 ui_hint（若存在），JS 中可识别首条 __hint 字段
    if usage.ui_hint:
        payload.insert(0, {'__hint': usage.ui_hint})
    return json.dumps(payload, ensure_ascii=False)


# ============================================================================
# 源码关联区块
# ============================================================================

def _render_project_banner(result: ApkSizeResult) -> str:
    """在 header 下方展示工程根与源码关联状态横幅"""
    if not result.project_root:
        return ''
    tag = '自动识别' if result.project_auto_detected else '显式指定'
    img_total = len(result.image_usages)
    red = sum(1 for u in result.image_usages if u.confidence == 'red')
    unused_count = len(result.unused_resources)

    bits = [f'<span class="pb-tag">🔗 {_esc(tag)}</span>']
    if result.app_module:
        mod_tag = '自动推断' if result.app_module_auto_detected else '显式'
        bits.append(f'<span class="pb-stat">module ({_esc(mod_tag)}): '
                    f'<b>{_esc(result.app_module)}</b></span>')
    if img_total:
        bits.append(f'<span class="pb-stat">图片引用: '
                    f'{img_total - red} 有 / '
                    f'<b style="color:#ef4444">{red}</b> 无</span>')
    if unused_count:
        size = sum(u.estimated_size for u in result.unused_resources)
        size_str = f'（约 {_fmt_bytes(size)}）' if size else ''
        bits.append(f'<span class="pb-stat">Lint 未用资源: '
                    f'<b style="color:#f59e0b">{unused_count}</b> 项'
                    f'{size_str}</span>')
    elif result.unused_res_scan_note:
        # note 可能多行，横幅里仅显示第一行概述（详情在未用资源 Tab 的引导块）
        first = result.unused_res_scan_note.splitlines()[0]
        bits.append(f'<span class="pb-stat pb-note">📋 '
                    f'{_esc(first)}</span>')

    return f"""
    <div class="project-banner">
        <div class="pb-head">
            <span class="pb-icon">📂</span>
            <code class="pb-path">{_esc(result.project_root)}</code>
            {''.join(bits)}
        </div>
    </div>"""


def _render_unused_tab_btn(result: ApkSizeResult) -> str:
    """未用资源 Tab 按钮；始终展示。未启用源码关联时，Tab 内显示启用引导"""
    count = len(result.unused_resources)
    badge = f'<span class="tab-count">{count}</span>' if count else ''
    return (f'<button class="tab-btn" data-tab="unused">'
            f'🧹 未用资源{badge}</button>')


def _render_unused_panel(result: ApkSizeResult) -> str:
    """未用资源 Tab 面板；始终渲染。未启用源码关联时，由 _render_unused_section 展示引导"""
    total_size = sum(u.estimated_size for u in result.unused_resources)
    badge = (_render_size_badge(total_size, 0.0)
             if total_size else '')
    return f"""
    <div class="panel" data-panel="unused">
        <h2>Lint 未使用资源{badge}</h2>
        {_render_unused_section(result)}
    </div>"""


def _render_unused_section(result: ApkSizeResult) -> str:
    """未使用资源表格"""
    if not result.unused_resources:
        # 优先使用扫描过程中产生的多行 note（含 gradlew 手动命令 + 重放命令）
        note = result.unused_res_scan_note
        if note:
            # note 形如：
            #   第1行：概述（"未找到 Lint XML 报告，已跳过未用资源扫描。"）
            #   后续行：缩进的说明与命令；其中 2 个缩进命令行需渲染为 <code>
            lines = note.splitlines()
            title_line = lines[0] if lines else '未找到 Lint 报告'
            body_html = []
            for raw in lines[1:]:
                stripped = raw.strip()
                if not stripped:
                    continue
                # 启发式：行首有 ./gradlew / gradle / python3 / cd 视为命令行
                is_cmd = stripped.startswith(('./gradlew', 'gradle ',
                                              'python3', 'cd '))
                if is_cmd:
                    body_html.append(
                        f'<div class="ue-cmd"><code>{_esc(stripped)}</code>'
                        f'<button class="copy-btn" '
                        f'onclick="copyReplayCmd(this)">复制</button></div>'
                    )
                else:
                    body_html.append(f'<div class="ue-line">{_esc(stripped)}</div>')
            return f"""
            <div class="unused-empty">
                <div class="ue-icon">📋</div>
                <div class="ue-title">{_esc(title_line)}</div>
                <div class="ue-guide">
                    {''.join(body_html)}
                </div>
            </div>"""
        # 兜底：区分「未传 --project」与「传了但未找到 Lint 报告」
        if not result.project_root:
            return """
        <div class="unused-empty">
            <div class="ue-icon">🔗</div>
            <div class="ue-title">未启用源码关联分析</div>
            <div class="ue-note">
                本次分析未指定 Android 工程根，无法执行 Lint 未使用资源扫描。
            </div>
            <div class="ue-guide">
                <div class="ue-line">传入 <code>--project &lt;工程根&gt;</code> 参数后重跑，即可启用：</div>
                <div class="ue-cmd">
                    <code>python3 analyze_apk.py &lt;APK&gt; --project &lt;工程根&gt;</code>
                    <button class="copy-btn" onclick="copyReplayCmd(this)">复制</button>
                </div>
                <div class="ue-line">
                    工程根需包含 <code>settings.gradle</code> 或 <code>settings.gradle.kts</code>。
                </div>
                <div class="ue-line">
                    若 APK 位于典型构建产物路径（<code>build/outputs/apk/</code> 等）下，脚本会自动推断工程根。
                </div>
            </div>
        </div>"""
        return """
        <div class="unused-empty">
            <div class="ue-icon">📋</div>
            <div class="ue-title">暂无数据</div>
            <div class="ue-note">未找到 Lint 报告。运行 ./gradlew lintReportRelease 后重放分析即可启用。</div>
            <div class="ue-hint">
                生成 Lint 报告：<code>./gradlew lintReportRelease</code>（不带冒号前缀，Gradle 会对所有启用 AGP 的 subproject 执行）<br>
                报告位置：<code>*/build/reports/lint-results-*.xml</code>
            </div>
        </div>"""

    unused = result.unused_resources
    total_size = sum(u.estimated_size for u in unused)
    root_abs = (os.path.abspath(result.project_root)
                if result.project_root else '')

    # 按类型分组统计
    # 按类型聚合（分类视图 + 顶部摘要里的 Top N 类型概览）
    by_type: dict = {}
    for u in unused:
        by_type.setdefault(u.res_type, []).append(u)
    # 顶部只用一句话给出"主要类型"，避免一排 13 个分类 pill 占整屏
    top_types = sorted(by_type.items(), key=lambda kv: -len(kv[1]))[:3]
    top_types_str = ''
    if top_types:
        parts = [f'<b>{len(items)}</b> {_esc(t)}'
                 for t, items in top_types]
        extra = (f'，另 {len(by_type) - 3} 类'
                 if len(by_type) > 3 else '')
        top_types_str = f'；主要是 {" / ".join(parts)}{extra}'

    # 按模块分组统计（用于顶部筛选 chips）
    by_module: dict = {}
    for u in unused:
        key = u.module or '(根工程)'
        by_module.setdefault(key, []).append(u)
    module_chips = ''
    if len(by_module) > 1:
        chips = ['<button type="button" class="mod-chip mod-chip-all active"'
                 ' data-mod="__all__"'
                 f' onclick="filterUnusedByModule(this)">全部 '
                 f'<b>{len(unused)}</b></button>']
        for mod, items in sorted(by_module.items(),
                                 key=lambda kv: -len(kv[1])):
            mod_size = sum(x.estimated_size for x in items)
            size_str = (f' · {_fmt_bytes(mod_size)}'
                        if mod_size else '')
            chips.append(
                f'<button type="button" class="mod-chip"'
                f' data-mod="{_esc(mod)}"'
                f' onclick="filterUnusedByModule(this)">'
                f'📦 {_esc(mod)} <b>{len(items)}</b>'
                f'<span class="mod-chip-size">{size_str}</span></button>')
        # 默认折叠：module 数量多时（如大型工程有 20+ 模块）chips 本身就是一大片，
        # 占掉两三行显示空间；用户绝大多数时候是"先看全部 → 按需下钻某个 module"，
        # 默认折起能让表格立刻上浮到视口内。summary 里带上「当前筛选：XXX」实时
        # 状态标签（由 filterUnusedByModule 同步更新），折叠态下也能看到选中的是哪个。
        module_chips = (
            '<details class="mod-chips-panel">'
            '<summary class="mod-chips-summary">'
            '<span class="mod-chips-label">按 module 筛选</span>'
            f'<span class="mod-chips-meta">共 <b>{len(by_module)}</b> 个 module</span>'
            '<span class="mod-chips-current" data-current-label>'
            '当前：<b>全部</b></span>'
            '</summary>'
            '<div class="mod-chips-wrap">'
            f'<div class="mod-chips">{"".join(chips)}</div>'
            '</div>'
            '</details>')

    # 按 module 升序 + 体积降序（供表格视图 / 非图片类分组共用，保留兼容）
    rows = []
    for u in sorted(unused,
                    key=lambda x: (x.module or '~', -x.estimated_size)):
        loc = _render_defined_at(u.defined_at, u.line, root_abs)
        size_cell = (_fmt_bytes(u.estimated_size)
                     if u.estimated_size else
                     '<span class="muted">-</span>')
        mod_display = u.module or '(根工程)'
        rows.append(f"""
        <tr data-mod="{_esc(mod_display)}">
            <td><span class="mod-tag">{_esc(mod_display)}</span></td>
            <td><span class="res-type">{_esc(u.res_type)}</span></td>
            <td><code>{_esc(u.res_name)}</code></td>
            <td class="num">{size_cell}</td>
            <td>{loc}</td>
        </tr>""")

    # 分类视图：按 res_type 分组，图片类用缩略图网格，其它用紧凑表格
    type_sections = _render_unused_type_sections(by_type, root_abs)

    # Lint 报告来源：多报告时列出所有路径（默认折叠），单报告保持原有单行
    lint_info = ''
    all_reports = result.lint_report_paths or (
        [result.lint_report_path] if result.lint_report_path else [])
    if len(all_reports) > 1:
        items = ''.join(
            f'<li><code>{_esc(_short_path(p, root_abs))}</code></li>'
            for p in all_reports)
        # 默认折叠（去掉 open），报告条数多时占位太长，用户需要时点开即可
        lint_info = (
            f'<details class="lint-sources">'
            f'<summary>已聚合 <b>{len(all_reports)}</b> 份 Lint 报告</summary>'
            f'<ul class="lint-sources-list">{items}</ul>'
            f'</details>')
    elif all_reports:
        lint_info = (f'<p class="hint">Lint 报告来源：'
                     f'<code>{_esc(_short_path(all_reports[0], root_abs))}</code></p>')

    coverage_warn = _render_coverage_warning(result, by_module)

    return f"""
    <p class="hint">⚠️ Lint 对反射、动态拼接（getIdentifier）、DataBinding 动态表达式等引用场景可能误报，删除前请核对。</p>
    <p class="summary-line">共 <b>{len(unused)}</b> 未使用资源，估算体积 <b>{_fmt_bytes(total_size)}</b>{top_types_str}</p>
    {coverage_warn}
    {module_chips}
    {lint_info}
    <div class="unused-view-tabs">
        <button type="button" class="uv-tab active" data-view="grouped"
                onclick="switchUnusedView(this)">📦 分类视图</button>
        <button type="button" class="uv-tab" data-view="table"
                onclick="switchUnusedView(this)">📋 汇总表格</button>
        <span class="uv-spacer"></span>
        <button type="button" class="uv-toggle" onclick="toggleAllUnusedGroups(this)"
                data-expanded="0" title="展开/收起所有分组">展开全部</button>
    </div>
    <div class="unused-view unused-view-grouped" data-view="grouped">
        {type_sections}
    </div>
    <div class="unused-view unused-view-table" data-view="table" style="display:none;">
        <table class="data-table sortable" id="unused-table">
            <thead>
                <tr>
                    <th>module</th>
                    <th>类型</th>
                    <th>资源名</th>
                    <th data-type="num">估算体积</th>
                    <th>定义位置</th>
                </tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
    </div>"""


# ----------------------------------------------------------------------------
# 未用资源分类视图
# ----------------------------------------------------------------------------

# 浏览器原生支持的光栅/矢量图扩展名（可直接作为 <img src="file://..."> 预览）
_PREVIEWABLE_IMG_EXTS = {'.png', '.webp', '.jpg', '.jpeg', '.gif', '.svg',
                         '.bmp', '.ico'}

# 类型图标（仅用于分组 summary 的装饰）
_RES_TYPE_ICONS = {
    'drawable': '🖼️', 'mipmap': '🖼️', 'raw': '📦', 'color': '🎨',
    'string': '🔤', 'layout': '📐', 'dimen': '📏', 'style': '✨',
    'menu': '📑', 'anim': '🎬', 'animator': '🎬', 'font': '🔠',
    'array': '📚', 'attr': '🏷️', 'id': '🆔', 'integer': '🔢',
    'bool': '☑️', 'plurals': '🔢', 'xml': '📄', 'interpolator': '📈',
    'transition': '🔄', 'navigation': '🧭',
}


def _unused_abs_path(u: 'UnusedResource', root_abs: str) -> str:
    """返回未用资源定义文件的绝对路径；取不到返回空串。"""
    if not u.defined_at:
        return ''
    if os.path.isabs(u.defined_at):
        return os.path.normpath(u.defined_at)
    if root_abs:
        return os.path.normpath(os.path.join(root_abs, u.defined_at))
    return ''


def _unused_is_previewable_image(u: 'UnusedResource') -> bool:
    """判断未用资源是否为浏览器可直接预览的光栅/矢量图。

    仅认扩展名是 png/webp/jpg/gif/svg/... 的文件。XML drawable（selector/
    shape/vector）不算——浏览器无法直接渲染 Android 的 XML drawable。
    """
    if not u.defined_at:
        return False
    # 9patch：`.9.png` 浏览器可以当普通 png 渲染，但有黑色 stretch 边缘——
    # 仍作为可预览（和可优化图片那边一致）
    ext = os.path.splitext(u.defined_at)[1].lower()
    return ext in _PREVIEWABLE_IMG_EXTS


def _is_image_res_type(res_type: str) -> bool:
    """res_type 是否为「可能包含图片」的类别，用于决定分组呈现形式。"""
    return res_type in ('drawable', 'mipmap')


def _render_unused_type_sections(by_type: dict, root_abs: str) -> str:
    """渲染「按类型分组」的未用资源视图。

    - drawable / mipmap：**缩略图网格**（图片资源用 file:// 直接预览，
      点击打开灯箱大图；非图片 XML 资源降级为"卡片占位"，仍能看到名称、
      体积、定义位置）
    - 其它类型：紧凑表格（资源名 / 体积 / 定义位置 / module）
    """
    if not by_type:
        return ''
    # 图片类优先展示（drawable → mipmap → 其它按数量降序）
    priority = ['drawable', 'mipmap']
    type_order = [t for t in priority if t in by_type] + [
        t for t, _ in sorted(by_type.items(), key=lambda kv: -len(kv[1]))
        if t not in priority]

    sections = []
    for t in type_order:
        items = by_type[t]
        total = sum(x.estimated_size for x in items)
        size_str = (f' · {_fmt_bytes(total)}' if total else '')
        icon = _RES_TYPE_ICONS.get(t, '📁')
        header = (f'<summary class="ut-summary">'
                  f'<span class="ut-icon">{icon}</span>'
                  f'<span class="ut-name">{_esc(t)}</span>'
                  f'<span class="ut-count"><b>{len(items)}</b> 项{size_str}</span>'
                  f'</summary>')
        if _is_image_res_type(t):
            body = _render_unused_image_grid(items, root_abs)
        else:
            body = _render_unused_simple_table(items, root_abs)
        sections.append(
            f'<details class="ut-section" data-type="{_esc(t)}">'
            f'{header}{body}</details>')
    return ''.join(sections)


def _render_unused_image_grid(items: list, root_abs: str) -> str:
    """drawable / mipmap 分组使用的缩略图网格。

    - 可预览图（png/webp/jpg/gif/svg）：<img src="file://..."> 直接加载
      本地文件，点击打开灯箱（复用 openLightbox）
    - 不可预览（如 XML drawable）：显示占位 + 格式标签
    """
    cards = []
    # 体积降序；无体积的沉底
    items_sorted = sorted(items, key=lambda u: -(u.estimated_size or 0))
    for u in items_sorted:
        abs_path = _unused_abs_path(u, root_abs)
        ext = (os.path.splitext(u.defined_at)[1].lower()
               if u.defined_at else '')
        basename = (os.path.basename(u.defined_at)
                    if u.defined_at else u.res_name)
        size_label = (_fmt_bytes(u.estimated_size)
                      if u.estimated_size else '—')
        size_cls = ''
        if u.estimated_size >= 1024 * 1024:
            size_cls = 'img-size-hot'
        elif u.estimated_size >= 512 * 1024:
            size_cls = 'img-size-warn'
        mod_display = u.module or '(根工程)'

        # 分辨率（仅可预览位图有效，SVG / XML 读不到时不展示）
        _wh = read_image_size(abs_path) if abs_path else None
        dim_html = (f'<span class="img-dim">{_wh[0]}×{_wh[1]}</span>'
                    if _wh else '')

        # 缩略图主体
        if _unused_is_previewable_image(u) and abs_path:
            # 未用资源：卡片不显示定义位置（path + 📄/📂），改在灯箱的右列展示
            # （卡片寸土寸金，缩略图网格塞路径会把每张卡挤得很高且可读性差）
            file_url = 'file://' + _encode_file_url_path(abs_path)
            # 灯箱 path 显示用"相对工程根"路径，size 显示体积
            lb_path = _short_path(u.defined_at, root_abs) or u.res_name
            # 构造未用资源专用的 refs payload：首项带 __unused 标记，
            # 携带定义位置的绝对路径 / 目录 / 行号，供灯箱 JS 识别并渲染
            # 「定义位置」区（而非默认的「源码引用」区）
            lb_payload = [{
                '__unused': True,
                'defined_at': lb_path,
                'abs': abs_path,
                'dir': os.path.dirname(abs_path),
                'line': int(u.line or 0),
                'module': mod_display,
                'res_type': u.res_type,
                'res_name': u.res_name,
            }]
            refs_json = json.dumps(lb_payload, ensure_ascii=False)
            img_html = (
                f'<img src="{_esc(file_url)}" loading="lazy" '
                f'alt="{_esc(basename)}" '
                f'onerror="handleImgError(this)" '
                f'onclick="openLightbox(this, '
                f'{_quote_js(lb_path)}, '
                f'{_quote_js(size_label)}, '
                f'{_quote_js(refs_json)})">'
                f'<div class="img-fallback" style="display:none;">'
                f'<div class="img-fb-icon">🖼️</div>'
                f'<div class="img-fb-ext">{_esc(ext or "?")}</div>'
                f'<div class="img-fb-msg">无法加载</div></div>')
        else:
            # 非图片（XML drawable 等）：占位卡片
            ext_tag = ext.lstrip('.').upper() or 'XML'
            img_html = (
                f'<div class="img-fallback img-fallback-inline">'
                f'<div class="img-fb-icon">📄</div>'
                f'<div class="img-fb-ext">{_esc(ext_tag)}</div>'
                f'<div class="img-fb-msg">非图片资源</div></div>')

        # 左上：module 徽章；右上：9P 类型标签
        tl_badges = f'<span class="img-tag img-tag-mod">📦 {_esc(mod_display)}</span>'
        tr_badges = ''
        if u.defined_at.lower().endswith('.9.png'):
            tr_badges += '<span class="img-tag img-tag-9p">9P</span>'

        # 卡片底部只留资源名 + 体积；定义位置（路径 + 📄/📂 按钮）移到灯箱内展示
        cards.append(f"""
        <div class="img-card" data-mod="{_esc(mod_display)}">
            <div class="img-thumb">
                {img_html}
                <div class="img-badges-tl">{tl_badges}</div>
                <div class="img-badges-tr">{tr_badges}</div>
            </div>
            <div class="img-meta">
                <div class="img-name" title="{_esc(u.res_name)}">{_esc(u.res_name)}</div>
                <div class="img-size">
                    <strong class="{size_cls}">{_esc(size_label)}</strong>
                    <span class="img-ext">{_esc(ext or '')}</span>
                    {dim_html}
                </div>
            </div>
        </div>""")

    return f'<div class="img-grid unused-img-grid">{"".join(cards)}</div>'


def _render_unused_simple_table(items: list, root_abs: str) -> str:
    """非图片类型的紧凑分组表格。"""
    # 体积降序 + module 升序
    items_sorted = sorted(items,
                          key=lambda u: (-(u.estimated_size or 0),
                                         u.module or '~'))
    rows = []
    for u in items_sorted:
        loc = _render_defined_at(u.defined_at, u.line, root_abs)
        size_cell = (_fmt_bytes(u.estimated_size)
                     if u.estimated_size else
                     '<span class="muted">-</span>')
        mod_display = u.module or '(根工程)'
        rows.append(f"""
        <tr data-mod="{_esc(mod_display)}">
            <td><span class="mod-tag">{_esc(mod_display)}</span></td>
            <td><code>{_esc(u.res_name)}</code></td>
            <td class="num">{size_cell}</td>
            <td>{loc}</td>
        </tr>""")
    return f"""
    <table class="data-table ut-table">
        <thead>
            <tr>
                <th>module</th>
                <th>资源名</th>
                <th class="num">估算体积</th>
                <th>定义位置</th>
            </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
    </table>"""


def _encode_file_url_path(abs_path: str) -> str:
    """把绝对路径转成 file:// URL 安全片段（保留 '/'）。

    与前端 JS 的 encodePath 保持一致逻辑，给 Windows 盘符前补 '/'。
    """
    if not abs_path:
        return ''
    norm = abs_path.replace('\\', '/')
    # Windows 盘符：C:/... → /C:/...
    if (len(norm) >= 2 and norm[1] == ':'
            and norm[0].isalpha() and not norm.startswith('/')):
        norm = '/' + norm
    return '/'.join(_url_quote(seg) for seg in norm.split('/'))


def _render_coverage_warning(result: ApkSizeResult,
                             by_module: dict) -> str:
    """当 lint 报告覆盖的 module 数明显少于工程总 module 数时，提示用户
    配置 `lint { checkDependencies true }`。

    Android Lint 默认对 library module **禁用** UnusedResources 检查
    （library 里的资源可能被依赖它的 app 引用，单独报 unused 会假阳性）；
    只有 app module 在启用 `checkDependencies` 后才能跨 module 扫出
    library 里的未用资源。因此若工程有多个 module 却只有 1~2 个 module
    命中了 UnusedResources，很可能是 app module 没开 `checkDependencies`。

    触发条件：
    - 聚合了 ≥ 3 份 lint 报告（工程确实是多 module）
    - 但出现 UnusedResources 的 module 数 ≤ 1（严重偏少）
    """
    all_reports = result.lint_report_paths or (
        [result.lint_report_path] if result.lint_report_path else [])
    total_reports = len(all_reports)
    covered_modules = len(by_module)

    # 只有多 module 工程 + 覆盖面过窄时才提示
    if total_reports < 3 or covered_modules > 1:
        return ''

    # 唯一命中的 module 名，用于示例命令
    sole_module = next(iter(by_module.keys()), result.app_module or 'app')
    if sole_module == '(根工程)':
        sole_module = result.app_module or 'app'

    sole_esc = _esc(sole_module)
    return f"""
    <div class="coverage-warn">
        <div class="cw-icon">💡</div>
        <div class="cw-body">
            <div class="cw-title">
                未用资源仅覆盖 <b>{sole_esc}</b> 1 个 module（共 {total_reports} 份 lint 报告）。
                如需扫描各 library 的未用资源，请在 app module（<b>{sole_esc}</b>）启用
                <code>checkDependencies</code>：
            </div>
            <pre class="cw-code">// {sole_esc}/build.gradle
android {{
    lint {{
        checkDependencies true
        // 可选：兜底强制开启
        enable += 'UnusedResources'
    }}
}}</pre>
            <div class="cw-foot">
                配好后重跑 <code>./gradlew :{sole_esc}:lintReportRelease</code>，
                然后重放本分析命令即可看到各 library 的未用资源。
            </div>
        </div>
    </div>"""


def _short_path(path: str, root_abs: str) -> str:
    """把绝对路径相对化为「相对工程根」的短路径；非绝对/外部路径原样返回。"""
    if not path:
        return ''
    if not root_abs or not os.path.isabs(path):
        return path
    try:
        rel = os.path.relpath(os.path.abspath(path), root_abs)
        if rel.startswith('..'):
            return path
        return rel.replace(os.sep, '/')
    except ValueError:
        return path


def _render_defined_at(defined_at: str, line: int, root_abs: str) -> str:
    """渲染未使用资源的「定义位置」单元格。

    - 相对路径：原样用 <code> 展示（主展示）
    - 若能推导出绝对路径：附带两颗按钮
      * 📄 文件：`file://` 链接，浏览器会尝试用默认程序打开文件本体
      * 📋 目录：**复制目录绝对路径到剪贴板**。之所以不做成"点击直接打开目录"，
        是因为浏览器点 `file://{dir}/` 时会把目录当成"目录列表页"渲染而不是
        交给系统文件管理器；所以这颗按钮统一只负责"复制路径"，用户粘贴到
        Finder（Cmd+Shift+G）/ Explorer 地址栏即可跳到该目录。
    - 行号：有则显示在路径右侧
    """
    if not defined_at:
        return ''
    # 相对化展示（无论原始是绝对还是相对都做兜底）
    short = _short_path(defined_at, root_abs)
    # 还原绝对路径用于跳转
    abs_file = ''
    if os.path.isabs(defined_at):
        abs_file = os.path.normpath(defined_at)
    elif root_abs:
        abs_file = os.path.normpath(os.path.join(root_abs, short))
    line_html = (f':<span class="muted">{line}</span>' if line else '')
    actions = ''
    if abs_file:
        abs_esc = _esc(abs_file)
        dir_path = os.path.dirname(abs_file)
        dir_esc = _esc(dir_path)
        actions = (
            f'<span class="loc-actions">'
            f'<a class="loc-act" href="file://{abs_esc}"'
            f' title="用默认程序打开文件：&#10;{abs_esc}"'
            f' target="_blank" rel="noopener">📄</a>'
            f'<button type="button" class="loc-act loc-copy-dir"'
            f' data-abs="{dir_esc}" onclick="copyAbsPath(this)"'
            f' title="复制目录路径到剪贴板，粘贴到 Finder（Cmd+Shift+G）/&#10;'
            f'Explorer 地址栏打开：&#10;{dir_esc}">📋</button>'
            f'</span>')
    return (f'<span class="loc-cell">'
            f'<code>{_esc(short)}</code>{line_html}{actions}'
            f'</span>')


def _render_tips_section(tips: List[OptimizationTip]) -> str:
    if not tips:
        return '<p class="empty">未发现明显的优化空间 🎉</p>'

    cards = []
    sev_label = {'high': '高优先级', 'medium': '中优先级',
                 'low': '低优先级', 'info': '提示'}
    for i, tip in enumerate(tips, 1):
        sev_cls = _severity_class(tip.severity)
        saving_html = ''
        if tip.estimated_saving:
            saving_html = f'<span class="tag good">预估节省 {_fmt_bytes(tip.estimated_saving)}</span>'

        files_html = ''
        if tip.related_files:
            items = ''.join(f'<li><code>{_esc(p)}</code></li>'
                            for p in tip.related_files[:10])
            files_html = f'<details class="file-list"><summary>涉及文件 ({len(tip.related_files)})</summary><ul>{items}</ul></details>'

        action_html = ''
        if tip.action:
            action_html = f'<div class="action"><div class="action-title">操作建议</div><pre>{_esc(tip.action)}</pre></div>'

        cards.append(f"""
        <div class="tip-card {sev_cls}">
            <div class="tip-head">
                <span class="tip-num">#{i}</span>
                <span class="tip-sev">{sev_label.get(tip.severity, tip.severity)}</span>
                {saving_html}
            </div>
            <div class="tip-title">{_esc(tip.title)}</div>
            <div class="tip-desc">{_esc(tip.description)}</div>
            {action_html}
            {files_html}
        </div>""")

    return ''.join(cards)


# ============================================================================
# HTML / CSS / JS 模板加载
# ============================================================================
# HTML 骨架 / CSS / JS 分别抽取到同级目录下的独立文件：
#   - report_html_template.html  HTML 骨架（含 {styles} / {scripts} / 各业务占位符）
#   - report_html_styles.css     样式（不经 .format()，直接字符串注入）
#   - report_html_scripts.js     交互脚本（不经 .format()，直接字符串注入）
# 把 CSS/JS 隔离到独立文件后，编辑它们时不再需要 `{{`/`}}` 双花括号转义。

_TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_template_asset(rel_name: str) -> str:
    """从脚本同级目录加载模板资源文件（CSS/JS/HTML 骨架）。"""
    path = os.path.join(_TEMPLATE_DIR, rel_name)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


_HTML_TEMPLATE = _load_template_asset('report_html_template.html')
_STYLES_CSS = _load_template_asset('report_html_styles.css')
_SCRIPTS_JS = _load_template_asset('report_html_scripts.js')
