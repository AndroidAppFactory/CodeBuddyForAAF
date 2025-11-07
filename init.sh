
#!/bin/bash
# author code@bihe0832.com
# CodeBuddyForAAF 初始化脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    printf "${BLUE}[INFO]${NC} %s\n" "$1"
}

log_success() {
    printf "${GREEN}[SUCCESS]${NC} %s\n" "$1"
}

log_warning() {
    printf "${YELLOW}[WARNING]${NC} %s\n" "$1"
}

log_error() {
    printf "${RED}[ERROR]${NC} %s\n" "$1"
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PROJECT_DIR="$SCRIPT_DIR"  # 直接在当前项目目录下克隆
PARENT_DIR="$(dirname "$SCRIPT_DIR")"  # 父目录

log_info "开始执行AAF CodeBuddy初始化：$(date '+%Y-%m-%d %H:%M:%S')"
log_info "脚本目录：$SCRIPT_DIR"
log_info "项目目录：$PROJECT_DIR"
log_info "父目录：$PARENT_DIR"

# 克隆AAF项目
clone_aaf_project() {
    local project_name=$1
    local git_url=""
    
    case $project_name in
        "AndroidAppFactory")
            git_url="https://github.com/AndroidAppFactory/AndroidAppFactory.git"
            ;;
        "AndroidAppFactory-Doc")
            git_url="https://github.com/AndroidAppFactory/AndroidAppFactory-Doc.git"
            ;;
        "Template-Empty")
            git_url="https://github.com/AndroidAppFactory/Template-Empty.git"
            ;;
        *)
            log_error "未知的项目名称：$project_name"
            return 1
            ;;
    esac
    
    log_info "正在克隆项目：$project_name"
    log_info "Git地址：$git_url"
    
    cd "$PROJECT_DIR"
    
    if git clone "$git_url"; then
        log_success "成功克隆项目：$project_name"
        
        # 移除git支持
        if [ -d "$PROJECT_DIR/$project_name/.git" ]; then
            log_info "移除项目 $project_name 的git支持..."
            rm -rf "$PROJECT_DIR/$project_name/.git"
            log_success "已移除项目 $project_name 的git支持"
        fi
        
        return 0
    else
        log_error "克隆项目失败：$project_name"
        return 1
    fi
}

# 检查必要的AAF项目是否存在
check_aaf_projects() {
    log_info "检查AAF相关项目..."
    
    local projects=("AndroidAppFactory" "AndroidAppFactory-Doc" "Template-Empty")
    local missing_projects=()
    local existing_projects=()
    local parent_projects=()
    
    # 检查哪些项目存在，哪些不存在
    for project in "${projects[@]}"; do
        if [ -d "$PROJECT_DIR/$project" ]; then
            existing_projects+=("$project")
            log_success "找到项目（当前目录）：$project"
        elif [ -d "$PARENT_DIR/$project" ]; then
            parent_projects+=("$project")
            log_success "找到项目（父目录）：$project"
        else
            missing_projects+=("$project")
        fi
    done
    
    # 如果有缺失的项目，尝试克隆
    if [ ${#missing_projects[@]} -gt 0 ]; then
        log_warning "发现缺少以下AAF项目："
        for project in "${missing_projects[@]}"; do
            echo "  - $project"
        done
        
        log_info "开始自动克隆缺失的项目..."
        
        for project in "${missing_projects[@]}"; do
            if ! clone_aaf_project "$project"; then
                log_error "克隆项目失败：$project"
                return 1
            fi
        done
        
        log_success "所有缺失的项目已成功克隆"
    fi
    
    # 检查现有项目是否需要移除git支持（只处理当前目录的项目）
    log_info "检查现有项目的git支持..."
    for project in "${existing_projects[@]}"; do
        if [ -d "$PROJECT_DIR/$project/.git" ]; then
            log_info "移除项目 $project 的git支持..."
            rm -rf "$PROJECT_DIR/$project/.git"
            log_success "已移除项目 $project 的git支持"
        else
            log_info "项目 $project 已经没有git支持"
        fi
    done
    
    # 对于父目录的项目，不移除git支持
    for project in "${parent_projects[@]}"; do
        log_info "项目 $project 位于父目录，保留git支持"
    done
    
    log_success "所有必要的AAF项目都已就绪"
    return 0
}

# 检查开发环境
check_development_environment() {
    log_info "检查开发环境..."
    
    # 检查Java
    if ! command -v java &> /dev/null; then
        log_error "未找到Java，请安装JDK"
        return 1
    else
        java_version=$(java -version 2>&1 | head -n 1)
        log_success "Java环境：$java_version"
    fi
    
    # 检查Android SDK
    if [ -z "$ANDROID_HOME" ] && [ -z "$ANDROID_SDK_ROOT" ]; then
        log_warning "未设置ANDROID_HOME或ANDROID_SDK_ROOT环境变量"
        log_info "请确保Android SDK已正确安装并配置环境变量"
    else
        log_success "Android SDK路径：${ANDROID_HOME:-$ANDROID_SDK_ROOT}"
    fi
    
    # 检查git
    if ! command -v git &> /dev/null; then
        log_error "未找到git命令"
        return 1
    else
        git_version=$(git --version)
        log_success "Git环境：$git_version"
    fi
    
    return 0
}

# 初始化Template-Empty项目
init_template_empty() {
    local template_dir="$PROJECT_DIR/Template-Empty"
    
    # 检查当前目录和父目录
    if [ -d "$PROJECT_DIR/Template-Empty" ]; then
        template_dir="$PROJECT_DIR/Template-Empty"
    elif [ -d "$PARENT_DIR/Template-Empty" ]; then
        template_dir="$PARENT_DIR/Template-Empty"
        log_info "使用父目录中的Template-Empty项目"
    else
        log_error "Template-Empty项目不存在"
        return 1
    fi
    
    log_info "初始化Template-Empty项目..."
    
    cd "$template_dir"
    
    # 检查是否有local.properties文件
    if [ ! -f "local.properties" ]; then
        log_info "创建local.properties文件..."
        if [ -n "$ANDROID_HOME" ]; then
            echo "sdk.dir=$ANDROID_HOME" > local.properties
            log_success "已创建local.properties文件"
        elif [ -n "$ANDROID_SDK_ROOT" ]; then
            echo "sdk.dir=$ANDROID_SDK_ROOT" > local.properties
            log_success "已创建local.properties文件"
        else
            log_warning "无法自动创建local.properties，请手动设置Android SDK路径"
        fi
    else
        log_success "local.properties文件已存在"
    fi
    
    # 检查gradlew权限
    if [ -f "gradlew" ]; then
        chmod +x gradlew
        log_success "已设置gradlew可执行权限"
    fi
    
    return 0
}

# 初始化AndroidAppFactory项目
init_android_app_factory() {
    local aaf_dir="$PROJECT_DIR/AndroidAppFactory"
    
    # 检查当前目录和父目录
    if [ -d "$PROJECT_DIR/AndroidAppFactory" ]; then
        aaf_dir="$PROJECT_DIR/AndroidAppFactory"
    elif [ -d "$PARENT_DIR/AndroidAppFactory" ]; then
        aaf_dir="$PARENT_DIR/AndroidAppFactory"
        log_info "使用父目录中的AndroidAppFactory项目"
    else
        log_error "AndroidAppFactory项目不存在"
        return 1
    fi
    
    log_info "初始化AndroidAppFactory项目..."
    
    cd "$aaf_dir"
    
    # 检查是否有local.properties文件
    if [ ! -f "local.properties" ]; then
        log_info "创建local.properties文件..."
        if [ -n "$ANDROID_HOME" ]; then
            echo "sdk.dir=$ANDROID_HOME" > local.properties
            log_success "已创建local.properties文件"
        elif [ -n "$ANDROID_SDK_ROOT" ]; then
            echo "sdk.dir=$ANDROID_SDK_ROOT" > local.properties
            log_success "已创建local.properties文件"
        else
            log_warning "无法自动创建local.properties，请手动设置Android SDK路径"
        fi
    else
        log_success "local.properties文件已存在"
    fi
    
    # 检查gradlew权限
    if [ -f "gradlew" ]; then
        chmod +x gradlew
        log_success "已设置gradlew可执行权限"
    fi
    
    return 0
}

# 验证项目配置
verify_project_setup() {
    log_info "验证项目配置..."
    
    # 验证Template-Empty项目
    local template_dir=""
    if [ -d "$PROJECT_DIR/Template-Empty" ]; then
        template_dir="$PROJECT_DIR/Template-Empty"
    elif [ -d "$PARENT_DIR/Template-Empty" ]; then
        template_dir="$PARENT_DIR/Template-Empty"
    fi
    
    if [ -n "$template_dir" ] && [ -d "$template_dir" ]; then
        cd "$template_dir"
        if [ -f "gradlew" ]; then
            log_info "检查Template-Empty项目依赖..."
            if ./gradlew tasks --quiet > /dev/null 2>&1; then
                log_success "Template-Empty项目配置正常"
            else
                log_warning "Template-Empty项目配置可能有问题，请检查"
            fi
        fi
    fi
    
    return 0
}

# 更新README文件
update_readme() {
    log_info "README.md文件已包含完整的开发指南信息"
    log_success "开发指南已集成到README.md中"
}

# 主执行流程
main() {
    log_info "========================================"
    log_info "AAF CodeBuddy 初始化脚本开始执行"
    log_info "========================================"
    
    # 检查AAF项目
    if ! check_aaf_projects; then
        log_error "AAF项目检查失败，请先确保相关项目存在"
        exit 1
    fi
    
    # 检查开发环境
    if ! check_development_environment; then
        log_error "开发环境检查失败"
        exit 1
    fi
    
    # 初始化Template-Empty项目
    if ! init_template_empty; then
        log_error "Template-Empty项目初始化失败"
        exit 1
    fi
    
    # 初始化AndroidAppFactory项目
    if ! init_android_app_factory; then
        log_error "AndroidAppFactory项目初始化失败"
        exit 1
    fi
    
    # 验证项目配置
    verify_project_setup
    
    # 更新README
    update_readme
    
    log_info "========================================"
    log_success "AAF CodeBuddy 初始化完成！"
    log_info "========================================"
    
    log_info "接下来可以："
    log_info "1. 在Template-Empty项目中开始开发"
    log_info "2. 参考README.md了解详细开发流程"
    
    cd "$SCRIPT_DIR"
}

# 执行主函数
main "$@"
