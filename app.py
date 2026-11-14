import os, re, time, shutil, zipfile, subprocess, requests
from concurrent.futures import ThreadPoolExecutor
import streamlit as st

st.set_page_config(page_title="Pro FHD Shorts Cutter", page_icon="⚡", layout="centered")

st.markdown("""
<style>
.stApp {background: radial-gradient(circle at top, #1a1025 0%, #090a0f 100%); color: #f8fafc;}
.title-box {background: linear-gradient(135deg, rgba(239,68,68,0.2), rgba(168,85,247,0.2)); border: 1px solid #ef4444; border-radius: 14px; padding: 18px; text-align: center; margin-bottom: 20px;}
.title-box h1 {color: #ff4d4d; margin: 0; font-size: 26px; font-weight: 900;}
.stButton>button {width: 100%; background: linear-gradient(90deg, #ef4444, #9333ea); color: white; font-weight: bold; border: none; border-radius: 10px; padding: 12px; font-size: 16px;}
.step-card {background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.15); border-radius: 10px; padding: 12px; margin-bottom: 15px;}
</style>
<div class="title-box">
  <h1>⚡ 100% WORKING FHD SHORTS STUDIO</h1>
  <p style="color:#cbd5e1; margin:4px 0 0 0; font-size:14px;">Zero Server Block • Direct Video Cutter • True 1080p FHD</p>
</div>
""", unsafe_allow_html=True)

OUTPUT_DIR = "/tmp/my_shorts"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_duration(file_path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path], capture_output=True, text=True)
    try:
        return int(float(r.stdout.strip()))
    except Exception:
        return 300

def cut_fhd_fast(i, st_time, dur, local_media, res_choice, frame_mode):
    is_fhd = "1080" in res_choice
    W, H = (1080, 1920) if is_fhd else (720, 1280)
    qual_tag = "1080p_FHD" if is_fhd else "720p_HD"
    out_mp4 = os.path.join(OUTPUT_DIR, f"Short_{i+1}_{qual_tag}.mp4")
    if os.path.exists(out_mp4): os.remove(out_mp4)

    enhance = ",unsharp=3:3:0.65:3:3:0.0"

    if "Square (1:1)" in frame_mode:
        vf = f"scale={W}:{W}:flags=bicubic:force_original_aspect_ratio=increase,crop={W}:{W}{enhance},pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p"
    elif "Wide Fit" in frame_mode:
        vf = f"scale={W}:{H}:flags=bicubic:force_original_aspect_ratio=decrease{enhance},pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p"
    else:
        vf = f"scale={W}:{H}:flags=bicubic:force_original_aspect_ratio=increase,crop={W}:{H}{enhance},setsar=1,format=yuv420p"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(st_time),
        "-i", local_media,
        "-t", str(dur),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "ultrafast",
        "-crf", "18", "-maxrate", "8000k", "-bufsize", "16000k",
        "-c:a", "aac", "-b:a", "160k", "-ac", "2", "-movflags", "+faststart",
        "-threads", "2",
        out_mp4
    ]
    subprocess.run(cmd, capture_output=True)
    return out_mp4 if os.path.exists(out_mp4) and os.path.getsize(out_mp4) > 10000 else None

# ---------------- 100% RELIABLE WORKFLOW UI ----------------
st.markdown("""
<div class="step-card">
<b>💡 Server IP Block Bypass Trick (100% Working):</b><br>
1. Niche button daba kar <b>Cobalt / Y2Mate</b> se 5 second mein YouTube video apne phone mein save karein.<br>
2. Fir niche <b>Browse files</b> mein vo video select karein — 20 second mein 1080p FHD Shorts kat kar ready ho jayengi!
</div>
""", unsafe_allow_html=True)

c_dl1, c_dl2 = st.columns(2)
with c_dl1:
    st.link_button("🌐 1. Fast Video Saver (Cobalt)", "https://cobalt.tools", use_container_width=True)
with c_dl2:
    st.link_button("⚡ Backup Video Saver (SSYouTube)", "https://ssyoutube.com", use_container_width=True)

st.markdown("### 📤 Step 2: Apni Video Yahan Select Karein")
uploaded_video = st.file_uploader("Phone se MP4 Video select karein (No IP Block, 100% Instant!)", type=["mp4", "mkv", "webm", "mov"])

col1, col2 = st.columns(2)
with col1:
    clip_count = st.selectbox("🎞️ Kitni Shorts Chahiye?", [5, 10, 15, 20], index=0)
with col2:
    res_choice = st.selectbox("💎 Video Quality:", ["1080p FHD (Ultra Crisp ⭐)", "720p HD (Super Fast)"], index=0)

frame_mode = st.radio("📐 Crop & Frame Ratio:", ["Square (1:1) in 9:16 [Less Crop ⭐]", "Full Vertical (9:16 Zoom)", "Wide Fit (Zero Crop in 9:16)"])

if st.button("🚀 GENERATE 1080p FHD SHORTS NOW"):
    if not uploaded_video:
        st.error("❌ Bhai pehle upar 'Browse files' daba kar apne phone se video select karo!")
    else:
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        t0 = time.time()

        local_media = os.path.join(OUTPUT_DIR, "input_source.mp4")
        with st.spinner("⚡ Video load ho rahi hai (2-5 sec)..."):
            with open(local_media, "wb") as f:
                f.write(uploaded_video.getbuffer())
            total_dur = get_duration(local_media)

        clip_len = 35 if total_dur >= 120 else max(10, total_dur // max(2, clip_count))
        step = max(5, max(clip_len, total_dur - clip_len - 2) // max(1, clip_count))

        prog_bar = st.progress(0, text="✂️ Fast 1080p FHD Cutting Shuru...")
        ready_files = []

        for i in range(clip_count):
            st_time = min(2 + (i * step), max(0, total_dur - clip_len))
            prog_bar.progress((i) / clip_count, text=f"⚡ Cutting FHD Short #{i+1} of {clip_count}...")
            out_f = cut_fhd_fast(i, st_time, clip_len, local_media, res_choice, frame_mode)
            if out_f:
                ready_files.append(out_f)
            prog_bar.progress((i + 1) / clip_count, text=f"✅ Short #{i+1}/{clip_count} Ready!")

        zip_path = os.path.join(OUTPUT_DIR, "All_FHD_Shorts.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zf:
            for fpath in ready_files:
                zf.write(fpath, os.path.basename(fpath))

        st.session_state["shorts"] = ready_files
        st.session_state["zip_path"] = zip_path
        st.session_state["total_time"] = int(time.time() - t0)

if "shorts" in st.session_state and st.session_state["shorts"]:
    t_taken = st.session_state.get("total_time", 30)
    st.success(f"🎉 {len(st.session_state['shorts'])} True 1080p FHD Shorts Ready in {t_taken} Seconds!")

    if "zip_path" in st.session_state and os.path.exists(st.session_state["zip_path"]):
        with open(st.session_state["zip_path"], "rb") as zb:
            st.download_button("📦 DOWNLOAD ALL SHORTS IN 1 CLICK (.ZIP - FASTEST)", data=zb, file_name="All_FHD_Shorts.zip", mime="application/zip", use_container_width=True)

    st.markdown("---")
    hooks = ["आखिर तक देखो भाई! 😱🔥", "ये क्या कर दिया भाई ने! 😂🔥", "सबसे खतरनाक सीन! ⚡💥", "99% लोग ये मिस कर देंगे! 🤯", "भाई का रिएक्शन देखो! 👀🔥"]

    for idx, fpath in enumerate(st.session_state["shorts"]):
        h = hooks[idx % len(hooks)]
        fsize_mb = round(os.path.getsize(fpath) / (1024 * 1024), 1)
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"**🎬 Short #{idx+1}** (`{fsize_mb} MB`) — `{h} #shorts #viral`")
        with c2:
            with open(fpath, "rb") as file_bytes:
                st.download_button(f"📥 Save #{idx+1} ({fsize_mb}MB)", data=file_bytes, file_name=os.path.basename(fpath), mime="video/mp4", key=f"dl_{idx}")
        with st.expander(f"▶️ Preview Short #{idx+1} (Optional)"):
            st.video(fpath)
          
