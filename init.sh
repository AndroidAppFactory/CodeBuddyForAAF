#!/bin/bash
# author code@bihe0832.com
# CodeBuddyForAAF 初始化脚本（优化版）

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    printf "${BLUE}[INFO]${NC} %s\n" "$1"
}

log_success() {
    printf "${GREEN}[✓]${NC} %s\n" "$1"
}

log_warning() {
    printf "${YELLOW}[!]${NC} %s\n" "$1"
}

log_error() {
    printf "${RED}[✗]${NC} %s\n" "$1"
}

log_prompt() {
    printf "${CYAN}[?]${NC} %s" "$1"
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

log_info "========================================"
log_info "AAF CodeBuddy 初始化脚本（优化版）"
log_info "========================================"
log_info "当前目录: $SCRIPT_DIR"
log_info "上级目录: $PARENT_DIR"
echo ""

# 项目配置
declare -A PROJECT_INFO
PROJECT_INFO["AndroidAppFactory"]="AAF 框架核心代码库（必需）"
PROJECT_INFO["AndroidAppFactory-Doc"]="AAF 框架完整文档和 API 说明（可选）"
PROJECT_INFO["Template-Empty"]="最简示例项目，用于快速开始和内部开发（可选）"
PROJECT_INFO["Template_Android"]="基础示例项目，标准 Android 集成（可选）"
PROJECT_INFO["Template-AAF"]="完整示例项目，展示 AAF 所有功能（可选）"

# Git 仓库地址
declare -A PROJECT_GIT
PROJECT_GIT["AndroidAppFactory"]="https://github.com/AndroidAppFactory/AndroidAppFactory.git"
PROJECT_GIT["AndroidAppFactory-Doc"]="https://github.com/AndroidAppFactory/AndroidAppFactory-Doc.git"
PROJECT_GIT["Template-Empty"]="https://github.com/AndroidAppFactory/Template-Empty.git"
PROJECT_GIT["Template_Android"]="https://github.com/AndroidAppFactory/Template_Android.git"
PROJECT_GIT["Template-AAF"]="https://github.com/AndroidAppFactory/Template-AAF.git"

# 询问用户是否执行操作
ask_yes_no() {
    local prompt="$1"
    local default="${2:-n}"
    local yn
    
    while true; do
        log_prompt "$prompt [y/n, 默认: $default]: "
        read -r yn
        yn=${yn:-$default}
        
        case $yn in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "请输入 y 或 n";;
        esac
    done
}

# 检查项目是否可以更新
can_git_pull() {
    local project_path="$1"
    
    if [ ! -d "$project_path/.git" ]; then
        return 1
    fi
    
    cd "$project_path"
    
    # 检查是否有未提交的修改
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        return 2  # 有未提交的修改
    fi
    
    # 检查是否可以 pull
    git fetch --dry-run &>/dev/null
    local behind=$(git rev-list HEAD..origin/$(git branch --show-current) --count 2>/dev/null)
    
    if [ -n "$behind" ] && [ "$behind" -gt 0 ]; then
        return 0  # 可以更新
    fi
    
    return 3  # 已是最新
}

# 更新项目
update_project() {
    local project_name="$1"
    local project_path="$2"
    
    log_info "正在更新项目: $project_name"
    
    cd "$project_path"
    
    if git pull; then
        log_success "成功更新项目: $project_name"
        return 0
    else
        log_error "更新项目失败: $project_name"
        return 1
    fi
}

# 克隆项目到上级目录
clone_project_to_parent() {
    local project_name="$1"
    local git_url="${PROJECT_GIT[$project_name]}"
    
    log_info "正在克隆项目: $project_name"
    log_info "目标位置: $PARENT_DIR/$project_name"
    log_info "Git 地址: $git_url"
    
    cd "$PARENT_DIR"
    
    if git clone "$git_url"; then
        log_success "成功克隆项目: $project_name"
        return 0
    else
        log_error "克隆项目失败: $project_name"
        return 1
    fi
}

# 检查并处理单个项目
check_and_handle_project() {
    local project_name="$1"
    local is_required="${2:-false}"
    local project_path="$PARENT_DIR/$project_name"
    
    echo ""
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "检查项目: $project_name"
    log_info "说明: ${PROJECT_INFO[$project_name]}"
    
    # 检查项目是否存在（仅检查上级目录）
    if [ -d "$project_path" ]; then
        log_success "项目已存在: $project_path"
        
        # 检查是否可以更新
        can_git_pull "$project_path"
        local status=$?
        
        case $status in
            0)
                log_info "发现可用更新"
                if ask_yes_no "是否更新此项目？"; then
                    update_project "$project_name" "$project_path"
                else
                    log_info "跳过更新"
                fi
                ;;
            2)
                log_warning "项目有未提交的修改，跳过更新"
                ;;
            3)
                log_success "项目已是最新版本"
                ;;
            *)
                log_info "项目没有 git 支持，跳过更新检查"
                ;;
        esac
    else
        log_warning "项目不存在: $project_path"
        
        # 必需项目自动克隆，可选项目询问
        local should_clone=false
        
        if [ "$is_required" = "true" ]; then
            log_info "这是必需项目，将自动克隆"
            should_clone=true
        else
            if ask_yes_no "是否克隆此项目？"; then
                should_clone=true
            fi
        fi
        
        if [ "$should_clone" = "true" ]; then
            clone_project_to_parent "$project_name"
        else
            log_info "跳过克隆: $project_name"
        fi
    fi
}

# 创建 AAF-Temp Demo 项目
create_aaf_temp() {
    echo ""
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "创建 AAF-Temp Demo 项目"
    log_info "说明: 内部临时开发项目，从 Template-Empty 复制而来"
    
    local aaf_temp_path="$SCRIPT_DIR/AAF-Temp"
    
    # 检查是否已存在
    if [ -d "$aaf_temp_path" ]; then
        log_success "AAF-Temp 项目已存在，跳过创建"
        return 0
    fi
    
    # 查找 Template-Empty 源
    local template_source=""
    if [ -d "$PARENT_DIR/Template-Empty" ]; then
        template_source="$PARENT_DIR/Template-Empty"
    else
        log_error "找不到 Template-Empty 项目"
        log_error "请先克隆 Template-Empty 项目到上级目录"
        return 1
    fi
    
    log_info "从以下位置复制: $template_source"
    log_info "目标位置: $aaf_temp_path"
    
    # 复制项目
    if cp -r "$template_source" "$aaf_temp_path"; then
        log_success "成功创建 AAF-Temp 项目"
        
        # 移除 .git 目录
        if [ -d "$aaf_temp_path/.git" ]; then
            rm -rf "$aaf_temp_path/.git"
            log_info "已移除 git 支持"
        fi
        
        # 添加到 .gitignore
        if [ -f "$SCRIPT_DIR/.gitignore" ]; then
            if ! grep -q "^AAF-Temp/$" "$SCRIPT_DIR/.gitignore"; then
                echo "AAF-Temp/" >> "$SCRIPT_DIR/.gitignore"
                log_success "已将 AAF-Temp/ 添加到 .gitignore"
            fi
        fi
        
        log_success "AAF-Temp 创建完成"
        log_info "位置: $aaf_temp_path"
        log_info "用途: 临时开发测试，可随意修改"
        
        return 0
    else
        log_error "创建 AAF-Temp 失败"
        return 1
    fi
}

# 初始化项目配置
init_project_config() {
    local project_name="$1"
    local project_path="$2"
    
    if [ ! -d "$project_path" ]; then
        return 0
    fi
    
    log_info "初始化项目配置: $project_name"
    
    cd "$project_path"
    
    # 创建 local.properties
    if [ ! -f "local.properties" ]; then
        if [ -n "$ANDROID_HOME" ]; then
            echo "sdk.dir=$ANDROID_HOME" > local.properties
            log_success "已创建 local.properties"
        elif [ -n "$ANDROID_SDK_ROOT" ]; then
            echo "sdk.dir=$ANDROID_SDK_ROOT" > local.properties
            log_success "已创建 local.properties"
        else
            log_warning "未设置 ANDROID_HOME，请手动配置 local.properties"
        fi
    fi
    
    # 设置 gradlew 可执行权限
    if [ -f "gradlew" ]; then
        chmod +x gradlew
        log_success "已设置 gradlew 可执行权限"
    fi
}

# 检查开发环境
check_environment() {
    echo ""
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "检查开发环境"
    
    # 检查 Java
    if command -v java &> /dev/null; then
        local java_version=$(java -version 2>&1 | head -n 1)
        log_success "Java: $java_version"
    else
        log_error "未找到 Java，请安装 JDK"
    fi
    
    # 检查 Android SDK
    if [ -n "$ANDROID_HOME" ] || [ -n "$ANDROID_SDK_ROOT" ]; then
        log_success "Android SDK: ${ANDROID_HOME:-$ANDROID_SDK_ROOT}"
    else
        log_warning "未设置 ANDROID_HOME，部分功能可能无法使用"
    fi
    
    # 检查 Git
    if command -v git &> /dev/null; then
        local git_version=$(git --version)
        log_success "Git: $git_version"
    else
        log_error "未找到 Git"
    fi
}

# 主执行流程
main() {
    echo ""
    
    # 检查环境
    check_environment
    
    echo ""
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "开始检查和初始化 AAF 项目"
    
    # 1. 检查 AndroidAppFactory（必需）
    check_and_handle_project "AndroidAppFactory" true
    
    # 2. 检查 AndroidAppFactory-Doc（可选）
    check_and_handle_project "AndroidAppFactory-Doc" false
    
    # 3. 检查 Template-Empty（可选）
    check_and_handle_project "Template-Empty" false
    
    # 4. 检查 Template_Android（可选）
    check_and_handle_project "Template_Android" false
    
    # 5. 检查 Template-AAF（可选）
    check_and_handle_project "Template-AAF" false
    
    # 6. 创建 AAF-Temp Demo 项目
    create_aaf_temp
    
    echo ""
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "初始化项目配置"
    
    # 初始化各项目配置
    init_project_config "AndroidAppFactory" "$PARENT_DIR/AndroidAppFactory"
    init_project_config "Template-Empty" "$PARENT_DIR/Template-Empty"
    init_project_config "Template_Android" "$PARENT_DIR/Template_Android"
    init_project_config "Template-AAF" "$PARENT_DIR/Template-AAF"
    init_project_config "AAF-Temp" "$SCRIPT_DIR/AAF-Temp"
    
    echo ""
    log_info "========================================"
    log_success "初始化完成！"
    log_info "========================================"
    
    echo ""
    log_info "项目布局："
    log_info "  $PARENT_DIR/"
    log_info "  ├── AndroidAppFactory/        (AAF 核心框架)"
    log_info "  ├── AndroidAppFactory-Doc/    (AAF 文档)"
    log_info "  ├── Template-Empty/           (Sample: 最简示例)"
    log_info "  ├── Template_Android/         (Sample: 基础示例)"
    log_info "  ├── Template-AAF/             (Sample: 完整示例)"
    log_info "  └── CodeBuddyForAAF/"
    log_info "      └── AAF-Temp/             (Demo: 内部开发)"
    
    echo ""
    log_info "接下来可以："
    log_info "  1. 在 AAF-Temp 项目中开始开发（临时开发项目）"
    log_info "  2. 参考 README.md 了解详细开发流程"
    log_info "  3. Sample 项目供学习参考，不要直接修改"
    
    cd "$SCRIPT_DIR"
}

# 执行主函数
main "$@"
