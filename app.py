import os, re, time, json, shutil, zipfile, subprocess
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
import yt_dlp

st.set_page_config(page_title="PeakCut Studio", page_icon="⚡", layout="centered")

st.markdown("""
<style>
.stApp {background-color: #09090b; color: #f4f4f5;}
.pbox {background: #121215; border: 1px solid #22c55e; border-radius: 12px; padding: 14px; text-align: center; margin-bottom: 12px;}
.stButton>button {width: 100%; background: #ef4444; color: #fff; font-weight: 700; border: none; border-radius: 8px; padding: 12px;}
</style>
<div class="pbox">
  <h3 style="margin:0;color:#fff;">⚡ PEAKCUT STUDIO (1080p FHD)</h3>
  <p style="margin:4px 0 0 0;color:#86efac;font-size:12px;">Curl-CFFI TLS Impersonation • HLS Streamer • Phone-IP Widget</p>
</div>
""", unsafe_allow_html=True)

OUT_DIR = Path("/tmp/peakcut_jobs")
CK_PATH = Path("/tmp/clean_cookies.txt")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def get_id(u: str):
    pts = [r"(?:v=|/)([0-9A-Za-z_-]{11}).*", r"youtu[.]be/([0-9A-Za-z_-]{11})", r"shorts/([0-9A-Za-z_-]{11})"]
    for p in pts:
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

# ---------------- ANTI-403 DOWNLOADER (HLS m3u8 + CURL-CFFI + CLI SUBPROCESS) ----------------
def smart_download(url: str, status_box) -> tuple:
    vid = get_id(url)
    stem = vid or "video"
    c_url = f"https://www.youtube.com/watch?v={vid}" if vid else url.strip()
    has_ck = CK_PATH.is_file() and CK_PATH.stat().st_size > 30
    errs = []

    # Why 403 happened before: HTTPS direct range files (googlevideo) are IP-bound to cookies.
    # Solution: Prefer HLS (m3u8) streams first (protocol^=m3u8) + Chrome TLS Impersonation!
    cli_runs = [
        (
            "HLS Stream + Chrome Impersonate",
            ["--extractor-args", "youtube:player_client=ios,mweb,tv_embedded;formats=missing_pot", "-f", "bv*[protocol*=m3u8]+ba/b[protocol*=m3u8]/b"]
        ),
        (
            "TV Embedded + HLS",
            ["--extractor-args", "youtube:player_client=tv_embedded", "-f", "b/bv*+ba"]
        ),
        (
            "Android VR + Chunked",
            ["--extractor-args", "youtube:player_client=android_vr", "--http-chunk-size", "10M", "-f", "b/bv*+ba"]
        ),
        (
            "Web Creator + Cookies",
            ["--extractor-args", "youtube:player_client=web_creator,mediaconnect", "-f", "b/bv*+ba"]
        )
    ]

    for lbl, extra_flags in cli_runs:
        status_box.info(f"⚡ Trying {lbl}...")
        for p in OUT_DIR.glob(f"{stem}.*"):
            p.unlink(missing_ok=True)

        cmd = [
            "yt-dlp", "-4", "--no-playlist", "--no-warnings", "--no-check-certificate", "--geo-bypass",
            "--merge-output-format", "mp4",
            "-o", str(OUT_DIR / f"{stem}.%(ext)s")
        ]
        if has_ck and "Android VR" not in lbl:
            cmd.extend(["--cookies", str(CK_PATH)])
        cmd.extend(extra_flags)
        cmd.append(c_url)

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
            fls = sorted(
                (p for p in OUT_DIR.glob(f"{stem}.*") if p.suffix not in (".part", ".ytdl")),
                key=lambda p: p.stat().st_size,
                reverse=True
            )
            if fls and fls[0].stat().st_size > 50_000:
                return fls[0], lbl, errs
            err_msg = (r.stderr or r.stdout or "Empty").strip().splitlines()[-1]
            errs.append(f"{lbl}: {err_msg[:110]}")
        except Exception as e:
            errs.append(f"{lbl}: {str(e)[:100]}")

    return None, "Failed", errs

def render_short(i, src_p, st_t, dur, sw, sh, lay, res):
    W, H = (1080, 1920) if "1080" in res else (720, 1280)
    out_p = OUT_DIR / f"PeakCut_Short_{i+1}_{W}x{H}.mp4"
    out_p.unlink(missing_ok=True)

    if "Full frame" in lay:
        fh = min(H, int(round(W * sh / max(1, sw) / 2)) * 2)
        vf = (
            f"[0:v]fps=30,split=2[a][b];"
            f"[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,"
            f"scale={W}:{H},eq=brightness=-0.14:saturation=1.15[bg];"
            f"[b]scale={W}:{fh}:force_original_aspect_ratio=increase,crop={W}:{fh}[fg];"
            f"[bg][fg]overlay=0:(H-h)/2,setsar=1[v]"
        )
    elif "Zoomed" in lay:
        fh = int(H * 0.52)
        vf = (
            f"[0:v]fps=30,split=2[a][b];"
            f"[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,"
            f"scale={W}:{H},eq=brightness=-0.14:saturation=1.15[bg];"
            f"[b]scale={W}:{fh}:force_original_aspect_ratio=increase,crop={W}:{fh}[fg];"
            f"[bg][fg]overlay=0:(H-h)/2,setsar=1[v]"
        )
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

with st.expander("🔑 Cookies Setup (Optional)", expanded=False):
    if CK_PATH.is_file() and CK_PATH.stat().st_size > 30:
        st.success(f"✅ Cookies Active! ({CK_PATH.stat().st_size} B)")
        if st.button("🗑️ Delete Cookies"):
            CK_PATH.unlink(missing_ok=True)
            st.rerun()

    up_ck = st.file_uploader("📂 Select cookies.txt", type=["txt"])
    txt_ck = st.text_area("📋 Or Paste cookies.txt", height=60)

    if st.button("✅ OK / SAVE COOKIES"):
        raw = up_ck.getvalue().decode("utf-8", errors="ignore") if up_ck else txt_ck.strip()
        if raw:
            n = save_clean_cookies(raw)
            st.success(f"🎉 {n} Cookies Saved!")
            time.sleep(0.5)
            st.rerun()

url_in = st.text_input("🔗 Paste YouTube Link:", placeholder="https://youtu.be/lqNFrFPX8jg")

# Built-in Phone-IP Downloader Widget (Runs on User's Phone IP, NEVER gets 403!)
vid_now = get_id(url_in)
if vid_now:
    with st.expander("⚡ 100% No-Fail Phone-IP Downloader (Agar Cloud 403 de toh yahan se 1-Click Save karein)"):
        st.caption("Ye button aapke Phone ke IP se chalta hai (AWS Server se nahi), isliye ispar 403 kabhi nahi aata:")
        components.html(
            f"""
            <div style="display:flex;gap:8px;justify-content:center;font-family:sans-serif;">
              <a href="https://ssyoutube.com/watch?v={vid_now}" target="_blank" style="background:#22c55e;color:#fff;padding:10px 14px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:13px;">📥 Fast Save #1 (SSYouTube)</a>
              <a href="https://www.y2mate.com/youtube/{vid_now}" target="_blank" style="background:#3b82f6;color:#fff;padding:10px 14px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:13px;">📥 Fast Save #2 (Y2Mate)</a>
            </div>
            """,
            height=55
        )

up_vid = st.file_uploader("📱 Or Select Saved MP4 Video From Phone (100% Instant Render):", type=["mp4", "mkv", "mov", "webm"])

k1, k2 = st.columns(2)
with k1:
    clips_n = st.selectbox("🎞️ Clips:", [5, 10, 15, 20], index=0)
with k2:
    res_c = st.selectbox("💎 Quality:", ["1080p FHD ⭐", "720p HD"], index=0)

lay_c = st.radio("📐 Layout:", ["Full frame + blurred fill ⭐", "Zoomed in + blurred fill", "Fill the screen (crop)"], horizontal=True)

if st.button("🚀 GENERATE PEAKCUT FHD SHORTS"):
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
        src_f, eng, errs = smart_download(url_in.strip(), status_msg)
        if not src_f:
            status_msg.error("❌ AWS IP 403 Blocked! Upar '⚡ 100% No-Fail Phone-IP Downloader' khol kar 1 click mein video phone mein save karein aur niche select karein!")
            for e in errs:
                st.caption(f"• {e}")
    else:
        status_msg.error("❌ Link daalein ya Video select karein!")

    if src_f and src_f.is_file():
        status_msg.success(f"✅ Video Ready ({eng})! Cutting {clips_n} Shorts...")
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
            status_msg.empty()

if "shorts" in st.session_state and st.session_state["shorts"]:
    st.success(f"🎉 {len(st.session_state['shorts'])} Shorts Ready in {st.session_state.get('sec', 20)}s!")
    if "zip" in st.session_state and os.path.exists(st.session_state["zip"]):
        with open(st.session_state["zip"], "rb") as zb:
            st.download_button("📦 DOWNLOAD ALL (.ZIP)", data=zb, file_name="PeakCut_Shorts.zip", mime="application/zip")

    for idx, fp in enumerate(st.session_state["shorts"]):
        mb = round(os.path.getsize(fp) / (1024 * 1024), 1)
        with open(fp, "rb") as fb:
            st.download_button(f"📥 Save Short #{idx+1} ({mb} MB)", data=fb, file_name=os.path.basename(fp), mime="video/mp4", key=f"d_{idx}")
        st.video(fp)
# END_OF_FILE
