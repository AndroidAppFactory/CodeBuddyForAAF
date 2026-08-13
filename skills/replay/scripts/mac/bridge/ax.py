"""AXUIElement 封装 — Accessibility 元素树操作

封装 pyobjc-framework-ApplicationServices 的 AX API：
- 坐标 → AX 元素（录制定位）
- AX 路径 → 坐标（回放定位）
- 元素操作（点击、输入、聚焦）
"""

import ApplicationServices as AX


# ─── 元素查找 ───────────────────────────────────────


def get_element_at_position(x: float, y: float) -> AX.AXUIElement or None:
    """获取屏幕某坐标处的 AX 元素。

    Args:
        x, y: 屏幕绝对坐标

    Returns:
        AXUIElement 对象，未找到返回 None
    """
    try:
        ref = AX.AXUIElementCreateSystemWide()
        err, element = AX.AXUIElementCopyElementAtPosition(ref, x, y, None)
        if err == AX.kAXErrorSuccess and element is not None:
            return element
        return None
    except Exception:
        return None


def get_focused_window() -> AX.AXUIElement or None:
    """获取当前焦点窗口的 AX 元素。"""
    try:
        app = AX.AXUIElementCreateSystemWide()
        window = AX.AXUIElementCopyAttributeValue(
            app, AX.kAXFocusedWindowAttribute, None
        )
        if window is None:
            return None
        return window[0] if isinstance(window, tuple) else window
    except Exception:
        return None


def get_frontmost_app() -> AX.AXUIElement or None:
    """获取最前台应用的 AX 元素。"""
    try:
        app = AX.AXUIElementCreateSystemWide()
        focused = AX.AXUIElementCopyAttributeValue(
            app, AX.kAXFocusedApplicationAttribute, None
        )
        if focused is None:
            return None
        return focused[0] if isinstance(focused, tuple) else focused
    except Exception:
        return None


# ─── 属性读取 ───────────────────────────────────────


def get_attribute(element, attr: str):
    """读取 AX 元素属性。

    Returns:
        属性值或 None
    """
    try:
        err, value = AX.AXUIElementCopyAttributeValue(element, attr, None)
        if err == AX.kAXErrorSuccess:
            return value
        return None
    except Exception:
        return None


def get_role(element) -> str:
    """获取元素角色（AXRole）。"""
    val = get_attribute(element, AX.kAXRoleAttribute)
    return val or ""


def get_title(element) -> str:
    """获取元素标题（AXTitle）。"""
    val = get_attribute(element, AX.kAXTitleAttribute)
    return val or ""


def get_description(element) -> str:
    """获取元素描述（AXDescription）。"""
    val = get_attribute(element, AX.kAXDescriptionAttribute)
    return val or ""


def get_identifier(element) -> str:
    """获取元素标识符（AXIdentifier）。"""
    val = get_attribute(element, AX.kAXIdentifierAttribute)
    return val or ""


def get_position(element) -> tuple or None:
    """获取元素位置。

    Returns:
        (x, y) 或 None
    """
    val = get_attribute(element, AX.kAXPositionAttribute)
    if val is None:
        return None
    try:
        # pyobjc 中 AXValue 需要通过 AXValueGetValue 提取 CGPoint
        import Quartz
        point = Quartz.CGPoint()
        AX.AXValueGetValue(val, AX.kAXValueCGPointType, point)
        return (point.x, point.y)
    except Exception:
        return None


def get_size(element) -> tuple or None:
    """获取元素尺寸。

    Returns:
        (width, height) 或 None
    """
    val = get_attribute(element, AX.kAXSizeAttribute)
    if val is None:
        return None
    try:
        import Quartz
        size = Quartz.CGSize()
        AX.AXValueGetValue(val, AX.kAXValueCGSizeType, size)
        return (size.width, size.height)
    except Exception:
        return None


def get_children(element) -> list or None:
    """获取子元素列表。"""
    val = get_attribute(element, AX.kAXChildrenAttribute)
    if val is None:
        return None
    return val if isinstance(val, list) else list(val)


def get_parent(element) -> AX.AXUIElement or None:
    """获取父元素。"""
    val = get_attribute(element, AX.kAXParentAttribute)
    return val if val is not None else None


def get_window_title(element) -> str:
    """获取窗口标题。"""
    val = get_attribute(element, AX.kAXTitleAttribute)
    return val or ""


def get_bundle_id(element) -> str:
    """获取应用 Bundle Identifier。"""
    val = get_attribute(element, "AXBundleIdentifier")
    if val is None:
        val = get_attribute(element, AX.kAXIdentifierAttribute)
    return val or ""


# ─── 元素操作 ───────────────────────────────────────


def set_focus(element):
    """设置 AX 元素为焦点。"""
    try:
        AX.AXUIElementSetAttributeValue(element, AX.kAXFocusedAttribute, True)
    except Exception:
        pass


def perform_press(element):
    """模拟点击 AX 元素（AXPress）。"""
    try:
        AX.AXUIElementPerformAction(element, AX.kAXPressAction)
    except Exception:
        pass


def perform_confirm(element):
    """模拟确认 AX 元素（AXConfirm，如回车）。"""
    try:
        AX.AXUIElementPerformAction(element, AX.kAXConfirmAction)
    except Exception:
        pass


# ─── AX 路径构建 ────────────────────────────────────


def build_ax_path(element) -> dict:
    """从指定元素向上构建 AX 路径链。

    Returns:
        {
            "app": "com.apple.Safari",
            "window": "百度一下",
            "path": [
                {"role": "AXWebArea", "name": "百度一下", "identifier": "", "index": 0},
                ...
            ],
            "fallback": {"x": 500, "y": 200}
        }
    """
    path = []
    current = element
    app_elem = None
    window_title = ""
    bundle_id = ""

    while current is not None:
        role = get_role(current)
        if not role:
            break

        if role == "AXApplication":
            app_elem = current
            bundle_id = get_bundle_id(current)
            break

        if role == "AXWindow":
            window_title = get_window_title(current)
            path.insert(0, {
                "role": role,
                "name": window_title,
                "identifier": get_identifier(current),
                "index": 0,
            })
            current = get_parent(current)
            continue

        name = get_title(current) or get_description(current)
        identifier = get_identifier(current)

        # 计算同级同角色元素的 index
        parent = get_parent(current)
        sibling_index = 0
        if parent:
            siblings = get_children(parent)
            if siblings:
                for i, sib in enumerate(siblings):
                    if get_role(sib) == role:
                        if sib == current:
                            sibling_index = i
                            break

        path.insert(0, {
            "role": role,
            "name": name,
            "identifier": identifier,
            "index": sibling_index,
        })
        current = get_parent(current)

    # fallback 坐标
    pos = get_position(element)
    size = get_size(element)
    fallback = {"x": 0, "y": 0}
    if pos and size:
        fallback = {"x": int(pos[0] + size[0] / 2), "y": int(pos[1] + size[1] / 2)}
    elif pos:
        fallback = {"x": int(pos[0]), "y": int(pos[1])}

    return {
        "app": bundle_id,
        "window": window_title,
        "path": path,
        "fallback": fallback,
    }


def resolve_ax_path(ax_path: dict) -> AX.AXUIElement or None:
    """按 AX 路径链逐级查找目标元素。

    Args:
        ax_path: build_ax_path 产出的路径字典

    Returns:
        找到的 AXUIElement，失败返回 None
    """
    app = ax_path.get("app", "")
    window_name = ax_path.get("window", "")
    elem_path = ax_path.get("path", [])

    if not app:
        return None

    # 获取目标应用
    target_app = None
    try:
        import Cocoa
        apps = Cocoa.NSRunningApplication.runningApplicationsWithBundleIdentifier_(app)
        if apps and len(apps) > 0:
            pid = apps[0].processIdentifier()
            target_app = AX.AXUIElementCreateApplication(pid)
    except Exception:
        pass

    if target_app is None:
        return None

    # 尝试两种查找策略
    element = _resolve_by_path(target_app, window_name, elem_path)
    if element is not None:
        return element

    element = _resolve_by_path(target_app, None, elem_path)
    return element


def _resolve_by_path(
    root, window_name: str or None, elem_path: list
) -> AX.AXUIElement or None:
    """按路径链查找，可选择性跳过窗口层匹配。"""
    current = root

    for step in elem_path:
        role = step.get("role", "")
        step_name = step.get("name", "")
        step_identifier = step.get("identifier", "")
        step_index = step.get("index", 0)

        children = get_children(current)
        if not children:
            return None

        candidates = []
        idx = 0
        for child in children:
            child_role = get_role(child)
            if child_role != role:
                continue

            child_name = get_title(child) or get_description(child)
            child_id = get_identifier(child)

            # 优先 identifier 匹配
            if step_identifier and child_id and step_identifier == child_id:
                current = child
                break

            # 其次 name 匹配
            if step_name and child_name and step_name in child_name:
                candidates.append(child)

            # 记录 index（仅当没命中 identifier 时用）
            if idx == step_index:
                candidates.append(child)
            idx += 1
        else:
            # for-else：没 break 出来说明没精确匹配
            if candidates:
                current = candidates[0]
            else:
                return None

    return current
