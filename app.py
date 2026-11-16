import os, re, time, shutil, zipfile, subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
import yt_dlp
from yt_dlp.utils import download_range_func

st.set_page_config(page_title="PeakCut Studio", page_icon="✂️", layout="centered")

# PeakCut Clean Dark UI Palette (No shadows, crisp borders, instant hover)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;700;800&display=swap');
html, body, [class*="css"] {font-family: 'Poppins', sans-serif;}
.stApp {background-color: #09090b; color: #f4f4f5;}
.peak-box {
    background-color: #121215;
    border: 1px solid #27272a;
    border-radius: 10px;
    padding: 20px;
    text-align: center;
    margin-bottom: 18px;
}
.peak-title {font-size: 26px; font-weight: 800; color: #fafafa; margin: 0;}
.peak-sub {color: #a1a1aa; font-size: 13px; margin-top: 4px;}
.stButton>button {
    width: 100%;
    background-color: #ef4444;
    color: #ffffff;
    font-weight: 700;
    border: none;
    border-radius: 8px;
    padding: 12px;
    font-size: 15px;
}
.stButton>button:hover {background-color: #dc2626; color: #ffffff;}
</style>
<div class="peak-box">
  <div class="peak-title">✂️ PEAKCUT STUDIO (1080p FHD)</div>
  <div class="peak-sub">Exact PeakCut Section-Fetcher • 4x Concurrent Fragments • AVC1 1080p</div>
</div>
""", unsafe_allow_html=True)

OUTPUT_DIR = Path("/tmp/peakcut_jobs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class _Quiet:
    def debug(self, m): pass
    def info(self, m): pass
    def warning(self, m): pass
    def error(self, m): pass

# Exact PeakCut _ydl setup from studio/media.py[span_1](start_span)[span_1](end_span)
def _ydl(opts, cookie_file=None):
    base = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "logger": _Quiet(),
        "extract_flat": "in_playlist",
        "playlistend": 1,
        "socket_timeout": 20,
        "concurrent_fragment_downloads": 4,
        "extractor_args": {"youtube": {"player_client": ["ios", "android_vr", "tv_embedded"]}},
    }
    if cookie_file and os.path.exists(cookie_file):
        base["cookiefile"] = cookie_file
    base.update(opts)
    return yt_dlp.YoutubeDL(base)

# Exact PeakCut _video_format from studio/media.py[span_2](start_span)[span_2](end_span)
def _video_format(height=1080):
    return f"bv*[height<={height}][vcodec^=avc1]+ba[ext=m4a]/bv*[height<={height}]+ba/b[height<={height}]/b"

def _biggest(job_dir: Path, stem: str) -> Path:
    files = sorted((p for p in job_dir.glob(stem + ".*") if p.suffix not in (".part", ".ytdl")),
                   key=lambda p: p.stat().st_size, reverse=True)
    if not files:
        raise RuntimeError("No file produced")
    return files[0]

def get_video_info(url: str, cookie_file=None) -> dict:
    with _ydl({}, cookie_file) as ydl:
        i = ydl.extract_info(url, download=False)
    return {
        "title": i.get("title") or "Video",
        "duration": float(i.get("duration") or 300),
    }

# Exact PeakCut download_section: Downloads ONLY the clip stretch instead of the whole video[span_3](start_span)[span_3](end_span)
def download_section(url: str, out_dir: Path, stem: str, start: float, end: float, height=1080, cookie_file=None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": _video_format(height),
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / (stem + ".%(ext)s")),
        "download_ranges": download_range_func(None, [(max(0.0, start), end)]),
    }
    with _ydl(opts, cookie_file) as ydl:
        ydl.download([url])
    return _biggest(out_dir, stem)

def probe_duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 300.0

def render_peakcut_clip(i, raw_clip_path: Path, res_choice: str, frame_mode: str, style_mode: str, ss_offset: float = 0.0, dur: float = 35.0) -> Path:
    is_fhd = "1080" in res_choice
    W, H = (1080, 1920) if is_fhd else (720, 1280)
    out_mp4 = OUTPUT_DIR / f"PeakCut_Short_{i+1}_{W}x{H}.mp4"
    out_mp4.unlink(missing_ok=True)

    if "Hype" in style_mode:
        fx = ",unsharp=5:5:0.8:3:3:0.0,eq=contrast=1.06:saturation=1.15"
    elif "Bounce" in style_mode:
        fx = ",unsharp=3:3:0.65:3:3:0.0,eq=contrast=1.03:saturation=1.08"
    else:
        fx = ",unsharp=3:3:0.5:3:3:0.0"

    if "Square (1:1)" in frame_mode:
        vf = f"scale={W}:{W}:flags=bicubic:force_original_aspect_ratio=increase,crop={W}:{W}{fx},pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p"
    elif "Blurred BG" in frame_mode:
        vf = f"split[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=20:10[b];[fg]scale={W}:{W}:force_original_aspect_ratio=increase,crop={W}:{W}{fx}[f];[b][f]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p"
    else:
        vf = f"scale={W}:{H}:flags=bicubic:force_original_aspect_ratio=increase,crop={W}:{H}{fx},setsar=1,format=yuv420p"

    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if ss_offset > 0:
        cmd += ["-ss", f"{ss_offset:.2f}"]
    cmd += [
        "-i", str(raw_clip_path),
        "-t", f"{dur:.2f}",
        "-vf", vf,
        "-r", "30",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-crf", "18", "-maxrate", "8000k", "-bufsize", "16000k",
        "-c:a", "aac", "-b:a", "160k", "-ac", "2", "-movflags", "+faststart",
        str(out_mp4)
    ]
    subprocess.run(cmd, capture_output=True)
    return out_mp4 if out_mp4.is_file() and out_mp4.stat().st_size > 10000 else None

# ---------------- UI ----------------
source_mode = st.radio("📥 Video Source:", ["🔗 YouTube / Twitch / Kick Link", "📱 Upload Video File (Guaranteed No Bot Check)"], horizontal=True)

url_input = ""
up_file = None
cookie_path = None

if "Link" in source_mode:
    url_input = st.text_input("🔗 Paste Video URL (YouTube, Twitch, Kick):", placeholder="https://youtu.be/...")
    with st.expander("🔑 Optional: Paste Cookies (If YouTube shows 'confirm you're not a bot')"):
        ck_text = st.text_area("Paste Netscape cookies.txt content here:", height=75)
        if ck_text.strip():
            cookie_path = str(OUTPUT_DIR / "cookies.txt")
            Path(cookie_path).write_text(ck_text, encoding="utf-8")
else:
    up_file = st.file_uploader("📱 Select Video File (MP4, MKV, MOV, WEBM):", type=["mp4", "mkv", "mov", "webm"])

c1, c2, c3 = st.columns(3)
with c1:
    clip_count = st.selectbox("🎞️ Clips:", [5, 10, 15, 20], index=0)
with c2:
    res_choice = st.selectbox("💎 Quality:", ["1080p FHD ⭐", "720p HD"], index=0)
with c3:
    style_mode = st.selectbox("🎨 Style:", ["Clean", "Bounce", "Hype"], index=0)

frame_mode = st.radio("📐 Layout:", ["Square (1:1) in 9:16 ⭐", "Blurred BG (9:16)", "Full Vertical (9:16)"], horizontal=True)

if st.button("🚀 MAKE PEAKCUT SHORTS NOW"):
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if cookie_path and ck_text.strip():
        Path(cookie_path).write_text(ck_text, encoding="utf-8")

    t0 = time.time()
    ready_files = []
    target_h = 1080 if "1080" in res_choice else 720

    if up_file is not None:
        src_path = OUTPUT_DIR / "uploaded.mp4"
        with st.spinner("📥 Saving uploaded video..."):
            src_path.write_bytes(up_file.getbuffer())
            dur = probe_duration(src_path)

        clip_len = 35.0 if dur >= 120 else max(12.0, dur / max(2, clip_count))
        step = max(8.0, max(clip_len, dur - clip_len - 4) / max(1, clip_count))
        prog = st.progress(0, text="✂️ Rendering 1080p Clips...")

        for i in range(clip_count):
            st_t = min(3.0 + i * step, max(0.0, dur - clip_len))
            prog.progress(i / clip_count, text=f"🎬 Rendering Short #{i+1}/{clip_count}...")
            out = render_peakcut_clip(i, src_path, res_choice, frame_mode, style_mode, ss_offset=st_t, dur=clip_len)
            if out: ready_files.append(out)
            prog.progress((i + 1) / clip_count, text=f"✅ Short #{i+1} Done!")

    elif url_input.strip():
        try:
            with st.spinner("🔍 Probing link metadata (PeakCut media.info)..."):
                meta = get_video_info(url_input.strip(), cookie_path)
                dur = meta["duration"]

            clip_len = 35.0 if dur >= 120 else max(12.0, dur / max(2, clip_count))
            step = max(8.0, max(clip_len, dur - clip_len - 4) / max(1, clip_count))
            prog = st.progress(0, text=f"⚡ Fetching & Rendering {clip_count} Sections...")

            for i in range(clip_count):
                st_t = min(5.0 + i * step, max(0.0, dur - clip_len))
                en_t = st_t + clip_len
                prog.progress(i / clip_count, text=f"⚡ Downloading & Cutting Short #{i+1}/{clip_count} ({int(st_t)}s - {int(en_t)}s)...")
                raw_sec = download_section(url_input.strip(), OUTPUT_DIR, f"sec_{i}", st_t, en_t, height=target_h, cookie_file=cookie_path)
                out = render_peakcut_clip(i, raw_sec, res_choice, frame_mode, style_mode, ss_offset=0.0, dur=clip_len)
                if out: ready_files.append(out)
                prog.progress((i + 1) / clip_count, text=f"✅ Short #{i+1} Ready!")
        except Exception as e:
            st.error(f"❌ YouTube refused this cloud server ('confirm you're not a bot'). PeakCut's solution: Switch to '📱 Upload Video File' above or use a Twitch/Kick link! ({str(e)[:120]})")
    else:
        st.error("❌ Link daalein ya Video File upload karein!")

    if ready_files:
        zip_path = OUTPUT_DIR / "PeakCut_All_Shorts.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
            for f in ready_files:
                z.write(f, f.name)
        st.session_state["shorts"] = [str(f) for f in ready_files]
        st.session_state["zip_path"] = str(zip_path)
        st.session_state["t_sec"] = int(time.time() - t0)

if "shorts" in st.session_state and st.session_state["shorts"]:
    st.success(f"🎉 {len(st.session_state['shorts'])} True 1080p Shorts Ready in {st.session_state.get('t_sec', 20)}s!")
    if "zip_path" in st.session_state and os.path.exists(st.session_state["zip_path"]):
        with open(st.session_state["zip_path"], "rb") as zb:
            st.download_button("📦 DOWNLOAD ALL SHORTS (.ZIP - INSTANT)", data=zb, file_name="PeakCut_Shorts.zip", mime="application/zip", use_container_width=True)

    st.markdown("---")
    for idx, fpath in enumerate(st.session_state["shorts"]):
        fsize_mb = round(os.path.getsize(fpath) / (1024 * 1024), 1)
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"**🎬 PeakCut Short #{idx+1}** (`{fsize_mb} MB`)")
        with c2:
            with open(fpath, "rb") as file_bytes:
                st.download_button(f"📥 Save #{idx+1}", data=file_bytes, file_name=os.path.basename(fpath), mime="video/mp4", key=f"dl_{idx}")
        with st.expander(f"▶️ Preview Short #{idx+1}"):
            st.video(fpath)
                
