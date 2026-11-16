import os, re, time, shutil, zipfile, subprocess, requests
from pathlib import Path
import streamlit as st
import yt_dlp

st.set_page_config(page_title="PeakCut Studio", page_icon="✂️", layout="centered")

# PeakCut Authentic Dark UI
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;700;800&display=swap');
html, body, [class*="css"] {font-family: 'Poppins', sans-serif;}
.stApp {background-color: #09090b; color: #f4f4f5;}
.peak-box {
    background-color: #121215;
    border: 1px solid #27272a;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    margin-bottom: 16px;
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
  <div class="peak-sub">Pure Web Cookie Engine • Zero Device Error • Exact PeakCut Render</div>
</div>
""", unsafe_allow_html=True)

OUTPUT_DIR = Path("/tmp/peakcut_jobs")
COOKIE_SAVED_PATH = Path("/tmp/saved_youtube_cookies.txt")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def get_id(url: str):
    p_list = [r"(?:v=|/)([0-9A-Za-z_-]{11}).*", r"youtu[.]be/([0-9A-Za-z_-]{11})", r"shorts/([0-9A-Za-z_-]{11})", r"live/([0-9A-Za-z_-]{11})"]
    for p in p_list:
        m = re.search(p, url.strip())
        if m: return m.group(1)
    return None

def probe_video(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True
    )
    try:
        import json
        d = json.loads(r.stdout)
        v = (d.get("streams") or [{}])[0]
        dur = float((d.get("format") or {}).get("duration") or 300.0)
        return {"width": int(v.get("width") or 1280), "height": int(v.get("height") or 720), "duration": dur}
    except Exception:
        return {"width": 1280, "height": 720, "duration": 300.0}

def fast_stream_save(stream_url: str, out_file: Path) -> bool:
    out_file.unlink(missing_ok=True)
    aria_cmd = [
        "aria2c", "-x", "16", "-s", "16", "-k", "1M",
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "--check-certificate=false",
        "-d", str(out_file.parent), "-o", out_file.name, stream_url
    ]
    subprocess.run(aria_cmd, capture_output=True, timeout=45)
    if out_file.is_file() and out_file.stat().st_size > 100_000:
        return True
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        with requests.get(stream_url, headers=headers, stream=True, timeout=40) as r:
            if r.status_code == 200:
                with open(out_file, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 512):
                        if chunk: f.write(chunk)
        return out_file.is_file() and out_file.stat().st_size > 100_000
    except Exception:
        return False

class _Quiet:
    def debug(self, m): pass
    def info(self, m): pass
    def warning(self, m): pass
    def error(self, m): pass

# Exact PeakCut studio/media.py _video_format
def _video_format(height: int = 1080) -> str:
    return f"bv*[height<={height}][vcodec^=avc1]+ba[ext=m4a]/bv*[height<={height}]+ba/b[height<={height}]/b"

# ---------------- PURE PEAKCUT DOWNLOADER (NO FAKE DEVICE CLIENTS!) ----------------
def master_video_downloader(url: str, height: int = 1080) -> tuple:
    vid_id = get_id(url)
    stem = vid_id or "video_src"
    out_raw = OUTPUT_DIR / f"{stem}.mp4"
    if out_raw.is_file() and out_raw.stat().st_size > 100_000:
        return out_raw, "Cached"

    clean_url = f"https://www.youtube.com/watch?v={vid_id}" if vid_id else url.strip()
    has_cookie = COOKIE_SAVED_PATH.is_file() and COOKIE_SAVED_PATH.stat().st_size > 20
    last_err = ""

    # ENGINE 1: Exact PeakCut studio/media.py _ydl (Pure Default Web Client + Your Browser Cookies!)
    # NO ios/android_vr/tv_embedded override when cookies are used, preventing "no longer supported in this application"!
    profiles = [
        ("PeakCut Web+Cookies", {}),
        ("PeakCut MWeb+TV", {"extractor_args": {"youtube": {"player_client": ["mweb", "web"]}}}),
    ]

    for label, extra_opts in profiles:
        for p in OUTPUT_DIR.glob(f"{stem}.*"):
            p.unlink(missing_ok=True)

        ydl_opts = {
            "format": _video_format(height),
            "merge_output_format": "mp4",
            "outtmpl": str(OUTPUT_DIR / f"{stem}.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "logger": _Quiet(),
            "extract_flat": "in_playlist",
            "playlistend": 1,
            "socket_timeout": 20,
            "concurrent_fragment_downloads": 4,
            "nocheckcertificate": True,
            **extra_opts
        }
        if has_cookie:
            ydl_opts["cookiefile"] = str(COOKIE_SAVED_PATH)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([clean_url])
            files = sorted((p for p in OUTPUT_DIR.glob(f"{stem}.*") if p.suffix not in (".part", ".ytdl")), key=lambda p: p.stat().st_size, reverse=True)
            if files and files[0].stat().st_size > 100_000:
                return files[0], label
        except Exception as e:
            last_err = str(e)

    # ENGINE 2: External Web-Downloader API (Loader.to / Oceansaver Engine)
    if vid_id:
        for q_fmt in ["720", "1080", "480", "360"]:
            try:
                api_init = f"https://ab.cococococ.com/ajax/download.php?copyright=0&format={q_fmt}&url={clean_url}&api=dfcb6d76f2f6a9894gjkege8a4ab232222"
                r_init = requests.get(api_init, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
                if r_init.get("success") and r_init.get("id"):
                    task_id = r_init["id"]
                    for _ in range(15):
                        time.sleep(1.5)
                        p_res = requests.get(f"https://p.oceansaver.in/ajax/progress.php?id={task_id}", timeout=8).json()
                        if p_res.get("success") == 1 and p_res.get("download_url"):
                            if fast_stream_save(p_res["download_url"], out_raw):
                                return out_raw, f"Web-Downloader API ({q_fmt}p)"
                            break
                    break
            except Exception as e:
                last_err = str(e)

    # ENGINE 3: Public Invidious / Piped Proxy Nodes
    if vid_id:
        proxy_nodes = [
            f"https://inv.nadeko.net/api/v1/videos/{vid_id}",
            f"https://invidious.nerdvpn.de/api/v1/videos/{vid_id}",
            f"https://pipedapi.kavin.rocks/streams/{vid_id}",
            f"https://api.piped.private.coffee/streams/{vid_id}"
        ]
        for node in proxy_nodes:
            try:
                r = requests.get(node, timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    streams = data.get("formatStreams") or data.get("videoStreams") or []
                    for s in streams:
                        if not s.get("videoOnly", False) and s.get("url"):
                            if fast_stream_save(s["url"], out_raw):
                                return out_raw, "Proxy Node API"
            except Exception:
                continue

    return None, last_err

# ---------------- EXACT PEAKCUT RENDER.PY FILTER & ENCODER ----------------
def render_peakcut_short(i: int, src_path: Path, st_time: float, dur: float, src_w: int, src_h: int, layout_choice: str, style_choice: str, res_choice: str) -> Path:
    is_fhd = "1080" in res_choice
    W, H = (1080, 1920) if is_fhd else (720, 1280)
    out_mp4 = OUTPUT_DIR / f"PeakCut_Short_{i+1}_{W}x{H}.mp4"
    out_mp4.unlink(missing_ok=True)

    if "Full frame + blurred fill" in layout_choice:
        fg_h = min(H, int(round(W * src_h / max(1, src_w) / 2)) * 2)
        vf = (
            f"[0:v]fps=30,split=2[a][b];"
            f"[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,"
            f"scale={W}:{H},eq=brightness=-0.14:saturation=1.15[bg];"
            f"[b]scale={W}:{fg_h}:force_original_aspect_ratio=increase,crop={W}:{fg_h},unsharp=3:3:0.6:3:3:0.0[fg];"
            f"[bg][fg]overlay=0:(H-h)/2,setsar=1[v]"
        )
    elif "Zoomed in + blurred fill" in layout_choice:
        fg_h = int(H * 0.52)
        vf = (
            f"[0:v]fps=30,split=2[a][b];"
            f"[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,"
            f"scale={W}:{H},eq=brightness=-0.14:saturation=1.15[bg];"
            f"[b]scale={W}:{fg_h}:force_original_aspect_ratio=increase,crop={W}:{fg_h},unsharp=3:3:0.6:3:3:0.0[fg];"
            f"[bg][fg]overlay=0:(H-h)/2,setsar=1[v]"
        )
    else:
        vf = f"[0:v]fps=30,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},unsharp=3:3:0.6:3:3:0.0,setsar=1[v]"

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{st_time:.2f}",
        "-t", f"{dur:.2f}",
        "-i", str(src_path),
        "-filter_complex", vf,
        "-map", "[v]", "-map", "0:a:0?",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
        str(out_mp4)
    ]
    subprocess.run(cmd, capture_output=True)
    return out_mp4 if out_mp4.is_file() and out_mp4.stat().st_size > 10_000 else None

# ---------------- UI: COOKIE SETUP WITH PHONE "OK" BUTTON ----------------
with st.expander("🔑 Cookies Setup (Phone Users Ke Liye 'OK' Button Ke Saath)", expanded=not COOKIE_SAVED_PATH.is_file()):
    if COOKIE_SAVED_PATH.is_file() and COOKIE_SAVED_PATH.stat().st_size > 20:
        st.success(f"✅ **Cookies Active Hain!** ({COOKIE_SAVED_PATH.stat().st_size} bytes saved)")
        if st.button("🗑️ Delete Saved Cookies"):
            COOKIE_SAVED_PATH.unlink(missing_ok=True)
            st.rerun()

    st.markdown("Phone se `cookies.txt` file chunein **YA** niche box mein text paste karke **'✅ OK / SAVE COOKIES'** button dabayein:")
    up_ck_file = st.file_uploader("📂 Option 1: Select cookies.txt file from phone", type=["txt"])
    ck_text_box = st.text_area("📋 Option 2: Paste cookies.txt content here", height=90, placeholder="# Netscape HTTP Cookie File...")

    if st.button("✅ OK / SAVE COOKIES NOW"):
        if up_ck_file is not None:
            COOKIE_SAVED_PATH.write_bytes(up_ck_file.getvalue())
            st.success("🎉 File wali Cookies Save ho gayi hain! Ab niche link daal kar Shorts banayein.")
            time.sleep(0.8)
            st.rerun()
        elif ck_text_box.strip():
            COOKIE_SAVED_PATH.write_text(ck_text_box.strip(), encoding="utf-8")
            st.success("🎉 Paste ki hui Cookies Save ho gayi hain! Ab niche link daal kar Shorts banayein.")
            time.sleep(0.8)
            st.rerun()
        else:
            st.error("❌ Pehle file select karein ya box mein cookies paste karein, fir OK dabayein!")

# ---------------- MAIN INPUT UI ----------------
source_mode = st.radio("📥 Select Video Input:", ["🔗 Video Link (YouTube / Twitch / Kick)", "📱 Upload Video From Phone (100% Instant)"], horizontal=True)

url_input = ""
up_video = None

if "Link" in source_mode:
    url_input = st.text_input("🔗 Paste Video Link:", placeholder="https://youtu.be/...")
else:
    up_video = st.file_uploader("📱 Phone se MP4/MKV Video Chunein:", type=["mp4", "mkv", "mov", "webm"])

c1, c2, c3 = st.columns(3)
with c1:
    clip_count = st.selectbox("🎞️ Clips Count:", [5, 10, 15, 20], index=0)
with c2:
    res_choice = st.selectbox("💎 Quality:", ["1080p FHD ⭐", "720p HD"], index=0)
with c3:
    style_choice = st.selectbox("🎨 PeakCut Style:", ["Bounce", "Hype", "Clean"], index=0)

layout_choice = st.radio(
    "📐 PeakCut Layout (studio/render.py):",
    ["Full frame + blurred fill ⭐", "Zoomed in + blurred fill", "Fill the screen (centre crop)"],
    horizontal=True
)

if st.button("🚀 MAKE PEAKCUT FHD SHORTS NOW"):
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    src_file = None
    engine_name = "Phone Upload"

    if up_video is not None:
        src_file = OUTPUT_DIR / "uploaded_source.mp4"
        with st.spinner("📥 Loading video from phone..."):
            src_file.write_bytes(up_video.getbuffer())
    elif url_input.strip():
        with st.spinner("⚡ Downloading 1080p Video via Pure PeakCut Web Engine (10-20 sec)..."):
            target_h = 1080 if "1080" in res_choice else 720
            src_file, engine_name = master_video_downloader(url_input.strip(), height=target_h)
        if not src_file:
            st.error(f"❌ Error ({engine_name[-140:]}). Check cookies or use '📱 Upload Video From Phone'!")
    else:
        st.error("❌ Bhai pehle Video Link daalo ya Phone se Video select karo!")

    if src_file and src_file.is_file():
        meta = probe_video(src_file)
        dur, src_w, src_h = meta["duration"], meta["width"], meta["height"]
        clip_len = 35.0 if dur >= 120 else max(12.0, dur / max(2, clip_count))
        step = max(8.0, max(clip_len, dur - clip_len - 4) / max(1, clip_count))

        prog = st.progress(0, text=f"✂️ Rendering {clip_count} PeakCut Shorts via {engine_name}...")
        ready_files = []

        for i in range(clip_count):
            st_t = min(3.0 + i * step, max(0.0, dur - clip_len))
            prog.progress(i / clip_count, text=f"🎬 Rendering Short #{i+1}/{clip_count} ({layout_choice.split('+')[0].strip()})...")
            out_p = render_peakcut_short(i, src_file, st_t, clip_len, src_w, src_h, layout_choice, style_choice, res_choice)
            if out_p:
                ready_files.append(out_p)
            prog.progress((i + 1) / clip_count, text=f"✅ Short #{i+1}/{clip_count} Ready!")

        if ready_files:
            zip_path = OUTPUT_DIR / "PeakCut_All_Shorts.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
                for f in ready_files:
                    z.write(f, f.name)
            st.session_state["shorts"] = [str(f) for f in ready_files]
            st.session_state["zip_path"] = str(zip_path)
            st.session_state["t_sec"] = int(time.time() - t0)
            st.session_state["eng"] = engine_name

if "shorts" in st.session_state and st.session_state["shorts"]:
    st.success(f"🎉 {len(st.session_state['shorts'])} PeakCut 1080p Shorts Ready in {st.session_state.get('t_sec', 25)}s! (Source: {st.session_state.get('eng', 'PeakCut')})")
    if "zip_path" in st.session_state and os.path.exists(st.session_state["zip_path"]):
        with open(st.session_state["zip_path"], "rb") as zb:
            st.download_button("📦 DOWNLOAD ALL SHORTS IN 1 CLICK (.ZIP)", data=zb, file_name="PeakCut_Shorts.zip", mime="application/zip", use_container_width=True)

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
        
