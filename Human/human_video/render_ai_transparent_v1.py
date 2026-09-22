"""
Ultra High-Definition 4K-Grade AI Background Removal & Transparent WebM Synthesizer
INFOSPHERE TACTICAL LIVE ENGINE · Human_video_1 Processing
Target: Human_video_1.mp4 → human_video_1_transparent.webm (VP9 yuva420p CRF 15)
"""

import os
import sys
import time
import shutil
import subprocess
import concurrent.futures
from PIL import Image
import numpy as np
import imageio_ffmpeg
from rembg import remove, new_session

def run():
    t_start = time.time()
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    here = os.path.dirname(os.path.abspath(__file__))
    in_video  = os.path.join(here, "Human_video_1.mp4")
    out_video = os.path.join(here, "human_video_1_transparent.webm")
    temp_dir  = os.path.join(here, "_temp_render_v1")

    if not os.path.exists(in_video):
        print(f"[ERR] Input video not found: {in_video}", flush=True)
        sys.exit(1)

    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    frames_in_dir  = os.path.join(temp_dir, "in")
    frames_out_dir = os.path.join(temp_dir, "out")
    os.makedirs(frames_in_dir, exist_ok=True)
    os.makedirs(frames_out_dir, exist_ok=True)

    print("=" * 70, flush=True)
    print("  INFOSPHERE · Human_video_1 · 4K AI MATTING PIPELINE", flush=True)
    print("=" * 70, flush=True)
    print(f"[*] Input video:  {in_video}", flush=True)
    print(f"[*] Output video: {out_video}", flush=True)
    print(f"[*] Architecture: Full u2net (176MB High-Precision)", flush=True)

    # 1. Extract frames at native 24 FPS
    print("[1/4] Extracting native 1080x1920 frames at 24 FPS...", flush=True)
    subprocess.run([
        exe, '-y', '-i', in_video, '-r', '24',
        os.path.join(frames_in_dir, "f_%04d.png")
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Extract stereo audio track
    audio_path = os.path.join(temp_dir, "audio.wav")
    print("[1/4] Extracting speech audio track...", flush=True)
    subprocess.run([
        exe, '-y', '-i', in_video,
        '-vn', '-acodec', 'pcm_s16le', audio_path
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    frame_files  = sorted([f for f in os.listdir(frames_in_dir) if f.endswith(".png")])
    total_frames = len(frame_files)
    print(f"[*] Total frames extracted: {total_frames}", flush=True)

    # 2. Parallel AI background removal with full u2net
    print("[2/4] Initializing high-precision u2net neural matting session...", flush=True)
    session = new_session("u2net")

    def process_frame(filename):
        in_p  = os.path.join(frames_in_dir, filename)
        out_p = os.path.join(frames_out_dir, filename)
        with Image.open(in_p) as raw_im:
            im = raw_im.convert("RGB")
        cutout = remove(im, session=session)
        arr    = np.array(cutout).astype(np.float32)
        alpha  = arr[:, :, 3]
        mask   = alpha > 0
        if np.any(mask):
            rgb     = arr[:, :, :3]
            boosted = np.clip(rgb * 1.18, 0, 255)
            arr[:, :, :3] = np.where(mask[:, :, None], boosted, 0)
        Image.fromarray(arr.astype(np.uint8)).save(out_p, format="PNG")
        return filename

    print(f"[3/4] Segmenting {total_frames} frames with u2net (4 worker threads)...", flush=True)
    t0 = time.time()
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for _ in executor.map(process_frame, frame_files):
            completed += 1
            if completed % 20 == 0 or completed == total_frames:
                pct      = (completed / total_frames) * 100
                elapsed  = time.time() - t0
                fps_rate = completed / max(0.1, elapsed)
                rem_sec  = (total_frames - completed) / max(0.1, fps_rate)
                print(f"    - Segmented {completed}/{total_frames} ({pct:.1f}%) | {fps_rate:.2f} fps | ~{rem_sec:.0f}s remaining", flush=True)

    elapsed_ai = time.time() - t0
    print(f"[*] Segmentation done in {elapsed_ai:.2f}s ({total_frames/elapsed_ai:.2f} fps avg)", flush=True)

    # 3. Encode: Crystal-clear VP9 WebM with native yuva420p alpha + Opus audio
    print("[4/4] Encoding VP9 WebM (CRF 15, yuva420p, Opus 160k)...", flush=True)
    subprocess.run([
        exe, '-y',
        '-framerate', '24',
        '-i', os.path.join(frames_out_dir, "f_%04d.png"),
        '-i', audio_path,
        '-c:v', 'libvpx-vp9',
        '-pix_fmt', 'yuva420p',
        '-auto-alt-ref', '0',
        '-cpu-used', '3',
        '-b:v', '0', '-crf', '15',
        '-c:a', 'libopus', '-b:a', '160k',
        out_video
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 4. Cleanup
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    total_time = time.time() - t_start
    size_mb    = os.path.getsize(out_video) / (1024 * 1024)
    print("=" * 70, flush=True)
    print(f"[SUCCESS] {out_video}", flush=True)
    print(f"[*] Size: {size_mb:.2f} MB | 1080x1920 CRF 15 | Time: {total_time:.2f}s", flush=True)
    print("=" * 70, flush=True)

if __name__ == "__main__":
    run()
