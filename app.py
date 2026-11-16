import os, re, time, json, shutil, zipfile, subprocess, requests
from pathlib import Path
import streamlit as st
import yt_dlp

st.set_page_config(page_title="PeakCut Studio", page_icon="⚡", layout="centered")

st.markdown("""
<style>
.stApp {background-color: #09090b; color: #f4f4f5;}
.pbox {background: #121215; border: 1px solid #ef4444; border-radius: 12px; padding: 16px; text-align: center; margin-bottom: 14px;}
.stButton>button {width: 100%; background: #ef4444; color: #fff; font-weight: 700; border: none; border-radius: 8px; padding: 12px;}
</style>
<div class="pbox">
  <h2 style="margin:0;color:#fff;">⚡ PEAKCUT STUDIO (1080p FHD)</h2>
  <p style="margin:4px 0 0 0;color:#a1a1aa;font-size:13px;">Anti-403 VR Engine • Clean Cookie Bypass • Residential Proxy</p>
</div>
""", unsafe_allow_html=True)

OUT_DIR = Path("/tmp/peakcut_jobs")
CK_PATH = Path("/tmp/clean_cookies.txt")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def get_id(u: str):
    for p in [r"(?:v=|/)([0-9A-Za-z_-]{11}).*", r"youtu[.]be/([0-9A-Za-z_-]{11})", r"shorts/([0-9A-Za-z_-]{11})", r"live/([0-9A-Za-z_-]{11})"]:
        m = re.search(p, u.strip())
        if m:
            return m.group(1)
    return None

def save_clean_cookies(raw: str) -> int:
    lines = ["# Netscape HTTP Cookie File"]
    cnt = 0
    for ln in raw.splitlines():
        s = ln.strip()
        if s.startswith("#HttpOnly_"):
            s = s[10:]
        elif not s or s.startswith("#"):
            continue
        pts = s.split("\t")
        if len(pts) < 7:
            pts = re.split(r"\s+", s, maxsplit=6)
        if len(pts) >= 7:
            dom = pts[0]
            flg = "TRUE" if dom.startswith(".") else "FALSE"
            pth = pts[2] if pts[2].startswith("/") else "/"
            sec = "TRUE" if pts[3].upper() == "TRUE" else "FALSE"
            exp = re.sub(r"[^0-9]", "", pts[4]) or "1893456000"
            lines.append(f"{dom}\t{flg}\t{pth}\t{sec}\t{exp}\t{pts[5]}\t{pts[6].strip()}")
            cnt += 1
    CK_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return cnt

def probe_vid(p: Path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(p)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        v = (d.get("streams") or [{}])[0]
        dur = float((d.get("format") or {}).get("duration") or 300.0)
        return int(v.get("width") or 1280), int(v.get("height") or 720), dur
    except Exception:
        return 1280, 720, 300.0

def get_working_proxies() -> list:
    proxies = []
    try:
        u = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=3000&country=all&ssl=yes&anonymity=elite"
        r = requests.get(u, timeout=5)
        if r.status_code == 200:
            for ln in r.text.splitlines()[:8]:
                if ":" in ln:
                    proxies.append(f"http://{ln.strip()}")
    except Exception:
        pass
    return proxies

def smart_download(url: str, h: int, user_proxy: str, status_box) -> tuple:
    vid = get_id(url)
    stem = vid or "video"
    out_raw = OUT_DIR / f"{stem}.mp4"
    if out_raw.is_file() and out_raw.stat().st_size > 100_000:
        return out_raw, "Cached", []

    c_url = f"https://www.youtube.com/watch?v={vid}" if vid else url.strip()
    has_ck = CK_PATH.is_file() and CK_PATH.stat().st_size > 30
    errs = []

    # STRATEGY 1: If Cookies are present -> Pure Web/MWeb Client (NO Authorization header -> Zero HTTP 400!)
    if has_ck:
        status_box.info("🔄 Step 1: Downloading with your Saved Cookies (Pure Browser Mode)...")
        ck_clients = [
            ("Cookies + Default Web", {}),
            ("Cookies + MWeb/TV", {"extractor_args": {"youtube": {"player_client": ["mweb", "tv_embedded"]}}}),
            ("Cookies + Creator", {"extractor_args": {"youtube": {"player_client": ["web_creator"]}}})
        ]
        for lbl, ex in ck_clients:
            for p in OUT_DIR.glob(f"{stem}.*"):
                p.unlink(missing_ok=True)
            opts = {
                "format": f"bv*[height<={h}][vcodec^=avc1]+ba[ext=m4a]/b[ext=mp4]/18/22/b",
                "merge_output_format": "mp4",
                "outtmpl": str(OUT_DIR / f"{stem}.%(ext)s"),
                "cookiefile": str(CK_PATH),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "nocheckcertificate": True,
                "concurrent_fragment_downloads": 4,
                **ex
            }
            if user_proxy:
                opts["proxy"] = user_proxy
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([c_url])
                fls = sorted((p for p in OUT_DIR.glob(f"{stem}.*") if p.suffix not in (".part", ".ytdl")), key=lambda p: p.stat().st_size, reverse=True)
                if fls and fls[0].stat().st_size > 100_000:
                    return fls[0], lbl, errs
            except Exception as e:
                errs.append(f"{lbl}: {str(e)[:110]}")

    # STRATEGY 2: Anti-403 Android VR & TV Embedded (Passed Bot Check in your logs! Tuned to avoid 403)
    status_box.info("🔄 Step 2: Trying Anti-403 Tuned Android_VR & TV_Embedded...")
    vr_profiles = [
        ("Android_VR (HLS/ Dash Tuned)", ["android_vr"], "18/b[ext=mp4]/bv*[height<=720]+ba/b"),
        ("TV_Embedded (HLS Tuned)", ["tv_embedded"], "18/b[ext=mp4]/bv*[height<=720]+ba/b"),
        ("Android_Testsuite", ["android_testsuite"], "18/b[ext=mp4]/b")
    ]
    for lbl, cl_list, fmt_str in vr_profiles:
        for p in OUT_DIR.glob(f"{stem}.*"):
            p.unlink(missing_ok=True)
        opts = {
            "format": fmt_str,
            "merge_output_format": "mp4",
            "outtmpl": str(OUT_DIR / f"{stem}.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "geo_bypass": True,
            "http_chunk_size": 10485760,
            "extractor_args": {
                "youtube": {
                    "player_client": cl_list,
                    "player_skip": ["webpage", "configs"]
                }
            }
        }
        if user_proxy:
            opts["proxy"] = user_proxy
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([c_url])
            fls = sorted((p for p in OUT_DIR.glob(f"{stem}.*") if p.suffix not in (".part", ".ytdl")), key=lambda p: p.stat().st_size, reverse=True)
            if fls and fls[0].stat().st_size > 100_000:
                return fls[0], lbl, errs
        except Exception as e:
            errs.append(f"{lbl}: {str(e)[:110]}")

    # STRATEGY 3: Auto-Rotating Proxy + Android_VR
    status_box.info("🔄 Step 3: Trying Auto-Rotating Proxy Pool...")
    proxy_list = [user_proxy] if user_proxy else get_working_proxies()
    for px in proxy_list[:4]:
        if not px:
            continue
        for p in OUT_DIR.glob(f"{stem}.*"):
            p.unlink(missing_ok=True)
        opts = {
            "format": "18/b[ext=mp4]/b",
            "outtmpl": str(OUT_DIR / f"{stem}.%(ext)s"),
            "proxy": px,
            "socket_timeout": 8,
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "extractor_args": {"youtube": {"player_client": ["android_vr", "tv_embedded"]}}
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([c_url])
            fls = sorted((p for p in OUT_DIR.glob(f"{stem}.*") if p.suffix not in (".part", ".ytdl")), key=lambda p: p.stat().st_size, reverse=True)
            if fls and fls[0].stat().st_size > 100_000:
                return fls[0], f"Proxy ({px})", errs
        except Exception as e:
            errs.append(f"Proxy({px}): {str(e)[:70]}")

    return None, "All Blocked", errs

# Exact PeakCut studio/render.py layout & loudnorm engine[span_0](start_span)[span_0](end_span)
def render_short(i, src_p, st_t, dur, sw, sh, lay, res):
    W, H = (1080, 1920) if "1080" in res else (720, 1280)
    out_p = OUT_DIR / f"PeakCut_Short_{i+1}_{W}x{H}.mp4"
    out_p.unlink(missing_ok=True)

    if "Full frame" in lay:
        fh = min(H, int(round(W * sh / max(1, sw) / 2)) * 2)
        vf = f"[0:v]fps=30,split=2[a][b];[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,scale={W}:{H},eq=brightness=-0.14:saturation=1.15[bg];[b]scale={W}:{fh}:force_original_aspect_ratio=increase,crop={W}:{fh}[fg];[bg][fg]overlay=0:(H-h)/2,setsar=1[v]"
    elif "Zoomed" in lay:
        fh = int(H * 0.52)
        vf = f"[0:v]fps=30,split=2[a][b];[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,scale={W}:{H},eq=brightness=-0.14:saturation=1.15[bg];[b]scale={W}:{fh}:force_original_aspect_ratio=increase,crop={W}:{fh}[fg];[bg][fg]overlay=0:(H-h)/2,setsar=1[v]"
    else:
        vf = f"[0:v]fps=30,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[v]"

    cmd = [
        "ffmpeg", "-y", "-v", "error", "-ss", f"{st_t:.2f}", "-t", f"{dur:.2f}", "-i", str(src_p),
        "-filter_complex", vf, "-map", "[v]", "-map", "0:a:0?", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", str(out_p)
    ]
    subprocess.run(cmd, capture_output=True)
    return out_p if out_p.is_file() and out_p.stat().st_size > 10_000 else None

# ---------------- UI: CLEAN COOKIE & PROXY SETUP ----------------
with st.expander("🔑 Step 1: Clean Cookies Setup (HTTP 400 Bug Fixed!)", expanded=not CK_PATH.is_file()):
    if CK_PATH.is_file() and CK_PATH.stat().st_size > 30:
        st.success(f"✅ Clean Cookies Active! ({CK_PATH.stat().st_size} bytes)")
        if st.button("🗑️ Delete Saved Cookies"):
            CK_PATH.unlink(missing_ok=True)
            st.rerun()

    up_ck = st.file_uploader("📂 Select cookies.txt from phone", type=["txt"])
    txt_ck = st.text_area("📋 Or Paste cookies.txt text here", height=70)
    custom_px = st.text_input("🌐 Optional Proxy (e.g. http://user:pass@ip:port):", value="")

    if st.button("✅ OK / SAVE CLEAN COOKIES"):
        raw = up_ck.getvalue().decode("utf-8", errors="ignore") if up_ck else txt_ck.strip()
        if raw:
            n = save_clean_cookies(raw)
            st.success(f"🎉 {n} Clean Cookies Saved (No Bad Headers)!")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("❌ Pehle cookies file select karein ya text paste karein!")

# ---------------- MAIN INPUT UI ----------------
mode = st.radio("📥 Select Method:", ["🔗 Paste YouTube Link", "📱 Upload Video From Phone (100% Guaranteed)"], horizontal=True)

url_in = ""
up_vid = None

if "Link" in mode:
    url_in = st.text_input("🔗 Paste YouTube / Twitch / Kick Link:", placeholder="https://youtu.be/...")
else:
    st.info("💡 Niche किसी भी 1 बटन पर टैप करके अपने फोन में वीडियो सेव करें, फिर नीचे सेलेक्ट करें (Phone IP को YouTube कभी ब्लॉक नहीं करता!):")
    c_d1, c_d2 = st.columns(2)
    with c_d1:
        st.link_button("⚡ 1. Download via Y2Mate", "https://www.y2mate.com", use_container_width=True)
    with c_d2:
        st.link_button("🌐 2. Download via SaveFrom", "https://en.savefrom.net", use_container_width=True)
    up_vid = st.file_uploader("📱 Phone se MP4/MKV Video Chunein:", type=["mp4", "mkv", "mov", "webm"])

k1, k2 = st.columns(2)
with k1:
    clips_n = st.selectbox("🎞️ Kitni Shorts Chahiye?", [5, 10, 15, 20], index=0)
with k2:
    res_c = st.selectbox("💎 Quality:", ["1080p FHD ⭐", "720p HD"], index=0)

lay_c = st.radio("📐 PeakCut Layout:", ["Full frame + blurred fill ⭐", "Zoomed in + blurred fill", "Fill the screen (crop)"], horizontal=True)

if st.button("🚀 GENERATE PEAKCUT FHD SHORTS"):
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    src_f = None
    eng = "Phone Upload"
    status_msg = st.empty()

    if up_vid is not None:
        src_f = OUT_DIR / "upload.mp4"
        status_msg.info("📥 Saving video from phone...")
        src_f.write_bytes(up_vid.getbuffer())
    elif url_in.strip():
        th = 1080 if "1080" in res_c else 720
        src_f, eng, errs = smart_download(url_in.strip(), th, custom_px.strip(), status_msg)
        if not src_f:
            status_msg.error("❌ AWS Cloud IP Blocked by YouTube! Upay: Upar '🔑 Step 1' mein fresh cookies.txt save karein YA '📱 Upload Video From Phone' par tap karein.")
            with st.expander("🔍 View Technical Logs"):
                for e in errs:
                    st.caption(f"• {e}")
    else:
        status_msg.error("❌ Link daalein ya Video select karein!")

    if src_f and src_f.is_file():
        status_msg.success(f"✅ Video Ready via **{eng}**! Rendering {clips_n} FHD Shorts...")
        sw, sh, dur = probe_vid(src_f)
        c_len = 35.0 if dur >= 120 else max(12.0, dur / max(2, clips_n))
        step = max(8.0, max(c_len, dur - c_len - 4) / max(1, clips_n))
        bar = st.progress(0.0, text="✂️ Rendering PeakCut 1080p Shorts...")
        done_fls = []

        for i in range(clips_n):
            st_t = min(3.0 + i * step, max(0.0, dur - c_len))
            bar.progress(i / clips_n, text=f"🎬 Cutting Short #{i+1}/{clips_n}...")
            out_p = render_short(i, src_f, st_t, c_len, sw, sh, lay_c, res_c)
            if out_p:
                done_fls.append(out_p)
            bar.progress((i + 1) / clips_n, text=f"✅ Short #{i+1}/{clips_n} Ready!")

        if done_fls:
            zp = OUT_DIR / "PeakCut_Shorts.zip"
            with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
                for f in done_fls:
                    z.write(f, f.name)
            st.session_state["shorts"] = [str(f) for f in done_fls]
            st.session_state["zip"] = str(zp)
            st.session_state["sec"] = int(time.time() - t0)
            st.session_state["eng"] = eng
            status_msg.empty()

if "shorts" in st.session_state and st.session_state["shorts"]:
    st.success(f"🎉 {len(st.session_state['shorts'])} FHD Shorts Ready in {st.session_state.get('sec', 20)}s! ({st.session_state.get('eng')})")
    if "zip" in st.session_state and os.path.exists(st.session_state["zip"]):
        with open(st.session_state["zip"], "rb") as zb:
            st.download_button("📦 DOWNLOAD ALL SHORTS (.ZIP)", data=zb, file_name="PeakCut_Shorts.zip", mime="application/zip")

    for idx, fp in enumerate(st.session_state["shorts"]):
        mb = round(os.path.getsize(fp) / (1024 * 1024), 1)
        with open(fp, "rb") as fb:
            st.download_button(f"📥 Save Short #{idx+1} ({mb} MB)", data=fb, file_name=os.path.basename(fp), mime="video/mp4", key=f"d_{idx}")
        st.video(fp)
# END_OF_CODE
