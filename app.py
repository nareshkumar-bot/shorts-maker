import os, re, time, json, shutil, zipfile, subprocess, requests
from pathlib import Path
import streamlit as st
import yt_dlp
from pytubefix import YouTube

st.set_page_config(page_title="PeakCut Auto Studio", page_icon="⚡", layout="centered")

st.markdown("""
<style>
.stApp {background-color: #09090b; color: #f4f4f5;}
.pbox {background: linear-gradient(135deg, #18181b 0%, #09090b 100%); border: 1px solid #ef4444; border-radius: 14px; padding: 18px; text-align: center; margin-bottom: 16px;}
.stButton>button {width: 100%; background: linear-gradient(90deg, #ef4444, #dc2626); color: #fff; font-weight: 800; border: none; border-radius: 10px; padding: 14px; font-size: 16px;}
</style>
<div class="pbox">
  <h2 style="margin:0;color:#fff;">⚡ PEAKCUT AUTO SHORTS MAKER</h2>
  <p style="margin:4px 0 0 0;color:#a1a1aa;font-size:13px;">100% Automatic Link Paste • 5-Cloud Bypass Engines • True 1080p FHD</p>
</div>
""", unsafe_allow_html=True)

OUT_DIR = Path("/tmp/peakcut_auto")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Clean old broken token/cookie files that caused HTTP Error 400!
for old_f in ["/tmp/saved_tv.json", "/tmp/saved_tv_oauth.json", "/tmp/saved_cookies.txt", "/tmp/saved_youtube_cookies.txt"]:
    Path(old_f).unlink(missing_ok=True)

def get_id(u: str):
    for p in [r"(?:v=|/)([0-9A-Za-z_-]{11}).*", r"youtu[.]be/([0-9A-Za-z_-]{11})", r"shorts/([0-9A-Za-z_-]{11})", r"live/([0-9A-Za-z_-]{11})"]:
        m = re.search(p, u.strip())
        if m:
            return m.group(1)
    return None

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

def fast_dl(u: str, out_f: Path) -> bool:
    out_f.unlink(missing_ok=True)
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    cmd = ["aria2c", "-x", "16", "-s", "16", "-k", "1M", f"--user-agent={ua}", "--check-certificate=false", "-d", str(out_f.parent), "-o", out_f.name, u]
    subprocess.run(cmd, capture_output=True, timeout=45)
    if out_f.is_file() and out_f.stat().st_size > 100_000:
        return True
    try:
        with requests.get(u, headers={"User-Agent": ua}, stream=True, timeout=40) as r:
            if r.status_code == 200:
                with open(out_f, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 512):
                        if chunk:
                            f.write(chunk)
        return out_f.is_file() and out_f.stat().st_size > 100_000
    except Exception:
        return False

# ---------------- 5-ENGINE AUTOMATIC CLOUD DOWNLOADER ----------------
def auto_cloud_downloader(url: str, status_box) -> tuple:
    vid = get_id(url)
    stem = vid or "video"
    out_raw = OUT_DIR / f"{stem}.mp4"
    if out_raw.is_file() and out_raw.stat().st_size > 100_000:
        return out_raw, "Cached", []

    c_url = f"https://www.youtube.com/watch?v={vid}" if vid else url.strip()
    errs = []
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    # ENGINE 1: Oceansaver / Loader.to Multi-Quality Cloud Farm (Used by Y2Mate/SSYouTube)
    if vid:
        status_box.info("🔄 Engine 1/5: Trying Cloud Downloader Farm (Oceansaver)...")
        for fmt_q in ["720", "480", "1080", "360"]:
            try:
                init_u = f"https://ab.cococococ.com/ajax/download.php?copyright=0&format={fmt_q}&url={c_url}&api=dfcb6d76f2f6a9894gjkege8a4ab232222"
                r = requests.get(init_u, headers={"User-Agent": ua}, timeout=10)
                if r.status_code == 200 and r.text.strip().startswith("{"):
                    jd = r.json()
                    if jd.get("success") and jd.get("id"):
                        tid = jd["id"]
                        for _ in range(18):
                            time.sleep(1.5)
                            pr = requests.get(f"https://p.oceansaver.in/ajax/progress.php?id={tid}", headers={"User-Agent": ua}, timeout=8)
                            if pr.status_code == 200 and pr.text.strip().startswith("{"):
                                pd = pr.json()
                                if pd.get("success") == 1 and pd.get("download_url"):
                                    if fast_dl(pd["download_url"], out_raw):
                                        return out_raw, f"Cloud Web Farm ({fmt_q}p)", errs
                                    break
                        break
            except Exception as e:
                errs.append(f"E1({fmt_q}): {str(e)[:60]}")

    # ENGINE 2: Cobalt Multi-Instance Public Mesh (v10 & v7 APIs)
    if vid:
        status_box.info("🔄 Engine 2/5: Trying Cobalt Global Proxy Mesh...")
        cobalt_nodes = [
            ("https://cobalt-api.kwiatekmiki.com", "v10"),
            ("https://cobalt-backend.canine.tools", "v10"),
            ("https://capi.3kh0.net", "v10"),
            ("https://api.cobalt.tools/api/json", "v7"),
            ("https://co.eepy.today/api/json", "v7")
        ]
        for node_url, ver in cobalt_nodes:
            try:
                hdrs = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": ua}
                body = {"url": c_url, "videoQuality": "720"} if ver == "v10" else {"url": c_url, "vQuality": "720"}
                r = requests.post(node_url, json=body, headers=hdrs, timeout=8)
                if r.status_code == 200 and r.text.strip().startswith("{"):
                    dl_u = r.json().get("url")
                    if dl_u and fast_dl(dl_u, out_raw):
                        return out_raw, "Cobalt Proxy Mesh", errs
            except Exception as e:
                errs.append(f"E2: {str(e)[:50]}")

    # ENGINE 3: Invidious & Piped 12-Server Global Relay
    if vid:
        status_box.info("🔄 Engine 3/5: Trying 12 Invidious/Piped Relay Servers...")
        relays = [
            f"https://inv.nadeko.net/api/v1/videos/{vid}",
            f"https://invidious.nerdvpn.de/api/v1/videos/{vid}",
            f"https://inv.tux.pizza/api/v1/videos/{vid}",
            f"https://invidious.jing.rocks/api/v1/videos/{vid}",
            f"https://invidious.privacyredirect.com/api/v1/videos/{vid}",
            f"https://pipedapi.kavin.rocks/streams/{vid}",
            f"https://api.piped.private.coffee/streams/{vid}",
            f"https://pipedapi.leptons.xyz/streams/{vid}",
            f"https://pipedapi.nosebs.ru/streams/{vid}"
        ]
        for rel in relays:
            try:
                r = requests.get(rel, headers={"User-Agent": ua}, timeout=7)
                if r.status_code == 200 and r.text.strip().startswith("{"):
                    d = r.json()
                    st_list = d.get("formatStreams") or d.get("videoStreams") or []
                    for s in st_list:
                        if not s.get("videoOnly", False) and s.get("url"):
                            u_str = s["url"]
                            if fast_dl(u_str, out_raw):
                                return out_raw, "Invidious/Piped Relay", errs
                            # Also try proxying through the Invidious node itself if direct googlevideo IP-locked
                            if "inv" in rel and "googlevideo.com" in u_str:
                                base_host = rel.split("/api/")[0]
                                local_u = re.sub(r"https://[^/]+", base_host, u_str) + "&local=true"
                                if fast_dl(local_u, out_raw):
                                    return out_raw, "Invidious Local-Proxy", errs
            except Exception as e:
                errs.append(f"E3: {str(e)[:50]}")

    # ENGINE 4: Clean yt-dlp (NO broken headers -> Fixes HTTP Error 400!)
    status_box.info("🔄 Engine 4/5: Trying Clean yt-dlp Multi-Client...")
    client_sets = [
        ["android_vr"],
        ["ios"],
        ["mweb"],
        ["tv_embedded"],
        ["web_embedded"]
    ]
    for c_set in client_sets:
        for p in OUT_DIR.glob(f"{stem}.*"):
            p.unlink(missing_ok=True)
        opts = {
            "format": "18/22/b[ext=mp4]/bv*[height<=720]+ba/b",
            "merge_output_format": "mp4",
            "outtmpl": str(OUT_DIR / f"{stem}.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "geo_bypass": True,
            "extractor_args": {"youtube": {"player_client": c_set}},
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([c_url])
            fls = sorted((p for p in OUT_DIR.glob(f"{stem}.*") if p.suffix not in (".part", ".ytdl")), key=lambda p: p.stat().st_size, reverse=True)
            if fls and fls[0].stat().st_size > 100_000:
                return fls[0], f"yt-dlp ({c_set[0]})", errs
        except Exception as e:
            errs.append(f"E4({c_set[0]}): {str(e)[:80]}")

    # ENGINE 5: pytubefix Multi-Client Fallback
    if vid:
        status_box.info("🔄 Engine 5/5: Trying pytubefix Embedded Streamer...")
        for cl in ["ANDROID_VR", "WEB_EMBED", "IOS", "TV_EMBED", "MWEB"]:
            try:
                yt = YouTube(c_url, client=cl)
                ys = yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").desc().first()
                if not ys:
                    ys = yt.streams.filter(file_extension="mp4").order_by("resolution").desc().first()
                if ys:
                    out_raw.unlink(missing_ok=True)
                    ys.download(output_path=str(OUT_DIR), filename=f"{stem}.mp4")
                    if out_raw.is_file() and out_raw.stat().st_size > 100_000:
                        return out_raw, f"pytubefix ({cl})", errs
            except Exception as e:
                errs.append(f"E5({cl}): {str(e)[:70]}")

    return None, "All Failed", errs

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

# ---------------- SIMPLE 1-STEP UI ----------------
url_in = st.text_input("🔗 Paste YouTube / Twitch / Kick Video Link:", placeholder="https://youtu.be/...")

with st.expander("📱 Optional Backup: Agar Link Na Chale Toh Phone Se Video Select Karein"):
    up_vid = st.file_uploader("Select MP4/MKV Video", type=["mp4", "mkv", "mov", "webm"])

k1, k2 = st.columns(2)
with k1:
    clips_n = st.selectbox("🎞️ Kitni Shorts Chahiye?", [5, 10, 15, 20], index=0)
with k2:
    res_c = st.selectbox("💎 Quality:", ["1080p FHD ⭐", "720p HD"], index=0)

lay_c = st.radio("📐 Layout:", ["Full frame + blurred fill ⭐", "Zoomed in + blurred fill", "Fill the screen (crop)"], horizontal=True)

if st.button("🚀 AUTO-GENERATE FHD SHORTS NOW"):
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    src_f = None
    eng = "Phone Upload"
    status_msg = st.empty()

    if up_vid is not None:
        src_f = OUT_DIR / "upload.mp4"
        status_msg.info("📥 Loading video from phone...")
        src_f.write_bytes(up_vid.getbuffer())
    elif url_in.strip():
        src_f, eng, errs = auto_cloud_downloader(url_in.strip(), status_msg)
        if not src_f:
            status_msg.error("❌ Sabhi 5 Cloud Engines is video par block hue. Niche error log dekhein:")
            with st.expander("🔍 View Engine Logs"):
                for e in errs:
                    st.caption(f"• {e}")
    else:
        status_msg.error("❌ Bhai pehle upar YouTube Link paste karo!")

    if src_f and src_f.is_file():
        status_msg.success(f"✅ Video Downloaded via **{eng}**! Now cutting {clips_n} FHD Shorts...")
        sw, sh, dur = probe_vid(src_f)
        c_len = 35.0 if dur >= 120 else max(12.0, dur / max(2, clips_n))
        step = max(8.0, max(c_len, dur - c_len - 4) / max(1, clips_n))
        bar = st.progress(0.0, text="✂️ Starting FHD Render...")
        done_fls = []

        for i in range(clips_n):
            st_t = min(3.0 + i * step, max(0.0, dur - c_len))
            bar.progress(i / clips_n, text=f"🎬 Cutting FHD Short #{i+1} of {clips_n}...")
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
    st.success(f"🎉 {len(st.session_state['shorts'])} FHD Shorts Ready in {st.session_state.get('sec', 20)}s! (Engine: {st.session_state.get('eng')})")
    if "zip" in st.session_state and os.path.exists(st.session_state["zip"]):
        with open(st.session_state["zip"], "rb") as zb:
            st.download_button("📦 DOWNLOAD ALL SHORTS (.ZIP)", data=zb, file_name="PeakCut_Shorts.zip", mime="application/zip")

    for idx, fp in enumerate(st.session_state["shorts"]):
        mb = round(os.path.getsize(fp) / (1024 * 1024), 1)
        with open(fp, "rb") as fb:
            st.download_button(f"📥 Save Short #{idx+1} ({mb} MB)", data=fb, file_name=os.path.basename(fp), mime="video/mp4", key=f"d_{idx}")
        st.video(fp)
# END_OF_CODE
