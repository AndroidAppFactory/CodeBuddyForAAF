#!/bin/bash

# 查找 AAF 相关项目的位置
# 按优先级：当前目录同级 > 父目录同级

CURRENT_DIR=$(pwd)
PARENT_DIR=$(dirname "$CURRENT_DIR")

find_project() {
    local project_name=$1
    
    # 优先查找同级目录
    if [ -d "$CURRENT_DIR/../$project_name" ]; then
        echo "$CURRENT_DIR/../$project_name"
        return 0
    fi
    
    # 查找父目录同级
    if [ -d "$PARENT_DIR/$project_name" ]; then
        echo "$PARENT_DIR/$project_name"
        return 0
    fi
    
    return 1
}

echo "=== 查找 AAF 项目位置 ==="

# 查找 AndroidAppFactory
AAF_PATH=$(find_project "AndroidAppFactory")
if [ $? -eq 0 ]; then
    echo "✅ AndroidAppFactory: $AAF_PATH"
else
    echo "❌ AndroidAppFactory: 未找到"
    exit 1
fi

# 查找 Template-AAF
TEMPLATE_AAF=$(find_project "Template-AAF")
if [ $? -eq 0 ]; then
    echo "✅ Template-AAF: $TEMPLATE_AAF"
else
    echo "❌ Template-AAF: 未找到"
fi

# 查找 Template_Android
TEMPLATE_ANDROID=$(find_project "Template_Android")
if [ $? -eq 0 ]; then
    echo "✅ Template_Android: $TEMPLATE_ANDROID"
else
    echo "❌ Template_Android: 未找到"
fi

# 查找 Template-Empty
TEMPLATE_EMPTY=$(find_project "Template-Empty")
if [ $? -eq 0 ]; then
    echo "✅ Template-Empty: $TEMPLATE_EMPTY"
else
    echo "❌ Template-Empty: 未找到"
fi

# 导出路径供其他脚本使用
export AAF_PATH
export TEMPLATE_AAF
export TEMPLATE_ANDROID
export TEMPLATE_EMPTY

echo ""
echo "=== 路径已导出到环境变量 ==="
echo "AAF_PATH=$AAF_PATH"
echo "TEMPLATE_AAF=$TEMPLATE_AAF"
echo "TEMPLATE_ANDROID=$TEMPLATE_ANDROID"
echo "TEMPLATE_EMPTY=$TEMPLATE_EMPTY"
