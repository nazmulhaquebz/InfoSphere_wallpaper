import os
import sys
import ctypes
from PIL import Image, ImageDraw, ImageFont

def create_standby_wallpaper():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(root, "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "infosphere_wallpaper.bmp")

    width, height = 1920, 1080
    img = Image.new("RGB", (width, height), color=(5, 8, 17))
    draw = ImageDraw.Draw(img)

    # 1. Subtle Cyber Grid
    grid_size = 40
    grid_color = (10, 22, 38)
    for x in range(0, width, grid_size):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, grid_size):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)

    # 2. Tactical border frame
    cyan_dim = (0, 110, 140)
    cyan_bright = (0, 229, 255)
    margin = 30
    draw.rectangle([margin, margin, width - margin, height - margin], outline=cyan_dim, width=1)

    # Corner brackets
    bracket_len = 50
    # Top-Left
    draw.line([(margin, margin), (margin + bracket_len, margin)], fill=cyan_bright, width=3)
    draw.line([(margin, margin), (margin, margin + bracket_len)], fill=cyan_bright, width=3)
    # Top-Right
    draw.line([(width - margin, margin), (width - margin - bracket_len, margin)], fill=cyan_bright, width=3)
    draw.line([(width - margin, margin), (width - margin, margin + bracket_len)], fill=cyan_bright, width=3)
    # Bottom-Left
    draw.line([(margin, height - margin), (margin + bracket_len, height - margin)], fill=cyan_bright, width=3)
    draw.line([(margin, height - margin), (margin, height - margin - bracket_len)], fill=cyan_bright, width=3)
    # Bottom-Right
    draw.line([(width - margin, height - margin), (width - margin - bracket_len, height - margin)], fill=cyan_bright, width=3)
    draw.line([(width - margin, height - margin), (width - margin, height - margin - bracket_len)], fill=cyan_bright, width=3)

    # 3. Paste Logo if available
    logo_path = os.path.join(root, "img", "logo.png")
    if os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((120, 120), Image.Resampling.LANCZOS)
            lx = (width - logo.width) // 2
            ly = height // 2 - 140
            img.paste(logo, (lx, ly), logo)
        except Exception:
            pass

    # 4. Text Branding (Center)
    try:
        font_title = ImageFont.truetype("arial.ttf", 36)
        font_sub = ImageFont.truetype("arial.ttf", 16)
        font_tag = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font_title = font_sub = font_tag = ImageFont.load_default()

    title_text = "INFOSPHERE TACTICAL CYBER ENGINE"
    sub_text = "LIVE SYSTEM OBSERVABILITY & KERNEL TELEMETRY"
    status_text = "[ LIVE ENGINE ACTIVE ]"

    bbox_title = draw.textbbox((0, 0), title_text, font=font_title)
    w_title = bbox_title[2] - bbox_title[0]
    draw.text(((width - w_title) // 2, height // 2 + 10), title_text, fill=(0, 229, 255), font=font_title)

    bbox_sub = draw.textbbox((0, 0), sub_text, font=font_sub)
    w_sub = bbox_sub[2] - bbox_sub[0]
    draw.text(((width - w_sub) // 2, height // 2 + 65), sub_text, fill=(160, 200, 220), font=font_sub)

    bbox_tag = draw.textbbox((0, 0), status_text, font=font_tag)
    w_tag = bbox_tag[2] - bbox_tag[0]
    draw.text(((width - w_tag) // 2, height // 2 + 110), status_text, fill=(0, 255, 157), font=font_tag)

    # Save as 24-bit BMP
    img.save(out_path, format="BMP")
    print(f"[OK] Generated clean standby wallpaper: {out_path}")

    # Apply to Windows Desktop Wallpaper immediately via SystemParametersInfoW
    if sys.platform == "win32":
        SPI_SETDESKWALLPAPER = 20
        SPIF_UPDATEINIFILE   = 0x01
        SPIF_SENDCHANGE      = 0x02
        res = ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, out_path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
        )
        print(f"[OK] Applied to Windows desktop wallpaper (result={res})")

if __name__ == "__main__":
    create_standby_wallpaper()
