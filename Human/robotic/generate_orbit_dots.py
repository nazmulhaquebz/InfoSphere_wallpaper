"""
Generate High-Density Orbit-Dot Matrix and 3D Orbital Rings Overlay.
Directly inspired by the 3D Cyber Defense Globe:
- Dense point-cloud matrix dots over the entire human silhouette
- 3D elliptical orbital rings with traveling satellite tracer nodes
- Edge-detected neon circuit contours
- Glowing sunglasses HUD targeting interface
- 100% preserves original face and body through transparent blending
"""

import os
import math
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

def generate_orbit_dots():
    here = os.path.dirname(os.path.abspath(__file__))
    human_path = os.path.join(here, "human_cutout.png")
    if not os.path.exists(human_path):
        print(f"[ERR] {human_path} not found.")
        return

    human_img = Image.open(human_path).convert("RGBA")
    W, H = human_img.size
    arr = np.array(human_img)
    alpha = arr[:, :, 3]

    # Create transparent canvas for orbit-dot overlay
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    cyan_bright = (0, 229, 255, 245)
    cyan_mid = (0, 180, 255, 180)
    cyan_faint = (0, 229, 255, 80)
    white_core = (240, 255, 255, 255)

    # 1. High-Density Point-Cloud Matrix Dots across the Body
    # Step size: 12px grid
    step = 12
    for y in range(step, H - step, step):
        for x in range(step, W - step, step):
            a_val = alpha[y, x]
            if a_val > 40:
                # Dot size and brightness based on density and position
                # Keep face region slightly subtle so natural expression shines through
                is_face_region = (H * 0.08 < y < H * 0.18) and (W * 0.38 < x < W * 0.62)
                
                if is_face_region:
                    # Subtle nano-dots over face
                    r = 1.0
                    col = (0, 229, 255, 110)
                else:
                    # Point cloud matrix dots over suit, arms, legs
                    # Check if near edge for brighter contour dot
                    is_edge = False
                    for dx, dy in [(-step, 0), (step, 0), (0, -step), (0, step)]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < W and 0 <= ny < H:
                            if alpha[ny, nx] < 30:
                                is_edge = True
                                break
                    
                    if is_edge:
                        r = 2.0
                        col = white_core
                    else:
                        r = 1.5
                        col = cyan_bright if (x + y) % (step * 2) == 0 else cyan_mid

                draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=col)

    # 2. 3D Orbital Defense Rings circling the avatar (matching top-right globe)
    # Ring 1: Tilted around chest / upper torso (Y ~ 460)
    ring1_cx, ring1_cy = int(W * 0.50), int(H * 0.32)
    rx1, ry1 = int(W * 0.52), int(H * 0.08)
    tilt1 = -18 # degrees

    # Ring 2: Tilted around waist / hips (Y ~ 740)
    ring2_cx, ring2_cy = int(W * 0.50), int(H * 0.50)
    rx2, ry2 = int(W * 0.54), int(H * 0.09)
    tilt2 = 15 # degrees

    # Ring 3: Tilted around knees (Y ~ 1080)
    ring3_cx, ring3_cy = int(W * 0.50), int(H * 0.72)
    rx3, ry3 = int(W * 0.48), int(H * 0.07)
    tilt3 = -10 # degrees

    def draw_tilted_orbit_ring(cx, cy, rx, ry, angle_deg, draw_beads=True):
        rad = math.radians(angle_deg)
        cos_t, sin_t = math.cos(rad), math.sin(rad)
        points = []
        num_pts = 72
        for i in range(num_pts):
            theta = (i / num_pts) * 2 * math.pi
            # Parametric ellipse
            ex = rx * math.cos(theta)
            ey = ry * math.sin(theta)
            # Rotate by tilt angle
            rot_x = cx + ex * cos_t - ey * sin_t
            rot_y = cy + ex * sin_t + ey * cos_t
            points.append((rot_x, rot_y))

        # Draw orbit path with dashed/dotted look
        for i in range(len(points)):
            p1 = points[i]
            p2 = points[(i + 1) % len(points)]
            # Draw segment
            if i % 3 != 0:
                draw.line([p1, p2], fill=cyan_bright, width=2)
            # Draw orbital tracer beads (satellite dots)
            if draw_beads and i % 9 == 0:
                draw.ellipse([(p1[0] - 4, p1[1] - 4), (p1[0] + 4, p1[1] + 4)], fill=white_core)
                draw.ellipse([(p1[0] - 6, p1[1] - 6), (p1[0] + 6, p1[1] + 6)], outline=cyan_mid, width=1)

    draw_tilted_orbit_ring(ring1_cx, ring1_cy, rx1, ry1, tilt1, draw_beads=True)
    draw_tilted_orbit_ring(ring2_cx, ring2_cy, rx2, ry2, tilt2, draw_beads=True)
    draw_tilted_orbit_ring(ring3_cx, ring3_cy, rx3, ry3, tilt3, draw_beads=True)

    # 3. Sunglasses HUD Targeting Crosshair & Arc
    gx1, gy1 = int(W * 0.42), int(H * 0.080)
    gx2, gy2 = int(W * 0.62), int(H * 0.098)
    draw.arc([(gx1, gy1), (int((gx1+gx2)/2), gy2)], start=0, end=180, fill=cyan_bright, width=2)
    draw.arc([(int((gx1+gx2)/2), gy1), (gx2, gy2)], start=0, end=180, fill=cyan_bright, width=2)
    # HUD Target reticle beside glasses
    ret_x, ret_y = gx2 + 15, int((gy1+gy2)/2)
    draw.ellipse([(ret_x - 7, ret_y - 7), (ret_x + 7, ret_y + 7)], outline=cyan_bright, width=1)
    draw.line([(ret_x - 10, ret_y), (ret_x + 10, ret_y)], fill=cyan_bright, width=1)
    draw.line([(ret_x, ret_y - 10), (ret_x, ret_y + 10)], fill=cyan_bright, width=1)

    # 4. Corner Tactical Brackets
    b_len = 40
    m = 10
    draw.line([(m, m + b_len), (m, m), (m + b_len, m)], fill=cyan_bright, width=2)
    draw.line([(W - m - b_len, m), (W - m, m), (W - m, m + b_len)], fill=cyan_bright, width=2)
    draw.line([(m, H - m - b_len), (m, H - m), (m + b_len, H - m)], fill=cyan_bright, width=2)
    draw.line([(W - m - b_len, H - m), (W - m, H - m), (W - m, H - m - b_len)], fill=cyan_bright, width=2)

    # 5. Composite Bloom / Glow Layer
    glow = overlay.filter(ImageFilter.GaussianBlur(radius=5))
    final_overlay = Image.alpha_composite(glow, overlay)

    out_overlay_path = os.path.join(here, "cyber_circuits_overlay.png")
    final_overlay.save(out_overlay_path, format="PNG")
    print(f"[SUCCESS] Saved enhanced Orbit-Dot overlay to {out_overlay_path}")

    # Generate composite preview for review
    preview = Image.alpha_composite(human_img, final_overlay)
    preview_path = os.path.join(here, "hologram_preview.png")
    preview.save(preview_path, format="PNG")
    print(f"[SUCCESS] Saved updated hologram preview to {preview_path}")

if __name__ == "__main__":
    generate_orbit_dots()
