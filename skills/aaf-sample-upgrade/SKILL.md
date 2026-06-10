---
version: 1
name: aaf-sample-upgrade
description: 升级 AAF Sample 项目（Template-AAF、Template_Android、Template-Empty）到最新 AAF 框架版本。当用户请求升级示例项目、更新模板版本、同步示例配置，或提到"升级sample"、"升级demo"、"更新Template版本"、"同步sample配置"等关键词时使用此 skill。
---

# AAF Sample 项目升级

## 概述

**AI 辅助升级** 三个 AAF 示例项目（Template-AAF、Template_Android、Template-Empty），同步最新的 AAF 框架版本、SDK 配置、Kotlin/Gradle 版本、Compose UI 代码和 Manifest 设置。

**工作方式**：
- 底层 CLI 工具：`aaf sample-check` / `aaf sample-apply --build` / `aaf sample-sync --build`
- Template-AAF 是唯一的"源"，其他两个项目通过 `sample-sync` 从 Template-AAF 复制
- AI 编排调度升级顺序
- 引用现有 rules 避免重复（aaf_version、aaf_dependency、aaf_git）

## 任务进度展示（必须）

**AI 必须使用 `todo_write` 工具展示升级进度**，让用户清晰了解当前状态。

### 初始化任务列表

用户触发升级后，立即创建任务列表：

```json
[
  {"id": "1", "status": "in_progress", "content": "检查 Template-AAF 与 AAF 的差异"},
  {"id": "2", "status": "pending", "content": "升级 Template-AAF + 编译验证"},
  {"id": "3", "status": "pending", "content": "同步修改到 Template_Android 和 Template-Empty"},
  {"id": "4", "status": "pending", "content": "编译验证其他两个项目"},
  {"id": "5", "status": "pending", "content": "生成变更报告"},
  {"id": "6", "status": "pending", "content": "提供提交建议"}
]
```

## 工作流程

```
用户请求
    ↓
【读取历史记录】（必须执行）
├─ 读取 $WORK_ROOT/temp/cache/aaf-sample-upgrade/corrections.log（若存在）
└─ 有纠正记录时，优化调度策略
    ↓
【创建任务列表】- 使用 todo_write 显示步骤
    ↓
aaf sample-check → 检查 Template-AAF 与 AAF 的差异
    ├─ 无差异 → 提示已是最新，结束
    └─ 有差异 → 展示报告，继续
    ↓
aaf sample-apply --build → 升级 Template-AAF + 编译验证
    ├─ 编译失败 → 展示错误，请求用户协助，不继续
    └─ 编译成功 → 继续
    ↓
aaf sample-sync --build → 将修改同步到 Template_Android 和 Template-Empty + 编译验证
    ├─ 某个项目编译失败 → 标记失败，继续其他项目
    └─ 全部成功 → 继续
    ↓
汇总三个项目的结果，生成变更报告
    ↓
提供提交建议（仅全部成功时）
    ↓
【记录日志】（必须执行）
├─ 成功 → 写入 history.log
└─ 用户纠正/取消 → 写入 corrections.log
```

## 执行步骤

### 步骤 1：检查差异

```bash
aaf sample-check          # 检查 Template-AAF
aaf sample-check --json   # JSON 格式
```

展示差异报告，确认有需要升级的内容后继续。

### 步骤 2：升级 Template-AAF

```bash
aaf sample-apply --build
```

这是最重要的步骤——Template-AAF 是所有其他项目的"源"。

**如果编译失败**：
- 停止 - 不要继续处理其他项目
- 展示错误信息
- 请求用户协助修复问题
- 验证修复有效后再继续

### 步骤 3：同步到其他项目

Template-AAF 编译成功后：

```bash
aaf sample-sync --build
```

这会自动将 Template-AAF 的修改复制到 Template_Android 和 Template-Empty，并编译验证。

**同步策略**：
- Template_Android：直接复制 config.gradle、build.gradle、gradle-wrapper.properties、APPTest/build.gradle、AndroidManifest.xml、3 个 Compose UI 文件；Application/build.gradle 只同步 AAF 依赖版本
- Template-Empty：同步 gradle-wrapper.properties、config.gradle（使用 appMinSdkVersion）、App/build.gradle 只同步 AAF 依赖版本、检查 AndroidManifest exported

### 步骤 4：生成变更报告

汇总三个项目的升级结果：
- AAF 最新配置（版本号、SDK、Kotlin、Gradle）
- 每个 Template 的变更详情
- 编译验证结果

### 步骤 5：提供提交建议

**只有在所有项目都编译成功后才提供提交建议！**

每个项目独立提交：
```bash
cd $AAF_HOME/Template-AAF && git commit -am "chore(sample): 升级 Template-AAF AAF 到 x.x.x"
cd $AAF_HOME/Template_Android && git commit -am "chore(sample): 同步 Template-AAF 修改到 Template_Android"
cd $AAF_HOME/Template-Empty && git commit -am "chore(sample): 同步 Template-AAF 修改到 Template-Empty"
```

## CLI 命令

| 命令 | 功能 |
|------|------|
| `aaf sample-check` | 检查 Template-AAF 与 AAF 最新配置的差异 |
| `aaf sample-apply --build` | 升级 Template-AAF + 编译验证 |
| `aaf sample-sync --build` | 将 Template-AAF 的修改同步到其他两个项目 + 编译验证 |
| `aaf config --json` | 读取 AAF 最新配置 |

## 规则依赖

| 规则 | 级别 | read_rules key | fallback 路径 |
|------|------|----------------|---------------|
| AAF 模块版本查找 | 必须 | `aaf-dev/aaf_version` | `rules/aaf/aaf_version.mdc` |
| AAF 依赖管理规范 | 必须 | `aaf-dev/aaf_dependency` | `rules/aaf/aaf_dependency.mdc` |
| AAF Git Scope | 补充 | `aaf-dev/aaf_git` | `rules/aaf/aaf_git.mdc` |

## 核心原则

- **Template-AAF 必须先编译通过**，才继续同步其他项目
- **sample-check / sample-apply 固定只处理 Template-AAF**，无需传项目参数
- **sample-sync 负责将 Template-AAF 的修改复制到其他两个项目**
- **不同模块可能有不同版本号**，逐个查找，不强行统一
- 编译失败不自行修复，展示错误请求用户协助

## 统计汇总

最终变更报告**必须**包含统计行：

```
---
[统计] 升级 X 个项目 | 成功 Y 个，失败 Z 个 | 总计变更 W 个文件，M 项依赖 | 总耗时约 Ns
```

## 自检清单

生成最终报告前，逐项自检：

| # | 检查项 | 标准 |
|---|--------|------|
| 1 | 项目覆盖 | 三个 Template 项目均已处理（或明确标注跳过原因） |
| 2 | 编译验证 | 每个项目都完成了编译验证 |
| 3 | 版本一致性 | 所有项目的 AAF 版本/SDK 配置与最新值一致 |
| 4 | 提交建议 | 仅在全部编译成功后才提供提交建议 |

## 历史归档

每次执行完成后，将摘要追加到 `$WORK_ROOT/temp/cache/aaf-sample-upgrade/history.log`：

```
[日期] AAF [版本] | Template-AAF: 成功/失败 | Template_Android: 成功/失败 | Template-Empty: 成功/失败 | 耗时约 Ns
```

## 负面反馈记录

当用户指出升级流程问题时，将反馈追加到 `$WORK_ROOT/temp/cache/aaf-sample-upgrade/corrections.log`：

```
[日期] 类型: {流程问题|遗漏|调度错误} | 用户反馈: <XXX> | 改进方案: <YYY>
```

执行前**应读取** corrections.log（如存在），优化调度策略。

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 无需升级 / 升级+编译全部成功 |
| 1 | 错误或编译失败 |
| 2 | 有可用升级（sample-check 专用） |
