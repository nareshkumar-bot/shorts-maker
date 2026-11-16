import os, re, time, json, shutil, zipfile, subprocess, requests
from pathlib import Path
import streamlit as st
import yt_dlp

st.set_page_config(page_title="PeakCut Studio", page_icon="✂️", layout="centered")

# PeakCut Authentic Dark UI[span_0](start_span)[span_0](end_span)
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
  <div class="peak-sub">TV Code Unlock + Auto-Fixed Cookies + Exact PeakCut Render</div>
</div>
""", unsafe_allow_html=True)

OUTPUT_DIR = Path("/tmp/peakcut_jobs")
COOKIE_SAVED_PATH = Path("/tmp/saved_youtube_cookies.txt")
TV_TOKEN_PATH = Path("/tmp/saved_tv_oauth.json")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Official YouTube TV Client Credentials
TV_CLIENT_ID = "861556708454-d6dlm3lh05idd8npek18k6be8ba3oc68.apps.googleusercontent.com"
TV_CLIENT_SECRET = "SboVhoG9s0rNafixCSGGKXAT"

def get_id(url: str):
    p_list = [r"(?:v=|/)([0-9A-Za-z_-]{11}).*", r"youtu[.]be/([0-9A-Za-z_-]{11})", r"shorts/([0-9A-Za-z_-]{11})", r"live/([0-9A-Za-z_-]{11})"]
    for p in p_list:
        m = re.search(p, url.strip())
        if m: return m.group(1)
    return None

# Auto-fixes mobile copy-paste spaces back into strict Netscape TAB format!
def sanitize_and_save_cookies(raw_text: str, out_path: Path) -> int:
    fixed_lines = ["# Netscape HTTP Cookie File"]
    valid_count = 0
    for line in raw_text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            if s.startswith("#HttpOnly_"):
                s = s[len("#HttpOnly_"):]
            else:
                continue
        parts = s.split("\t")
        if len(parts) < 7:
            parts = re.split(r"\s+", s, maxsplit=6)
        if len(parts) >= 7:
            domain = parts[0]
            flag = "TRUE" if domain.startswith(".") else "FALSE"
            if parts[1].upper() in ("TRUE", "FALSE"):
                flag = parts[1].upper()
            path_str = parts[2] if parts[2].startswith("/") else "/"
            secure = "TRUE" if parts[3].upper() == "TRUE" else "FALSE"
            expiry = re.sub(r"[^0-9]", "", parts[4]) or "1893456000"
            name = parts[5]
            val = parts[6].strip()
            fixed_lines.append(f"{domain}\t{flag}\t{path_str}\t{secure}\t{expiry}\t{name}\t{val}")
            valid_count += 1
    out_path.write_text("\n".join(fixed_lines) + "\n", encoding="utf-8")
    return valid_count

def get_valid_tv_token() -> str:
    if not TV_TOKEN_PATH.is_file():
        return ""
    try:
        data = json.loads(TV_TOKEN_PATH.read_text(encoding="utf-8"))
        if time.time() < data.get("expires_at", 0) - 60:
            return data.get("access_token", "")
        if data.get("refresh_token"):
            r = requests.post(
                "https://www.youtube.com/o/oauth2/token",
                data={
                    "client_id": TV_CLIENT_ID,
                    "client_secret": TV_CLIENT_SECRET,
                    "refresh_token": data["refresh_token"],
                    "grant_type": "refresh_token"
                },
                timeout=10
            ).json()
            if "access_token" in r:
                data["access_token"] = r["access_token"]
                data["expires_at"] = int(time.time()) + int(r.get("expires_in", 3600))
                TV_TOKEN_PATH.write_text(json.dumps(data), encoding="utf-8")
                return data["access_token"]
    except Exception:
        pass
    return ""

def probe_video(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True
    )
    try:
        d = json.loads(r.stdout)
        v = (d.get("streams") or [{}])[0]
        dur = float((d.get("format") or {}).get("duration") or 300.0)
        return {"width": int(v.get("width") or 1280), "height": int(v.get("height") or 720), "duration": dur}
    except Exception:
        return {"width": 1280, "height": 720, "duration": 300.0}

def fast_stream_save(stream_url: str, out_file: Path, extra_headers: dict = None) -> bool:
    out_file.unlink(missing_ok=True)
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    aria_cmd = [
        "aria2c", "-x", "16", "-s", "16", "-k", "1M",
        f"--user-agent={ua}",
        "--check-certificate=false",
        "-d", str(out_file.parent), "-o", out_file.name
    ]
    if extra_headers:
        for k, v in extra_headers.items():
            aria_cmd.append(f"--header={k}: {v}")
    aria_cmd.append(stream_url)
    subprocess.run(aria_cmd, capture_output=True, timeout=40)
    if out_file.is_file() and out_file.stat().st_size > 100_000:
        return True
    try:
        hdrs = {"User-Agent": ua}
        if extra_headers:
            hdrs.update(extra_headers)
        with requests.get(stream_url, headers=hdrs, stream=True, timeout=35) as r:
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

# Exact PeakCut studio/media.py _video_format[span_1](start_span)[span_1](end_span)
def _video_format(height: int = 1080) -> str:
    return f"bv*[height<={height}][vcodec^=avc1]+ba[ext=m4a]/bv*[height<={height}]+ba/b[height<={height}]/b"

# ---------------- MASTER 4-ENGINE DOWNLOADER (TV OAUTH + COOKIES + YTDLP + PROXIES) ----------------
def master_video_downloader(url: str, height: int = 1080) -> tuple:
    vid_id = get_id(url)
    stem = vid_id or "video_src"
    out_raw = OUTPUT_DIR / f"{stem}.mp4"
    if out_raw.is_file() and out_raw.stat().st_size > 100_000:
        return out_raw, "Cached", []

    clean_url = f"https://www.youtube.com/watch?v={vid_id}" if vid_id else url.strip()
    has_cookie = COOKIE_SAVED_PATH.is_file() and COOKIE_SAVED_PATH.stat().st_size > 30
    tv_token = get_valid_tv_token()
    error_log = []

    # ENGINE 1: Direct TV OAuth Bearer Token (If user connected TV Code!)
    if tv_token and vid_id:
        for p in OUTPUT_DIR.glob(f"{stem}.*"):
            p.unlink(missing_ok=True)
        ydl_tv_opts = {
            "format": _video_format(height),
            "merge_output_format": "mp4",
            "outtmpl": str(OUTPUT_DIR / f"{stem}.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "logger": _Quiet(),
            "concurrent_fragment_downloads": 4,
            "nocheckcertificate": True,
            "http_headers": {"Authorization": f"Bearer {tv_token}"},
            "extractor_args": {"youtube": {"player_client": ["tv_embedded", "web", "mweb"]}},
        }
        try:
            with yt_dlp.YoutubeDL(ydl_tv_opts) as ydl:
                ydl.download([clean_url])
            files = sorted((p for p in OUTPUT_DIR.glob(f"{stem}.*") if p.suffix not in (".part", ".ytdl")), key=lambda p: p.stat().st_size, reverse=True)
            if files and files[0].stat().st_size > 100_000:
                return files[0], "TV Code OAuth (yt-dlp)", error_log
        except Exception as e:
            error_log.append(f"TV-ytdlp: {str(e)[:120]}")

        # Direct InnerTube TV Player API Call with OAuth Bearer Token (No PoToken needed!)
        try:
            innertube_r = requests.post(
                "https://www.youtube.com/youtubei/v1/player?prettyPrint=false",
                headers={
                    "Authorization": f"Bearer {tv_token}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (ChromiumStylePlatform) Cobalt/Version"
                },
                json={
                    "videoId": vid_id,
                    "context": {
                        "client": {
                            "clientName": "TVHTML5_SIMPLY_EMBEDDED_PLAYER",
                            "clientVersion": "2.0",
                            "hl": "en",
                            "gl": "US"
                        },
                        "thirdParty": {"embedUrl": "https://www.youtube.com/"}
                    }
                },
                timeout=12
            )
            if innertube_r.status_code == 200:
                p_data = innertube_r.json()
                fmts = (p_data.get("streamingData") or {}).get("formats") or []
                for f_item in reversed(fmts):
                    s_url = f_item.get("url")
                    if s_url and fast_stream_save(s_url, out_raw, {"Authorization": f"Bearer {tv_token}"}):
                        return out_raw, "TV InnerTube Direct API", error_log
                error_log.append(f"TV-API status: {(p_data.get('playabilityStatus') or {}).get('reason', 'No direct url')}")
        except Exception as e:
            error_log.append(f"TV-InnerTube: {str(e)[:100]}")

    # ENGINE 2: Pure PeakCut yt-dlp + Auto-Repaired Browser Cookies[span_2](start_span)[span_2](end_span)
    profiles = [
        ("PeakCut Web+Cookies", {}),
        ("PeakCut TV-Embed+Cookies", {"extractor_args": {"youtube": {"player_client": ["tv_embedded", "mweb"]}}}),
        ("PeakCut Creator+Cookies", {"extractor_args": {"youtube": {"player_client": ["web_creator", "mediaconnect"]}}}),
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
                return files[0], label, error_log
        except Exception as e:
            error_log.append(f"{label}: {str(e)[:140]}")

    # ENGINE 3: Public Invidious / Piped Proxy Nodes (Safe JSON Parsing)
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
                if r.status_code == 200 and r.text.strip().startswith("{"):
                    data = r.json()
                    streams = data.get("formatStreams") or data.get("videoStreams") or []
                    for s in streams:
                        if not s.get("videoOnly", False) and s.get("url"):
                            if fast_stream_save(s["url"], out_raw):
                                return out_raw, "Proxy Node API", error_log
            except Exception as e:
                error_log.append(f"Proxy: {str(e)[:80]}")

    return None, "All Engines Refused", error_log

# ---------------- EXACT PEAKCUT RENDER.PY FILTER & ENCODER[span_3](start_span)[span_3](end_span) ----------------
def render_peakcut_short(i: int, src_path: Path, st_time: float, dur: float, src_w: int, src_h: int, layout_choice: str, style_choice: str, res_choice: str) -> Path:
    is_fhd = "1080" in res_choice
    W, H = (1080, 1920) if is_fhd else (720, 1280)
    out_mp4 = OUTPUT_DIR / f"PeakCut_Short_{i+1}_{W}x{H}.mp4"
    out_mp4.unlink(missing_ok=True)

    # Exact PeakCut studio/render.py _filter[span_4](start_span)[span_4](end_span)
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

    # Exact PeakCut studio/render.py _render_in[span_5](start_span)[span_5](end_span)
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

# ---------------- UI: DUAL UNLOCK (TV CODE + COOKIES WITH OK BUTTONS) ----------------
col_u1, col_u2 = st.columns(2)

with col_u1:
    with st.expander("📺 Option A: TV Code Unlock", expanded=not TV_TOKEN_PATH.is_file()):
        if TV_TOKEN_PATH.is_file():
            st.success("✅ **TV Code Connected!**")
            if st.button("🔄 Reset TV Code"):
                TV_TOKEN_PATH.unlink(missing_ok=True)
                st.rerun()
        else:
            if st.button("1️⃣ Get TV Code"):
                try:
                    r = requests.post(
                        "https://www.youtube.com/o/oauth2/device/code",
                        json={"client_id": TV_CLIENT_ID, "scope": "http://gdata.youtube.com https://www.googleapis.com/auth/youtube-paid-content"},
                        timeout=10
                    )
                    if r.status_code == 200:
                        st.session_state["tv_dev"] = r.json()
                    else:
                        st.error("❌ Try again!")
                except Exception as e:
                    st.error(f"Error: {e}")

            if "tv_dev" in st.session_state:
                d = st.session_state["tv_dev"]
                v_url = d.get("verification_url", "https://www.google.com/device")
                u_code = d.get("user_code", "")
                st.warning(f"1. Tap: [{v_url}]({v_url})\n2. Enter Code: **`{u_code}`**")
                if st.button("2️⃣ ✅ Confirm TV Code"):
                    pr = requests.post(
                        "https://www.youtube.com/o/oauth2/token",
                        data={
                            "client_id": TV_CLIENT_ID,
                            "client_secret": TV_CLIENT_SECRET,
                            "code": d["device_code"],
                            "grant_type": "http://oauth.net/grant_type/device/1.0"
                        },
                        timeout=10
                    ).json()
                    if "access_token" in pr:
                        pr["expires_at"] = int(time.time()) + int(pr.get("expires_in", 3600))
                        TV_TOKEN_PATH.write_text(json.dumps(pr), encoding="utf-8")
                        del st.session_state["tv_dev"]
                        st.success("🎉 TV Connected!")
                        time.sleep(0.6)
                        st.rerun()
                    else:
                        st.error("❌ Pehle Google link par code daal kar Allow karein!")

with col_u2:
    with st.expander("🔑 Option B: Cookies Setup", expanded=not COOKIE_SAVED_PATH.is_file()):
        if COOKIE_SAVED_PATH.is_file() and COOKIE_SAVED_PATH.stat().st_size > 30:
            st.success(f"✅ **Cookies Active!** ({COOKIE_SAVED_PATH.stat().st_size} B)")
            if st.button("🗑️ Delete Cookies"):
                COOKIE_SAVED_PATH.unlink(missing_ok=True)
                st.rerun()

        up_ck_file = st.file_uploader("📂 Select cookies.txt", type=["txt"])
        ck_text_box = st.text_area("📋 Or Paste cookies.txt text", height=68, placeholder="# Netscape HTTP Cookie File...")

        if st.button("✅ OK / SAVE COOKIES"):
            raw_ck = ""
            if up_ck_file is not None:
                raw_ck = up_ck_file.getvalue().decode("utf-8", errors="ignore")
            elif ck_text_box.strip():
                raw_ck = ck_text_box.strip()

            if raw_ck:
                cnt = sanitize_and_save_cookies(raw_ck, COOKIE_SAVED_PATH)
                st.success(f"🎉 {cnt} Cookie lines repaired & saved!")
                time.sleep(0.7)
                st.rerun()
            else:
                st.error("❌ Pehle file select karein ya text paste karein!")

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
            
