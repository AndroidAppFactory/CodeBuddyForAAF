"""replay-core 报告模块单元测试"""


def test_step_desc_html_tap():
    """坐标类事件描述"""
    from core.report import _step_desc_html
    assert "500" in _step_desc_html({"action": "tap", "x": 500, "y": 300})
    assert "swipe" in _step_desc_html({"action": "swipe", "x1": 0, "y1": 0, "x2": 100, "y2": 100})
    assert "keyevent" in _step_desc_html({"action": "keyevent", "code": 3})


def test_step_desc_html_web():
    """选择器类事件描述"""
    from core.report import _step_desc_html
    ev = {"action": "click", "selectors": [{"type": "css", "value": ".btn"}]}
    assert ".btn" in _step_desc_html(ev)
    ev2 = {"action": "navigate", "value": "https://example.com/very/long/path"}
    assert "导航" in _step_desc_html(ev2)
    ev3 = {"action": "input", "value": "hello"}
    assert "hello" in _step_desc_html(ev3)


def test_step_desc_html_legacy():
    """兼容旧格式（type 充当 action）"""
    from core.report import _step_desc_html
    assert "500" in _step_desc_html({"type": "tap", "x": 500, "y": 300})
