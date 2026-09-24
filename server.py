#!/usr/bin/env python3
import atexit
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

DEFAULT_OUTPUT = str(Path.home() / "Downloads" / "YT Extracts")
JOBS = {}  # job_id -> { status, progress, error, output_path }

# ─── PID file ────────────────────────────────────────────────────────────────

_PID_FILE = Path(__file__).parent / "server.pid"

def _write_pid():
    _PID_FILE.write_text(str(os.getpid()))

def _remove_pid():
    try:
        _PID_FILE.unlink()
    except Exception:
        pass

_write_pid()
atexit.register(_remove_pid)

# ─── Inactivity watchdog ─────────────────────────────────────────────────────

INACTIVITY_MINUTES = 30
_last_activity = time.time()

def _touch():
    global _last_activity
    _last_activity = time.time()

def _watchdog():
    while True:
        time.sleep(60)
        if time.time() - _last_activity > INACTIVITY_MINUTES * 60:
            print(f"No activity for {INACTIVITY_MINUTES} min — shutting down.")
            _remove_pid()
            os._exit(0)

threading.Thread(target=_watchdog, daemon=True).start()

def open_folder_dialog(initial_dir=None):
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        folder = filedialog.askdirectory(initialdir=initial_dir or str(Path.home()))
        root.destroy()
        return folder or None
    except Exception:
        return None

# ─── yt-dlp discovery ────────────────────────────────────────────────────────

def find_ytdlp():
    # 1. Same Python's Scripts dir (pip install yt-dlp)
    scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
    candidate = os.path.join(scripts_dir, "yt-dlp.exe")
    if os.path.exists(candidate):
        return candidate

    # 2. System PATH
    try:
        r = subprocess.run(["where", "yt-dlp"], capture_output=True, text=True, timeout=5, creationflags=_NO_WINDOW)
        if r.returncode == 0:
            return r.stdout.strip().splitlines()[0]
    except Exception:
        pass

    # 3. Windows Store Python variants
    local = os.environ.get("LOCALAPPDATA", "")
    for pkg in [
        "PythonSoftwareFoundation.Python.3.10_qbz5n2kfra8p0",
        "PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0",
        "PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0",
    ]:
        for ver in ["Python310", "Python311", "Python312"]:
            p = os.path.join(local, "Packages", pkg, "LocalCache", "local-packages", ver, "Scripts", "yt-dlp.exe")
            if os.path.exists(p):
                return p

    # 4. Common user installs
    home = str(Path.home())
    for p in [
        os.path.join(home, "AppData", "Roaming", "Python", "Python310", "Scripts", "yt-dlp.exe"),
        r"C:\yt-dlp\yt-dlp.exe",
        r"C:\tools\yt-dlp.exe",
    ]:
        if os.path.exists(p):
            return p

    return None

YTDLP = find_ytdlp()
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

def find_ffmpeg():
    try:
        r = subprocess.run(["where", "ffmpeg"], capture_output=True, text=True,
                           timeout=5, creationflags=_NO_WINDOW)
        if r.returncode == 0:
            return r.stdout.strip().splitlines()[0]
    except Exception:
        pass
    for p in [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\tools\ffmpeg\bin\ffmpeg.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe"),
    ]:
        if os.path.exists(p):
            return p
    # search WinGet packages dir
    winget_pkgs = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    if os.path.isdir(winget_pkgs):
        for root, dirs, files in os.walk(winget_pkgs):
            if "ffmpeg.exe" in files:
                return os.path.join(root, "ffmpeg.exe")
    return None

FFMPEG = find_ffmpeg()

# ─── helpers ─────────────────────────────────────────────────────────────────

def ts_to_seconds(ts):
    """'HH:MM:SS' or 'MM:SS' or plain seconds → float"""
    ts = ts.strip()
    if not ts:
        return 0.0
    parts = ts.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(ts)
    except ValueError:
        return 0.0

def seconds_to_ts(s):
    s = int(s)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"

# ─── background extract ───────────────────────────────────────────────────────

def run_extract(job_id, url, start, end, output_dir, fmt="mp4"):
    job = JOBS[job_id]
    try:
        os.makedirs(output_dir, exist_ok=True)
        section = f"*{start}-{end}"
        template = os.path.join(output_dir, "%(title).80s [%(id)s] %(section_start)s-%(section_end)s.%(ext)s")

        js_runtime = ["--js-runtimes", r"node:C:\Program Files\nodejs\node.exe"]
        # visionos returns HLS+DASH up to 1080p without SABR issues.
        # android triggers SABR (360p only), web requires PO token.
        player_client = ["--extractor-args", "youtube:player_client=visionos"]
        ffmpeg_args = ["--ffmpeg-location", FFMPEG] if FFMPEG else []

        if fmt == "mp3":
            cmd = [
                YTDLP,
                "--download-sections", section,
                "-f", "bestaudio/best",
                "-x", "--audio-format", "mp3", "--audio-quality", "0",
                "-o", template,
                "--no-playlist",
                "--newline",
                *js_runtime,
                *player_client,
                *ffmpeg_args,
                url,
            ]
        else:
            cmd = [
                YTDLP,
                "--download-sections", section,
                "-f", "bestvideo[vcodec!^=av01][height<=1080]+bestaudio/bestvideo[height<=1080]+bestaudio/best",
                "--merge-output-format", "mp4",
                "-o", template,
                "--no-playlist",
                "--newline",
                *js_runtime,
                *player_client,
                *ffmpeg_args,
                url,
            ]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", creationflags=_NO_WINDOW)
        lines = []
        for line in proc.stdout:
            line = line.rstrip()
            lines.append(line)
            # parse progress percentage from yt-dlp [download] X.X% lines
            if "[download]" in line and "%" in line:
                try:
                    pct = float(line.split("%")[0].split()[-1])
                    job["progress"] = pct
                    job["status_msg"] = line.strip()
                except Exception:
                    pass

        proc.wait()
        if proc.returncode != 0:
            job["status"] = "error"
            job["error"] = "\n".join(lines[-10:])
        else:
            job["status"] = "done"
            job["output_dir"] = output_dir
            job["log"] = "\n".join(lines[-20:])
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)

# ─── HTTP handler ─────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_OPTIONS(self):
        self.send_response(200)
        for k, v in [("Access-Control-Allow-Origin", "*"),
                      ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                      ("Access-Control-Allow-Headers", "Content-Type")]:
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        _touch()
        if self.path == "/api/ping":
            self.send_json({"ok": True})
        elif self.path == "/" or self.path == "/index.html":
            self._serve_static("index.html", "text/html; charset=utf-8")
        elif self.path == "/api/status":
            self.send_json({"ytdlp": YTDLP, "ok": bool(YTDLP), "ffmpeg": FFMPEG, "default_output": DEFAULT_OUTPUT})
        elif self.path == "/api/browse":
            folder = open_folder_dialog(DEFAULT_OUTPUT)
            self.send_json({"path": folder})
        elif self.path.startswith("/api/job/"):
            job_id = self.path.split("/")[-1]
            job = JOBS.get(job_id)
            if job:
                self.send_json(job)
            else:
                self.send_json({"error": "Job not found"}, 404)
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        _touch()
        data = self.read_body()
        if self.path == "/api/metadata":
            self._handle_metadata(data)
        elif self.path == "/api/extract":
            self._handle_extract(data)
        else:
            self.send_json({"error": "Not found"}, 404)

    def _handle_metadata(self, data):
        url = data.get("url", "").strip()
        if not url:
            return self.send_json({"error": "URL required"}, 400)
        if not YTDLP:
            return self.send_json({"error": "yt-dlp not found"}, 500)
        try:
            r = subprocess.run(
                [YTDLP, "--dump-json", "--no-download", "--no-playlist",
                 "--js-runtimes", r"node:C:\Program Files\nodejs\node.exe",
                 "--extractor-args", "youtube:player_client=visionos", url],
                capture_output=True, text=True, timeout=30, errors="replace",
                creationflags=_NO_WINDOW
            )
            if r.returncode != 0:
                return self.send_json({"error": (r.stderr or r.stdout).strip()[-300:]})
            info = json.loads(r.stdout)
            self.send_json({
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", ""),
                "thumbnail": info.get("thumbnail", ""),
            })
        except subprocess.TimeoutExpired:
            self.send_json({"error": "Timeout — check URL or network"})
        except Exception as e:
            self.send_json({"error": str(e)})

    def _handle_extract(self, data):
        url = data.get("url", "").strip()
        start = data.get("start", "00:00:00")
        end = data.get("end", "00:00:00")
        output_dir = data.get("output_dir", DEFAULT_OUTPUT).strip() or DEFAULT_OUTPUT
        fmt = data.get("format", "mp4")

        if not url:
            return self.send_json({"error": "URL required"}, 400)
        if not YTDLP:
            return self.send_json({"error": "yt-dlp not found"}, 500)

        job_id = str(uuid.uuid4())[:8]
        JOBS[job_id] = {"status": "running", "progress": 0, "status_msg": "Starting…"}
        t = threading.Thread(target=run_extract, args=(job_id, url, start, end, output_dir, fmt), daemon=True)
        t.start()
        self.send_json({"job_id": job_id})

    def _serve_static(self, filename, content_type):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        try:
            with open(p, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_json({"error": "index.html not found"}, 404)

    def log_message(self, *_):
        pass


# ─── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = 7433
    if YTDLP:
        print(f"yt-dlp: {YTDLP}")
    else:
        print("WARNING: yt-dlp not found! Install: pip install yt-dlp")
    print(f"Server → http://localhost:{port}")

    import webbrowser
    webbrowser.open(f"http://localhost:{port}")

    HTTPServer(("localhost", port), Handler).serve_forever()
