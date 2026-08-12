#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
models.py
APK 体积分析数据模型定义
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


# ============================================================================
# 常量定义
# ============================================================================

# 大文件阈值（字节）
LARGE_FILE_THRESHOLD = 1024 * 1024           # 1 MB：单文件 > 1MB 标记为「关注项」
LARGE_IMAGE_THRESHOLD = 100 * 1024           # 100 KB：图片 > 100KB 建议压缩/转 WebP

# DEX 限制
DEX_METHOD_LIMIT = 65536                     # 单个 DEX 文件方法数上限

# ZIP 压缩方式
COMPRESS_STORED = 0
COMPRESS_DEFLATED = 8


# 文件分类枚举（字符串常量，兼容 Python 3.6+）
class FileCategory:
    DEX = "dex"
    NATIVE = "native"          # lib/*/*.so
    RESOURCE = "resource"      # res/*
    RES_TABLE = "res_table"    # resources.arsc
    ASSETS = "assets"          # assets/*
    SIGNATURE = "signature"    # META-INF/*
    KOTLIN = "kotlin"          # kotlin/*
    MANIFEST = "manifest"      # AndroidManifest.xml
    OTHER = "other"

    ALL = [DEX, NATIVE, RESOURCE, RES_TABLE, ASSETS,
           SIGNATURE, KOTLIN, MANIFEST, OTHER]

    LABELS = {
        DEX: "DEX (代码)",
        NATIVE: "Native 库 (.so)",
        RESOURCE: "资源文件 (res/)",
        RES_TABLE: "资源表 (arsc)",
        ASSETS: "Assets",
        SIGNATURE: "签名信息",
        KOTLIN: "Kotlin 元数据",
        MANIFEST: "AndroidManifest",
        OTHER: "其他",
    }


# 终端颜色
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    CYAN = '\033[0;36m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    BOLD = '\033[1m'
    NC = '\033[0m'


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class FileEntry:
    """APK 内单个文件的信息"""
    path: str                   # ZIP 内完整路径
    category: str               # FileCategory
    compressed_size: int        # 压缩后大小（APK 实际占用）
    uncompressed_size: int      # 原始大小
    compress_type: int = COMPRESS_DEFLATED  # 压缩方式 (0=STORED, 8=DEFLATED)

    @property
    def is_stored(self) -> bool:
        """是否为不压缩存储"""
        return self.compress_type == COMPRESS_STORED

    @property
    def compression_ratio(self) -> float:
        """压缩率（0~1），越接近 1 压缩效果越好"""
        if self.uncompressed_size <= 0:
            return 0.0
        saved = self.uncompressed_size - self.compressed_size
        return max(0.0, saved / self.uncompressed_size)


@dataclass
class CategoryStats:
    """按类别的汇总统计"""
    category: str
    file_count: int = 0
    total_compressed: int = 0    # 压缩后总大小（APK 实际占用）
    total_uncompressed: int = 0  # 原始总大小

    @property
    def label(self) -> str:
        return FileCategory.LABELS.get(self.category, self.category)


@dataclass
class DexInfo:
    """单个 DEX 文件信息"""
    path: str
    compressed_size: int
    uncompressed_size: int
    method_count: int = 0       # method_ids_size
    class_count: int = 0        # class_defs_size
    string_count: int = 0       # string_ids_size
    magic_valid: bool = True    # DEX magic 是否正确
    error: str = ""

    @property
    def method_usage_ratio(self) -> float:
        """方法数占单 DEX 上限的比例"""
        return self.method_count / DEX_METHOD_LIMIT if DEX_METHOD_LIMIT else 0


@dataclass
class SoInfo:
    """单个 Native SO 文件信息"""
    path: str                   # ZIP 内完整路径 lib/{abi}/{name}.so
    name: str                   # 文件名
    abi: str                    # arm64-v8a / armeabi-v7a / x86 / x86_64 / ...
    compressed_size: int
    uncompressed_size: int
    is_stored: bool = False     # 是否不压缩存储
    source_module: str = ""     # 来源模块/Maven 坐标
    source_type: str = ""       # "project" / "external" / ""


@dataclass
class AbiStats:
    """按 ABI 汇总的统计"""
    abi: str
    file_count: int = 0
    total_compressed: int = 0
    total_uncompressed: int = 0


@dataclass
class OptimizationTip:
    """单条优化建议"""
    id: str                     # 建议 ID（如 'so_compression'、'png_to_webp'）
    title: str                  # 建议标题
    severity: str = "info"      # "high" / "medium" / "low" / "info"
    estimated_saving: int = 0   # 预估节省字节数（0 表示未估算）
    description: str = ""       # 问题描述
    action: str = ""            # 操作步骤
    related_files: List[str] = field(default_factory=list)  # 涉及文件


@dataclass
class ImageUsageRef:
    """图片的一条引用记录（源码中的匹配位置）"""
    file: str                    # 相对 project_root 的文件路径
    line: int                    # 行号（从 1 开始）
    snippet: str = ""            # 行内代码片段（已截断）
    kind: str = "static"         # "static"(强引用 XML/R.xxx) / "dynamic"(弱引用 字符串字面量)


@dataclass
class ImageUsage:
    """某张图片在源码中的使用情况"""
    resource_name: str           # 去扩展名的资源名（如 'ic_launcher'）
    apk_path: str                # APK 内的完整路径（用于匹配 FileEntry）
    refs: List[ImageUsageRef] = field(default_factory=list)
    ui_hint: str = ""            # 界面归属推断（如 'LoginActivity'）

    @property
    def has_static_ref(self) -> bool:
        return any(r.kind == "static" for r in self.refs)

    @property
    def has_any_ref(self) -> bool:
        return len(self.refs) > 0

    @property
    def confidence(self) -> str:
        """三档可信度：green(有强引用) / yellow(仅有弱引用) / red(未找到)"""
        if self.has_static_ref:
            return "green"
        if self.has_any_ref:
            return "yellow"
        return "red"


@dataclass
class UnusedResource:
    """Lint 检测出的未使用资源"""
    res_type: str                # drawable / layout / string / color / dimen / raw / anim / ...
    res_name: str                # 资源名（如 'ic_old_icon'）
    defined_at: str = ""         # 定义文件路径（相对项目根）
    line: int = 0                # 定义行号
    message: str = ""            # Lint 原始 message
    estimated_size: int = 0      # 从 APK 条目倒推的体积（字节，0 表示未匹配）
    module: str = ""             # 所属 Gradle module（从 lint 报告路径的第一段目录名推出，
                                 # 如 'APPTest'、'LibCommon'；无法确定时留空）


@dataclass
class ApkSizeResult:
    """APK 体积分析结果"""
    file_path: str
    file_size: int                                        # APK 总大小
    check_time: str = ""
    analyze_duration: float = 0.0                         # 分析耗时（秒），由 main() 测量
    entries: List[FileEntry] = field(default_factory=list)
    category_stats: Dict[str, CategoryStats] = field(default_factory=dict)
    dex_infos: List[DexInfo] = field(default_factory=list)
    so_infos: List[SoInfo] = field(default_factory=list)
    abi_stats: Dict[str, AbiStats] = field(default_factory=dict)
    large_files: List[FileEntry] = field(default_factory=list)
    optimizable_images: List[FileEntry] = field(default_factory=list)

    # 模块归因
    project_root: str = ""
    so_source_map: Dict[str, Dict] = field(default_factory=dict)

    # 源码关联分析（仅当 project_root 有效时填充）
    project_auto_detected: bool = False                   # True=自动推断，False=显式 --project 或未关联
    app_module: str = ""                                  # 从 APK 路径推断的 Gradle module 名（如 'app' / 'APPTest'）
    app_module_auto_detected: bool = False                # True=从 APK 路径推断得到
    image_usages: List[ImageUsage] = field(default_factory=list)
    unused_resources: List[UnusedResource] = field(default_factory=list)
    lint_report_path: str = ""                            # 使用的 lint 报告路径（主报告，一般是 app_module 的）
    lint_report_paths: List[str] = field(default_factory=list)  # 所有参与聚合的 lint 报告路径（多 module 聚合）
    unused_res_scan_note: str = ""                        # 扫描说明（如"未找到 lint 报告"）

    # 优化建议
    tips: List[OptimizationTip] = field(default_factory=list)

    # ------------------------------------------------------------------
    # 便捷属性
    # ------------------------------------------------------------------
    @property
    def total_compressed(self) -> int:
        return sum(s.total_compressed for s in self.category_stats.values())

    @property
    def total_uncompressed(self) -> int:
        return sum(s.total_uncompressed for s in self.category_stats.values())

    @property
    def total_files(self) -> int:
        return len(self.entries)

    @property
    def total_methods(self) -> int:
        return sum(d.method_count for d in self.dex_infos)

    @property
    def total_classes(self) -> int:
        return sum(d.class_count for d in self.dex_infos)

    @property
    def has_stored_so(self) -> bool:
        return any(so.is_stored for so in self.so_infos)

    @property
    def abi_count(self) -> int:
        return len(self.abi_stats)
