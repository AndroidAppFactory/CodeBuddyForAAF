#!/usr/bin/env bash
set -euo pipefail
# author zixie
# APK 可优化图片批量压缩脚本（apk-size-analyzer 通用工具，随 skill 一起发布）
#
# 用法：
#   export tinypng_api_key=xxxxxxxx   # 必须先设置 TinyPNG API Key
#
#   bash compress_images.sh --list <file>           # 默认 dry-run，只打印将要压缩的文件
#   bash compress_images.sh --list <file> --apply   # 真执行：自动备份 → 调用 TinyPNG → 原地覆盖
#   bash compress_images.sh --list <file> --restore # 从 .backup/ 恢复所有原文件
#
#   可选过滤参数（dry-run / apply 均生效，restore 不过滤）：
#     --min-size <值>   只处理原大小 ≥ 阈值的条目
#                       支持 500000 / 500K / 500KB / 1M / 1MB / 0.5M 等写法
#
# 设计：
# - 脚本本体常驻 skill 目录，不随每次分析复制到报告产物中
# - 每次分析产物 {report}_assets/ 下只放 compress_images.list（清单）
# - --apply 运行时：备份目录 {list 同级}/.backup/、日志 {list 同级}/compress_images.log
#
# 注意：
# - 清单中的第 1 列是工程源文件的真实路径，脚本会原地替换这些文件
# - 压缩前会把源文件按项目相对路径镜像到 .backup/，--restore 可一键回滚
# - 同格式压缩（PNG→PNG / JPG→JPG），不做格式转换
# - 申请 API Key：https://tinypng.com/developers

set -u

# ============================================================================
# 默认值与参数
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIST_FILE=""          # 必须通过 --list 指定
BACKUP_DIR=""         # 默认由 LIST_FILE 所在目录派生
LOG_FILE=""           # 默认由 LIST_FILE 所在目录派生

MODE="dryrun"   # dryrun / apply / restore
MIN_SIZE_RAW=""  # --min-size 原始字符串（未解析）
MIN_SIZE=0       # 解析后的字节数

while [ $# -gt 0 ]; do
  case "$1" in
    --apply)
      MODE="apply"
      shift
      ;;
    --restore)
      MODE="restore"
      shift
      ;;
    --list)
      LIST_FILE="$2"
      shift 2
      ;;
    --min-size)
      MIN_SIZE_RAW="$2"
      shift 2
      ;;
    --backup-dir)
      BACKUP_DIR="$2"
      shift 2
      ;;
    --log)
      LOG_FILE="$2"
      shift 2
      ;;
    -h|--help)
      sed -n '1,22p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "❌ 未知参数: $1"
      echo "   使用 --help 查看用法"
      exit 1
      ;;
  esac
done

# ============================================================================
# 前置检查
# ============================================================================

# --list 为必填（兼容：没传时尝试 skill 同级 compress_images.list，一般不存在）
if [ -z "$LIST_FILE" ]; then
  if [ -f "$SCRIPT_DIR/compress_images.list" ]; then
    LIST_FILE="$SCRIPT_DIR/compress_images.list"
  else
    echo "❌ 缺少 --list <file> 参数"
    echo "   用法: bash $0 --list /path/to/compress_images.list [--apply|--restore]"
    exit 1
  fi
fi

if [ ! -f "$LIST_FILE" ]; then
  echo "❌ 清单文件不存在: $LIST_FILE"
  exit 1
fi

# 清单同级目录作为备份/日志的落盘位置（除非用户显式指定）
LIST_DIR="$(cd "$(dirname "$LIST_FILE")" && pwd)"
[ -z "$BACKUP_DIR" ] && BACKUP_DIR="$LIST_DIR/.backup"
[ -z "$LOG_FILE" ]   && LOG_FILE="$LIST_DIR/compress_images.log"

# 依赖检查
for cmd in curl python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "❌ 缺少依赖命令: $cmd"
    exit 1
  fi
done

# 解析 --min-size（支持 500 / 500K / 500KB / 1M / 1MB / 0.5M，大小写不敏感）
parse_size() {
  # stdin/arg -> 字节数（整数），无法解析返回 -1
  python3 - "$1" <<'PY'
import sys, re
s = (sys.argv[1] or '').strip()
if not s:
    print(0); sys.exit(0)
m = re.match(r'^\s*([0-9]+(?:\.[0-9]+)?)\s*([kKmMgG]?[bB]?)\s*$', s)
if not m:
    print(-1); sys.exit(0)
num = float(m.group(1))
unit = m.group(2).lower().rstrip('b')
mult = {'': 1, 'k': 1024, 'm': 1024*1024, 'g': 1024*1024*1024}.get(unit, -1)
if mult < 0:
    print(-1); sys.exit(0)
print(int(num * mult))
PY
}

if [ -n "$MIN_SIZE_RAW" ]; then
  MIN_SIZE=$(parse_size "$MIN_SIZE_RAW")
  if [ "$MIN_SIZE" -lt 0 ] 2>/dev/null; then
    echo "❌ --min-size 值无法解析: $MIN_SIZE_RAW"
    echo "   支持格式示例: 500000 / 500K / 500KB / 1M / 1MB / 0.5M"
    exit 1
  fi
fi

# ============================================================================
# 清单解析（过滤注释和空行）
# 清单格式: <source_real_path> | <apk_internal_path> | <size_bytes>
# ============================================================================

parse_list() {
  # 输出三列 TSV: 源路径 \t APK内路径 \t 原大小
  awk -F'|' '
    /^[[:space:]]*#/ {next}
    /^[[:space:]]*$/ {next}
    NF>=1 {
      # 去除每列首尾空白
      for (i=1;i<=NF;i++) { gsub(/^[ \t]+|[ \t]+$/, "", $i) }
      if ($1 == "") next
      printf "%s\t%s\t%s\n", $1, (NF>=2?$2:""), (NF>=3?$3:"0")
    }
  ' "$LIST_FILE"
}

# 按 MIN_SIZE 过滤 parse_list 的输出（restore 模式不过滤）
filter_by_min_size() {
  if [ "$MIN_SIZE" -le 0 ] 2>/dev/null; then
    cat
    return
  fi
  awk -F'\t' -v min="$MIN_SIZE" '{
    sz = $3 + 0
    if (sz >= min) print $0
  }'
}

TOTAL_RAW=$(parse_list | wc -l | tr -d ' ')
if [ "$MODE" = "restore" ]; then
  TOTAL_ITEMS="$TOTAL_RAW"
else
  TOTAL_ITEMS=$(parse_list | filter_by_min_size | wc -l | tr -d ' ')
fi

if [ "$TOTAL_RAW" -eq 0 ]; then
  echo "⚠️  清单中没有可压缩项（全是注释/空行）"
  exit 0
fi

if [ "$MODE" != "restore" ] && [ "$TOTAL_ITEMS" -eq 0 ]; then
  echo "⚠️  --min-size $MIN_SIZE_RAW 过滤后没有匹配的条目（原清单共 ${TOTAL_RAW} 条）"
  exit 0
fi

# ============================================================================
# 工具函数
# ============================================================================

format_bytes() {
  # 输入字节数，输出易读格式
  python3 -c "
import sys
n = int(sys.argv[1]) if sys.argv[1].isdigit() else 0
for u in ['B','KB','MB','GB']:
  if n < 1024: print(f'{n:.1f}{u}' if isinstance(n,float) else f'{n}{u}'); break
  n = n/1024
else:
  print(f'{n:.1f}TB')
" "$1" 2>/dev/null || echo "${1}B"
}

backup_path_for() {
  # 把绝对源路径映射到 .backup/ 下（保留相对根的目录结构）
  # 策略：去掉开头的 /，直接拼到 .backup/
  local src="$1"
  # 去掉开头的 / 和任何 .. 引用
  local rel="${src#/}"
  rel="$(echo "$rel" | sed 's|\.\./||g')"
  echo "$BACKUP_DIR/$rel"
}

log_line() {
  # 写入日志（如果 $LOG_FILE 可写）
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE" 2>/dev/null || true
}

# ============================================================================
# restore 模式
# ============================================================================

do_restore() {
  echo "=========================================="
  echo "🔄 从 .backup/ 恢复原文件"
  echo "=========================================="

  if [ ! -d "$BACKUP_DIR" ]; then
    echo "⚠️  没有找到 .backup/ 目录，无可恢复内容"
    exit 0
  fi

  local restored=0
  local failed=0
  local skipped=0

  parse_list | while IFS="	" read -r src apk_path orig_size; do
    local bak
    bak="$(backup_path_for "$src")"
    if [ ! -f "$bak" ]; then
      echo "  ⏭️  $src (无备份，跳过)"
      skipped=$((skipped + 1))
      continue
    fi
    if cp -f "$bak" "$src" 2>/dev/null; then
      echo "  ✅ $src"
      restored=$((restored + 1))
      log_line "RESTORE $src"
    else
      echo "  ❌ $src (恢复失败)"
      failed=$((failed + 1))
    fi
  done

  echo ""
  echo "恢复完成。如需清理备份目录，执行:"
  echo "  rm -rf \"$BACKUP_DIR\""
  exit 0
}

if [ "$MODE" = "restore" ]; then
  do_restore
fi

# ============================================================================
# API Key 校验（dryrun 仅给提示，apply 强校验）
# ============================================================================

validate_api_key() {
  if [ -z "${tinypng_api_key:-}" ]; then
    echo "❌ 未设置 tinypng_api_key 环境变量"
    echo "   请执行: export tinypng_api_key=your_key_here"
    echo "   申请地址: https://tinypng.com/developers"
    return 1
  fi

  echo "🔑 校验 TinyPNG API Key..."
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" \
    -u "api:$tinypng_api_key" \
    https://api.tinify.com/shrink -X POST 2>/dev/null || echo "000")

  # TinyPNG 对空请求体返回 400 (input missing) 表示 key 有效
  # 401 / 403 表示 key 无效
  case "$code" in
    400)
      echo "   ✅ Key 有效"
      return 0
      ;;
    401|403)
      echo "   ❌ Key 无效（HTTP ${code}），请检查 tinypng_api_key"
      return 1
      ;;
    *)
      echo "   ⚠️  校验返回 HTTP ${code}，继续尝试（可能为网络异常）"
      return 0
      ;;
  esac
}

# ============================================================================
# 压缩单个文件（调用 TinyPNG，原地覆盖）
# ============================================================================

compress_one() {
  local src="$1"
  local apk_path="$2"
  local orig_size="$3"

  # 1. 源文件检查
  if [ ! -f "$src" ]; then
    echo "  ⚠️  源文件不存在，跳过: $src"
    log_line "SKIP $src (file not found)"
    return 1
  fi

  # 2. 扩展名校验（只支持 png/jpg/jpeg）
  local ext_lower
  ext_lower=$(echo "${src##*.}" | tr '[:upper:]' '[:lower:]')
  case "$ext_lower" in
    png|jpg|jpeg) ;;
    *)
      echo "  ⏭️  跳过非 PNG/JPG: $src"
      log_line "SKIP $src (unsupported ext: $ext_lower)"
      return 1
      ;;
  esac

  # 3. 9-patch 强制跳过（避免破坏 stretch/padding 区域）
  case "$src" in
    *.9.png|*.9.PNG)
      echo "  ⏭️  跳过 9-patch: $src"
      log_line "SKIP $src (9-patch)"
      return 1
      ;;
  esac

  # 4. 备份
  local bak
  bak="$(backup_path_for "$src")"
  mkdir -p "$(dirname "$bak")"
  if ! cp -f "$src" "$bak" 2>/dev/null; then
    echo "  ❌ 备份失败: $src"
    log_line "FAIL $src (backup failed)"
    return 1
  fi

  # 5. 调 TinyPNG /shrink（upload）
  local _zixie_tmp="${ZIXIEKIT_TMP:-$HOME/.zixiekit}"; mkdir -p "${_zixie_tmp}/skill/apk-size-analyzer"
  local tmp_resp="$(mktemp --tmpdir=\"${_zixie_tmp}/skill/apk-size-analyzer\" \"tinypng_resp.XXXXXX\")"
  local http_code
  http_code=$(curl -s -o "$tmp_resp" -w "%{http_code}" \
    -u "api:$tinypng_api_key" \
    --data-binary "@$src" \
    https://api.tinify.com/shrink 2>/dev/null || echo "000")

  if [ "$http_code" != "201" ]; then
    local err
    err=$(cat "$tmp_resp" 2>/dev/null | head -c 200)
    rm -f "$tmp_resp"
    echo "  ❌ 上传失败 (HTTP $http_code): $src"
    [ -n "$err" ] && echo "     $err"
    log_line "FAIL $src (upload HTTP $http_code: $err)"
    return 1
  fi

  # 6. 提取压缩后的下载 URL（从响应 JSON 的 output.url）
  local output_url
  output_url=$(python3 -c "
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    print(d.get('output', {}).get('url', ''))
except Exception:
    print('')
" "$tmp_resp" 2>/dev/null)
  rm -f "$tmp_resp"

  if [ -z "$output_url" ]; then
    echo "  ❌ 解析响应失败: $src"
    log_line "FAIL $src (parse response)"
    return 1
  fi

  # 7. 下载压缩后的文件到临时位置
  local tmp_out="$(mktemp --tmpdir=\"${_zixie_tmp}/skill/apk-size-analyzer\" \"tinypng_out.XXXXXX\")"
  if ! curl -s -o "$tmp_out" -u "api:$tinypng_api_key" "$output_url"; then
    rm -f "$tmp_out"
    echo "  ❌ 下载结果失败: $src"
    log_line "FAIL $src (download)"
    return 1
  fi

  # 8. 校验：新文件 > 0 字节 且 <= 原文件大小
  local new_size
  new_size=$(wc -c < "$tmp_out" | tr -d ' ')
  if [ "$new_size" -le 0 ]; then
    rm -f "$tmp_out"
    echo "  ❌ 压缩结果为空: $src"
    log_line "FAIL $src (empty result)"
    return 1
  fi

  local old_size
  old_size=$(wc -c < "$src" | tr -d ' ')
  if [ "$new_size" -ge "$old_size" ]; then
    rm -f "$tmp_out"
    echo "  ⏭️  压缩无收益（原 $(format_bytes $old_size) → 新 $(format_bytes $new_size)），保留原文件: $src"
    log_line "SKIP $src (no gain: $old_size -> $new_size)"
    return 1
  fi

  # 9. 原地覆盖
  if ! mv -f "$tmp_out" "$src"; then
    rm -f "$tmp_out"
    echo "  ❌ 覆盖失败: $src"
    log_line "FAIL $src (overwrite failed)"
    return 1
  fi

  local saved=$((old_size - new_size))
  echo "  ✅ $(format_bytes $old_size) → $(format_bytes $new_size) (省 $(format_bytes $saved)): $src"
  log_line "OK $src $old_size -> $new_size (saved $saved)"

  # 累计统计：写到临时文件里（因为 while 在子 shell 中）
  echo "$saved" >> "$STATS_FILE"
  return 0
}

# ============================================================================
# dryrun 模式
# ============================================================================

if [ "$MODE" = "dryrun" ]; then
  echo "=========================================="
  echo "🔍 Dry-run 预览（未执行压缩）"
  echo "=========================================="
  echo "清单: $LIST_FILE"
  if [ "$MIN_SIZE" -gt 0 ] 2>/dev/null; then
    echo "过滤: --min-size $MIN_SIZE_RAW (${MIN_SIZE} 字节)"
    echo "条目总数: ${TOTAL_ITEMS}（原清单 ${TOTAL_RAW} 条，已按阈值过滤）"
  else
    echo "条目总数: ${TOTAL_ITEMS}"
  fi
  echo ""
  echo "以下文件将在 --apply 后被原地压缩："
  echo ""

  missing=0
  total_orig=0
  parse_list | filter_by_min_size | while IFS="	" read -r src apk_path orig_size; do
    marker="✅"
    [ ! -f "$src" ] && marker="❌(不存在)" && missing=$((missing + 1))
    printf "  %s %s\n" "$marker" "$src"
    printf "       APK 路径: %s  大小: %s\n" "$apk_path" "$(format_bytes $orig_size)"
  done

  echo ""
  echo "真执行请添加 --apply："
  echo "  export tinypng_api_key=your_key_here"
  if [ "$MIN_SIZE" -gt 0 ] 2>/dev/null; then
    echo "  bash $0 --list \"$LIST_FILE\" --min-size $MIN_SIZE_RAW --apply"
  else
    echo "  bash $0 --list \"$LIST_FILE\" --apply"
  fi
  echo ""
  echo "API Key 申请: https://tinypng.com/developers"
  exit 0
fi

# ============================================================================
# apply 模式
# ============================================================================

if ! validate_api_key; then
  exit 1
fi

echo ""
echo "=========================================="
echo "🗜️  开始批量压缩（原地替换，自动备份）"
echo "=========================================="
echo "清单: $LIST_FILE"
echo "备份目录: $BACKUP_DIR"
echo "日志: $LOG_FILE"
if [ "$MIN_SIZE" -gt 0 ] 2>/dev/null; then
  echo "过滤: --min-size $MIN_SIZE_RAW (${MIN_SIZE} 字节)"
  echo "条目总数: ${TOTAL_ITEMS}（原清单 ${TOTAL_RAW} 条，已按阈值过滤）"
else
  echo "条目总数: ${TOTAL_ITEMS}"
fi
echo ""

mkdir -p "$BACKUP_DIR"
_zixie_tmp="${ZIXIEKIT_TMP:-$HOME/.zixiekit}"; mkdir -p "${_zixie_tmp}/skill/apk-size-analyzer"
STATS_FILE="$(mktemp --tmpdir=\"${_zixie_tmp}/skill/apk-size-analyzer\" \"tinypng_stats.XXXXXX\")"
: > "$STATS_FILE"
export STATS_FILE

log_line "===== START apply: list=$LIST_FILE total=$TOTAL_ITEMS ====="

succ=0
fail=0
idx=0

# 不用管道读清单（避免子 shell 丢计数），改用重定向
while IFS="	" read -r src apk_path orig_size; do
  idx=$((idx + 1))
  echo "[${idx}/${TOTAL_ITEMS}] 处理: $src"
  if compress_one "$src" "$apk_path" "$orig_size"; then
    succ=$((succ + 1))
  else
    fail=$((fail + 1))
  fi
done <<EOF
$(parse_list | filter_by_min_size)
EOF

# 汇总节省字节数
total_saved=0
if [ -s "$STATS_FILE" ]; then
  total_saved=$(awk '{s+=$1} END {print s+0}' "$STATS_FILE")
fi
rm -f "$STATS_FILE"

echo ""
echo "=========================================="
echo "📦 压缩完成"
echo "=========================================="
echo "成功: $succ"
echo "跳过/失败: $fail"
echo "累计节省: $(format_bytes $total_saved)"
echo "日志: $LOG_FILE"
echo ""
echo "如需回滚，执行:"
echo "  bash $0 --restore"

log_line "===== END apply: succ=$succ fail=$fail saved=$total_saved ====="
