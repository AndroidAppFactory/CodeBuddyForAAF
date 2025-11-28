#!/bin/bash

# 读取 AAF 最新配置和版本号
# 依赖：find_projects.sh 已设置 AAF_PATH 环境变量

if [ -z "$AAF_PATH" ]; then
    echo "❌ AAF_PATH 未设置，请先运行 find_projects.sh"
    exit 1
fi

echo "=== 读取 AAF 最新配置 ==="

AAF_CONFIG="$AAF_PATH/config.gradle"
AAF_DEPS="$AAF_PATH/dependencies.gradle"
AAF_BUILD="$AAF_PATH/build.gradle"

if [ ! -f "$AAF_CONFIG" ]; then
    echo "❌ 找不到 AAF config.gradle: $AAF_CONFIG"
    exit 1
fi

# 读取 SDK 配置
COMPILE_SDK=$(grep "compileSdkVersion\s*=" "$AAF_CONFIG" | head -1 | sed 's/.*=\s*//' | tr -d ' ')
BUILD_TOOLS=$(grep "buildToolsVersion\s*=" "$AAF_CONFIG" | head -1 | sed 's/.*=\s*//' | tr -d ' "')
MIN_SDK=$(grep "libMinSdkVersion\s*=" "$AAF_CONFIG" | head -1 | sed 's/.*=\s*//' | tr -d ' ')
TARGET_SDK=$(grep "targetSdkVersion\s*=" "$AAF_CONFIG" | head -1 | sed 's/.*=\s*//' | tr -d ' ')

# 读取 AAF 版本
if [ -f "$AAF_DEPS" ]; then
    AAF_VERSION=$(grep "ext.moduleVersionName\s*=" "$AAF_DEPS" | head -1 | sed 's/.*=\s*//' | tr -d ' "')
else
    AAF_VERSION="未找到"
fi

# 读取 Kotlin 版本（优先从 build.gradle 读取）
if [ -f "$AAF_BUILD" ]; then
    KOTLIN_VERSION=$(grep "kotlin-gradle-plugin:" "$AAF_BUILD" | head -1 | sed 's/.*://;s/"//g;s/'\''//g' | tr -d ' ')
    if [ -z "$KOTLIN_VERSION" ]; then
        # 备选：从 config.gradle 读取
        KOTLIN_VERSION=$(grep "kotlin_version\s*=" "$AAF_CONFIG" | head -1 | sed 's/.*=\s*//' | tr -d ' "')
    fi
else
    KOTLIN_VERSION="未找到"
fi

# 读取 Gradle Plugin 版本
if [ -f "$AAF_BUILD" ]; then
    GRADLE_VERSION=$(grep "com.android.tools.build:gradle:" "$AAF_BUILD" | head -1 | sed 's/.*://;s/"//g;s/'\''//g' | tr -d ' ')
else
    GRADLE_VERSION="未找到"
fi

# 读取 Compose Compiler 版本
COMPOSE_VERSION=$(grep "compose_version\s*=" "$AAF_CONFIG" | head -1 | sed 's/.*=\s*//' | tr -d ' "'\''')
if [ -z "$COMPOSE_VERSION" ]; then
    COMPOSE_VERSION="未找到"
fi

# 输出结果
echo "✅ AAF 版本: $AAF_VERSION"
echo "✅ compileSdkVersion: $COMPILE_SDK"
echo "✅ buildToolsVersion: $BUILD_TOOLS"
echo "✅ libMinSdkVersion: $MIN_SDK"
echo "✅ targetSdkVersion: $TARGET_SDK"
echo "✅ Kotlin 版本: $KOTLIN_VERSION"
echo "✅ Gradle 版本: $GRADLE_VERSION"
echo "✅ Compose Compiler 版本: $COMPOSE_VERSION"

# 导出环境变量供后续使用
export AAF_VERSION
export COMPILE_SDK
export BUILD_TOOLS
export MIN_SDK
export TARGET_SDK
export KOTLIN_VERSION
export GRADLE_VERSION
export COMPOSE_VERSION

echo ""
echo "=== 配置已导出到环境变量 ==="
