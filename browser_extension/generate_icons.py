"""
Script tạo icons cho extension
Chạy: python generate_icons.py
"""

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Cần cài Pillow: pip install Pillow")
    exit(1)

import os

# Đường dẫn output
icons_dir = os.path.join(os.path.dirname(__file__), "icons")
os.makedirs(icons_dir, exist_ok=True)

def create_icon(size, filename):
    """Tạo icon với kích thước cho trước"""
    # Tạo image với background gradient-like
    img = Image.new("RGBA", (size, size), (67, 97, 238, 255))  # Blue
    draw = ImageDraw.Draw(img)

    # Vẽ hình tròn ở giữa
    margin = size // 6
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(255, 255, 255, 255)
    )

    # Vẽ chữ "T" ở giữa (Token)
    try:
        # Thử load font
        font_size = size // 2
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()

    text = "T"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (size - text_width) // 2
    y = (size - text_height) // 2 - size // 10

    draw.text((x, y), text, fill=(67, 97, 238, 255), font=font)

    # Lưu
    filepath = os.path.join(icons_dir, filename)
    img.save(filepath, "PNG")
    print(f"Created: {filepath}")

# Tạo các kích thước cần thiết
create_icon(16, "icon16.png")
create_icon(48, "icon48.png")
create_icon(128, "icon128.png")

print("\nDone! Icons created successfully.")
