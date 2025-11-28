---
name: aaf-sample-upgrade
description: 升级 AAF Sample 项目（Template-AAF、Template_Android、Template-Empty）到最新 AAF 框架版本。当用户请求升级示例项目、更新模板版本、同步示例配置，或提到"升级sample"、"升级demo"、"更新Template版本"、"同步sample配置"等关键词时使用此 skill。
---

# AAF Sample 项目升级

## 概述

**AI 辅助升级** 三个 AAF 示例项目（Template-AAF、Template_Android、Template-Empty），同步最新的 AAF 框架版本、SDK 配置、Kotlin/Gradle 版本、Compose UI 代码和 Manifest 设置。

**工作方式**：
- ✅ 提供辅助脚本（项目定位、配置读取、编译验证）
- ✅ AI 根据指导执行实际的文件修改（使用 replace_in_file 等工具）
- ✅ 灵活处理特殊情况和错误
- ✅ 引用现有 rules 避免重复（aaf_version、aaf_dependency、aaf_git）

## 工作流程决策树

当用户触发此 skill 时：

```
用户请求
    ↓
确定项目位置
    ↓
读取 AAF 最新配置
    ↓
升级 Template-AAF（第一优先级）⭐ [必须先完成]
    ├─ 更新配置
    ├─ 同步依赖  
    ├─ 同步 Compose UI 代码
    ├─ 验证编译
    └─ 如果失败 → 请求用户协助
    ↓
┌─────────────────────────────────────────────────────┐
│ 并发升级（Template-AAF 成功后可同时进行）          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  升级 Template_Android        升级 Template-Empty  │
│  （第二优先级）                （第三优先级）       │
│  ├─ 参照 Template-AAF         ├─ 参照 Template-AAF │
│  ├─ 应用相同更新              ├─ 应用最小化更新    │
│  └─ 验证编译                  └─ 验证编译          │
│                                                     │
└─────────────────────────────────────────────────────┘
    ↓
等待两个项目都完成
    ↓
生成变更报告
    ↓
提供提交建议
```

**并发执行优势**：
- ⚡ 节省时间：两个项目可同时更新和编译
- ✅ 互不影响：两者都参照 Template-AAF，彼此独立
- 🎯 效率提升：总耗时约为原来的 60-70%

## 核心升级策略

### 升级优先级顺序

**重要：必须按此顺序升级**：

1. **Template-AAF**（完整示例，第一优先级）⭐
2. **Template_Android**（基础示例，第二优先级）
3. **Template-Empty**（最简示例，第三优先级）

**为什么顺序很重要**：
- Template-AAF 是最完整的参考实现
- 如果 Template-AAF 遇到问题，必须先修复再继续
- Template_Android 和 Template-Empty 参照 Template-AAF 的解决方案
- 绝不跳过 Template-AAF 或改变顺序

### 升级内容（不只是版本号！）

**必须检查和同步**：
1. SDK 配置（compileSdk、targetSdk、buildTools）
2. Kotlin 和 Gradle 版本
3. AAF 依赖版本（所有 `com.bihe0832.android:xxx` 制品）
4. Compose 配置（`buildFeatures`、`composeOptions`）
5. Compose UI 代码（DebugMainActivity.kt、DebugTempView.kt、DebugRouterView.kt）
6. Manifest 配置（android:exported）

## 步骤 1：确定项目位置

执行 `scripts/find_projects.sh` 定位：
- AndroidAppFactory（配置源）
- Template-AAF（目标 1）
- Template_Android（目标 2）
- Template-Empty（目标 3）

预期位置：
- 与当前工作区同级 或
- 父目录同级

## 步骤 2：读取 AAF 最新配置

执行 `scripts/read_aaf_versions.sh` 提取：

**从 `AndroidAppFactory/config.gradle` 读取**：
- `compileSdkVersion`
- `buildToolsVersion`
- `libMinSdkVersion`
- `targetSdkVersion`
- `kotlin_version`
- Gradle 版本

**从 `AndroidAppFactory/dependencies.gradle` 读取**：
- `ext.moduleVersionName`（AAF 模块默认版本）

**从 `AndroidAppFactory/dependencies_*.gradle` 读取**：
- 通过 `artifactId` 查找特定模块版本
- 详见 `aaf_version.mdc` rule 的查找策略（可使用 read_rules 工具读取）

**版本查找策略**（详细方法见 `aaf_version.mdc` rule）：
1. **优先**：在 `dependencies_*.gradle` 中通过 `artifactId` 查找模块版本
2. **备选**：如果未找到，使用 `ext.moduleVersionName`
3. **验证**：验证关键依赖（kapt 处理器）的 Maven 可用性
4. **回退**：如果最新版本不可用，使用已发布版本

**重要**：执行版本查找时，使用 `read_rules` 工具读取规则，rule 名称为 `aaf_version`（不带 .mdc 后缀）。

## 步骤 3：升级 Template-AAF（第一优先级）⭐

**最重要的步骤 - 所有其他项目都参照这个**

**AI 执行以下更新**（使用 `replace_in_file` 工具）：

### 3.1 更新 config.gradle
```gradle
// 从 AAF/config.gradle 同步
compileSdkVersion = [AAF_VALUE]
buildToolsVersion = [AAF_VALUE]
libMinSdkVersion = [AAF_VALUE]
targetSdkVersion = [AAF_VALUE]
```

### 3.2 更新 build.gradle
```gradle
// Kotlin 版本
ext.kotlin_version = '[AAF_KOTLIN_VERSION]'

// Gradle 插件版本
classpath 'com.android.tools.build:gradle:[AAF_GRADLE_VERSION]'
```

### 3.3 更新 gradle-wrapper.properties
```properties
distributionUrl=https\://services.gradle.org/distributions/gradle-[VERSION]-all.zip
```

### 3.4 更新 dependencies.gradle

**两种更新方式**：

**方式 1：更新 ext.moduleVersionName**
```gradle
ext.moduleVersionName = "[NEW_AAF_VERSION]"
```

**方式 2：逐个更新模块版本**
- 在 AAF 的 `dependencies_*.gradle` 中通过 `artifactId` 查找实际版本
- 更新每个 `com.bihe0832.android:xxx:x.x.x` 依赖

### 3.5 更新 APPTest/build.gradle

**添加/更新 Compose 配置**：
```gradle
buildFeatures {
    compose = true
}
composeOptions {
    kotlinCompilerExtensionVersion = "[VERSION]"
}
```

**更新所有 AAF 依赖**：
```gradle
dependencies {
    implementation "com.bihe0832.android:common-wrapper:[VERSION]"
    implementation "com.bihe0832.android:common-debug:[VERSION]"
    kapt "com.bihe0832.android:lib-router-compiler:[VERSION]"
    // ... 其他依赖
}
```

### 3.6 同步 Compose UI 代码

**AI 执行文件复制**（使用 `read_file` + `write_to_file` 工具）：

**从 `AAF/APPTest` 复制到 `Template-AAF/APPTest`**：
- `src/main/java/com/bihe0832/android/test/DebugMainActivity.kt`
- `src/main/java/com/bihe0832/android/test/module/DebugTempView.kt`
- `src/main/java/com/bihe0832/android/test/module/DebugRouterView.kt`

**为什么要同步 UI 代码**：
- AAF 的调试视图展示最新框架特性
- Compose 实现可能有破坏性变更
- 确保示例项目展示当前最佳实践

**执行方法**：
```
1. read_file 读取 AAF 的文件内容
2. write_to_file 写入到 Template 对应位置
3. 对比确认文件已更新
```

### 3.7 更新 AndroidManifest.xml

**为所有 LAUNCHER Activity 添加 android:exported**：
```xml
<activity
    android:name=".MainActivity"
    android:exported="true">
    <intent-filter>
        <action android:name="android.intent.action.MAIN" />
        <category android:name="android.intent.category.LAUNCHER" />
    </intent-filter>
</activity>
```

### 3.8 验证编译

执行 `scripts/verify_build.sh Template-AAF`：
```bash
cd Template-AAF
./gradlew clean
./gradlew assembleDebug
```

**如果编译失败**：
- ❌ 停止 - 不要继续处理其他项目
- 📋 收集错误信息
- 👤 请求用户协助修复问题
- ✅ 验证修复有效后再继续

## 步骤 4 & 5：并发升级 Template_Android 和 Template-Empty

**重要**：Template-AAF 验证编译成功后，可以**同时**升级 Template_Android 和 Template-Empty。

### 并发执行方式

AI 可以使用以下策略：
1. **批量工具调用** - 在同一轮次中对两个项目执行相同操作
2. **并行编译** - 同时启动两个 `verify_build.sh` 进程

---

## 步骤 4：升级 Template_Android（第二优先级）

**AI 参照 Template-AAF 的成功变更执行升级**：

**💡 提示**：此步骤可与步骤 5（Template-Empty）并发执行。

### 4.1 应用 config.gradle 变更
- 从 Template-AAF 同步 SDK 配置

### 4.2 应用 build.gradle 变更
- 从 Template-AAF 同步 Kotlin 和 Gradle 版本

### 4.3 更新 Application/build.gradle
```gradle
dependencies {
    // 通过 artifactId 查找版本：
    // common-wrapper → dependencies_common.gradle → CommonWrapper.version
    // lib-router-compiler → dependencies_lib.gradle → RouterCompiler.version
    implementation "com.bihe0832.android:common-wrapper:[VERSION]"
    kapt "com.bihe0832.android:lib-router-compiler:[VERSION]"
}
```

### 4.4 更新 APPTest/build.gradle（重要！经常被遗漏！）
```gradle
// 从 Template-AAF 同步 Compose 配置
buildFeatures {
    compose = true
}
composeOptions {
    kotlinCompilerExtensionVersion = "[VERSION]"
}

dependencies {
    // common-debug → dependencies_common.gradle → CommonDebug.version
    // lib-router-compiler → dependencies_lib.gradle → RouterCompiler.version
    implementation "com.bihe0832.android:common-debug:[VERSION]"
    kapt "com.bihe0832.android:lib-router-compiler:[VERSION]"
}
```

### 4.5 同步 Compose UI 代码

**AI 从 `Template-AAF/APPTest` 复制到 `Template_Android/APPTest`**：
- DebugMainActivity.kt
- module/DebugTempView.kt
- module/DebugRouterView.kt

**重要**：直接从 Template-AAF 复制（已经在步骤 3 同步过了），确保三个项目的 UI 代码一致。

### 4.6 更新 AndroidManifest.xml
- 参照 Template-AAF 添加 android:exported

### 4.7 验证编译
```bash
cd Template_Android
./gradlew clean
./gradlew assembleDebug
```

## 步骤 5：升级 Template-Empty（第三优先级）

**AI 参照 Template-AAF 的成功变更执行升级**：

**💡 提示**：此步骤可与步骤 4（Template_Android）并发执行。

### 5.1 更新 config.gradle
```gradle
// 从 Template-AAF 同步
compileSdkVersion = [VALUE]
buildToolsVersion = [VALUE]
appMinSdkVersion = [VALUE]
targetSdkVersion = [VALUE]
```

### 5.2 更新 build.gradle（如需要）
- 从 Template-AAF 同步 Kotlin 和 Gradle 版本

### 5.3 更新 App/build.gradle

**依赖版本查找**：
```gradle
dependencies {
    // 提取 artifactId，在 AAF/dependencies_*.gradle 中查找版本：
    // common-compose-debug → dependencies_common.gradle → CommonDebugCompose.version
    // common-wrapper-min → dependencies_common.gradle → CommonWrapperMin.version
    // lib-router-compiler → dependencies_lib.gradle → RouterCompiler.version
    
    implementation "com.bihe0832.android:common-compose-debug:[VERSION]"
    implementation "com.bihe0832.android:common-wrapper-min:[VERSION]"
    kapt "com.bihe0832.android:lib-router-compiler:[VERSION]"
}
```

**注意**：某些模块如 `lib-router-compiler` 可能尚未发布到最新版本（参见 `aaf_version.mdc` rule 的特殊情况处理）。

### 5.4 更新 AndroidManifest.xml
- 参照 Template-AAF 添加 android:exported

### 5.5 兼容性修复（Android 12+）
- 确保所有 launcher Activity 都设置了 android:exported
- 如果缺少 libs/ 目录则创建

### 5.6 验证编译
```bash
cd Template-Empty
./gradlew clean
./gradlew assembleDebug
```

## 步骤 6：生成变更报告

**格式**：
```
✅ AAF 最新配置
   版本号: 8.0.0
   compileSdkVersion: 34
   buildToolsVersion: 34.0.0
   libMinSdkVersion: 23
   targetSdkVersion: 31
   Kotlin: 1.8.10
   Gradle: 7.4.1

📦 Template-AAF（第一优先级）⭐
   config.gradle:
   - compileSdkVersion: 32 → 34
   - targetSdkVersion: 30 → 31
   
   build.gradle:
   - Kotlin: 1.7.10 → 1.8.10
   - Gradle: 7.0.4 → 7.4.1
   
   dependencies.gradle:
   - 所有 AAF 模块: → 8.0.0
   
   Compose UI: ✅ 已同步
   AndroidManifest: ✅ 已更新

📦 Template_Android（第二优先级）
   [与 Template-AAF 相同结构]

📦 Template-Empty（第三优先级）
   [与 Template-AAF 相同结构]

🔍 编译验证
   ✅ Template-AAF: 通过
   ✅ Template_Android: 通过
   ✅ Template-Empty: 通过
```

## 步骤 7：提供提交建议

**只有在所有项目都编译成功后才提供提交建议！**

```bash
# Template-AAF
git commit -m "chore(sample): 升级 AAF 到 8.0.0 并同步 Compose UI

配置升级：版本号、Kotlin、Gradle、targetSdk
依赖升级：AAF 框架和所有模块
代码同步：Compose UI 代码和 Manifest 配置"

# Template_Android
git commit -m "chore(sample): 升级 AAF 到 8.0.0 并同步 Compose UI

参照 Template-AAF 的升级方案：代码、配置、依赖"

# Template-Empty
git commit -m "chore(sample): 升级 AAF 到 8.0.0 并同步编译配置

AAF 框架、targetSdk、android:exported 属性"
```

## 常见问题和解决方案

### 问题 1：Manifest 合并失败
**错误**：`android:exported needs to be explicitly specified for <activity>`
**解决**：为所有 LAUNCHER Activity 添加 `android:exported="true"`

### 问题 2：kotlin-android-extensions 已废弃
**错误**：`'kotlin-android-extensions' Gradle plugin is deprecated`
**解决**：从 build.gradle 移除该插件

### 问题 3：Kotlin 1.8+ 和 kapt 兼容性
**解决**：升级 Kotlin 到 1.8.10+，升级 Gradle 到 7.4.1+

### 问题 4：Compose Compiler 版本不匹配
**错误**：Compose Compiler version incompatible with Kotlin version
**解决**：匹配 Compose Compiler 版本到 Kotlin 版本：
- Kotlin 1.8.10 → Compose Compiler 1.4.3
- 参见 https://developer.android.com/jetpack/androidx/releases/compose-kotlin

### 问题 5：lib-router-compiler 未发布
**问题**：Maven 上没有最新版本
**解决**：使用最后发布的版本（详见 `aaf_version.mdc` rule 的 Maven 验证方法）

## 执行检查清单

### Template-AAF（第一优先级）⭐
- [ ] 读取 AAF 最新版本（ext.moduleVersionName）
- [ ] 读取 AAF SDK 配置
- [ ] 读取 Kotlin 和 Gradle 版本
- [ ] 更新 config.gradle
- [ ] 更新 build.gradle
- [ ] 更新 gradle-wrapper.properties
- [ ] 更新 dependencies.gradle
- [ ] 更新 APPTest/build.gradle（Compose 配置）
- [ ] 同步 Compose UI 代码（DebugMainActivity.kt 等）
- [ ] 更新 APPTest/AndroidManifest.xml
- [ ] **验证 Template-AAF 编译** ⚠️ **必须**
- [ ] **如果失败，请求用户协助**

### Template_Android（第二优先级）
- [ ] 参照 Template-AAF：更新 config.gradle
- [ ] 参照 Template-AAF：更新 build.gradle
- [ ] 参照 Template-AAF：更新 gradle-wrapper.properties
- [ ] 更新 Application/build.gradle
- [ ] 更新 APPTest/build.gradle
- [ ] 同步 Template-AAF 的 Compose UI 代码
- [ ] 更新 APPTest/AndroidManifest.xml
- [ ] **验证 Template_Android 编译** ⚠️ **必须**

### Template-Empty（第三优先级）
- [ ] 参照 Template-AAF：更新 config.gradle
- [ ] 参照 Template-AAF：更新 gradle-wrapper.properties（如需要）
- [ ] 更新 App/build.gradle
- [ ] 更新 App/AndroidManifest.xml
- [ ] **验证 Template-Empty 编译** ⚠️ **必须**

### 最后步骤
- [ ] 生成变更报告
- [ ] 提供提交建议
- [ ] 确认所有变更

## 资源说明

### 内部资源（辅助脚本）

**scripts/** - 辅助工具
- `find_projects.sh` - 定位 AAF 和 Template 项目位置
- `read_aaf_versions.sh` - 提取 AAF 最新配置和版本号
- `verify_build.sh` - 验证 Gradle 编译是否成功

**references/** - 参考文档
- `upgrade_checklist.md` - 详细升级检查清单和示例

**AI 使用工具**：
- `read_file` - 读取配置文件和源码
- `replace_in_file` - 更新配置文件内容
- `write_to_file` - 复制 Compose UI 代码
- `execute_command` - 执行脚本和编译验证
- `read_rules` - 读取相关规则（aaf_version、aaf_dependency）

### 外部引用（使用 read_rules 工具读取）

本 skill 依赖以下 rules，AI 执行升级时使用 `read_rules` 工具读取：

- **aaf_version** - AAF 模块版本查找方法
  - 如何通过 artifactId 查找版本号
  - Maven 验证方法
  - 版本回退策略
  
- **aaf_dependency** - AAF 依赖管理规范
  - 依赖配置文件结构
  - 依赖添加方法（Template-AAF 使用集中式依赖管理）
  
- **aaf_git** - Git 提交规范
  - Commit Message 格式
  - 提交前检查流程

## AI 执行流程说明

**这是一个 AI 辅助升级 Skill，而非完全自动化脚本**

### AI 的职责

1. **调用辅助脚本**
   - 执行 `find_projects.sh` 定位项目
   - 执行 `read_aaf_versions.sh` 读取配置
   - 执行 `verify_build.sh` 验证编译

2. **执行文件修改**
   - 使用 `read_file` 读取现有配置
   - 使用 `replace_in_file` 更新配置值
   - 使用 `write_to_file` 同步 UI 代码

3. **并发执行优化**（Template-AAF 完成后）
   - 同时修改 Template_Android 和 Template-Empty 的配置文件
   - 批量调用工具，减少轮次
   - 并行启动编译验证

4. **处理特殊情况**
   - 编译失败时分析错误
   - 版本冲突时查找正确版本（参考 aaf_version rule）
   - 依赖问题时参考 aaf_dependency rule

5. **生成报告**
   - 记录所有变更
   - 提供 git commit 建议（遵循 aaf_git rule）

### 用户的职责

1. 确认 AI 的升级方案
2. 决定是否执行 git commit
3. 处理 AI 无法解决的复杂问题

### 优势

- ✅ **灵活性**：AI 可以根据实际情况调整策略
- ✅ **智能性**：遇到问题可以分析和解决
- ✅ **可控性**：用户可以审查每一步操作
- ✅ **可扩展**：易于应对新的升级场景
- ⚡ **高效性**：Template_Android 和 Template-Empty 可并发升级

### 并发执行示例

**Template-AAF 完成后**，AI 可以在同一轮次中：

```
轮次 N：Template_Android 和 Template-Empty 配置更新
├─ replace_in_file(Template_Android/config.gradle, ...)
├─ replace_in_file(Template-Empty/config.gradle, ...)
├─ replace_in_file(Template_Android/Application/build.gradle, ...)
└─ replace_in_file(Template-Empty/App/build.gradle, ...)

轮次 N+1：UI 代码同步
├─ write_to_file(Template_Android/APPTest/DebugMainActivity.kt, ...)
└─ write_to_file(Template-Empty/.../..., ...)

轮次 N+2：并行编译验证
├─ execute_command(cd Template_Android && ./gradlew assembleDebug &)
└─ execute_command(cd Template-Empty && ./gradlew assembleDebug &)
```

**预计节省时间**：约 30-40%（主要节省在编译等待时间）
