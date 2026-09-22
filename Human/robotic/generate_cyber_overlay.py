"""
Generate high-resolution Cybernetic Circuit Overlay and Dot-Matrix Holographic Accents.
Inspired by robotic.jpeg:
- Glowing cyan (#00E5FF) and electric blue (#0088FF) circuit tracks
- Circuit bus junctions with glowing solder/micro dots
- Holographic scanlines and telemetry brackets
- Accents along suit edges and sunglasses
- Completely transparent where face and natural features reside so they remain 100% untouched.
"""

import os
import math
from PIL import Image, ImageDraw, ImageFilter

def create_cyber_overlay(width=1256, height=1588):
    # Base transparent RGBA canvas
    base = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)

    # Cyan palette
    cyan_bright = (0, 229, 255, 230)
    cyan_glow = (0, 180, 255, 140)
    cyan_faint = (0, 229, 255, 60)
    white_core = (220, 250, 255, 255)

    # 1. Futuristic HUD Brackets and Corner Telemetry Framing the figure
    margin = 40
    bracket_len = 120
    lw = 3

    # Top-Left Bracket
    draw.line([(margin, margin + bracket_len), (margin, margin), (margin + bracket_len, margin)], fill=cyan_bright, width=lw)
    # Top-Right Bracket
    draw.line([(width - margin - bracket_len, margin), (width - margin, margin), (width - margin, margin + bracket_len)], fill=cyan_bright, width=lw)
    # Bottom-Left Bracket
    draw.line([(margin, height - margin - bracket_len), (margin, height - margin), (margin + bracket_len, height - margin)], fill=cyan_bright, width=lw)
    # Bottom-Right Bracket
    draw.line([(width - margin - bracket_len, height - margin), (width - margin, height - margin), (width - margin, height - margin - bracket_len)], fill=cyan_bright, width=lw)

    # Small corner dots
    for cx, cy in [(margin + 10, margin + 10), (width - margin - 10, margin + 10), (margin + 10, height - margin - 10), (width - margin - 10, height - margin - 10)]:
        draw.ellipse([(cx - 4, cy - 4), (cx + 4, cy + 4)], fill=white_core)

    # 2. Tech Data Marks & Scale Rulers along sides
    for y in range(margin + bracket_len + 30, height - margin - bracket_len, 45):
        draw.line([(margin + 5, y), (margin + 20, y)], fill=cyan_faint, width=2)
        draw.line([(width - margin - 20, y), (width - margin - 5, y)], fill=cyan_faint, width=2)

    # 3. Holographic Dot Matrix Grid in outer boundary (subtle cyber aura)
    dot_step = 60
    for gx in range(margin + 50, width - margin - 50, dot_step):
        for gy in range(margin + 50, height - margin - 50, dot_step):
            # Keep center clear for the human body
            rel_x = abs(gx - width / 2) / (width / 2)
            rel_y = gy / height
            if rel_x > 0.42 or rel_y < 0.08 or rel_y > 0.92:
                draw.ellipse([(gx - 1.5, gy - 1.5), (gx + 1.5, gy + 1.5)], fill=cyan_faint)

    # 4. Cybernetic Circuit Traces running along Suit & Shoulders (calculated to human proportions)
    # Head/Sunglasses center approx: x=650, y=240
    # Left Shoulder approx: x=480, y=360; Right Shoulder approx: x=820, y=360
    # Chest center: x=650, y=550; Tie center: x=660, y=450-750
    # Left Arm: x=380, y=550-900; Right Arm: x=900, y=550-900
    # Waist: x=650, y=900; Legs: x=580, y=1000-1450 & x=730, y=1000-1450

    circuits = [
        # Left shoulder & arm circuit branch
        [(450, 360), (410, 420), (410, 600), (370, 680), (370, 780)],
        [(480, 380), (440, 440), (440, 560)],
        # Right shoulder & arm circuit branch
        [(840, 360), (880, 420), (880, 600), (920, 680), (920, 780)],
        [(810, 380), (850, 440), (850, 560)],
        # Lapel accent lines
        [(580, 420), (560, 520), (580, 640), (610, 720)],
        [(710, 420), (730, 520), (710, 640), (680, 720)],
        # Waist / Beltline cyber bus
        [(520, 880), (650, 885), (780, 880)],
        # Left leg outer bus
        [(520, 960), (510, 1080), (530, 1250), (550, 1400)],
        # Right leg outer bus
        [(770, 960), (780, 1080), (760, 1250), (740, 1400)],
        # Shoes base cyber contact pad
        [(510, 1480), (570, 1500), (640, 1490)],
        [(670, 1490), (730, 1500), (790, 1480)]
    ]

    for track in circuits:
        # Draw circuit line
        for i in range(len(track) - 1):
            draw.line([track[i], track[i+1]], fill=cyan_bright, width=3)
        # Draw node terminals / solder micro dots
        for pt in track:
            draw.ellipse([(pt[0] - 4, pt[1] - 4), (pt[0] + 4, pt[1] + 4)], fill=white_core)
            draw.ellipse([(pt[0] - 7, pt[1] - 7), (pt[0] + 7, pt[1] + 7)], outline=cyan_glow, width=1)

    # 5. Sunglasses Subtle Cyber-HUD Tint (Thin glowing digital line on lens rims)
    # Glasses approx: x=600 to 715, y=215 to 255
    draw.arc([(595, 218), (655, 252)], start=0, end=180, fill=cyan_bright, width=2)
    draw.arc([(655, 218), (715, 252)], start=0, end=180, fill=cyan_bright, width=2)
    draw.line([(645, 226), (665, 226)], fill=cyan_bright, width=2)
    # Tiny HUD target reticle next to sunglasses
    draw.ellipse([(735, 225), (755, 245)], outline=cyan_bright, width=1)
    draw.line([(745, 220), (745, 250)], fill=cyan_bright, width=1)
    draw.line([(730, 235), (760, 235)], fill=cyan_bright, width=1)

    # 6. Create glowing bloom effect
    glow_layer = base.filter(ImageFilter.GaussianBlur(radius=6))
    
    # Composite glow behind crisp circuits
    final_img = Image.alpha_composite(glow_layer, base)

    here = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(here, "cyber_circuits_overlay.png")
    final_img.save(out_path, format="PNG")
    print(f"[SUCCESS] Saved cybernetic overlay: {out_path} ({width}x{height})")

if __name__ == "__main__":
    create_cyber_overlay()
