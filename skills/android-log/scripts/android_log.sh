#!/usr/bin/env bash
set -euo pipefail
# android_log.sh - Android 日志抓取工具
# 用法:
#   ./android_log.sh logcat [TAG]        — 抓取调试日志（默认 TAG=APP_DEBUG）
#   ./android_log.sh logcat-errors [TAG]  — 抓取调试日志 + 异常
#   ./android_log.sh logcat-raw [FILTER]  — 抓取原始 logcat（支持 grep 过滤）
#   ./android_log.sh clear                — 清空 logcat 缓冲区
#   ./android_log.sh history              — 查看调试历史（最近 10 条）
#   ./android_log.sh corrections          — 查看纠正记录（最近 5 条）
#   ./android_log.sh record <摘要>        — 记录调试历史
#   ./android_log.sh correct <类型> <模块> <AI判断> <用户反馈>  — 记录纠正

DEBUG_DIR="${WORK_ROOT:-$HOME/zixie}/temp/cache/debug"
HISTORY_FILE="$DEBUG_DIR/history.log"
CORRECTIONS_FILE="$DEBUG_DIR/corrections.log"
DEFAULT_TAG="APP_DEBUG"

mkdir -p "$DEBUG_DIR"

# 抓取调试日志
do_logcat() {
  local tag="${1:-$DEFAULT_TAG}"
  echo "# 调试日志 (TAG=$tag)"
  adb logcat -d -v time | grep "$tag" || echo "(无匹配日志)"
}

# 抓取调试日志 + 异常
do_logcat_errors() {
  local tag="${1:-$DEFAULT_TAG}"
  echo "# 调试日志 + 异常 (TAG=$tag)"
  adb logcat -d -v time | grep -E "($tag|Exception|Error|FATAL)" || echo "(无匹配日志)"
}

# 抓取原始 logcat（可自定义过滤）
do_logcat_raw() {
  local filter="${1:-}"
  echo "# 原始 logcat"
  if [ -n "$filter" ]; then
    adb logcat -d -v time | grep -E "$filter" || echo "(无匹配日志)"
  else
    adb logcat -d -v time | tail -200
  fi
}

# 清空 logcat
do_clear() {
  echo "清空 logcat 缓冲区..."
  adb logcat -c
  echo "  ✓ 已清空"
}

# 查看调试历史
do_history() {
  if [ ! -f "$HISTORY_FILE" ]; then
    echo "(无调试历史)"
    return 0
  fi
  echo "# 调试历史（最近 10 条）"
  tail -10 "$HISTORY_FILE"
}

# 查看纠正记录
do_corrections() {
  if [ ! -f "$CORRECTIONS_FILE" ]; then
    echo "(无纠正记录)"
    return 0
  fi
  echo "# 纠正记录（最近 5 条）"
  awk -v RS='---\n' 'NF{buf[NR]=$0; n++} END{for(i=NR-n+5>n?NR-n+5:n-4; i<=NR; i++) if(i>0 && buf[i]) print buf[i]"---"}' "$CORRECTIONS_FILE" | tail -5
}

# 记录调试历史（保留最近 10 条）
do_record() {
  local summary="$1"
  local lines
  lines=$(wc -l < "$HISTORY_FILE" 2>/dev/null || echo 0)
  if [ "$lines" -ge 10 ]; then
    local tmp
    local _zixie_tmp="${ZIXIEKIT_TMP:-$HOME/.zixiekit}"
    mkdir -p "${_zixie_tmp}/skill/android-log"
    tmp=$(mktemp --tmpdir="${_zixie_tmp}/skill/android-log")
    tail -9 "$HISTORY_FILE" > "$tmp"
    mv "$tmp" "$HISTORY_FILE"
  fi
  echo "[$(date '+%Y-%m-%d %H:%M')] $summary" >> "$HISTORY_FILE"
  echo "  ✓ 已记录"
}

# 记录纠正
do_correct() {
  local type="$1" module="$2" ai_judgment="$3" user_feedback="$4"
  {
    echo "[$(date '+%Y-%m-%d %H:%M')] 类型: $type"
    echo "模块: $module"
    echo "AI判断: $ai_judgment"
    echo "用户反馈: $user_feedback"
    echo "---"
  } >> "$CORRECTIONS_FILE"
  echo "  ✓ 已记录纠正"
}

# 主入口
case "${1:-help}" in
  logcat)         do_logcat "${2:-$DEFAULT_TAG}" ;;
  logcat-errors)  do_logcat_errors "${2:-$DEFAULT_TAG}" ;;
  logcat-raw)     do_logcat_raw "${2:-}" ;;
  clear)          do_clear ;;
  history)        do_history ;;
  corrections)    do_corrections ;;
  record)         do_record "${2:?需要提供摘要}" ;;
  correct)        do_correct "${2:?需要类型}" "${3:?需要模块}" "${4:?需要AI判断}" "${5:?需要用户反馈}" ;;
  *)
    echo "用法: $0 {logcat|logcat-errors|logcat-raw|clear|history|corrections|record|correct}"
    echo ""
    echo "  logcat [TAG]         抓取调试日志（默认 TAG=${DEFAULT_TAG}）"
    echo "  logcat-errors [TAG]  抓取调试日志 + 异常"
    echo "  logcat-raw [FILTER]  抓取原始 logcat（支持 grep 正则过滤）"
    echo "  clear                清空 logcat 缓冲区"
    echo "  history              查看调试历史（最近 10 条）"
    echo "  corrections          查看纠正记录（最近 5 条）"
    echo "  record <摘要>        记录调试历史"
    echo "  correct <类型> <模块> <AI判断> <用户反馈>  记录纠正"
    ;;
esac
