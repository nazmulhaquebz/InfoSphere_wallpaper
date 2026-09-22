"""
Prepare transparent cutout of human.jpeg using rembg.
Preserves 100% of the original photo pixels (face, sunglasses, suit, shoes).
Only background (trees, walls, pavers) is converted to transparent alpha.
"""

import os
import sys
import time
from PIL import Image

def process():
    try:
        from rembg import remove, new_session
    except ImportError:
        print("[ERR] rembg not installed yet.", flush=True)
        sys.exit(1)

    here = os.path.dirname(os.path.abspath(__file__))
    in_file = os.path.join(here, "human.jpeg")
    out_file = os.path.join(here, "human_cutout.png")

    if not os.path.exists(in_file):
        print(f"[ERR] Input file {in_file} does not exist.", flush=True)
        sys.exit(1)

    print(f"[INFO] Reading {in_file}...", flush=True)
    img = Image.open(in_file).convert("RGBA")
    print(f"[INFO] Processing background removal with u2netp (fast portable model)...", flush=True)
    t0 = time.time()
    session = new_session("u2netp")
    cutout = remove(img, session=session)
    elapsed = time.time() - t0
    print(f"[INFO] Background removed in {elapsed:.2f}s", flush=True)

    print(f"[INFO] Saving transparent cutout to {out_file}...", flush=True)
    cutout.save(out_file, format="PNG")
    print(f"[SUCCESS] Saved {out_file} ({cutout.size}, mode={cutout.mode})", flush=True)

if __name__ == "__main__":
    process()
