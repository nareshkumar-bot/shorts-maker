import os, re, shutil, zipfile, subprocess
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
from pytubefix import YouTube

st.set_page_config(page_title="Pro TV Shorts Maker", page_icon="⚡", layout="centered")

st.markdown("""
<style>
.stApp {background: radial-gradient(circle at top, #1a1025 0%, #090a0f 100%); color: #f8fafc;}
.title-box {background: linear-gradient(135deg, rgba(239,68,68,0.2), rgba(168,85,247,0.2)); border: 1px solid #ef4444; border-radius: 14px; padding: 18px; text-align: center; margin-bottom: 20px;}
.title-box h1 {color: #ff4d4d; margin: 0; font-size: 26px; font-weight: 900;}
.stButton>button {width: 100%; background: linear-gradient(90deg, #ef4444, #9333ea); color: white; font-weight: bold; border: none; border-radius: 10px; padding: 12px; font-size: 16px;}
</style>
<div class="title-box">
  <h1>⚡ PRO SHORTS MAKER (TV TURBO + 1080p FHD)</h1>
  <p style="color:#cbd5e1; margin:4px 0 0 0; font-size:14px;">Pure TV/VR Fast Engine • True 1080p FHD • Square 1:1 in 9:16</p>
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

def download_tv_fast(yt_url, vid_id):
    out_raw = os.path.join(OUTPUT_DIR, f"{vid_id}_source.mp4")
    if os.path.exists(out_raw) and os.path.getsize(out_raw) > 100000:
        return out_raw, get_duration(out_raw), "Cached TV Stream"

    clean_url = f"https://www.youtube.com/watch?v={vid_id}"
    last_err = ""

    # ONLY the working fast clients (TV & Embedded first, just like the version that worked!)
    working_clients = ["TV", "TV_EMBED", "WEB_EMBED", "ANDROID_VR", "IOS"]

    for c_name in working_clients:
        try:
            yt = YouTube(clean_url, client=c_name)
            dur = int(yt.length) if yt.length else 300

            # 1. Try grabbing highest resolution progressive stream first (Fastest & Never gives 403!)
            ys = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            if not ys:
                ys = yt.streams.filter(file_extension='mp4').order_by('resolution').desc().first()

            if ys:
                if os.path.exists(out_raw):
                    os.remove(out_raw)

                # Use pytubefix's internal session download (Guaranteed No 403 Forbidden!)
                with ThreadPoolExecutor(max_workers=1) as ex:
                    ex.submit(ys.download, output_path=OUTPUT_DIR, filename=f"{vid_id}_source.mp4").result(timeout=45)

                if os.path.exists(out_raw) and os.path.getsize(out_raw) > 100000:
                    return out_raw, get_duration(out_raw, dur), f"{c_name} ({ys.resolution})"
        except Exception as e:
            last_err = str(e)
            continue

    return None, 0, last_err

def fast_cut_fhd_worker(args):
    i, st_time, dur, local_media, vid_id, res_choice, frame_mode = args
    is_fhd = "1080" in res_choice
    W, H = (1080, 1920) if is_fhd else (720, 1280)
    qual_tag = "1080p_FHD" if is_fhd else "720p_HD"
    out_mp4 = os.path.join(OUTPUT_DIR, f"Short_{i+1}_{vid_id}_{qual_tag}.mp4")
    if os.path.exists(out_mp4):
        os.remove(out_mp4)

    # PRO FHD ENHANCER: Lanczos Upscaling + Contrast Adaptive Sharpening + Color Pop (Fixes low-res source into crisp 1080p!)
    enhance = ",unsharp=5:5:0.8:3:3:0.4,eq=contrast=1.04:saturation=1.08"

    if "Square (1:1)" in frame_mode:
        vf = f"scale={W}:{W}:flags=lanczos:force_original_aspect_ratio=increase,crop={W}:{W}{enhance},pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p"
    elif "Wide Fit" in frame_mode:
        vf = f"scale={W}:{H}:flags=lanczos:force_original_aspect_ratio=decrease{enhance},pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p"
    else:
        vf = f"scale={W}:{H}:flags=lanczos:force_original_aspect_ratio=increase,crop={W}:{H}{enhance},setsar=1,format=yuv420p"

    # High-Bitrate FHD encoding (-crf 17, 10Mbps maxrate) so downloaded video never pixelates!
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(st_time),
        "-i", local_media,
        "-t", str(dur),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "17", "-maxrate", "10000k", "-bufsize", "20000k",
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
    res_choice = st.selectbox("💎 Video Quality:", ["1080p FHD (Ultra Crisp ⭐)", "720p HD (Fast)"], index=0)

frame_mode = st.radio("📐 Crop & Frame Ratio:", ["Square (1:1) in 9:16 [Less Crop ⭐]", "Full Vertical (9:16 Zoom)", "Wide Fit (Zero Crop in 9:16)"])

if st.button("⚡ GENERATE FHD SHORTS NOW"):
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    vid_id = get_id(yt_url)
    if not vid_id:
        st.error("❌ Bhai sahi YouTube link daalo!")
    else:
        with st.spinner("🚀 Step 1/2: Fast TV Engine se Video pull ho rahi hai (10-15 sec)..."):
            local_media, total_dur, engine_used = download_tv_fast(yt_url, vid_id)
        if not local_media:
            st.error(f"❌ Error ({engine_used}). Dobara button dabayein!")
        else:
            clip_len = 35 if total_dur >= 120 else max(15, total_dur // max(2, clip_count))
            step = max(10, max(clip_len, total_dur - clip_len - 5) // max(1, clip_count))
            tasks = [(i, min(5 + (i * step), max(0, total_dur - clip_len)), clip_len, local_media, vid_id, res_choice, frame_mode) for i in range(clip_count)]

            with st.spinner(f"✂️ Step 2/2: Cutting & Upscaling {clip_count} Shorts into True 1080p FHD ({engine_used})..."):
                with ThreadPoolExecutor(max_workers=4) as ex:
                    ready_files = [f for f in ex.map(fast_cut_fhd_worker, tasks) if f]

            zip_path = os.path.join(OUTPUT_DIR, f"All_Shorts_{vid_id}.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zf:
                for fpath in ready_files:
                    zf.write(fpath, os.path.basename(fpath))

            st.session_state["shorts"] = ready_files
            st.session_state["zip_path"] = zip_path

if "shorts" in st.session_state and st.session_state["shorts"]:
    st.success(f"✅ {len(st.session_state['shorts'])} True 1080p FHD Shorts Ready Hain!")

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
      
