"""
Crop human_cutout.png to the person's exact bounding box with comfortable cyber margin.
Then generate pixel-perfect cybernetic circuits and holographic HUD framing overlay.
"""

from PIL import Image, ImageDraw, ImageFilter
import numpy as np

def process_cropped_avatar():
    src_path = "Human/robotic/human_cutout.png"
    img = Image.open(src_path).convert("RGBA")
    arr = np.array(img)
    alpha = arr[:, :, 3]

    y_indices, x_indices = np.where(alpha > 20)
    x_min, x_max = int(x_indices.min()), int(x_indices.max())
    y_min, y_max = int(y_indices.min()), int(y_indices.max())

    pad_x = 35
    pad_top = 30
    pad_bottom = 15

    crop_x1 = max(0, x_min - pad_x)
    crop_y1 = max(0, y_min - pad_top)
    crop_x2 = min(img.width, x_max + pad_x)
    crop_y2 = min(img.height, y_max + pad_bottom)

    cropped_human = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
    cropped_human.save("Human/robotic/human_cutout.png", format="PNG")
    W, H = cropped_human.size
    print(f"[OK] Cropped human_cutout.png to {W}x{H}")

    # Now generate the matching Cybernetic Circuit Overlay
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    cyan_bright = (0, 229, 255, 240)
    cyan_glow = (0, 180, 255, 160)
    cyan_faint = (0, 229, 255, 70)
    white_core = (230, 250, 255, 255)

    # 1. Tech HUD Brackets around the cropped boundary
    b_len = 50
    m = 12
    lw = 2
    # Top-Left
    draw.line([(m, m + b_len), (m, m), (m + b_len, m)], fill=cyan_bright, width=lw)
    # Top-Right
    draw.line([(W - m - b_len, m), (W - m, m), (W - m, m + b_len)], fill=cyan_bright, width=lw)
    # Bottom-Left
    draw.line([(m, H - m - b_len), (m, H - m), (m + b_len, H - m)], fill=cyan_bright, width=lw)
    # Bottom-Right
    draw.line([(W - m - b_len, H - m), (W - m, H - m), (W - m, H - m - b_len)], fill=cyan_bright, width=lw)

    # Corner dots
    for cx, cy in [(m + 4, m + 4), (W - m - 4, m + 4), (m + 4, H - m - 4), (W - m - 4, H - m - 4)]:
        draw.ellipse([(cx - 3, cy - 3), (cx + 3, cy + 3)], fill=white_core)

    # 2. Tech Data Marks along vertical sides
    for y in range(m + b_len + 20, H - m - b_len, 35):
        draw.line([(m + 2, y), (m + 12, y)], fill=cyan_faint, width=1)
        draw.line([(W - m - 12, y), (W - m - 2, y)], fill=cyan_faint, width=1)

    # 3. Micro Cybernetic Circuits on Suit Lapels, Arms, Waist, Legs
    # Measure silhouette coordinates relative to cropped origin:
    # Head center: X ~ W*0.5, Y ~ 100
    # Left Shoulder: X ~ W*0.28, Y ~ 260
    # Right Shoulder: X ~ W*0.78, Y ~ 270
    # Left Arm: X ~ W*0.14, Y ~ 430 -> 650
    # Right Arm: X ~ W*0.92, Y ~ 430 -> 650
    # Lapels: X ~ W*0.42 & 0.58, Y ~ 320 -> 560
    # Belt / Waist: X ~ W*0.25 -> 0.75, Y ~ 720
    # Legs: X ~ W*0.35 & 0.70, Y ~ 800 -> 1380
    # Shoes: X ~ W*0.32 & 0.72, Y ~ 1420

    circuits = [
        # Left Arm & Shoulder
        [(int(W*0.26), 280), (int(W*0.18), 340), (int(W*0.13), 480), (int(W*0.10), 620)],
        [(int(W*0.22), 380), (int(W*0.16), 520), (int(W*0.14), 660)],
        # Right Arm & Shoulder
        [(int(W*0.75), 285), (int(W*0.84), 350), (int(W*0.90), 480), (int(W*0.93), 620)],
        [(int(W*0.80), 390), (int(W*0.86), 520), (int(W*0.88), 660)],
        # Suit Lapels
        [(int(W*0.43), 320), (int(W*0.40), 420), (int(W*0.44), 540), (int(W*0.47), 640)],
        [(int(W*0.57), 320), (int(W*0.60), 420), (int(W*0.56), 540), (int(W*0.53), 640)],
        # Waist Cyber Bus
        [(int(W*0.22), 720), (int(W*0.50), 725), (int(W*0.78), 720)],
        # Left Leg Outer Bus
        [(int(W*0.24), 800), (int(W*0.23), 960), (int(W*0.26), 1160), (int(W*0.30), 1360)],
        # Right Leg Outer Bus
        [(int(W*0.76), 800), (int(W*0.78), 960), (int(W*0.75), 1160), (int(W*0.72), 1360)],
        # Shoe Bases
        [(int(W*0.26), 1435), (int(W*0.36), 1445), (int(W*0.45), 1440)],
        [(int(W*0.58), 1440), (int(W*0.68), 1445), (int(W*0.76), 1435)],
    ]

    for track in circuits:
        for i in range(len(track) - 1):
            draw.line([track[i], track[i+1]], fill=cyan_bright, width=2)
        for pt in track:
            draw.ellipse([(pt[0] - 3, pt[1] - 3), (pt[0] + 3, pt[1] + 3)], fill=white_core)
            draw.ellipse([(pt[0] - 5, pt[1] - 5), (pt[0] + 5, pt[1] + 5)], outline=cyan_glow, width=1)

    # 4. Sunglasses HUD Reticle (Calculated precisely to the glasses area)
    # Glasses are at Y ~ 115-135, X ~ W*0.42 to W*0.62
    gx1, gy1 = int(W*0.42), 112
    gx2, gy2 = int(W*0.62), 138
    draw.arc([(gx1, gy1), (int((gx1+gx2)/2), gy2)], start=0, end=180, fill=cyan_bright, width=2)
    draw.arc([(int((gx1+gx2)/2), gy1), (gx2, gy2)], start=0, end=180, fill=cyan_bright, width=2)
    # Target reticle
    ret_x, ret_y = gx2 + 15, int((gy1+gy2)/2)
    draw.ellipse([(ret_x - 8, ret_y - 8), (ret_x + 8, ret_y + 8)], outline=cyan_bright, width=1)
    draw.line([(ret_x - 12, ret_y), (ret_x + 12, ret_y)], fill=cyan_bright, width=1)
    draw.line([(ret_x, ret_y - 12), (ret_x, ret_y + 12)], fill=cyan_bright, width=1)

    # 5. Glowing bloom composite
    glow = overlay.filter(ImageFilter.GaussianBlur(radius=5))
    final_overlay = Image.alpha_composite(glow, overlay)
    final_overlay.save("Human/robotic/cyber_circuits_overlay.png", format="PNG")
    print(f"[OK] Saved precise cyber_circuits_overlay.png to {W}x{H}")

    # Generate composite preview
    preview = Image.alpha_composite(cropped_human, final_overlay)
    preview.save("Human/robotic/hologram_preview.png", format="PNG")
    print(f"[OK] Saved updated hologram_preview.png ({W}x{H})")

if __name__ == "__main__":
    process_cropped_avatar()
