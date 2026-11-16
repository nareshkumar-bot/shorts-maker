import os, re, time, json, shutil, zipfile, subprocess, requests
from pathlib import Path
import streamlit as st
import yt_dlp

st.set_page_config(page_title="PeakCut Studio", page_icon="✂️", layout="centered")

st.markdown("""
<style>
.stApp {background-color: #09090b; color: #f4f4f5;}
.pbox {background: #121215; border: 1px solid #27272a; border-radius: 12px; padding: 16px; text-align: center; margin-bottom: 14px;}
.stButton>button {width: 100%; background: #ef4444; color: #fff; font-weight: 700; border: none; border-radius: 8px; padding: 10px;}
</style>
<div class="pbox">
  <h2 style="margin:0;color:#fff;">✂️ PEAKCUT STUDIO (1080p FHD)</h2>
  <p style="margin:4px 0 0 0;color:#a1a1aa;font-size:13px;">TV Code + Cookies OK Button + PeakCut 1080p Engine</p>
</div>
""", unsafe_allow_html=True)

OUT_DIR = Path("/tmp/peakcut_jobs")
CK_PATH = Path("/tmp/saved_cookies.txt")
TV_PATH = Path("/tmp/saved_tv.json")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TV_ID = "861556708454-d6dlm3lh05idd8npek18k6be8ba3oc68.apps.googleusercontent.com"
TV_SEC = "SboVhoG9s0rNafixCSGGKXAT"

def get_id(u):
    for p in [r"(?:v=|/)([0-9A-Za-z_-]{11}).*", r"youtu[.]be/([0-9A-Za-z_-]{11})", r"shorts/([0-9A-Za-z_-]{11})"]:
        m = re.search(p, u.strip())
        if m:
            return m.group(1)
    return None

def save_cookies(raw):
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

def get_tv_tok():
    if not TV_PATH.is_file():
        return ""
    try:
        d = json.loads(TV_PATH.read_text())
        if time.time() < d.get("expires_at", 0) - 60:
            return d.get("access_token", "")
        if d.get("refresh_token"):
            url = "https://www.youtube.com/o/oauth2/token"
            pl = {"client_id": TV_ID, "client_secret": TV_SEC, "refresh_token": d["refresh_token"], "grant_type": "refresh_token"}
            r = requests.post(url, data=pl, timeout=10).json()
            if "access_token" in r:
                d["access_token"] = r["access_token"]
                d["expires_at"] = int(time.time()) + int(r.get("expires_in", 3600))
                TV_PATH.write_text(json.dumps(d))
                return d["access_token"]
    except Exception:
        pass
    return ""

def probe_vid(p):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(p)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        v = (d.get("streams") or [{}])[0]
        dur = float((d.get("format") or {}).get("duration") or 300.0)
        return int(v.get("width") or 1280), int(v.get("height") or 720), dur
    except Exception:
        return 1280, 720, 300.0

def fast_dl(u, out_f, hdr=None):
    out_f.unlink(missing_ok=True)
    cmd = ["aria2c", "-x", "16", "-s", "16", "-k", "1M", "--check-certificate=false", "-d", str(out_f.parent), "-o", out_f.name]
    if hdr:
        for k, v in hdr.items():
            cmd.append(f"--header={k}: {v}")
    cmd.append(u)
    subprocess.run(cmd, capture_output=True, timeout=40)
    return out_f.is_file() and out_f.stat().st_size > 100000

def download_master(url, h=1080):
    vid = get_id(url)
    stem = vid or "src"
    out_raw = OUT_DIR / f"{stem}.mp4"
    if out_raw.is_file() and out_raw.stat().st_size > 100000:
        return out_raw, "Cached", []

    c_url = f"https://www.youtube.com/watch?v={vid}" if vid else url.strip()
    has_ck = CK_PATH.is_file() and CK_PATH.stat().st_size > 30
    tok = get_tv_tok()
    errs = []
    fmt = f"bv*[height<={h}][vcodec^=avc1]+ba[ext=m4a]/bv*[height<={h}]+ba/b[height<={h}]/b"

    if tok and vid:
        try:
            p_url = "https://www.youtube.com/youtubei/v1/player?prettyPrint=false"
            hd = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
            ctx = {"client": {"clientName": "TVHTML5_SIMPLY_EMBEDDED_PLAYER", "clientVersion": "2.0", "hl": "en", "gl": "US"}, "thirdParty": {"embedUrl": "https://www.youtube.com/"}}
            r = requests.post(p_url, headers=hd, json={"videoId": vid, "context": ctx}, timeout=12)
            if r.status_code == 200:
                for f in reversed((r.json().get("streamingData") or {}).get("formats") or []):
                    if f.get("url") and fast_dl(f["url"], out_raw, {"Authorization": f"Bearer {tok}"}):
                        return out_raw, "TV Direct API", errs
        except Exception as e:
            errs.append(f"TV-API: {str(e)[:80]}")

    runs = [
        ("PeakCut Web", {}),
        ("PeakCut TV", {"extractor_args": {"youtube": {"player_client": ["tv_embedded", "mweb"]}}})
    ]
    for lbl, ex in runs:
        for p in OUT_DIR.glob(f"{stem}.*"):
            p.unlink(missing_ok=True)
        opts = {
            "format": fmt,
            "merge_output_format": "mp4",
            "outtmpl": str(OUT_DIR / f"{stem}.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "concurrent_fragment_downloads": 4,
            "nocheckcertificate": True,
            **ex
        }
        if has_ck:
            opts["cookiefile"] = str(CK_PATH)
        if tok:
            opts["http_headers"] = {"Authorization": f"Bearer {tok}"}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([c_url])
            fls = sorted((p for p in OUT_DIR.glob(f"{stem}.*") if p.suffix not in (".part", ".ytdl")), key=lambda p: p.stat().st_size, reverse=True)
            if fls and fls[0].stat().st_size > 100000:
                return fls[0], lbl, errs
        except Exception as e:
            errs.append(f"{lbl}: {str(e)[:100]}")

    return None, "Blocked", errs

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
    return out_p if out_p.is_file() and out_p.stat().st_size > 10000 else None

c_a, c_b = st.columns(2)

with c_a:
    st.markdown("##### 📺 Option A: TV Code")
    if TV_PATH.is_file():
        st.success("✅ TV Connected!")
        if st.button("🔄 Reset TV"):
            TV_PATH.unlink(missing_ok=True)
            st.rerun()
    else:
        if st.button("1️⃣ Get TV Code"):
            u = "https://www.youtube.com/o/oauth2/device/code"
            sc = "http://gdata.youtube.com https://www.googleapis.com/auth/youtube-paid-content"
            r = requests.post(u, json={"client_id": TV_ID, "scope": sc}, timeout=10)
            if r.status_code == 200:
                st.session_state["tvd"] = r.json()
        if "tvd" in st.session_state:
            d = st.session_state["tvd"]
            vu = d.get("verification_url", "https://www.google.com/device")
            st.warning(f"1. Open: [{vu}]({vu})\n2. Code: **`{d.get('user_code')}`**")
            if st.button("2️⃣ ✅ Confirm TV Code"):
                u = "https://www.youtube.com/o/oauth2/token"
                pl = {"client_id": TV_ID, "client_secret": TV_SEC, "code": d["device_code"], "grant_type": "http://oauth.net/grant_type/device/1.0"}
                pr = requests.post(u, data=pl, timeout=10).json()
                if "access_token" in pr:
                    pr["expires_at"] = int(time.time()) + int(pr.get("expires_in", 3600))
                    TV_PATH.write_text(json.dumps(pr))
                    del st.session_state["tvd"]
                    st.rerun()
                else:
                    st.error("❌ Pehle Google par code Allow karein!")

with c_b:
    st.markdown("##### 🔑 Option B: Cookies")
    if CK_PATH.is_file() and CK_PATH.stat().st_size > 30:
        st.success("✅ Cookies Active!")
        if st.button("🗑️ Delete Cookies"):
            CK_PATH.unlink(missing_ok=True)
            st.rerun()
    up_ck = st.file_uploader("📂 cookies.txt file", type=["txt"])
    txt_ck = st.text_area("📋 Or Paste cookies", height=60)
    if st.button("✅ OK / SAVE COOKIES"):
        raw = up_ck.getvalue().decode("utf-8", errors="ignore") if up_ck else txt_ck.strip()
        if raw:
            n = save_cookies(raw)
            st.success(f"🎉 {n} Cookies Saved!")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("❌ File ya text daalein!")

st.markdown("---")
mode = st.radio("📥 Video Input:", ["🔗 Video Link", "📱 Upload Video From Phone"], horizontal=True)
url_in = st.text_input("🔗 Paste Link:") if "Link" in mode else ""
up_vid = st.file_uploader("📱 Select MP4/MKV:", type=["mp4", "mkv", "mov", "webm"]) if "Upload" in mode else None

k1, k2 = st.columns(2)
with k1:
    clips_n = st.selectbox("🎞️ Clips:", [5, 10, 15, 20], index=0)
with k2:
    res_c = st.selectbox("💎 Quality:", ["1080p FHD ⭐", "720p HD"], index=0)

lay_c = st.radio("📐 Layout:", ["Full frame + blurred fill ⭐", "Zoomed in + blurred fill", "Fill the screen (crop)"], horizontal=True)

if st.button("🚀 MAKE PEAKCUT FHD SHORTS NOW"):
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    src_f = None
    eng = "Phone Upload"

    if up_vid is not None:
        src_f = OUT_DIR / "upload.mp4"
        with st.spinner("📥 Saving video..."):
            src_f.write_bytes(up_vid.getbuffer())
    elif url_in.strip():
        with st.spinner("⚡ Downloading video..."):
            th = 1080 if "1080" in res_c else 720
            src_f, eng, errs = download_master(url_in.strip(), th)
        if not src_f:
            st.error("❌ Cloud IP Blocked! Logs dekhein ya Phone se Video Upload karein:")
            for e in errs:
                st.caption(f"• {e}")
    else:
        st.error("❌ Link daalein ya Video select karein!")

    if src_f and src_f.is_file():
        sw, sh, dur = probe_vid(src_f)
        c_len = 35.0 if dur >= 120 else max(12.0, dur / max(2, clips_n))
        step = max(8.0, max(c_len, dur - c_len - 4) / max(1, clips_n))
        bar = st.progress(0.0)
        done_fls = []

        for i in range(clips_n):
            st_t = min(3.0 + i * step, max(0.0, dur - c_len))
            bar.progress(i / clips_n)
            out_p = render_short(i, src_f, st_t, c_len, sw, sh, lay_c, res_c)
            if out_p:
                done_fls.append(out_p)
            bar.progress((i + 1) / clips_n)

        if done_fls:
            zp = OUT_DIR / "PeakCut_Shorts.zip"
            with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
                for f in done_fls:
                    z.write(f, f.name)
            st.session_state["shorts"] = [str(f) for f in done_fls]
            st.session_state["zip"] = str(zp)
            st.session_state["sec"] = int(time.time() - t0)

if "shorts" in st.session_state and st.session_state["shorts"]:
    st.success(f"🎉 {len(st.session_state['shorts'])} FHD Shorts Ready in {st.session_state.get('sec', 20)}s!")
    if "zip" in st.session_state and os.path.exists(st.session_state["zip"]):
        with open(st.session_state["zip"], "rb") as zb:
            st.download_button("📦 DOWNLOAD ALL (.ZIP)", data=zb, file_name="PeakCut_Shorts.zip", mime="application/zip")

    for idx, fp in enumerate(st.session_state["shorts"]):
        mb = round(os.path.getsize(fp) / (1024 * 1024), 1)
        with open(fp, "rb") as fb:
            st.download_button(f"📥 Save Short #{idx+1} ({mb} MB)", data=fb, file_name=os.path.basename(fp), mime="video/mp4", key=f"d_{idx}")
        st.video(fp)
# END_OF_CODE
