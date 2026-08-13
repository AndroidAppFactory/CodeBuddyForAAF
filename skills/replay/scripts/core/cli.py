"""replay-core 统一 CLI 框架

四端共享的命令结构定义。各端只需：
1. import build_parser
2. 注册平台专有参数（--device 等）
3. 绑定各子命令的 handler
"""

from __future__ import annotations

import argparse
from typing import Callable, Optional


def build_parser(
    platform: str,
    *,
    description: str = "",
    add_platform_args: Optional[Callable[[argparse.ArgumentParser, str], None]] = None,
) -> argparse.ArgumentParser:
    """构建统一的 CLI parser

    Args:
        platform: 平台名（adb/web/win/mac）
        description: 顶层描述
        add_platform_args: 回调，给特定子命令追加平台专有参数
            签名：(sub_parser, sub_command_name) -> None
    """
    prog = f"zk replay {platform}"
    parser = argparse.ArgumentParser(
        prog=prog,
        description=description or f"ZixieKit {platform.upper()} Replay",
    )
    subs = parser.add_subparsers(dest="command", help="子命令")

    # ── record ──
    p_record = subs.add_parser("record", help="录制（素材 → ZIXIEKIT_TMP，自动命名）")
    if add_platform_args:
        add_platform_args(p_record, "record")

    # ── play ──
    p_play = subs.add_parser("play", help="回放素材确认")
    p_play.add_argument("target", help="录制目录路径或名称")
    p_play.add_argument("--speed", type=float, default=1.0, help="速度倍率（默认 1.0）")
    p_play.add_argument("--repeat", "-r", type=int, default=1, help="重复次数（默认 1）")
    p_play.add_argument("--screenshot-duration", type=float, default=1.0, help="截图间隔秒数（默认 1.0）")
    if add_platform_args:
        add_platform_args(p_play, "play")

    # ── flow ──
    p_flow = subs.add_parser("flow", help="Flow 管理与运行")
    flow_subs = p_flow.add_subparsers(dest="flow_command", help="flow 子命令")

    # flow run
    p_run = flow_subs.add_parser("run", help="运行 Flow")
    p_run.add_argument("id", help="Flow ID")
    p_run.add_argument("--speed", type=float, default=1.0, help="速度倍率")
    p_run.add_argument("--step", type=str, default=None, help="步骤选择（如 1,3,5-8）")
    p_run.add_argument("--fail-fast", action="store_true", help="遇错即停")
    p_run.add_argument("--rerun", action="store_true", help="复用上次目录重跑")
    p_run.add_argument("--no-notify", action="store_true", help="跳过所有通知（文本 + 图片）")
    if add_platform_args:
        add_platform_args(p_run, "flow_run")

    # flow report
    p_freport = flow_subs.add_parser("report", help="重新生成 Flow 报告")
    p_freport.add_argument("id", help="Flow ID")

    # ── init ──
    p_init = subs.add_parser("init", help="初始化环境（安装平台依赖：adb:zinput / web:playwright）")
    if add_platform_args:
        add_platform_args(p_init, "init")

    # ── doctor ──
    p_doctor = subs.add_parser("doctor", help="环境检查")
    if add_platform_args:
        add_platform_args(p_doctor, "doctor")

    # ── report ──
    p_report = subs.add_parser("report", help="对已有运行产物重生成报告")
    p_report.add_argument("run_dir", help="运行产物目录路径")

    # ── edit ──
    p_edit = subs.add_parser("edit", help="打开录制素材编辑器（Web 管理界面）")
    p_edit.add_argument("target", nargs="?", default=None, help="录制目录路径（可选，默认打开编辑器首页）")
    if add_platform_args:
        add_platform_args(p_edit, "edit")

    return parser


def parse_step_indices(step_str: str) -> list[int]:
    """解析 --step 参数为步骤序号列表

    支持格式：1,3,5-8 → [1, 3, 5, 6, 7, 8]
    """
    if not step_str:
        return []
    indices = []
    for part in step_str.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            indices.extend(range(int(a), int(b) + 1))
        else:
            indices.append(int(part))
    return sorted(set(indices))


# ── 统一输出格式 ──


def print_banner_start(name: str, steps: int, device: str, run_dir: str, note: str = "") -> None:
    """运行开始 banner"""
    print(f"\n{'═' * 50}")
    print(f"🚀 运行: {name} {note}")
    print(f"   设备: {device}")
    print(f"   步骤: {steps}")
    print(f"   产物: {run_dir}")
    print(f"{'═' * 50}\n")


def print_banner_end(success: int, total: int, report_path: str = "") -> None:
    """运行结束 banner"""
    icon = "✅" if success == total else "⚠️"
    print(f"\n{'═' * 50}")
    print(f"{icon} 完成: {success}/{total} 成功")
    if report_path:
        print(f"   报告: {report_path}")
    print(f"{'═' * 50}")


# ── 视频合成脚本生成 ──


def generate_merge_video_script(base_dir: str, media_paths: list, screenshot_duration: float = 1) -> str | None:
    """生成 merge_video.sh，将截图+录屏合成为 replay.mp4。

    Args:
        base_dir:     产物根目录（脚本写入 base_dir/merge_video.sh）
        media_paths:  [(full_path, is_video), ...] 媒体文件列表
        screenshot_duration: 截图停留秒数
    Returns:
        生成的脚本路径，没有媒体时返回 None
    """
    import os
    from pathlib import Path

    if not media_paths:
        return None

    base = Path(base_dir)
    img_count = sum(1 for _, is_vid in media_paths if not is_vid)
    video_count = sum(1 for _, is_vid in media_paths if is_vid)

    script_file = base / "merge_video.sh"
    tmp_dir = base / "tmp_segments"
    concat_list = base / "concat_list.txt"
    output_mp4 = base / "replay.mp4"

    with open(script_file, "w", encoding="utf-8") as sf:
        sf.write("#!/bin/bash\n")
        sf.write("# 自动生成的视频合成脚本（截图+录屏 → replay.mp4）\n")
        sf.write("set -e\n\n")
        sf.write(f'RECORD_DIR="{base}"\n')
        sf.write(f'TMP_DIR="{tmp_dir}"\n')
        sf.write(f'CONCAT_LIST="{concat_list}"\n')
        sf.write(f'OUTPUT="{output_mp4}"\n\n')
        sf.write(f'SCREENSHOT_DURATION=${{SCREENSHOT_DURATION:-{screenshot_duration}}}\n\n')
        sf.write('mkdir -p "$TMP_DIR"\n')
        sf.write('rm -f "$CONCAT_LIST"\n\n')

        first_media = media_paths[0][0] if media_paths else ""
        sf.write("# 获取统一分辨率（取第一个媒体文件的尺寸）\n")
        if first_media.endswith((".mp4", ".webm")):
            sf.write(f"RESOLUTION=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 '{first_media}' | head -1)\n")
        else:
            sf.write(f"RESOLUTION=$(ffprobe -v error -show_entries stream=width,height -of csv=p=0 '{first_media}' | head -1)\n")
        sf.write('WIDTH=$(echo $RESOLUTION | cut -d"," -f1)\n')
        sf.write('HEIGHT=$(echo $RESOLUTION | cut -d"," -f2)\n')
        sf.write("WIDTH=$((WIDTH / 2 * 2))\n")
        sf.write("HEIGHT=$((HEIGHT / 2 * 2))\n")
        sf.write('echo "统一分辨率: ${WIDTH}x${HEIGHT}"\n\n')

        for i, (path, is_video) in enumerate(media_paths):
            segment_name = f"seg_{i:04d}.mp4"
            segment_path = f"$TMP_DIR/{segment_name}"
            if is_video:
                sf.write(f"# 片段 {i}: 录屏\n")
                sf.write(f'ffmpeg -y -i \'{path}\' -vf "scale=${{WIDTH}}:${{HEIGHT}}:force_original_aspect_ratio=decrease,pad=${{WIDTH}}:${{HEIGHT}}:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -pix_fmt yuv420p -an "{segment_path}" 2>/dev/null\n')
            else:
                sf.write(f"# 片段 {i}: 截图（$SCREENSHOT_DURATION 秒）\n")
                sf.write(f'ffmpeg -y -loop 1 -i \'{path}\' -t $SCREENSHOT_DURATION -vf "scale=${{WIDTH}}:${{HEIGHT}}:force_original_aspect_ratio=decrease,pad=${{WIDTH}}:${{HEIGHT}}:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -pix_fmt yuv420p "{segment_path}" 2>/dev/null\n')
            sf.write(f'echo "file \'{tmp_dir}/{segment_name}\'" >> "$CONCAT_LIST"\n\n')

        sf.write("# 拼接所有片段\n")
        sf.write('echo "正在拼接..."\n')
        sf.write('ffmpeg -y -f concat -safe 0 -i "$CONCAT_LIST" -c copy "$OUTPUT"\n\n')
        sf.write("# 清理临时文件\n")
        sf.write('rm -rf "$TMP_DIR" "$CONCAT_LIST"\n\n')
        sf.write('echo "✅ 合成完成: $OUTPUT"\n')

    os.chmod(script_file, 0o755)
    print(f"   合成脚本: merge_video.sh ({img_count} 张截图, {video_count} 个录屏)")
    return str(script_file)


# ── 后续命令提示（双格式：zk + python3）──


def tips_after_record(platform: str, record_dir: str, script_path: str = "") -> None:
    """录制结束后的提示"""
    prefix = f"zk replay"
    print(f"\n💡 后续命令：")
    print(f"   ▶️  回放确认:     {prefix} play {record_dir}")
    if script_path:
        print(f"                   python3 {script_path} play {record_dir}")
    print(f"   ✏️  编辑:         {prefix} edit {record_dir}")
    if script_path:
        print(f"                   python3 {script_path} edit {record_dir}")
    print(f"   🖥️  管理器:       zk replay flow manage")
    if script_path:
        print(f"                   python3 {script_path} flow manage")


def tips_after_play(platform: str, record_dir: str, script_path: str = "") -> None:
    """回放确认后的提示"""
    print(f"\n💡 后续命令：")
    print(f"   ▶️  再次回放:     zk replay play {record_dir}")
    if script_path:
        print(f"                   python3 {script_path} play {record_dir}")
    print(f"   ✏️  编辑:         zk replay edit {record_dir}")
    if script_path:
        print(f"                   python3 {script_path} edit {record_dir}")
    print(f"   🖥️  管理器:       zk replay flow manage  （发布为 Flow / 编辑）")
    if script_path:
        print(f"                   python3 {script_path} flow manage")


def tips_after_flow_run(platform: str, flow_id: str, script_path: str = "", report_path: str = "", merge_script: str = "") -> None:
    """Flow 运行结束后的提示"""
    fid = flow_id[:4] if len(flow_id) > 4 else flow_id
    print(f"\n💡 后续命令:")
    print(f"   ▶️  再次运行:     zk replay flow run {fid}")
    if script_path:
        print(f"                   python3 {script_path} flow run {fid}")
    print(f"   📊 重新生成报告: zk replay flow report {fid}")
    if script_path:
        print(f"                   python3 {script_path} flow report {fid}")
    print(f"   🖥️  管理器:       zk replay flow manage")
    if script_path:
        print(f"                   python3 {script_path} flow manage")
    if report_path:
        print(f"   📂 打开报告:     open {report_path}")
    if merge_script:
        print(f"   🎬 合成视频:     bash {merge_script}")


def tips_after_flow_manage(platform: str, flow_id: str = "", script_path: str = "") -> None:
    """管理器关闭后的提示"""
    print(f"\n💡 后续命令:")
    if flow_id:
        fid = flow_id[:4] if len(flow_id) > 4 else flow_id
        print(f"   ▶️  运行 Flow:    zk replay flow run {fid}")
        if script_path:
            print(f"                   python3 {script_path} flow run {fid}")
    print(f"   🎬 录制:         zk replay {platform} record")
    if script_path:
        print(f"                   python3 {script_path} record")


def tips_after_flow_save(flow_id: str) -> None:
    """Flow 保存后的提示（从 Web 管理界面保存时输出到终端）"""
    fid = flow_id[:4] if len(flow_id) > 4 else flow_id
    print(f"\n💡 后续命令：")
    print(f"   ▶️  运行 Flow:    zk replay flow run {fid}")
    print(f"   ✏️  继续编排:     zk replay flow manage")


# ── 日志工具 ──


def log_error(msg: str, detail: str = "") -> None:
    """统一错误日志格式（支持定位异常原因）"""
    print(f"❌ {msg}")
    if detail:
        print(f"   原因: {detail}")


def log_warning(msg: str) -> None:
    """统一警告日志"""
    print(f"⚠️  {msg}")


def log_info(msg: str) -> None:
    """统一信息日志"""
    print(f"ℹ️  {msg}")


def log_success(msg: str) -> None:
    """统一成功日志"""
    print(f"✅ {msg}")
