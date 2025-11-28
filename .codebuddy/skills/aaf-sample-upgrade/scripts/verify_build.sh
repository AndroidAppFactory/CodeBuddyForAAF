#!/bin/bash

# 验证项目编译是否通过

PROJECT_PATH=$1

if [ -z "$PROJECT_PATH" ]; then
    echo "❌ 用法: verify_build.sh <项目路径>"
    exit 1
fi

if [ ! -d "$PROJECT_PATH" ]; then
    echo "❌ 项目不存在: $PROJECT_PATH"
    exit 1
fi

echo "=== 验证编译: $(basename "$PROJECT_PATH") ==="

cd "$PROJECT_PATH" || exit 1

# 清理
echo "🧹 清理构建缓存..."
./gradlew clean > /dev/null 2>&1

# 编译
echo "🔨 开始编译..."
if ./gradlew assembleDebug; then
    echo "✅ 编译成功: $(basename "$PROJECT_PATH")"
    exit 0
else
    echo "❌ 编译失败: $(basename "$PROJECT_PATH")"
    echo ""
    echo "请检查错误信息并修复后重试"
    exit 1
fi
