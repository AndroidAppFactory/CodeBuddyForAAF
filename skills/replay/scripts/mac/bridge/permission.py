"""权限检测与引导

检测 macOS 辅助功能和屏幕录制权限状态，未授权时引导用户开启。
"""

import subprocess
import sys


def check_accessibility_permission() -> bool:
    """检测辅助功能权限是否已授权。

    通过 AXIsProcessTrusted 和 AXIsProcessTrustedWithOptions 双重检测。

    Returns:
        True 已授权，False 未授权
    """
    import ApplicationServices as AX
    try:
        trusted = AX.AXIsProcessTrusted()
        if trusted:
            return True
        # 尝试带选项检测
        options = {AX.kAXTrustedCheckOptionPrompt: False}
        trusted = AX.AXIsProcessTrustedWithOptions(options, None)
        return trusted
    except Exception:
        return False


def check_screen_recording_permission() -> bool:
    """检测屏幕录制权限是否已授权。

    通过尝试创建截屏图像来检测，CGWindowListCreateImage 在没有权限时会
    返回空图像或抛出异常。

    Returns:
        True 已授权，False 未授权
    """
    import Quartz
    try:
        image = Quartz.CGWindowListCreateImage(
            Quartz.CGRectInfinite,
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID,
            Quartz.kCGWindowImageDefault,
        )
        if image is None:
            return False
        return True
    except Exception:
        return False


def prompt_accessibility_permission():
    """引导用户开启辅助功能权限。

    弹出系统授权对话框（如果支持），否则打开系统偏好设置。
    """
    import ApplicationServices as AX

    print("\n" + "=" * 50)
    print("需要辅助功能权限才能捕获键盘/鼠标事件。")
    print()

    # 尝试弹出授权对话框
    try:
        options = {AX.kAXTrustedCheckOptionPrompt: True}
        trusted = AX.AXIsProcessTrustedWithOptions(options, None)
        if not trusted:
            print("请在弹出的系统对话框中授予辅助功能权限。")
            print("如未弹出对话框，请手动操作：")
    except Exception:
        print("请手动操作：")

    print("  系统偏好设置 → 隐私与安全性 → 辅助功能")
    print(f"  添加: {sys.executable}")
    print()
    print("授权后请重新运行本命令。")
    print("=" * 50 + "\n")

    # 同时打开系统偏好设置
    try:
        subprocess.run(
            [
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            ],
            timeout=5,
        )
    except Exception:
        pass


def prompt_screen_recording_permission():
    """引导用户开启屏幕录制权限。"""
    print("\n" + "=" * 50)
    print("需要屏幕录制权限才能截图。")
    print()
    print("请前往系统偏好设置 → 隐私与安全性 → 屏幕录制，")
    print("勾选你的终端程序。")
    print("=" * 50 + "\n")
