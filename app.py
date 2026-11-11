import os, re, shutil, zipfile, subprocess
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
from pytubefix import YouTube

st.set_page_config(page_title="Turbo Shorts Studio", page_icon="⚡", layout="centered")

st.markdown("""
<style>
.stApp {background: radial-gradient(circle at top, #1a1025 0%, #090a0f 100%); color: #f8fafc;}
.title-box {background: linear-gradient(135deg, rgba(239,68,68,0.2), rgba(168,85,247,0.2)); border: 1px solid #ef4444; border-radius: 14px; padding: 18px; text-align: center; margin-bottom: 20px;}
.title-box h1 {color: #ff4d4d; margin: 0; font-size: 26px; font-weight: 900;}
.stButton>button {width: 100%; background: linear-gradient(90deg, #ef4444, #9333ea); color: white; font-weight: bold; border: none; border-radius: 10px; padding: 12px; font-size: 16px;}
</style>
<div class="title-box">
  <h1>⚡ TURBO SHORTS MAKER (ANTI-BLOCK HD)</h1>
  <p style="color:#cbd5e1; margin:4px 0 0 0; font-size:14px;">Triple-Engine Unblocker • Parallel Multi-Core Cutting • Zero Pixel Loss</p>
</div>
""", unsafe_allow_html=True)

OUTPUT_DIR = "/tmp/my_shorts"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_id(url):
    p_list = [r"(?:v=|/)([0-9A-Za-z_-]{11}).*", r"youtu[.]be/([0-9A-Za-z_-]{11})", r"shorts/([0-9A-Za-z_-]{11})", r"live/([0-9A-Za-z_-]{11})"]
    for p in p_list:
        m = re.search(p, url.strip())
        if m: return m.group(1)
    return None

def get_duration(file_path, default_dur=300):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path], capture_output=True, text=True)
    try:
        return int(float(r.stdout.strip()))
    except Exception:
        return default_dur

def turbo_download_source(yt_url, vid_id):
    out_raw = os.path.join(OUTPUT_DIR, f"{vid_id}_source.mp4")
    if os.path.exists(out_raw) and os.path.getsize(out_raw) > 100000:
        return out_raw, get_duration(out_raw), "Cached"

    last_err = ""

    # ENGINE 1: yt-dlp Multi-Client + Aria2c 16x Turbo (Bypasses Cloud Blocks Fast!)
    ytdlp_clients = [
        "youtube:player_client=android_vr,tv_downgraded",
        "youtube:player_client=ios,mweb",
        "youtube:player_client=web_embedded,tv"
    ]
    for c_arg in ytdlp_clients:
        if os.path.exists(out_raw): os.remove(out_raw)
        cmd_ydl = [
            "yt-dlp", "-4", "--geo-bypass", "--no-warnings", "--no-playlist",
            "--extractor-args", c_arg,
            "-f", "best[height<=720][ext=mp4]/best[ext=mp4]/best",
            "--downloader", "aria2c",
            "--downloader-args", "aria2c:-x 16 -s 16 -k 1M",
            "-o", out_raw, yt_url.strip()
        ]
        try:
            r = subprocess.run(cmd_ydl, capture_output=True, text=True, timeout=45)
            if os.path.exists(out_raw) and os.path.getsize(out_raw) > 100000:
                return out_raw, get_duration(out_raw), f"yt-dlp ({c_arg.split('=')[1]})"
            last_err = r.stderr[-200:] if r.stderr else "yt-dlp empty"
        except Exception as e:
            last_err = str(e)

    # ENGINE 2: pytubefix with NodeJS PO-Token (WEB, ANDROID_VR, IOS, MWEB)
    for c_name in ["WEB", "ANDROID_VR", "IOS", "MWEB", "WEB_EMBED", "TV"]:
        try:
            yt = YouTube(yt_url.strip(), client=c_name)
            ys = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            if not ys:
                ys = yt.streams.filter(file_extension='mp4').first()
            if ys:
                if os.path.exists(out_raw): os.remove(out_raw)
                with ThreadPoolExecutor(max_workers=1) as ex:
                    ex.submit(ys.download, output_path=OUTPUT_DIR, filename=f"{vid_id}_source.mp4").result(timeout=45)
                if os.path.exists(out_raw) and os.path.getsize(out_raw) > 100000:
                    return out_raw, get_duration(out_raw, int(yt.length) if yt.length else 300), f"pytubefix ({c_name})"
        except Exception as e:
            last_err = str(e)
            continue

    return None, 0, last_err

def fast_cut_worker(args):
    i, st_time, dur, local_media, vid_id, res_choice, frame_mode = args
    is_fhd = "1080" in res_choice
    W, H = (1080, 1920) if is_fhd else (720, 1280)
    qual_tag = "1080p" if is_fhd else "720p"
    out_mp4 = os.path.join(OUTPUT_DIR, f"Short_{i+1}_{vid_id}_{qual_tag}.mp4")
    if os.path.exists(out_mp4): os.remove(out_mp4)

    sharp = ",unsharp=3:3:0.6:3:3:0.0"
    if "Square (1:1)" in frame_mode:
        vf = f"scale={W}:{W}:flags=lanczos:force_original_aspect_ratio=increase,crop={W}:{W}{sharp},pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p"
    elif "Wide Fit" in frame_mode:
        vf = f"scale={W}:{H}:flags=lanczos:force_original_aspect_ratio=decrease{sharp},pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p"
    else:
        vf = f"scale={W}:{H}:flags=lanczos:force_original_aspect_ratio=increase,crop={W}:{H}{sharp},setsar=1,format=yuv420p"

    cmd = [
        "ffmpeg", "-y", "-ss", str(st_time), "-i", local_media, "-t", str(dur),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "superfast",
        "-crf", "18", "-maxrate", "8000k", "-bufsize", "16000k",
        "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-movflags", "+faststart",
        out_mp4
    ]
    subprocess.run(cmd, capture_output=True)
    return out_mp4 if os.path.exists(out_mp4) and os.path.getsize(out_mp4) > 10000 else None

yt_url = st.text_input("🔗 Paste YouTube Video Link:", placeholder="https://youtu.be/...")
col1, col2 = st.columns(2)
with col1:
    clip_count = st.selectbox("🎞️ Kitni Shorts Chahiye?", [5, 10, 15, 20], index=0)
with col2:
    res_choice = st.selectbox("💎 Video Quality:", ["1080p FHD (Ultra Crisp ⭐)", "720p HD (High Clarity)"], index=0)

frame_mode = st.radio("📐 Crop & Frame Ratio:", ["Square (1:1) in 9:16 [Less Crop ⭐]", "Full Vertical (9:16 Zoom)", "Wide Fit (Zero Crop in 9:16)"])

if st.button("⚡ TURBO GENERATE SHORTS NOW"):
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    vid_id = get_id(yt_url)
    if not vid_id:
        st.error("❌ Bhai sahi YouTube link daalo!")
    else:
        with st.spinner("🚀 Step 1/2: Triple-Engine Unblocker se Video pull ho rahi hai (10-20 sec)..."):
            local_media, total_dur, engine_used = turbo_download_source(yt_url, vid_id)
        if not local_media:
            st.error(f"❌ Video stream block hui ({engine_used}), dobara try karein!")
        else:
            clip_len = 35 if total_dur >= 120 else max(15, total_dur // max(2, clip_count))
            step = max(10, max(clip_len, total_dur - clip_len - 5) // max(1, clip_count))
            tasks = [(i, min(5 + (i * step), max(0, total_dur - clip_len)), clip_len, local_media, vid_id, res_choice, frame_mode) for i in range(clip_count)]

            with st.spinner(f"✂️ Step 2/2: Parallel Multi-Core Cutting {clip_count} Crystal-Clear Shorts..."):
                with ThreadPoolExecutor(max_workers=4) as ex:
                    ready_files = [f for f in ex.map(fast_cut_worker, tasks) if f]

            zip_path = os.path.join(OUTPUT_DIR, f"All_Shorts_{vid_id}.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zf:
                for fpath in ready_files:
                    zf.write(fpath, os.path.basename(fpath))

            st.session_state["shorts"] = ready_files
            st.session_state["zip_path"] = zip_path

if "shorts" in st.session_state and st.session_state["shorts"]:
    st.success(f"✅ {len(st.session_state['shorts'])} Crystal-Clear HD Shorts Ready Hain!")

    if "zip_path" in st.session_state and os.path.exists(st.session_state["zip_path"]):
        with open(st.session_state["zip_path"], "rb") as zb:
            st.download_button("📦 DOWNLOAD ALL SHORTS IN 1 CLICK (.ZIP - FASTEST)", data=zb, file_name=os.path.basename(st.session_state["zip_path"]), mime="application/zip", use_container_width=True)

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
          
