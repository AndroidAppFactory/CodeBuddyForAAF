# AAF Sample 升级检查清单

## 升级前准备

- [ ] 确认 AAF 项目已编译通过
- [ ] 确认 AAF 最新版本已发布到 Maven
- [ ] 备份 Template 项目（可选）

## Template-AAF 升级 (第一优先级) ⭐

### 配置文件升级

- [ ] **config.gradle** SDK 配置
  ```gradle
  compileSdkVersion = [从 AAF 读取]
  buildToolsVersion = [从 AAF 读取]
  libMinSdkVersion = [从 AAF 读取]
  targetSdkVersion = [从 AAF 读取]
  ```

- [ ] **build.gradle** 版本配置
  ```gradle
  ext.kotlin_version = '[从 AAF 读取]'
  classpath 'com.android.tools.build:gradle:[从 AAF 读取]'
  ```

- [ ] **gradle-wrapper.properties**
  ```properties
  distributionUrl=https\://services.gradle.org/.../gradle-[VERSION]-all.zip
  ```

### 依赖升级

- [ ] **dependencies.gradle** - 方式 1：更新通用版本
  ```gradle
  ext.moduleVersionName = "[NEW_VERSION]"
  ```

  **或方式 2：**逐个更新模块版本（在各项目的 dependencies 中）

- [ ] **APPTest/build.gradle** - Compose 配置
  ```gradle
  buildFeatures {
      compose = true
  }
  composeOptions {
      kotlinCompilerExtensionVersion = "[VERSION]"
  }
  ```

- [ ] **APPTest/build.gradle** - AAF 依赖版本
  ```gradle
  dependencies {
      implementation "com.bihe0832.android:common-wrapper:[VERSION]"
      implementation "com.bihe0832.android:common-debug:[VERSION]"
      kapt "com.bihe0832.android:lib-router-compiler:[VERSION]"
      // ... 其他依赖
  }
  ```

### 代码同步

- [ ] **DebugMainActivity.kt**
  - 从 `AAF/APPTest/src/main/java/com/bihe0832/android/test/`
  - 复制到 `Template-AAF/APPTest/src/main/java/com/bihe0832/android/test/`

- [ ] **DebugTempView.kt**
  - 从 `AAF/APPTest/src/main/java/com/bihe0832/android/test/module/`
  - 复制到 `Template-AAF/APPTest/src/main/java/com/bihe0832/android/test/module/`

- [ ] **DebugRouterView.kt**
  - 从 `AAF/APPTest/src/main/java/com/bihe0832/android/test/module/`
  - 复制到 `Template-AAF/APPTest/src/main/java/com/bihe0832/android/test/module/`

### Manifest 配置

- [ ] **APPTest/src/main/AndroidManifest.xml**
  ```xml
  <activity
      android:name=".MainActivity"
      android:exported="true">  <!-- 添加此属性 -->
      <intent-filter>
          <action android:name="android.intent.action.MAIN" />
          <category android:name="android.intent.category.LAUNCHER" />
      </intent-filter>
  </activity>
  ```

### 编译验证

- [ ] **执行清理**
  ```bash
  cd Template-AAF
  ./gradlew clean
  ```

- [ ] **执行编译**
  ```bash
  ./gradlew assembleDebug
  ```

- [ ] **编译成功** ✅
  - 如果失败，必须先修复再继续！

---

## Template_Android 升级 (第二优先级)

### 配置文件升级

- [ ] **config.gradle** - 参照 Template-AAF 的修改

- [ ] **build.gradle** - 参照 Template-AAF 的修改

- [ ] **gradle-wrapper.properties** - 参照 Template-AAF 的修改

### 依赖升级

- [ ] **Application/build.gradle**
  ```gradle
  dependencies {
      // 查找版本：common-wrapper → dependencies_common.gradle → CommonWrapper.version
      implementation "com.bihe0832.android:common-wrapper:[VERSION]"
      
      // 查找版本：lib-router-compiler → dependencies_lib.gradle → RouterCompiler.version
      kapt "com.bihe0832.android:lib-router-compiler:[VERSION]"
  }
  ```

- [ ] **APPTest/build.gradle** - Compose 配置（参照 Template-AAF）
  ```gradle
  buildFeatures {
      compose = true
  }
  composeOptions {
      kotlinCompilerExtensionVersion = "[VERSION]"
  }
  ```

- [ ] **APPTest/build.gradle** - AAF 依赖
  ```gradle
  dependencies {
      // 查找版本：common-debug → dependencies_common.gradle → CommonDebug.version
      implementation "com.bihe0832.android:common-debug:[VERSION]"
      
      // 查找版本：lib-router-compiler → dependencies_lib.gradle → RouterCompiler.version
      kapt "com.bihe0832.android:lib-router-compiler:[VERSION]"
  }
  ```

### 代码同步

- [ ] **DebugMainActivity.kt** - 从 Template-AAF 复制

- [ ] **DebugTempView.kt** - 从 Template-AAF 复制

- [ ] **DebugRouterView.kt** - 从 Template-AAF 复制

### Manifest 配置

- [ ] **APPTest/src/main/AndroidManifest.xml** - 参照 Template-AAF 添加 `android:exported`

### 编译验证

- [ ] **执行清理和编译**
  ```bash
  cd Template_Android
  ./gradlew clean
  ./gradlew assembleDebug
  ```

- [ ] **编译成功** ✅

---

## Template-Empty 升级 (第三优先级)

### 配置文件升级

- [ ] **config.gradle** - 参照 Template-AAF 的修改
  ```gradle
  compileSdkVersion = [VALUE]
  buildToolsVersion = [VALUE]
  appMinSdkVersion = [VALUE]  // 注意：这里是 appMinSdkVersion
  targetSdkVersion = [VALUE]
  ```

- [ ] **build.gradle** (如需要) - 参照 Template-AAF 的修改

- [ ] **gradle-wrapper.properties** (如需要) - 参照 Template-AAF 的修改

### 依赖升级

- [ ] **App/build.gradle**
  ```gradle
  dependencies {
      // 查找版本：common-compose-debug → dependencies_common.gradle → CommonDebugCompose.version
      implementation "com.bihe0832.android:common-compose-debug:[VERSION]"
      
      // 查找版本：common-wrapper-min → dependencies_common.gradle → CommonWrapperMin.version
      implementation "com.bihe0832.android:common-wrapper-min:[VERSION]"
      
      // 查找版本：lib-router-compiler → dependencies_lib.gradle → RouterCompiler.version
      // ⚠️ 注意：可能未发布到最新版，需验证 Maven 可用性
      kapt "com.bihe0832.android:lib-router-compiler:[VERSION]"
  }
  ```

### Manifest 配置

- [ ] **App/src/main/AndroidManifest.xml** - 参照 Template-AAF 添加 `android:exported`

### 兼容性修复

- [ ] **检查 libs/ 目录** - 如不存在则创建

- [ ] **Android 12+ 兼容性** - 确认所有 LAUNCHER Activity 都有 `android:exported`

### 编译验证

- [ ] **执行清理和编译**
  ```bash
  cd Template-Empty
  ./gradlew clean
  ./gradlew assembleDebug
  ```

- [ ] **编译成功** ✅

---

## 升级完成后

### 变更报告

- [ ] 生成完整的变更报告
  - AAF 配置信息
  - 每个项目的具体变更
  - 编译验证结果

### 提交建议

- [ ] 提供 Template-AAF 的提交命令

- [ ] 提供 Template_Android 的提交命令

- [ ] 提供 Template-Empty 的提交命令

### 最终确认

- [ ] 所有三个项目编译通过 ✅

- [ ] 变更报告已生成 ✅

- [ ] 提交信息符合规范 ✅

- [ ] 用户已确认所有变更 ✅

---

## 常见问题处理

### Q1: Manifest Merger Failed
**症状**: `android:exported needs to be explicitly specified`
**解决**: 为所有 LAUNCHER Activity 添加 `android:exported="true"`

### Q2: Compose Compiler Mismatch
**症状**: Compose Compiler version incompatible
**解决**: 根据 Kotlin 版本选择对应的 Compose Compiler 版本

### Q3: kapt 依赖找不到
**症状**: Could not find com.bihe0832.android:lib-router-compiler:x.x.x
**解决**: 验证 Maven 仓库，使用已发布的最新版本

### Q4: Kotlin 版本不兼容
**症状**: Various Kotlin compatibility errors
**解决**: 确保 Kotlin、Gradle、Compose Compiler 版本匹配

### Q5: gradle-wrapper.properties 错误
**症状**: Gradle distribution not found
**解决**: 检查 distributionUrl 格式和版本号

---

## 快速参考

### 必须同步的文件

```
Template-AAF:
  config.gradle
  build.gradle
  gradle-wrapper.properties
  dependencies.gradle
  APPTest/build.gradle
  APPTest/.../DebugMainActivity.kt
  APPTest/.../DebugTempView.kt
  APPTest/.../DebugRouterView.kt
  APPTest/.../AndroidManifest.xml

Template_Android:
  config.gradle
  build.gradle
  gradle-wrapper.properties
  Application/build.gradle
  APPTest/build.gradle
  APPTest/.../DebugMainActivity.kt
  APPTest/.../DebugTempView.kt
  APPTest/.../DebugRouterView.kt
  APPTest/.../AndroidManifest.xml

Template-Empty:
  config.gradle
  gradle-wrapper.properties (如需要)
  App/build.gradle
  App/.../AndroidManifest.xml
```

### 必须验证的点

- ✅ SDK 版本同步
- ✅ Kotlin 版本同步
- ✅ Gradle 版本同步
- ✅ AAF 依赖版本更新
- ✅ Compose 配置添加
- ✅ Compose UI 代码同步
- ✅ android:exported 添加
- ✅ 所有项目编译通过
