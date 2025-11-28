#!/bin/bash
# author code@bihe0832.com
# CodeBuddyForAAF 初始化脚本

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

echo "========================================"
echo "AAF CodeBuddy 初始化脚本"
echo "========================================"
echo ""

# 项目配置（使用函数代替关联数组，兼容旧版 bash）
get_project_info() {
    case "$1" in
        "AndroidAppFactory") echo "AAF 框架核心代码库（必需）" ;;
        "AndroidAppFactory-Doc") echo "AAF 框架完整文档和 API 说明（可选）" ;;
        "Template-Empty") echo "最简示例项目，用于快速开始和内部开发（可选）" ;;
        "Template_Android") echo "基础示例项目，标准 Android 集成（可选）" ;;
        "Template-AAF") echo "完整示例项目，展示 AAF 所有功能（可选）" ;;
    esac
}

get_project_git() {
    case "$1" in
        "AndroidAppFactory") echo "https://github.com/AndroidAppFactory/AndroidAppFactory.git" ;;
        "AndroidAppFactory-Doc") echo "https://github.com/AndroidAppFactory/AndroidAppFactory-Doc.git" ;;
        "Template-Empty") echo "https://github.com/AndroidAppFactory/Template-Empty.git" ;;
        "Template_Android") echo "https://github.com/AndroidAppFactory/Template_Android.git" ;;
        "Template-AAF") echo "https://github.com/AndroidAppFactory/Template-AAF.git" ;;
    esac
}

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
    
    (
        if [ ! -d "$project_path/.git" ]; then
            exit 1
        fi
        
        cd "$project_path" || exit 1
        
        # 检查是否有未提交的修改
        if ! git diff-index --quiet HEAD -- 2>/dev/null; then
            exit 2
        fi
        
        # 获取当前分支
        local current_branch=$(git branch --show-current 2>/dev/null)
        if [ -z "$current_branch" ]; then
            exit 1
        fi
        
        # 检查远程分支是否存在
        if ! git rev-parse --verify "origin/$current_branch" &>/dev/null; then
            exit 1
        fi
        
        # 比较本地和远程的提交数
        local behind=$(git rev-list HEAD..origin/$current_branch --count 2>/dev/null)
        if [ -n "$behind" ] && [ "$behind" -gt 0 ]; then
            exit 0
        fi
        
        exit 3  # 已是最新
    )
    return $?
}

# 更新项目
update_project() {
    local project_name="$1"
    local project_path="$2"
    
    (
        cd "$project_path" || exit 1
        
        if git pull; then
            log_success "成功更新项目: $project_name"
        else
            log_error "更新项目失败: $project_name"
            exit 1
        fi
    )
}

# 克隆项目到上级目录
clone_project_to_parent() {
    local project_name="$1"
    local git_url="$(get_project_git "$project_name")"
    
    (
        cd "$PARENT_DIR" || exit 1
        
        if git clone "$git_url"; then
            log_success "成功克隆项目: $project_name"
        else
            log_error "克隆项目失败: $project_name"
            exit 1
        fi
    )
}

# 检查并处理单个项目
check_and_handle_project() {
    local project_name="$1"
    local is_required="${2:-false}"
    local project_path="$PARENT_DIR/$project_name"
    local project_info="$(get_project_info "$project_name")"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "检查项目: $project_name ($project_info)"
    
    # 检查项目是否存在（仅检查上级目录）
    if [ -d "$project_path" ]; then
        log_success "项目已存在: $project_path"
        
        # 检查是否可以更新
        can_git_pull "$project_path"
        local status=$?
        
        case $status in
            0)
                if ask_yes_no "发现可用更新，是否更新此项目？"; then
                    update_project "$project_name" "$project_path"
                fi
                ;;
            2)
                log_warning "项目有未提交的修改，跳过更新"
                ;;
            3)
                log_success "项目已是最新版本"
                ;;
        esac
    else
        log_warning "项目不存在: $project_path"
        
        # 必需项目自动克隆，可选项目询问
        local should_clone=false
        
        if [ "$is_required" = "true" ]; then
            echo "这是必需项目，将自动克隆"
            should_clone=true
        else
            if ask_yes_no "是否克隆此项目？"; then
                should_clone=true
            fi
        fi
        
        if [ "$should_clone" = "true" ]; then
            clone_project_to_parent "$project_name"
        fi
    fi
    
    sleep 1
}

# 创建 AAF-Temp Demo 项目
create_aaf_temp() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "创建 AAF-Temp Demo 项目（内部临时开发）"
    
    local aaf_temp_path="$SCRIPT_DIR/AAF-Temp"
    
    # 检查是否已存在
    if [ -d "$aaf_temp_path" ]; then
        log_success "AAF-Temp 项目已存在，跳过创建"
        return 0
    fi
    
    # 查找 Template-Empty 源
    if [ ! -d "$PARENT_DIR/Template-Empty" ]; then
        log_error "找不到 Template-Empty 项目"
        log_error "请先克隆 Template-Empty 项目到上级目录"
        return 1
    fi
    
    local template_source="$PARENT_DIR/Template-Empty"
    
    # 复制项目
    if ! cp -r "$template_source" "$aaf_temp_path"; then
        log_error "创建 AAF-Temp 失败"
        return 1
    fi
    
    log_success "成功创建 AAF-Temp 项目"
    
    # 移除 .git 目录
    if [ -d "$aaf_temp_path/.git" ]; then
        rm -rf "$aaf_temp_path/.git"
    fi
    
    # 添加到 .gitignore
    if [ -f "$SCRIPT_DIR/.gitignore" ]; then
        if ! grep -q "^AAF-Temp/$" "$SCRIPT_DIR/.gitignore"; then
            echo "AAF-Temp/" >> "$SCRIPT_DIR/.gitignore"
            log_success "已将 AAF-Temp/ 添加到 .gitignore"
        fi
    fi
    
    sleep 1
}

# 初始化项目配置
init_project_config() {
    local project_name="$1"
    local project_path="$2"
    
    if [ ! -d "$project_path" ]; then
        return 0
    fi
    
    (
        cd "$project_path" || exit 1
        
        # 创建 local.properties
        if [ ! -f "local.properties" ]; then
            if [ -n "$ANDROID_HOME" ]; then
                echo "sdk.dir=$ANDROID_HOME" > local.properties
                log_success "[$project_name] 已创建 local.properties"
            elif [ -n "$ANDROID_SDK_ROOT" ]; then
                echo "sdk.dir=$ANDROID_SDK_ROOT" > local.properties
                log_success "[$project_name] 已创建 local.properties"
            else
                log_warning "[$project_name] 未设置 ANDROID_HOME，请手动配置 local.properties"
            fi
        fi
        
        # 设置 gradlew 可执行权限
        [ -f "gradlew" ] && chmod +x gradlew
    )
}

# 检查开发环境
check_environment() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "检查开发环境"
    
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
    
    sleep 1
}

# 主执行流程
main() {
    echo ""
    
    # 检查环境
    check_environment
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "开始检查和初始化 AAF 项目"
    
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
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "初始化项目配置"
    
    # 初始化各项目配置
    init_project_config "AndroidAppFactory" "$PARENT_DIR/AndroidAppFactory"
    init_project_config "Template-Empty" "$PARENT_DIR/Template-Empty"
    init_project_config "Template_Android" "$PARENT_DIR/Template_Android"
    init_project_config "Template-AAF" "$PARENT_DIR/Template-AAF"
    init_project_config "AAF-Temp" "$SCRIPT_DIR/AAF-Temp"
    
    sleep 1
    
    echo ""
    echo "========================================"
    log_success "初始化完成！"
    echo "========================================"
    
    echo ""
    echo "项目布局："
    echo "  $PARENT_DIR/"
    echo "  ├── AndroidAppFactory/        (AAF 核心框架)"
    echo "  ├── AndroidAppFactory-Doc/    (AAF 文档)"
    echo "  ├── Template-Empty/           (Sample: 最简示例)"
    echo "  ├── Template_Android/         (Sample: 基础示例)"
    echo "  ├── Template-AAF/             (Sample: 完整示例)"
    echo "  └── CodeBuddyForAAF/"
    echo "      └── AAF-Temp/             (Demo: 内部开发)"
    
    echo ""
    echo "接下来可以："
    echo "  1. 在 AAF-Temp 项目中开始开发（临时开发项目）"
    echo "  2. 参考 README.md 了解详细开发流程"
    echo "  3. Sample 项目供学习参考，不要直接修改"
    
    cd "$SCRIPT_DIR"
}

# 执行主函数
main "$@"
