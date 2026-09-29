# CueClipper

A minimal local web app for extracting clips from YouTube (and other platforms) by time range — no GUI framework, no Electron, just a Python HTTP server and a browser UI.

Useful for video editors who need specific scenes from online sources without downloading entire files.

---

## Requirements

You need to install these once before using the app:

1. **Python** — [python.org/downloads](https://www.python.org/downloads/) — during install, check "Add Python to PATH"
2. **yt-dlp** — open Command Prompt and run: `pip install yt-dlp`
3. **ffmpeg** — [ffmpeg.org](https://ffmpeg.org/download.html) or install via WinGet: `winget install Gyan.FFmpeg`
4. **Node.js** *(optional, improves compatibility for some videos)* — [nodejs.org](https://nodejs.org/)

---

## Usage

Double-click `launch.vbs` — the server starts silently in the background and the browser opens automatically at `http://localhost:7433`.

---

## Features

**Clip extraction**
- Extract any time range from a YouTube video as MP4 or MP3
- Downloads only the requested segment — not the full video
- Merges separate video + audio streams via ffmpeg for maximum quality
- Uses the `visionos` YouTube client to bypass SABR restrictions and get full DASH format availability (up to 1080p)
- Excludes AV1 formats that route through CDN nodes with regional 403 issues

**Smart paste**
- Paste a full client message into any field — URL, start, or end — and all fields are filled automatically
- Detects URLs and timestamps in the same paste
- Accepts any timestamp format:
  - `TCI 00:27 / TCO 00:48`
  - `0:59 - 1:02` · `00:00:26 - 00:00:49`
  - `00;26` (semicolons) · `00.26` (dots)
  - `1m26s` (minute+second) · `00:00:26:12` (SMPTE, frames ignored)
  - `from 00:26 to 00:49` · `[00:26] → [00:49]`
- Auto-applies **−1s on start / +1s on end** for safe handles

**Time input UX**
- Arrow Up / Down adjusts timestamp by ±1 second
- Typing freely in any format — normalized on blur
- "Select whole clip" button fills the full video duration

**No console window**
- Launched via `launch.vbs` — runs silently in the background, opens the browser automatically
- All subprocesses (`yt-dlp`, `ffmpeg`) run with `CREATE_NO_WINDOW`

**Auto-detection**
- Finds `yt-dlp` in pip Scripts, PATH, Windows Store Python, and common install paths
- Finds `ffmpeg` in PATH and WinGet packages directory — passes explicit path to `yt-dlp` so it works regardless of environment

---

## Planned

**Adobe Premiere Pro CEP panel**

Turn CueClipper into a docked panel inside Premiere Pro — same UI, same smart paste, but with two extra buttons after the clip downloads:

- **Place above** — drops the clip onto a new track above existing ones at the playhead position, nothing on the timeline moves
- **Insert** — places the clip at the playhead and ripple-shifts everything to the right

The goal: paste a client reference message, hit download, click a button — clip lands on the timeline without touching the file browser.
