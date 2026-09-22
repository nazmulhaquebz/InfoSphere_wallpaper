"""
InfoSphere Operator Photo & Cyber Avatar Customizer.
Allows any user to replace the avatar photo with their own custom picture:

Usage:
    python Human/update_operator_photo.py "C:/path/to/my_photo.jpg"
    python Human/update_operator_photo.py
    (If run without arguments, looks for Human/human.jpeg or Human/human.png)

Pipeline:
1. Validates input image.
2. Performs 100% face-preserved background removal with u2netp.
3. Automatically crops to centered human bounding box.
4. Generates high-density Orbit-Dot Point Cloud & 3D Orbital Rings overlay.
5. Saves composite preview and updates the live wallpaper immediately!
"""

import os
import sys
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROBOTIC_DIR = os.path.join(HERE, "robotic")

def update_avatar(input_image_path=None):
    if not input_image_path:
        # Default lookups
        candidates = [
            os.path.join(ROBOTIC_DIR, "human.jpeg"),
            os.path.join(ROBOTIC_DIR, "human.jpg"),
            os.path.join(ROBOTIC_DIR, "human.png"),
            os.path.join(HERE, "human.jpeg"),
            os.path.join(HERE, "human.jpg"),
            os.path.join(HERE, "human.png"),
            os.path.join(HERE, "operator.jpg"),
            os.path.join(HERE, "operator.png")
        ]
        for c in candidates:
            if os.path.exists(c):
                input_image_path = c
                break

    if not input_image_path or not os.path.exists(input_image_path):
        print(f"[ERR] No valid input image found. Please provide path:")
        print(f"      python Human/update_operator_photo.py \"path/to/your_photo.jpg\"")
        sys.exit(1)

    print("=" * 65)
    print("  INFOSPHERE · OPERATOR CYBER AVATAR GENERATOR")
    print("=" * 65)
    print(f"[*] Input Photo: {input_image_path}")

    # Copy to Human/robotic/human.jpeg as canonical source
    canonical_human = os.path.join(ROBOTIC_DIR, "human.jpeg")
    if os.path.abspath(input_image_path) != os.path.abspath(canonical_human):
        shutil.copy2(input_image_path, canonical_human)
        print(f"[OK] Stored as {canonical_human}")

    # 1. Background removal
    print("[*] Step 1/3: Extracting clean transparent silhouette (100% Face Preserved)...")
    cmd1 = [sys.executable, os.path.join(ROBOTIC_DIR, "prepare_cutout.py")]
    res1 = subprocess.run(cmd1)
    if res1.returncode != 0:
        print("[ERR] Background removal failed.")
        sys.exit(1)

    # 2. Crop & Map
    print("[*] Step 2/3: Calibrating bounding box and centering...")
    cmd2 = [sys.executable, os.path.join(ROBOTIC_DIR, "crop_and_map_circuits.py")]
    res2 = subprocess.run(cmd2)
    if res2.returncode != 0:
        print("[ERR] Cropping failed.")
        sys.exit(1)

    # 3. Generate 3D Orbit-Dots & Orbital Rings
    print("[*] Step 3/3: Generating 3D Orbit-Dot Matrix & Orbital Defense Rings...")
    cmd3 = [sys.executable, os.path.join(ROBOTIC_DIR, "generate_orbit_dots.py")]
    res3 = subprocess.run(cmd3)
    if res3.returncode != 0:
        print("[ERR] Orbit-Dot generation failed.")
        sys.exit(1)

    print("=" * 65)
    print("  [SUCCESS] New Cybernetic Hologram Avatar is ready and live!")
    print(f"  Preview available at: {os.path.join(ROBOTIC_DIR, 'hologram_preview.png')}")
    print("=" * 65)

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    update_avatar(arg)
