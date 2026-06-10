#!/usr/bin/env python3
"""
ADB 端口管理工具 - 完全独立 Python 版本

用法:
    python3 adb_port_manager.py check [--port PORT]
    python3 adb_port_manager.py kill [--port PORT]
    python3 adb_port_manager.py kill-server
    python3 adb_port_manager.py kill-pid PID
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import List

@dataclass
class PortProcess:
    """端口占用进程信息"""
    pid: int
    cmd: str
    is_protected: bool

@dataclass
class PortStatus:
    """端口状态信息"""
    port: int
    status: str  # "free" or "occupied"
    killable: List[PortProcess]
    protected: List[PortProcess]
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "port": self.port,
            "status": self.status,
            "killable": [{"pid": p.pid, "cmd": p.cmd} for p in self.killable],
            "protected": [{"pid": p.pid, "cmd": p.cmd} for p in self.protected],
        }
    
    def to_json(self) -> str:
        """转换为 JSON 格式"""
        return json.dumps(self.to_dict(), indent=2)
    
    def summary(self) -> str:
        """生成状态摘要"""
        if self.status == "free":
            return f"✅ 端口 {self.port} 空闲"
        
        lines = [f"📊 端口 {self.port} 占用状态:"]
        if self.protected:
            lines.append(f"  🔒 保护进程 ({len(self.protected)} 个):")
            for proc in self.protected:
                lines.append(f"    - PID {proc.pid}: {proc.cmd}")
        
        if self.killable:
            lines.append(f"  🎯 可终止进程 ({len(self.killable)} 个):")
            for proc in self.killable:
                lines.append(f"    - PID {proc.pid}: {proc.cmd}")
        else:
            lines.append("  ℹ️  无可终止进程")
        
        return "\n".join(lines)

def get_port_status(port: int = 5037) -> PortStatus:
    """获取端口占用状态"""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}"],
            capture_output=True,
            text=True,
            timeout=10
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"检查端口 {port} 超时")
    
    output = result.stdout.strip()
    print(f"DEBUG: lsof output = '{output}'", file=sys.stderr)
    
    if not output:
        print("DEBUG: output is empty, returning free status", file=sys.stderr)
        return PortStatus(port=port, status="free", killable=[], protected=[])
    
    # 保护进程名列表（小写匹配）
    protected_patterns = ["studio", "idea", "java"]
    
    killable = []
    protected = []
    seen_pids = set()
    
    for line in output.split('\n'):
        # 跳过标题行
        if line.startswith("COMMAND"):
            continue
        
        parts = line.split()
        if len(parts) < 2:
            continue
        
        cmd = parts[0]
        try:
            pid = int(parts[1])
        except ValueError:
            continue
        
        # 按 PID 去重
        if pid in seen_pids:
            continue
        seen_pids.add(pid)
        
        is_protected = any(pattern in cmd.lower() for pattern in protected_patterns)
        proc = PortProcess(pid=pid, cmd=cmd, is_protected=is_protected)
        if is_protected:
            protected.append(proc)
            print(f"DEBUG: 保护进程 PID {pid}: {cmd}", file=sys.stderr)
        else:
            killable.append(proc)
            print(f"DEBUG: 可终止进程 PID {pid}: {cmd}", file=sys.stderr)
    
    # 如果解析了进程信息，返回占用状态
    if killable or protected:
        return PortStatus(
            port=port,
            status="occupied",
            killable=killable,
            protected=protected
        )
    else:
        # 如果没有解析到任何进程信息，返回空闲状态
        return PortStatus(port=port, status="free", killable=[], protected=[])

def kill_killable_processes(port: int = 5037) -> bool:
    """终止占用端口的非保护进程"""
    status = get_port_status(port)
    
    if not status.killable:
        print(f"端口 {port} 无需 kill 的进程（仅有保护进程或端口空闲）")
        return True
    
    print(f"正在 kill 占用端口 {port} 的非保护进程:")
    all_success = True
    
    for proc in status.killable:
        try:
            subprocess.run(["kill", "-9", str(proc.pid)], check=True)
            print(f"  ✅ 已终止 PID {proc.pid}: {proc.cmd}")
        except subprocess.CalledProcessError:
            print(f"  ❌ 终止 PID {proc.pid} 失败（权限不足或进程已退出）")
            all_success = False
        
        # 验证结果
        import time
        time.sleep(0.5)
        
        new_status = get_port_status(port)
        if not new_status.killable:
            print(f"✅ 端口 {port} 已释放（studio 等保护进程已保留）")
            return True
        else:
            remaining_pids = [str(p.pid) for p in new_status.killable]
            print(f"⚠️  仍有非保护进程占用端口 {port}: {', '.join(remaining_pids)}")
            return False

def kill_adb_server() -> bool:
    """优雅关闭 ADB server（保留保护进程）"""
    print("尝试 adb kill-server ...")
    
    try:
        subprocess.run(["adb", "kill-server"], check=True, capture_output=True)
        print("  ✅ adb kill-server 成功")
    except subprocess.CalledProcessError:
        print("  ❌ adb kill-server 失败，尝试强制 kill 非保护进程")
        return kill_killable_processes()
    
    # 验证结果
    import time
    time.sleep(0.5)
    
    status = get_port_status()
    if not status.killable:
        print("✅ 端口 5037 已释放（studio 等保护进程已保留）")
        return True
    else:
        print("⚠️  仍有非保护进程占用端口 5037，尝试强制 kill")
        return kill_killable_processes()
    
def kill_specific_pid(pid: int) -> bool:
    """终止指定 PID 的进程"""
    print(f"正在 kill PID {pid} ...")
    
    try:
        subprocess.run(["kill", "-9", str(pid)], check=True)
        print(f"  ✅ 已终止 PID {pid}")
        return True
    except subprocess.CalledProcessError:
        print(f"  ❌ 终止 PID {pid} 失败")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="ADB 端口管理工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # check 命令
    check_parser = subparsers.add_parser("check", help="检查端口状态")
    check_parser.add_argument("--port", type=int, default=5037, help="端口号，默认 5037")
    check_parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    
    # kill 命令
    kill_parser = subparsers.add_parser("kill", help="强制释放端口")
    kill_parser.add_argument("--port", type=int, default=5037, help="端口号，默认 5037")
    
    # kill-server 命令
    subparsers.add_parser("kill-server", help="优雅关闭 ADB server")
    
    # kill-pid 命令
    kill_pid_parser = subparsers.add_parser("kill-pid", help="终止指定 PID")
    kill_pid_parser.add_argument("pid", type=int, help="进程 ID")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == "check":
            status = get_port_status(args.port)
            print(f"DEBUG: status type = {type(status)}", file=sys.stderr)
            print(f"DEBUG: status value = {status}", file=sys.stderr)
            if status is None:
                print("ERROR: get_port_status returned None", file=sys.stderr)
                return 1
            if args.json:
                print(status.to_json())
            else:
                print(status.summary())
        
        elif args.command == "kill":
            success = kill_killable_processes(args.port)
            return 0 if success else 1
        
        elif args.command == "kill-server":
            success = kill_adb_server()
            return 0 if success else 1
        
        elif args.command == "kill-pid":
            success = kill_specific_pid(args.pid)
            return 0 if success else 1
        
        return 0
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())