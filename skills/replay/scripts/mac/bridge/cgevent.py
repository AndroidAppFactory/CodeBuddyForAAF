"""CGEvent 封装 — 事件捕获与模拟

封装 pyobjc-framework-Quartz 的 CGEvent API：
- 录制：CGEventTap 创建事件流监听器
- 回放：CGEventPost 发送模拟事件
"""

import Quartz


def create_event_tap(callback, mask=None):
    """创建 CGEventTap 监听器。

    Args:
        callback: 事件回调函数 f(proxy, event_type, event) -> event
        mask: 要监听的事件类型掩码，默认监听鼠标/键盘/滚轮

    Returns:
        CFMachPortRef 或 None（权限不足时返回 None）
    """
    if mask is None:
        mask = (
            Quartz.kCGEventMaskForAllEvents
        )
    tap = Quartz.CGEventTapCreate(
        Quartz.kCGHIDEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionDefault,
        mask,
        callback,
        None,
    )
    if tap is None:
        return None
    return tap


def run_event_loop(tap, timeout: float = 1e8):
    """将 CGEventTap 加入 CFRunLoop 并永久运行。

    Args:
        tap: CGEventTapCreate 返回的 CFMachPortRef
        timeout: CFRunLoop 超时秒数，默认值足够大（~3年）即永久运行
    """
    run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    Quartz.CFRunLoopAddSource(
        Quartz.CFRunLoopGetCurrent(),
        run_loop_source,
        Quartz.kCFRunLoopCommonModes,
    )
    Quartz.CGEventTapEnable(tap, True)
    Quartz.CFRunLoopRun()


def stop_event_loop():
    """停止当前 CFRunLoop。"""
    Quartz.CFRunLoopStop(Quartz.CFRunLoopGetCurrent())


def post_mouse_event(event_type, x: float, y: float, button=Quartz.kCGMouseButtonLeft, click_state: int = 1):
    """发送鼠标事件。

    Args:
        event_type: kCGEventLeftMouseDown / kCGEventLeftMouseUp / kCGEventMouseMoved 等
        x, y: 屏幕坐标
        button: 鼠标按键常量
        click_state: 点击计数（kCGMouseEventClickState），1=单击 2=双击。
            接收方（Finder/浏览器等）依赖此字段而非纯时间间隔判断双击，
            不设置该字段会导致合成的两次单击无法被识别为双击。
    """
    point = Quartz.CGPoint(x, y)
    event = Quartz.CGEventCreateMouseEvent(None, event_type, point, button)
    Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventClickState, click_state)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def post_key_event(key_code, key_down: bool, flags=0):
    """发送按键事件。

    Args:
        key_code: CGKeyCode 键码
        key_down: True = 按下，False = 释放
        flags: CGEventFlags 修饰键位掩码（如 kCGEventFlagMaskCommand）
    """
    event_type = Quartz.kCGEventKeyDown if key_down else Quartz.kCGEventKeyUp
    event = Quartz.CGEventCreateKeyboardEvent(None, key_code, key_down)
    if flags:
        Quartz.CGEventSetFlags(event, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def get_event_location(event) -> tuple:
    """从 CGEvent 提取鼠标位置。

    Returns:
        (x, y) 屏幕坐标
    """
    loc = Quartz.CGEventGetLocation(event)
    return (loc.x, loc.y)


def get_event_type_name(event) -> str:
    """获取事件类型名称（用于日志）。

    Returns:
        "LMouseDown" / "LMouseUp" / "KeyDown" / "ScrollWheel" 等
    """
    event_type = Quartz.CGEventGetType(event)
    type_map = {
        Quartz.kCGEventLeftMouseDown: "LMouseDown",
        Quartz.kCGEventLeftMouseUp: "LMouseUp",
        Quartz.kCGEventRightMouseDown: "RMouseDown",
        Quartz.kCGEventRightMouseUp: "RMouseUp",
        Quartz.kCGEventMouseMoved: "MouseMoved",
        Quartz.kCGEventLeftMouseDragged: "MouseDragged",
        Quartz.kCGEventScrollWheel: "ScrollWheel",
        Quartz.kCGEventKeyDown: "KeyDown",
        Quartz.kCGEventKeyUp: "KeyUp",
        Quartz.kCGEventFlagsChanged: "FlagsChanged",
    }
    return type_map.get(event_type, f"Unknown({event_type})")


def get_event_flags(event) -> int:
    """获取事件修饰键标记（Bitmask）。"""
    return Quartz.CGEventGetFlags(event)


def get_key_code(event) -> int:
    """获取按键码（仅键盘事件有效）。"""
    return Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)


def get_mouse_button(event) -> int:
    """获取鼠标按键编号（仅鼠标事件有效）。"""
    return Quartz.CGEventGetIntegerValueField(event, Quartz.kCGMouseEventButtonNumber)


def get_scroll_delta(event) -> tuple:
    """获取滚轮增量（仅滚轮事件有效）。

    Returns:
        (delta_x, delta_y) 像素级增量
    """
    dx = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGScrollWheelEventDeltaAxis2)
    dy = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGScrollWheelEventDeltaAxis1)
    return (dx, dy)


def post_scroll_event(x: float, y: float, delta_x: int, delta_y: int):
    """发送滚轮事件。

    Args:
        x, y: 屏幕坐标
        delta_x: 水平滚动量
        delta_y: 垂直滚动量
    """
    event = Quartz.CGEventCreateScrollWheelEvent(
        None,
        Quartz.kCGScrollEventUnitLine,
        2,       # wheelCount
        delta_y,  # axis 1 (垂直)
        delta_x,  # axis 2 (水平)
    )
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
