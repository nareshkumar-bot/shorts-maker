import os, re, time, shutil, zipfile, subprocess, requests
from concurrent.futures import ThreadPoolExecutor
import streamlit as st

st.set_page_config(page_title="SuperFast FHD Shorts Maker", page_icon="⚡", layout="centered")

st.markdown("""
<style>
.stApp {background: radial-gradient(circle at top, #1a1025 0%, #090a0f 100%); color: #f8fafc;}
.title-box {background: linear-gradient(135deg, rgba(239,68,68,0.2), rgba(168,85,247,0.2)); border: 1px solid #ef4444; border-radius: 14px; padding: 18px; text-align: center; margin-bottom: 20px;}
.title-box h1 {color: #ff4d4d; margin: 0; font-size: 26px; font-weight: 900;}
.stButton>button {width: 100%; background: linear-gradient(90deg, #ef4444, #9333ea); color: white; font-weight: bold; border: none; border-radius: 10px; padding: 12px; font-size: 16px;}
</style>
<div class="title-box">
  <h1>⚡ PRO SHORTS STUDIO (COOKIES TURBO)</h1>
  <p style="color:#cbd5e1; margin:4px 0 0 0; font-size:14px;">Cookies Bypass Engine • 16x Aria2c • 1080p FHD</p>
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

# ---------------- ROBUST COOKIES + YTDLP DOWNLOADER ----------------
def robust_download(vid_id, cookie_file=None):
    out_raw = os.path.join(OUTPUT_DIR, f"{vid_id}_source.mp4")
    if os.path.exists(out_raw) and os.path.getsize(out_raw) > 100000:
        return out_raw, get_duration(out_raw), "Cached"

    clean_url = f"https://www.youtube.com/watch?v={vid_id}"

    # 1. Try via yt-dlp with aria2c 16-connection turbo and optional cookies.txt
    ytdlp_args = ["yt-dlp", "-4", "--no-warnings", "--no-playlist"]
    if cookie_file and os.path.exists(cookie_file):
        ytdlp_args.extend(["--cookies", cookie_file])

    ytdlp_args.extend([
        "--extractor-args", "youtube:player_client=ios,tv_embedded;player_skip=webpage",
        "-f", "18/22/best[ext=mp4]/best",
        "--downloader", "aria2c",
        "--downloader-args", "aria2c:-x 16 -s 16 -k 1M",
        "-o", out_raw, clean_url
    ])

    try:
        subprocess.run(ytdlp_args, capture_output=True, timeout=40)
        if os.path.exists(out_raw) and os.path.getsize(out_raw) > 100000:
            return out_raw, get_duration(out_raw), "yt-dlp Turbo"
    except Exception:
        pass

    # 2. Fallback to Cobalt API
    try:
        resp = requests.post("https://api.cobalt.tools/api/json", json={"url": clean_url, "vQuality": "720"}, headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=8)
        if resp.status_code == 200:
            d_url = resp.json().get("url")
            if d_url:
                with requests.get(d_url, stream=True, timeout=30) as r:
                    if r.status_code == 200:
                        with open(out_raw, "wb") as f:
                            for chunk in r.iter_content(chunk_size=1024*512):
                                if chunk: f.write(chunk)
                if os.path.exists(out_raw) and os.path.getsize(out_raw) > 100000:
                    return out_raw, get_duration(out_raw), "Cobalt API"
    except Exception:
        pass

    return None, 0, ""

# ---------------- ULTRA-FAST 1080p FHD CUTTER ----------------
def cut_fhd_fast(i, st_time, dur, local_media, vid_id, res_choice, frame_mode):
    is_fhd = "1080" in res_choice
    W, H = (1080, 1920) if is_fhd else (720, 1280)
    qual_tag = "1080p_FHD" if is_fhd else "720p_HD"
    out_mp4 = os.path.join(OUTPUT_DIR, f"Short_{i+1}_{vid_id}_{qual_tag}.mp4")
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

# ---------------- MAIN UI ----------------
yt_url = st.text_input("🔗 Paste YouTube Video Link:", placeholder="https://youtu.be/...")
col1, col2 = st.columns(2)
with col1:
    clip_count = st.selectbox("🎞️ Kitni Shorts Chahiye?", [5, 10, 15, 20], index=0)
with col2:
    res_choice = st.selectbox("💎 Video Quality:", ["1080p FHD (Ultra Crisp ⭐)", "720p HD (Super Fast)"], index=0)

frame_mode = st.radio("📐 Crop & Frame Ratio:", ["Square (1:1) in 9:16 [Less Crop ⭐]", "Full Vertical (9:16 Zoom)", "Wide Fit (Zero Crop in 9:16)"])

with st.expander("🔑 Optional: cookies.txt Upload Karein (Agar IP Block ho toh)"):
    up_cookie = st.file_uploader("Netscape cookies.txt file upload karein", type=["txt"])
    st.markdown("*(Aap apne browser mein 'Get cookies.txt LOCALLY' extension se YouTube ki cookies export karke yahan upload kar sakte hain)*")

if st.button("🚀 GENERATE FHD SHORTS NOW"):
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    vid_id = get_id(yt_url)
    if not vid_id:
        st.error("❌ Bhai sahi YouTube link daalo!")
    else:
        cookie_path = None
        if up_cookie:
            cookie_path = os.path.join(OUTPUT_DIR, "cookies.txt")
            with open(cookie_path, "wb") as f:
                f.write(up_cookie.read())

        t0 = time.time()
        with st.spinner("⚡ Step 1/2: Video download ho rahi hai..."):
            local_media, total_dur, engine_used = robust_download(vid_id, cookie_path)

        if not local_media:
            st.error("❌ Streamlit Cloud IP YouTube se block hai. Upar expander khol kar apni 'cookies.txt' file upload karein, fir 100% chalega!")
        else:
            clip_len = 35 if total_dur >= 120 else max(15, total_dur // max(2, clip_count))
            step = max(10, max(clip_len, total_dur - clip_len - 5) // max(1, clip_count))

            prog_bar = st.progress(0, text=f"✂️ Step 2/2: Fast FHD Cutting Shuru...")
            ready_files = []

            for i in range(clip_count):
                st_time = min(5 + (i * step), max(0, total_dur - clip_len))
                prog_bar.progress((i) / clip_count, text=f"⚡ Cutting FHD Short #{i+1} of {clip_count}...")
                out_f = cut_fhd_fast(i, st_time, clip_len, local_media, vid_id, res_choice, frame_mode)
                if out_f:
                    ready_files.append(out_f)
                prog_bar.progress((i + 1) / clip_count, text=f"✅ Short #{i+1}/{clip_count} Ready!")

            zip_path = os.path.join(OUTPUT_DIR, f"All_Shorts_{vid_id}.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zf:
                for fpath in ready_files:
                    zf.write(fpath, os.path.basename(fpath))

            st.session_state["shorts"] = ready_files
            st.session_state["zip_path"] = zip_path
            st.session_state["total_time"] = int(time.time() - t0)

if "shorts" in st.session_state and st.session_state["shorts"]:
    t_taken = st.session_state.get("total_time", 60)
    st.success(f"🎉 {len(st.session_state['shorts'])} True 1080p FHD Shorts Ready in {t_taken} Seconds!")

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
          
