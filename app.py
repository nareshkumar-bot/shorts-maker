import os, re, time, json, shutil, zipfile, subprocess
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="Nexus Clipping Studio", page_icon="✨", layout="centered")

# Nexus Clipping Futuristic Dark UI
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;700;800&display=swap');
html, body, [class*="css"] {font-family: 'Plus Jakarta Sans', sans-serif;}
.stApp {background: radial-gradient(circle at 50% 0%, #0f172a 0%, #020617 100%); color: #f8fafc;}
.nexus-banner {
    background: linear-gradient(135deg, rgba(56, 189, 248, 0.1) 0%, rgba(147, 51, 234, 0.1) 100%);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    margin-bottom: 20px;
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
}
.nexus-badge {
    background: rgba(147, 51, 234, 0.2);
    color: #c084fc;
    padding: 4px 12px;
    border-radius: 99px;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}
.nexus-title {
    font-size: 28px;
    font-weight: 800;
    color: #ffffff;
    margin: 10px 0 4px 0;
    background: linear-gradient(90deg, #ffffff, #94a3b8, #c084fc);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.nexus-sub {color: #94a3b8; font-size: 13px; margin: 0;}
.stButton>button {
    width: 100%;
    background: linear-gradient(90deg, #6366f1 0%, #a855f7 100%);
    color: #ffffff;
    font-weight: 700;
    border: none;
    border-radius: 12px;
    padding: 14px;
    font-size: 15px;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
    transition: all 0.2s ease;
}
.stButton>button:hover {opacity: 0.9; transform: translateY(-1px);}
</style>

<div class="nexus-banner">
  <span class="nexus-badge">⚡ Nexus Engine v2.0</span>
  <div class="nexus-title">NEXUS CLIPPING STUDIO</div>
  <p class="nexus-sub">Step 1: Web Staging Buffer • Step 2: Auto-Smart 9:16 Shorts Renderer</p>
</div>
""", unsafe_allow_html=True)

WORK_DIR = Path("/tmp/nexus_clipping")
WORK_DIR.mkdir(parents=True, exist_ok=True)

def get_youtube_id(url: str):
    for p in [r"(?:v=|/)([0-9A-Za-z_-]{11}).*", r"youtu[.]be/([0-9A-Za-z_-]{11})", r"shorts/([0-9A-Za-z_-]{11})"]:
        m = re.search(p, url.strip())
        if m:
            return m.group(1)
    return None

def get_video_meta(path: Path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        v = (d.get("streams") or [{}])[0]
        dur = float((d.get("format") or {}).get("duration") or 300.0)
        return int(v.get("width") or 1280), int(v.get("height") or 720), dur
    except Exception:
        return 1280, 720, 300.0

def render_nexus_short(i: int, src_path: Path, st_t: float, dur: float, sw: int, sh: int, quality: str, layout: str) -> Path:
    is_fhd = "1080" in quality
    W, H = (1080, 1920) if is_fhd else (720, 1280)
    out_p = WORK_DIR / f"Nexus_Short_{i+1}_{W}x{H}.mp4"
    out_p.unlink(missing_ok=True)

    if "Blurred BG" in layout:
        fh = min(H, int(round(W * sh / max(1, sw) / 2)) * 2)
        vf = (
            f"[0:v]fps=30,split=2[a][b];"
            f"[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,"
            f"scale={W}:{H},eq=brightness=-0.14:saturation=1.15[bg];"
            f"[b]scale={W}:{fh}:force_original_aspect_ratio=increase,crop={W}:{fh},unsharp=3:3:0.6:3:3:0.0[fg];"
            f"[bg][fg]overlay=0:(H-h)/2,setsar=1[v]"
        )
    elif "Zoomed" in layout:
        fh = int(H * 0.52)
        vf = (
            f"[0:v]fps=30,split=2[a][b];"
            f"[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,"
            f"scale={W}:{H},eq=brightness=-0.14:saturation=1.15[bg];"
            f"[b]scale={W}:{fh}:force_original_aspect_ratio=increase,crop={W}:{fh},unsharp=3:3:0.6:3:3:0.0[fg];"
            f"[bg][fg]overlay=0:(H-h)/2,setsar=1[v]"
        )
    else:
        vf = f"[0:v]fps=30,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},unsharp=3:3:0.6:3:3:0.0,setsar=1[v]"

    cmd = [
        "ffmpeg", "-y", "-v", "error", "-ss", f"{st_t:.2f}", "-t", f"{dur:.2f}", "-i", str(src_path),
        "-filter_complex", vf, "-map", "[v]", "-map", "0:a:0?", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", str(out_p)
    ]
    subprocess.run(cmd, capture_output=True)
    return out_p if out_p.is_file() and out_p.stat().st_size > 10_000 else None

# ---------------- NEXUS STEP 1: STAGING BUFFER & RESOLUTION CHOOSE ----------------
st.markdown("### 📥 Step 1: Nexus Staging Fetcher")
input_mode = st.radio("Choose Input Method:", ["🔗 YouTube / Direct Link", "📱 Upload Local Video File"], horizontal=True)

video_file = None
source_label = ""

if "Link" in input_mode:
    nexus_url = st.text_input("Paste Video Link (Supports 360p up to 4K):", placeholder="https://youtu.be/...")
    res_pref = st.selectbox("🎯 Select Staging Resolution:", ["4K Ultra HD", "2K QHD", "1080p FHD ⭐", "720p HD", "360p Fast"])
    
    if nexus_url.strip():
        vid_id = get_youtube_id(nexus_url)
        if vid_id:
            st.info(f"✨ Video detected (ID: `{vid_id}`). Staging buffer ready for acquisition.")
            if st.button("📥 ACQUIRE VIDEO INTO NEXUS BUFFER"):
                with st.spinner("⚡ Fetching stream into website staging memory..."):
                    target_h = 2160 if "4K" in res_pref else (1440 if "2K" in res_pref else (1080 if "1080" in res_pref else 720))
                    staged_path = WORK_DIR / "staged_video.mp4"
                    staged_path.unlink(missing_ok=True)
                    
                    # High-speed yt-dlp pull into staging memory
                    cmd = [
                        "yt-dlp", "-4", "--no-playlist", "--no-warnings", "--geo-bypass",
                        "-f", f"bv*[height<={target_h}][vcodec^=avc1]+ba/b[height<={target_h}]/b",
                        "--merge-output-format", "mp4", "-o", str(staged_path), nexus_url.strip()
                    ]
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    if staged_path.is_file() and staged_path.stat().st_size > 100_000:
                        st.session_state["staged_video"] = str(staged_path)
                        st.success("🎉 Video successfully staged in Nexus memory! Proceed to Step 2 below.")
                    else:
                        # Fallback to general best format if avc1 restricted
                        cmd_fallback = [
                            "yt-dlp", "-4", "--no-playlist", "--no-warnings", "--geo-bypass",
                            "-f", "b/bv+ba", "--merge-output-format", "mp4", "-o", str(staged_path), nexus_url.strip()
                        ]
                        subprocess.run(cmd_fallback, capture_output=True)
                        if staged_path.is_file() and staged_path.stat().st_size > 100_000:
                            st.session_state["staged_video"] = str(staged_path)
                            st.success("🎉 Video successfully staged via fallback stream!")
                        else:
                            st.error("❌ Acquisition failed due to platform restriction. Use 'Upload Local Video File' tab below.")
        else:
            st.warning("⚠️ Valid YouTube link daalein.")
else:
    up_local = st.file_uploader("Upload video file directly into Nexus memory:", type=["mp4", "mkv", "mov", "webm"])
    if up_local is not None:
        staged_path = WORK_DIR / "staged_video.mp4"
        staged_path.write_bytes(up_local.getbuffer())
        st.session_state["staged_video"] = str(staged_path)
        st.success("📱 Local video loaded into Nexus buffer!")

# ---------------- NEXUS STEP 2: CLIPPING SETUP & SMART RENDERER ----------------
if "staged_video" in st.session_state and Path(st.session_state["staged_video"]).is_file():
    st.markdown("---")
    st.markdown("### ✂️ Step 2: Nexus Clipping Studio")
    
    st.video(st.session_state["staged_video"])
    
    c1, c2 = st.columns(2)
    with c1:
        clips_count = st.selectbox("🎞️ Number of Shorts to Cut:", [5, 10, 15, 20], index=0)
    with c2:
        output_res = st.selectbox("💎 Output Short Quality:", ["1080p FHD ⭐", "720p HD"], index=0)
        
    layout_style = st.radio("📐 Nexus Vertical Layout:", ["Blurred BG (Full Frame) ⭐", "Zoomed in + Blurred BG", "Full Screen (Center Crop)"], horizontal=True)
    
    if st.button("🚀 LAUNCH NEXUS SMART CLIPPING ENGINE"):
        staged_p = Path(st.session_state["staged_video"])
        sw, sh, dur = get_video_meta(staged_p)
        
        clip_len = 35.0 if dur >= 120 else max(12.0, dur / max(2, clips_count))
        step = max(8.0, max(clip_len, dur - clip_len - 4) / max(1, clips_count))
        
        prog_bar = st.progress(0.0, text="✨ Initializing Nexus AI Cutting Grid...")
        nexus_outputs = []
        
        for i in range(clips_count):
            st_time = min(3.0 + i * step, max(0.0, dur - clip_len))
            prog_bar.progress(i / clips_count, text=f"⚡ Processing Short #{i+1} of {clips_count}...")
            
            out_file = render_nexus_short(i, staged_p, st_time, clip_len, sw, sh, output_res, layout_style)
            if out_file:
                nexus_outputs.append(out_file)
            prog_bar.progress((i + 1) / clips_count, text=f"✅ Short #{i+1} Rendered!")
            
        if nexus_outputs:
            zip_nexus = WORK_DIR / "Nexus_Clipping_Shorts.zip"
            with zipfile.ZipFile(zip_nexus, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
                for fpath in nexus_outputs:
                    zf.write(fpath, fpath.name)
            
            st.session_state["nexus_zip"] = str(zip_nexus)
            st.session_state["nexus_files"] = [str(f) for f in nexus_outputs]
            prog_bar.empty()
            st.success(f"🎉 All {len(nexus_outputs)} Shorts successfully generated in Nexus memory!")

if "nexus_zip" in st.session_state and os.path.exists(st.session_state["nexus_zip"]):
    st.markdown("---")
    st.markdown("### 📦 Download Nexus Package")
    with open(st.session_state["nexus_zip"], "rb") as zb:
        st.download_button("📥 DOWNLOAD ALL SHORTS (.ZIP - INSTANT)", data=zb, file_name="Nexus_Clipping_Shorts.zip", mime="application/zip", use_container_width=True)
        
    for idx, fp in enumerate(st.session_state["nexus_files"]):
        f_mb = round(os.path.getsize(fp) / (1024 * 1024), 1)
        with open(fp, "rb") as f_bytes:
            st.download_button(f"⬇️ Save Short #{idx+1} ({f_mb} MB)", data=f_bytes, file_name=os.path.basename(fp), mime="video/mp4", key=f"nexus_dl_{idx}")
        st.video(fp)
      
