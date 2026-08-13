"""截图封装 — CGDisplayCreateImage

对每个显示器独立截图再拼接，比 CGWindowListCreateImage 更可靠。
"""

import Quartz
import Cocoa
from pathlib import Path


def capture_fullscreen(output_path: str or Path, mark_pos: tuple = None) -> bool:
    """主显示器截图，保存为 JPG（原分辨率）。

    Args:
        output_path: 输出文件路径
        mark_pos: 可选 (x, y) 屏幕坐标，在该位置绘制鼠标指示器

    Returns:
        True 成功，False 失败
    """
    from PIL import Image, ImageDraw
    import io

    display_id = Quartz.CGMainDisplayID()
    cg_image = Quartz.CGDisplayCreateImage(display_id)
    if cg_image is None:
        print("    ⚠ CGDisplayCreateImage 返回 None")
        return False

    bitmap = Cocoa.NSBitmapImageRep.alloc().initWithCGImage_(cg_image)
    if bitmap is None:
        print("    ⚠ NSBitmapImageRep 初始化失败")
        return False

    png_data = bitmap.representationUsingType_properties_(Cocoa.NSPNGFileType, {})
    img = Image.open(io.BytesIO(bytes(png_data)))

    if img.mode == "RGBA":
        img = img.convert("RGB")

    # 绘制鼠标位置
    if mark_pos:
        gx, gy = mark_pos
        bounds = Quartz.CGDisplayBounds(display_id)
        rx, ry = int(gx - bounds.origin.x), int(gy - bounds.origin.y)

        if 0 <= rx < img.width and 0 <= ry < img.height:
            draw = ImageDraw.Draw(img)
            r = 15
            draw.ellipse([rx - r, ry - r, rx + r, ry + r], outline="#ff4444", width=3)
            draw.line([rx - r - 5, ry, rx + r + 5, ry], fill="#ff4444", width=2)
            draw.line([rx, ry - r - 5, rx, ry + r + 5], fill="#ff4444", width=2)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), format="JPEG", quality=85)
    return True

