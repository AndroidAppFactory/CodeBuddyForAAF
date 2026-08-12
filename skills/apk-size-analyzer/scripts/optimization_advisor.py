#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
optimization_advisor.py
优化建议引擎：基于规则匹配，根据分析结果生成针对性的瘦身建议
"""

from typing import List

from models import (
    ApkSizeResult, OptimizationTip, FileCategory,
    LARGE_IMAGE_THRESHOLD, LARGE_FILE_THRESHOLD,
    DEX_METHOD_LIMIT,
)


# 严重程度
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"
SEVERITY_INFO = "info"


def advise(result: ApkSizeResult) -> List[OptimizationTip]:
    """根据分析结果生成优化建议列表

    :return: 按严重程度降序排列的 OptimizationTip 列表（同时写入 result.tips）
    """
    tips: List[OptimizationTip] = []

    tips.extend(_advise_native(result))
    tips.extend(_advise_resources(result))
    tips.extend(_advise_assets(result))
    tips.extend(_advise_dex(result))
    tips.extend(_advise_general(result))
    tips.extend(_advise_source_linked(result))

    # 按严重程度排序（high -> medium -> low -> info），相同级别按预估节省降序
    severity_rank = {SEVERITY_HIGH: 0, SEVERITY_MEDIUM: 1, SEVERITY_LOW: 2, SEVERITY_INFO: 3}
    tips.sort(key=lambda t: (severity_rank.get(t.severity, 99),
                             -t.estimated_saving))

    result.tips = tips
    return tips


# ============================================================================
# Native SO 相关建议
# ============================================================================

def _advise_native(result: ApkSizeResult) -> List[OptimizationTip]:
    tips: List[OptimizationTip] = []
    if not result.so_infos:
        return tips

    # 1) 多 ABI：建议 abiFilters 或 App Bundle
    if result.abi_count > 1:
        # 粗略估算：保留最大 ABI 即可删除其他 ABI 的总大小
        ordered = sorted(result.abi_stats.values(),
                         key=lambda s: s.total_compressed, reverse=True)
        kept = ordered[0].total_compressed if ordered else 0
        removed = sum(s.total_compressed for s in ordered[1:])

        abi_list = ", ".join(sorted(result.abi_stats.keys()))
        tips.append(OptimizationTip(
            id="multi_abi",
            title=f"APK 含 {result.abi_count} 个 ABI，建议使用 App Bundle 或 abiFilters",
            severity=SEVERITY_HIGH if removed > 1024 * 1024 else SEVERITY_MEDIUM,
            estimated_saving=removed,
            description=(
                f"APK 同时包含 {abi_list}，用户设备只会用到其中一种。"
                f"最大 ABI 占 {kept} 字节，其他 ABI 合计 {removed} 字节冗余。"
            ),
            action=(
                "方案一（推荐）：发布 Android App Bundle（AAB），Google Play 自动按设备分发；\n"
                "方案二：在 build.gradle 中配置 splits { abi { enable true; ... } } 生成多 APK；\n"
                "方案三（临时）：android { defaultConfig { ndk { abiFilters 'arm64-v8a' } } } 只保留 64 位。"
            ),
        ))

    # 2) SO 压缩存储：未压缩的 .so 应可减小 APK 体积（需要与 16KB 对齐要求权衡）
    stored_sos = [so for so in result.so_infos if so.is_stored]
    if stored_sos:
        # SO 以 STORED 存储时 compressed_size == uncompressed_size
        # 预估压缩收益（通常 DEFLATE 可省 30~50%，此处保守取 30%）
        saving = int(sum(so.compressed_size for so in stored_sos) * 0.3)
        tips.append(OptimizationTip(
            id="so_stored",
            title=f"{len(stored_sos)} 个 .so 以 STORED 方式存储（未压缩）",
            severity=SEVERITY_MEDIUM,
            estimated_saving=saving,
            description=(
                "AGP 3.6+ 默认 useLegacyPackaging=false，.so 会以未压缩存储，便于运行时 mmap。"
                "如需缩小 APK 体积，可重新启用压缩存储；"
                "但这会与 16KB 页面对齐要求冲突，需权衡评估。"
            ),
            action=(
                "android {\n"
                "    packagingOptions {\n"
                "        jniLibs { useLegacyPackaging = true }\n"
                "    }\n"
                "}\n"
                "注：Android 6.0+ 运行时会先解压再加载，启动稍慢但体积更小。"
            ),
            related_files=[so.path for so in stored_sos[:10]],
        ))

    # 3) 大型 .so 警告
    big_sos = [so for so in result.so_infos if so.compressed_size >= LARGE_FILE_THRESHOLD]
    if big_sos:
        top = sorted(big_sos, key=lambda s: s.compressed_size, reverse=True)[:5]
        top_desc = "; ".join(f"{s.name}({s.abi}, {s.compressed_size} B)" for s in top)
        tips.append(OptimizationTip(
            id="large_so",
            title=f"发现 {len(big_sos)} 个体积较大的 .so（>1MB）",
            severity=SEVERITY_LOW,
            description=(
                f"Top 5: {top_desc}. "
                "Native 库通常是 APK 体积大户，可考虑：移除未使用的模块、启用 LTO、strip 调试符号、升级到更精简的替代实现。"
            ),
            action=(
                "1) 通过 'nm -D' 检查导出符号是否都被使用；\n"
                "2) CMake 配置 -flto / -Os 优化体积；\n"
                "3) 使用 'strip --strip-unneeded' 去除调试符号（release 变体 AGP 会自动执行）；\n"
                "4) 评估第三方 SDK 是否有更轻量的替代方案。"
            ),
            related_files=[so.path for so in top],
        ))

    return tips


# ============================================================================
# 资源相关建议
# ============================================================================

def _advise_resources(result: ApkSizeResult) -> List[OptimizationTip]:
    tips: List[OptimizationTip] = []

    # 1) PNG/JPG → WebP
    images = result.optimizable_images
    if images:
        # 估算：PNG/JPG → WebP 通常节省 25~35%
        saving = int(sum(img.compressed_size for img in images) * 0.3)
        tips.append(OptimizationTip(
            id="png_to_webp",
            title=f"{len(images)} 张大图（>100KB）可转 WebP 格式",
            severity=SEVERITY_HIGH if saving > 1024 * 1024 else SEVERITY_MEDIUM,
            estimated_saving=saving,
            description=(
                "PNG/JPG 转为 WebP 通常可节省 25~35% 体积，且保持视觉无损（或接近无损）。"
                "Android 4.0+ 支持 WebP，4.3+ 支持透明 WebP。"
            ),
            action=(
                "方案一：Android Studio → 右键图片 → Convert to WebP...\n"
                "方案二：命令行 cwebp -q 75 input.png -o output.webp\n"
                "注意：.9.png（NinePatch）不建议转 WebP，会丢失拉伸信息。"
            ),
            related_files=[img.path for img in images[:10]],
        ))

    # 2) drawable 密度冗余
    density_counts = _count_density_variants(result)
    if len(density_counts) >= 4:
        tips.append(OptimizationTip(
            id="drawable_densities",
            title=f"drawable 存在 {len(density_counts)} 个密度变体，可精简",
            severity=SEVERITY_LOW,
            description=(
                "通常只需保留 xxhdpi 和 xxxhdpi 两档即可覆盖主流设备。"
                f"当前密度目录: {sorted(density_counts.keys())}"
            ),
            action=(
                "1) 在 build.gradle 中配置 resConfigs 'xxhdpi', 'xxxhdpi' 限定打包；\n"
                "2) 或删除低密度 drawable-mdpi/hdpi 目录（系统会自动降采样）。"
            ),
        ))

    return tips


def _count_density_variants(result: ApkSizeResult) -> dict:
    from resource_analyzer import count_density_variants
    return count_density_variants(result)


# ============================================================================
# Assets 相关建议
# ============================================================================

def _advise_assets(result: ApkSizeResult) -> List[OptimizationTip]:
    tips: List[OptimizationTip] = []
    asset_stats = result.category_stats.get(FileCategory.ASSETS)
    if not asset_stats or asset_stats.total_compressed < LARGE_FILE_THRESHOLD:
        return tips

    large_assets = [e for e in result.entries
                    if e.path.lower().startswith('assets/')
                    and e.compressed_size >= LARGE_IMAGE_THRESHOLD]
    if not large_assets:
        return tips

    large_assets.sort(key=lambda e: e.compressed_size, reverse=True)
    top = large_assets[:5]
    tips.append(OptimizationTip(
        id="large_assets",
        title=f"assets/ 下有 {len(large_assets)} 个大文件（>100KB）",
        severity=SEVERITY_MEDIUM,
        description=(
            "assets/ 中的大文件会直接占用 APK 体积。"
            f"Top 5: " + "; ".join(f"{e.path}({e.compressed_size} B)" for e in top)
        ),
        action=(
            "1) 评估能否通过网络下载后缓存（首次使用时拉取）；\n"
            "2) 静态资源可放到 CDN 按需加载；\n"
            "3) 文本/JSON 可考虑运行时压缩存储（gzip）；\n"
            "4) 音频/视频使用更高效编码（如 opus、h264 → h265）。"
        ),
        related_files=[e.path for e in top],
    ))

    return tips


# ============================================================================
# DEX 相关建议
# ============================================================================

def _advise_dex(result: ApkSizeResult) -> List[OptimizationTip]:
    tips: List[OptimizationTip] = []
    if not result.dex_infos:
        return tips

    total_methods = result.total_methods
    dex_count = len(result.dex_infos)

    # 1) 多 DEX 但方法数未达上限，可能 R8/Proguard 未开启
    if dex_count >= 2:
        avg_method = total_methods / dex_count if dex_count else 0
        if avg_method < DEX_METHOD_LIMIT * 0.5:
            tips.append(OptimizationTip(
                id="r8_not_enabled",
                title=f"APK 含 {dex_count} 个 DEX 但方法数利用率低，疑似未启用 R8",
                severity=SEVERITY_HIGH,
                description=(
                    f"共 {total_methods} 个方法分布在 {dex_count} 个 DEX 中，"
                    f"平均每 DEX {avg_method:.0f} 个（上限 {DEX_METHOD_LIMIT}）。"
                    "启用 R8 代码收缩后通常能消除冗余代码、合并 DEX。"
                ),
                action=(
                    "android {\n"
                    "    buildTypes {\n"
                    "        release {\n"
                    "            minifyEnabled true\n"
                    "            shrinkResources true\n"
                    "            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'),\n"
                    "                          'proguard-rules.pro'\n"
                    "        }\n"
                    "    }\n"
                    "}"
                ),
            ))

    # 2) 方法数接近上限提醒
    if total_methods >= DEX_METHOD_LIMIT * 0.9 and dex_count == 1:
        tips.append(OptimizationTip(
            id="dex_method_near_limit",
            title=f"方法数 {total_methods} 接近单 DEX 上限（{DEX_METHOD_LIMIT}）",
            severity=SEVERITY_MEDIUM,
            description="即将触发 MultiDex，建议提前启用 R8 或拆分模块",
            action="在 build.gradle 中 defaultConfig { multiDexEnabled true }，并启用 R8 收缩。",
        ))

    return tips


# ============================================================================
# 通用建议
# ============================================================================

def _advise_general(result: ApkSizeResult) -> List[OptimizationTip]:
    tips: List[OptimizationTip] = []

    # 资源压缩 / shrinkResources
    res_stats = result.category_stats.get(FileCategory.RESOURCE)
    if res_stats and res_stats.total_compressed > 2 * 1024 * 1024:
        tips.append(OptimizationTip(
            id="shrink_resources",
            title="资源目录 > 2MB，建议启用 shrinkResources 移除未引用资源",
            severity=SEVERITY_MEDIUM,
            description=(
                f"res/ 目录占 {res_stats.total_compressed} 字节。"
                "R8 的 shrinkResources 可在编译期移除未被代码引用的资源。"
            ),
            action=(
                "buildTypes { release { shrinkResources true; minifyEnabled true } }\n"
                "如果使用反射/WebView 引用资源，需在 res/raw/keep.xml 中声明保留规则。"
            ),
        ))

    # 整体 APK > 50MB 的 App Bundle 建议
    if result.file_size > 50 * 1024 * 1024:
        tips.append(OptimizationTip(
            id="use_app_bundle",
            title=f"APK 总大小 {result.file_size} 字节（>50MB），强烈建议改用 App Bundle",
            severity=SEVERITY_HIGH,
            description=(
                "Google Play 建议发布 AAB，按设备密度/ABI/语言动态分发，"
                "通常下载体积可降低 30~50%。"
            ),
            action="gradle 命令：./gradlew bundleRelease，生成 .aab 上传 Play Console。",
        ))

    return tips


# ============================================================================
# 源码关联建议（仅当关联了 project_root 时生成）
# ============================================================================

def _advise_source_linked(result: ApkSizeResult) -> List[OptimizationTip]:
    """基于源码关联分析的建议

    依赖 image_usages / unused_resources（由 analyze_apk.py 填充）。
    未关联 project_root 时这两个列表为空，自然跳过。
    """
    tips: List[OptimizationTip] = []

    # 1) 图片未被源码引用：强信号可删除
    if result.image_usages:
        red = [u for u in result.image_usages if u.confidence == "red"]
        if red:
            # 估算：从 optimizable_images 反查大小
            path_to_size = {e.path: e.compressed_size
                            for e in result.optimizable_images}
            saving = sum(path_to_size.get(u.apk_path, 0) for u in red)
            top = sorted(red,
                         key=lambda u: path_to_size.get(u.apk_path, 0),
                         reverse=True)[:10]
            tips.append(OptimizationTip(
                id="unreferenced_image",
                title=f"{len(red)} 张大图在源码中未找到引用",
                severity=SEVERITY_HIGH if saving > 512 * 1024
                else SEVERITY_MEDIUM,
                estimated_saving=saving,
                description=(
                    f"反查 {len(result.image_usages)} 张可优化图片，"
                    f"其中 {len(red)} 张在工程源码中既无静态引用"
                    f"（XML @drawable 或 R.xxx），也无动态引用（字符串字面量）。"
                    "这些图片大概率可以直接删除。"
                    "⚠️ 删除前请人工核对：可能被运行时下发、反射、"
                    "或在 buildSrc / 独立模块中引用。"
                ),
                action=(
                    "1) 对照 HTML 报告的「图片使用位置」Tab，确认 confidence=red 的图片；\n"
                    "2) 若确认未使用，直接在 res/drawable*/ 下删除对应文件；\n"
                    "3) 多密度变体（drawable-xxhdpi 等）需一并清理；\n"
                    "4) 删除后重新构建验证是否有运行时找不到资源的报错。"
                ),
                related_files=[u.apk_path for u in top],
            ))

        yellow = [u for u in result.image_usages if u.confidence == "yellow"]
        if yellow:
            top_y = yellow[:10]
            tips.append(OptimizationTip(
                id="weakly_referenced_image",
                title=f"{len(yellow)} 张图片仅有动态引用（字符串字面量）",
                severity=SEVERITY_LOW,
                description=(
                    "这些图片只在代码中以字符串形式出现（可能通过 "
                    "getIdentifier() 或拼接资源名加载），无法 100% 确认是否真被使用。"
                    "需结合业务逻辑判断。"
                ),
                action=(
                    "1) 查看 HTML 报告中的引用位置，判断上下文是否真的会加载该图片；\n"
                    "2) 若确认无用，可一并删除以节省体积；\n"
                    "3) 建议重构为 R.drawable.xxx 静态引用以便后续静态分析。"
                ),
                related_files=[u.apk_path for u in top_y],
            ))

    # 2) Lint 未使用资源汇总
    if result.unused_resources:
        unused = result.unused_resources
        total_size = sum(u.estimated_size for u in unused)
        # 按类型分组统计
        by_type: dict = {}
        for u in unused:
            by_type.setdefault(u.res_type, []).append(u)
        type_desc = ", ".join(
            f"{t}:{len(items)}" for t, items in sorted(
                by_type.items(), key=lambda kv: -len(kv[1]))[:6])

        severity = SEVERITY_HIGH if total_size > 1024 * 1024 \
            else (SEVERITY_MEDIUM if len(unused) >= 20 else SEVERITY_LOW)

        tips.append(OptimizationTip(
            id="unused_resources_significant"
            if severity != SEVERITY_LOW else "unused_resources_minor",
            title=(f"Lint 检测出 {len(unused)} 个未使用资源"
                   + (f"（估算 {total_size} 字节）"
                      if total_size else "")),
            severity=severity,
            estimated_saving=total_size,
            description=(
                f"Lint 报告: {result.lint_report_path or '(未知路径)'}\n"
                f"资源类型分布: {type_desc}\n"
                "⚠️ Lint 的 UnusedResources 检查对反射和动态引用有局限："
                "通过 getIdentifier()、DataBinding 动态表达式、Kotlin 合成属性等"
                "引用的资源可能被误报为未使用。"
            ),
            action=(
                "1) 对照 HTML 报告的「未用资源」Tab 逐项核对；\n"
                "2) 启用 R8 的 shrinkResources 自动移除未引用资源："
                "   buildTypes { release { shrinkResources true; minifyEnabled true } }；\n"
                "3) 对疑似动态引用的资源，在 res/raw/keep.xml 中声明保留："
                "   <resources tools:keep=\"@drawable/ic_dynamic_*\" />；\n"
                "4) 批量删除前先跑一遍 UI 自动化测试，确认无运行时异常。"
            ),
            related_files=[f"{u.res_type}/{u.res_name}"
                           for u in unused[:15]],
        ))

    return tips
