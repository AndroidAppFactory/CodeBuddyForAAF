"""aaf CLI 入口"""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaf",
        description="AAF — Android App Factory 框架开发辅助工具",
        epilog="""常用示例：
  aaf config                       读取 AAF 最新配置（SDK/模块版本）
  aaf projects                     列出 AAF_HOME 下所有项目
  aaf version-check /path/to/project  检查项目 AAF 依赖是否有新版本
  aaf version-apply /path/to/project  执行版本号升级替换
  aaf sample-check                  检查 Template-AAF 与 AAF 的差异
  aaf sample-apply --build           升级 Template-AAF + 编译验证
  aaf sample-sync --build            将 Template-AAF 的修改同步到其他两个 Template 项目
  aaf release-check                发布前全面检查
  aaf doc-info LibAudio            获取模块元信息（供文档生成）
  aaf doc-changes                  查看自上次 Tag 以来的变更模块
  aaf apk-16kb-check app.apk       检查 APK 16KB 页面对齐
  aaf apk-size-analyzer app.apk    分析 APK 体积构成与瘦身建议
  aaf replay record test           录制 ADB 操作序列
  aaf replay play test             回放录制的操作序列
  aaf replay flow list             列出所有 Flow
  aaf replay flow show <name>      查看 Flow 详情
  aaf replay flow create           创建 Flow
  aaf replay flow edit <name>      编辑 Flow
  aaf replay flow run <name>       运行 Flow
  aaf replay flow runs [name]      查看运行历史
  aaf replay flow delete <name>    删除 Flow
  aaf kill-adb check               检查 ADB 端口占用状态
  aaf kill-adb kill                强制释放 ADB 端口
  aaf kill-adb kill-server         优雅关闭 ADB server

环境变量：
  AAF_HOME    AAF 项目根目录（包含 AndroidAppFactory 等子目录）
              定义在 ~/.zixiekit/.env

运行方式：
  python3 -m aafkit <command>      模块方式（无需安装）
  aaf <command>                    pip install -e . 后可直接使用""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # aaf config — 读取 AAF 最新配置
    p_config = subparsers.add_parser("config", help="读取 AAF 最新配置（输出 JSON）")
    p_config.add_argument("--pull", action="store_true", default=True, help="先拉取最新代码（默认）")
    p_config.add_argument("--no-pull", action="store_true", help="不拉取，使用本地版本")
    p_config.add_argument("--json", action="store_true", help="输出 JSON 格式")

    # aaf projects — 列出所有项目
    p_projects = subparsers.add_parser("projects", help="列出 AAF_HOME 下所有项目")

    # aaf version-check — 检查项目 AAF 依赖版本
    p_vcheck = subparsers.add_parser("version-check", help="检查项目 AAF 依赖版本")
    p_vcheck.add_argument("project_path", help="项目路径（绝对路径或相对路径）")
    p_vcheck.add_argument("--json", action="store_true", help="输出 JSON 格式")

    # aaf version-apply — 执行版本号替换
    p_vapply = subparsers.add_parser("version-apply", help="执行 AAF 依赖版本升级")
    p_vapply.add_argument("project_path", help="项目路径（绝对路径或相对路径）")

    # aaf sample-check — 检查 Template-AAF
    p_scheck = subparsers.add_parser("sample-check", help="检查 Template-AAF 与 AAF 最新配置的差异")
    p_scheck.add_argument("--json", action="store_true", help="输出 JSON 格式")

    # aaf sample-apply — 升级 Template-AAF
    p_sapply = subparsers.add_parser("sample-apply", help="升级 Template-AAF 到最新 AAF 版本")
    p_sapply.add_argument("--build", action="store_true", help="升级后自动编译验证")

    # aaf sample-sync — 将 Template-AAF 的修改同步到其他两个项目
    p_ssync = subparsers.add_parser(
        "sample-sync",
        help="将 Template-AAF 的修改同步到 Template_Android 和 Template-Empty",
    )
    p_ssync.add_argument("--build", action="store_true", help="同步后自动编译验证")

    # aaf release-check — 发布前检查
    p_release = subparsers.add_parser("release-check", help="发布前自动检查（版本号/模块/依赖/编译/Git）")
    p_release.add_argument("--skip-build", action="store_true", help="跳过编译检查（加速）")
    p_release.add_argument("--json", action="store_true", help="输出 JSON 格式")

    # aaf doc-inspect — 文档巡检
    p_doc = subparsers.add_parser("doc-inspect", help="检查模块与文档的对应关系")
    p_doc.add_argument("--json", action="store_true", help="输出 JSON 格式")

    # aaf doc-info — 获取模块元信息（供文档生成使用）
    p_dinfo = subparsers.add_parser("doc-info", help="获取模块元信息（artifactId/版本/公共API）")
    p_dinfo.add_argument("module", help="模块名（如 LibAudio）")
    p_dinfo.add_argument("--json", action="store_true", help="输出 JSON 格式")

    # aaf doc-changes — 获取增量变更信息
    p_dchanges = subparsers.add_parser("doc-changes", help="获取自上次 Tag 以来的模块变更")
    p_dchanges.add_argument("--module", help="只查看指定模块的变更")
    p_dchanges.add_argument("--json", action="store_true", help="输出 JSON 格式")

    # aaf replay — ADB 操作录制、回放与 Flow 管理
    p_replay = subparsers.add_parser(
        "replay",
        help="ADB 操作录制与回放（record/play/list/export/flow）",
    )
    p_replay.add_argument("replay_args", nargs=argparse.REMAINDER,
                          help="子命令: record, play, list, export, flow create|list|show|edit|run|runs|delete")

    # aaf apk-16kb-check — APK 16KB 对齐检查
    p_16kb = subparsers.add_parser("apk-16kb-check", help="APK/AAB/AAR/工程目录 16KB 页面对齐检查")
    p_16kb.add_argument("target", help="APK/AAB/AAR 文件路径或 Android 工程目录")
    p_16kb.add_argument("--html", help="指定 HTML 报告输出路径")
    p_16kb.add_argument("--batch", action="store_true", help="批量检查目录下的所有文件")
    p_16kb.add_argument("--project", help="关联 Android 工程根目录（用于 AGP 版本检测和 SO 来源分析）")

    # aaf apk-size-analyzer — APK 体积分析
    p_size = subparsers.add_parser("apk-size-analyzer", help="APK/AAB/AAR 体积分析与瘦身建议")
    p_size.add_argument("target", help="APK/AAB/AAR 文件路径")
    p_size.add_argument("--project", help="关联 Android 工程根目录（启用源码分析）")
    p_size.add_argument("--html", help="指定 HTML 报告输出路径")
    p_size.add_argument("--batch", action="store_true", help="批量分析目录下的所有文件")

    # aaf kill-adb — ADB 端口管理
    p_kill_adb = subparsers.add_parser("kill-adb", help="ADB 端口管理（检查/释放/优雅关闭）")
    p_kill_adb.add_argument("action", choices=["check", "kill", "kill-server"], 
                           help="操作类型：check=检查端口状态，kill=强制释放，kill-server=优雅关闭")
    p_kill_adb.add_argument("--port", type=int, default=5037, help="端口号（默认 5037）")
    p_kill_adb.add_argument("--json", action="store_true", help="输出 JSON 格式")

    args = parser.parse_args(argv)

    try:
        if args.command == "config":
            return cmd_config(args)
        elif args.command == "projects":
            return cmd_projects(args)
        elif args.command == "version-check":
            return cmd_version_check(args)
        elif args.command == "version-apply":
            return cmd_version_apply(args)
        elif args.command == "sample-check":
            return cmd_sample_check(args)
        elif args.command == "sample-apply":
            return cmd_sample_apply(args)
        elif args.command == "sample-sync":
            return cmd_sample_sync(args)
        elif args.command == "release-check":
            return cmd_release_check(args)
        elif args.command == "doc-inspect":
            return cmd_doc_inspect(args)
        elif args.command == "doc-info":
            return cmd_doc_info(args)
        elif args.command == "doc-changes":
            return cmd_doc_changes(args)
        elif args.command == "replay":
            return cmd_replay(args)
        elif args.command == "apk-16kb-check":
            return cmd_apk_16kb_check(args)
        elif args.command == "apk-size-analyzer":
            return cmd_apk_size_analyzer(args)
        elif args.command == "kill-adb":
            return cmd_kill_adb(args)
    except RuntimeError as e:
        print(f"\033[31m错误: {e}\033[0m", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


def cmd_config(args: argparse.Namespace) -> int:
    """读取 AAF 最新配置"""
    from ..core.config_reader import get_aaf_root, pull_latest, read_config

    aaf_root = get_aaf_root()

    if not args.no_pull:
        status = pull_latest(aaf_root)
        if not getattr(args, "json", False):
            print(f"📥 {status}")

    config = read_config(aaf_root)

    if getattr(args, "json", False):
        print(config.to_json())
    else:
        d = config.to_dict()
        print("\n## AAF 最新配置\n")
        print("### SDK 配置")
        print("| 配置项 | 值 |")
        print("|--------|-----|")
        for k, v in d["sdk"].items():
            if v:
                print(f"| {k} | {v} |")

        print("\n### 构建工具")
        print("| 配置项 | 值 |")
        print("|--------|-----|")
        for k, v in d["build_tools"].items():
            if v:
                print(f"| {k} | {v} |")

        print(f"\n### 模块默认版本: {config.module_version_name}")
        print(f"\n### 模块版本（共 {len(d['modules'])} 个）")
        print("| artifactId | 版本 | 来源 |")
        print("|-----------|------|------|")
        for aid, info in sorted(d["modules"].items()):
            print(f"| {aid} | {info['version']} | {info['source']} |")

    return 0


def cmd_projects(args: argparse.Namespace) -> int:
    """列出所有项目"""
    from ..core.config_reader import list_projects

    projects = list_projects()
    print("\n## AAF 项目列表\n")
    print("| 项目 | 路径 | 状态 |")
    print("|------|------|------|")
    for p in projects:
        print(f"| {p['name']} | {p['path']} | {p['status']} |")
    return 0


def cmd_version_check(args: argparse.Namespace) -> int:
    """检查版本"""
    from ..core.version_upgrade import version_check

    report = version_check(args.project_path)

    if args.json:
        print(report.to_json())
    else:
        print(report.summary())

    return 0 if not report.has_upgrades else 2  # 2 表示有可用升级


def cmd_version_apply(args: argparse.Namespace) -> int:
    """执行版本升级"""
    from ..core.version_upgrade import generate_commit_message, version_apply, version_check

    report = version_check(args.project_path)

    if not report.has_upgrades:
        print("✅ 所有版本已是最新，无需升级")
        return 0

    print(report.summary())
    print("\n---\n")

    result = version_apply(args.project_path, report)
    for change in result.changes:
        print(f"  {change}")

    commit_msg = generate_commit_message(report)
    if commit_msg:
        unique_files = list(dict.fromkeys(result.changed_files))
        add_cmd = " ".join(unique_files) if unique_files else "."
        cmd_lines = [
            "```bash\n",
            f"cd {args.project_path}\n",
            f"git add {add_cmd}\n",
            f'git commit -m "{commit_msg}\n"\n',
            "```",
        ]
        print("\n" + "\n".join(cmd_lines))

    return 0


def cmd_sample_check(args: argparse.Namespace) -> int:
    """检查 Template-AAF"""
    from ..core.sample_upgrade import sample_check

    project_path = _resolve_sample_project("Template-AAF")
    report = sample_check(project_path)

    if args.json:
        print(report.to_json())
    else:
        print(report.summary())

    has_changes = any(p.has_changes for p in report.projects)
    return 0 if not has_changes else 2


def cmd_sample_apply(args: argparse.Namespace) -> int:
    """升级 Template-AAF"""
    from ..core.sample_upgrade import sample_apply, sample_check
    from ..core.config_reader import build_project
    from pathlib import Path

    project_path = _resolve_sample_project("Template-AAF")
    report = sample_check(project_path)

    proj = report.projects[0] if report.projects else None
    if not proj or proj.status != "ready" or not proj.has_changes:
        print("✅ Template-AAF 已是最新，无需升级")
        return 0

    print(report.summary())
    print("\n---\n执行升级...\n")

    results = sample_apply(project_path, report)

    print("## 执行结果\n")
    all_success = True
    for proj_name, changes in results.items():
        print(f"### {proj_name}")
        for change in changes:
            print(f"  {change}")
        print()

    # 编译验证
    if args.build:
        print("## 编译验证\n")
        proj_path = Path(proj.path)
        print(f"🔨 编译 {proj.name}...")
        success, output = build_project(proj_path)
        if success:
            print(f"  ✅ {proj.name} 编译成功")
        else:
            print(f"  ❌ {proj.name} 编译失败")
            print(f"  {output[:500]}")
            all_success = False

    if all_success:
        ver = report.aaf_config.module_version_name
        commit_msg = f"chore(sample): 升级 Template-AAF AAF 到 {ver}"
        print(f"\n```bash\ncd {proj.path}\ngit add .\ngit commit -m '{commit_msg}'\n```")

    return 0 if all_success else 1


def cmd_sample_sync(args: argparse.Namespace) -> int:
    """将 Template-AAF 的修改同步到 Template_Android 和 Template-Empty"""
    from ..core.sample_sync import sample_sync
    from ..core.config_reader import build_project, get_aaf_home

    print("🔄 将 Template-AAF 的修改同步到其他 Template 项目...\n")

    results = sample_sync()

    print("## 同步结果\n")
    all_success = True
    for proj_name, changes in results.items():
        print(f"### {proj_name}")
        for change in changes:
            print(f"  {change}")
        if any("❌" in c or "⚠️" in c for c in changes):
            all_success = False
        print()

    aaf_home = get_aaf_home()

    # 编译验证
    if args.build and all_success:
        print("## 编译验证\n")
        for proj_name in ["Template_Android", "Template-Empty"]:
            proj_path = aaf_home / proj_name
            if proj_path.exists():
                print(f"🔨 编译 {proj_name}...")
                success, output = build_project(proj_path)
                if success:
                    print(f"  ✅ {proj_name} 编译成功")
                else:
                    print(f"  ❌ {proj_name} 编译失败")
                    print(f"  {output[:500]}")
                    all_success = False

    if all_success:
        for proj_name in ["Template_Android", "Template-Empty"]:
            proj_path = aaf_home / proj_name
            if proj_path.exists():
                commit_msg = f"chore(sample): 同步 Template-AAF 修改到 {proj_name}"
                print(f"```bash\ncd {proj_path}\ngit add .\ngit commit -m '{commit_msg}'\n```")

    return 0 if all_success else 1


def cmd_kill_adb(args: argparse.Namespace) -> int:
    """ADB 端口管理"""
    from ..core.config_reader import get_aaf_home
    import importlib.util
    from pathlib import Path
    
    try:
        # 通过 ZIXIEKIT_HOME 获取 ZixieKit 根路径，找到独立的 adb_port_manager.py
        from ..core.config_reader import get_zixiekit_home
        
        zixie_kit_root = get_zixiekit_home()
        
        adb_manager_path = (
            zixie_kit_root / "skills" / "android" / "adb-port-killer" / "scripts" / "adb_port_manager.py"
        )
        
        if not adb_manager_path.exists():
            raise RuntimeError(f"找不到独立的 ADB 端口管理脚本: {adb_manager_path}")
        
        # 动态加载独立的 adb_port_manager 模块
        spec = importlib.util.spec_from_file_location("adb_port_manager", adb_manager_path)
        adb_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adb_module)
        
        if args.action == "check":
            # 检查端口状态
            status = adb_module.get_port_status(args.port)
            
            if args.json:
                print(status.to_json())
            else:
                print(status.summary())
            
            return 0
            
        elif args.action == "kill":
            # 强制释放端口
            success = adb_module.kill_killable_processes(args.port)
            return 0 if success else 1
            
        elif args.action == "kill-server":
            # 优雅关闭 ADB server
            success = adb_module.kill_adb_server()
            return 0 if success else 1
            
    except RuntimeError as e:
        print(f"\033[31m错误: {e}\033[0m", file=sys.stderr)
        return 1


def _resolve_sample_project(project: str) -> Path:
    """将项目名称或路径解析为绝对路径"""
    from pathlib import Path
    from ..core.config_reader import get_aaf_home

    p = Path(project)
    if p.is_absolute() and p.exists():
        return p

    # 尝试在 AAF_HOME 下查找
    aaf_home = get_aaf_home()
    proj_path = aaf_home / project
    if proj_path.exists():
        return proj_path

    # 尝试当前目录
    if p.exists():
        return p.resolve()

    raise RuntimeError(f"找不到项目: {project}（已尝试: 绝对路径、AAF_HOME/{project}、相对路径）")


def cmd_doc_inspect(args: argparse.Namespace) -> int:
    """文档巡检"""
    from ..core.doc_inspect import doc_inspect

    print("📋 执行文档巡检...\n")
    report = doc_inspect()

    if args.json:
        print(report.to_json())
    else:
        print(report.summary())

    has_issues = bool(report.missing_docs or report.missing_index)
    return 0 if not has_issues else 2  # 2 表示有缺失


def cmd_doc_info(args: argparse.Namespace) -> int:
    """获取模块元信息"""
    from ..core.doc_generator import get_module_info

    info = get_module_info(args.module)

    if args.json:
        print(info.to_json())
    else:
        print(info.summary())

    return 0


def cmd_doc_changes(args: argparse.Namespace) -> int:
    """获取增量变更信息"""
    from ..core.doc_generator import get_update_info

    update = get_update_info(module=args.module if hasattr(args, "module") else None)

    if args.json:
        print(update.to_json())
    else:
        print(update.summary())

    return 0 if update.changed_modules else 0


def cmd_release_check(args: argparse.Namespace) -> int:
    """发布前检查"""
    from ..core.release_check import release_check

    print("🔍 执行发布前检查...\n")
    report = release_check(skip_build=args.skip_build)

    if args.json:
        print(report.to_json())
    else:
        print(report.summary())

    return 0 if report.all_passed else 1


def cmd_replay(args: argparse.Namespace) -> int:
    """ADB 操作录制与回放（委托给 adb_replay.py）"""
    import importlib.util
    from pathlib import Path

    # 定位 adb_replay.py 脚本
    skill_dir = Path(__file__).resolve().parents[2] / "skills" / "dev" / "replay" / "scripts" / "adb"
    # 如果 aafkit 是通过 pip install -e . 安装的，skill_dir 可能不对，尝试从 ZixieKit 根查找
    if not skill_dir.exists():
        # fallback: 从当前文件向上找 ZixieKit 根
        for parent in Path(__file__).resolve().parents:
            candidate = parent / "skills" / "dev" / "replay" / "scripts" / "adb" / "adb_replay.py"
            if candidate.exists():
                skill_dir = candidate.parent
                break

    script_path = skill_dir / "adb_replay.py"
    if not script_path.exists():
        print(f"\033[31m错误: 找不到 replay/adb 脚本: {script_path}\033[0m", file=sys.stderr)
        return 1

    # 动态加载 adb_replay 模块
    spec = importlib.util.spec_from_file_location("adb_replay", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # 将 replay_args 传递给 adb_replay.main()
    replay_argv = args.replay_args or []
    # argparse.REMAINDER 可能在前面带一个 '--'，去掉
    if replay_argv and replay_argv[0] == "--":
        replay_argv = replay_argv[1:]

    return mod.main(replay_argv)


def cmd_apk_16kb_check(args: argparse.Namespace) -> int:
    """APK 16KB 对齐检查"""
    import importlib.util
    from pathlib import Path
    import sys

    # 定位 apk-16kb-check 脚本
    skill_dir = Path(__file__).resolve().parents[2] / "skills" / "android" / "apk-16kb-check" / "scripts"
    # 如果 aafkit 是通过 pip install -e . 安装的，skill_dir 可能不对，尝试从 ZixieKit 根查找
    if not skill_dir.exists():
        # fallback: 从当前文件向上找 ZixieKit 根
        for parent in Path(__file__).resolve().parents:
            candidate = parent / "skills" / "android" / "apk-16kb-check" / "scripts" / "check_alignment.py"
            if candidate.exists():
                skill_dir = candidate.parent
                break

    script_path = skill_dir / "check_alignment.py"
    if not script_path.exists():
        print(f"\033[31m错误: 找不到 apk-16kb-check 脚本: {script_path}\033[0m", file=sys.stderr)
        return 1

    # 添加脚本目录到 sys.path 以便相对导入能正常工作
    original_path = sys.path.copy()
    sys.path.insert(0, str(skill_dir))
    
    try:
        # 动态加载模块
        spec = importlib.util.spec_from_file_location("check_alignment", script_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # 构建 sys.argv 列表
        original_argv = sys.argv.copy()
        sys.argv = ["aaf apk-16kb-check"]
        if args.batch:
            sys.argv.append("--batch")
        sys.argv.append(args.target)
        if args.project:
            sys.argv.extend(["--project", args.project])
        if args.html:
            sys.argv.append(args.html)

        return mod.main()
    finally:
        # 恢复原始 sys.path 和 sys.argv
        sys.path = original_path
        sys.argv = original_argv


def cmd_apk_size_analyzer(args: argparse.Namespace) -> int:
    """APK 体积分析"""
    import importlib.util
    from pathlib import Path
    import sys

    # 定位 apk-size-analyzer 脚本
    skill_dir = Path(__file__).resolve().parents[2] / "skills" / "android" / "apk-size-analyzer" / "scripts"
    # 如果 aafkit 是通过 pip install -e . 安装的，skill_dir 可能不对，尝试从 ZixieKit 根查找
    if not skill_dir.exists():
        # fallback: 从当前文件向上找 ZixieKit 根
        for parent in Path(__file__).resolve().parents:
            candidate = parent / "skills" / "android" / "apk-size-analyzer" / "scripts" / "analyze_apk.py"
            if candidate.exists():
                skill_dir = candidate.parent
                break

    script_path = skill_dir / "analyze_apk.py"
    if not script_path.exists():
        print(f"\033[31m错误: 找不到 apk-size-analyzer 脚本: {script_path}\033[0m", file=sys.stderr)
        return 1

    # 添加脚本目录到 sys.path 以便相对导入能正常工作
    original_path = sys.path.copy()
    sys.path.insert(0, str(skill_dir))
    
    try:
        # 动态加载模块
        spec = importlib.util.spec_from_file_location("analyze_apk", script_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # 构建 sys.argv 列表
        original_argv = sys.argv.copy()
        sys.argv = ["aaf apk-size-analyzer"]
        if args.batch:
            sys.argv.append("--batch")
        sys.argv.append(args.target)
        if args.project:
            sys.argv.extend(["--project", args.project])
        if args.html:
            sys.argv.append(args.html)

        return mod.main()
    finally:
        # 恢复原始 sys.path 和 sys.argv
        sys.path = original_path
        sys.argv = original_argv


if __name__ == "__main__":
    sys.exit(main())
