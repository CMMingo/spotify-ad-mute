# Spotify Ad Mute

Automatically mutes Spotify the moment an ad starts, and restores the
volume the moment it ends — so you're not interrupted while working.
Nothing else on your system is touched.

Available for:
- 🖥️ **macOS** — desktop app
- 🖥️ **Windows** — desktop app
- 🌐 **Browser** — the Spotify web player (open.spotify.com), any OS

## What's included

| Files | For |
|---|---|
| `spotify_ad_mute_mac.py`, `Start Spotify Ad Mute (Mac).command`, `com.user.spotifyadmute.plist` | macOS desktop app |
| `spotify_ad_mute_windows.py`, `Start Spotify Ad Mute (Windows).bat` | Windows desktop app |
| `extension/` | Browser (Chrome, Edge, etc.) |

## Requirements

| Platform | Needs |
|---|---|
| **macOS** | Python 3.12+ (standard library only — no extra packages) |
| **Windows** | Python 3.12+ and the packages `pycaw`, `pywin32`, `comtypes` |
| **Browser** | A Chromium-based browser (Chrome, Edge, Brave, ...) — no Python needed |

All Python dependencies are declared in [`pyproject.toml`](./pyproject.toml)
and managed with [uv](https://docs.astral.sh/uv/). From the project folder:

```bash
uv sync
```

This creates a `.venv` with the right Python version (from `.python-version`)
and installs the platform-specific packages — on macOS it installs nothing
extra, on Windows it pulls in `pycaw`, `pywin32` and `comtypes`.

If you don't have uv yet:

```bash
# macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Getting started

- **macOS** — double-click `Start Spotify Ad Mute (Mac).command`
  (first time only: right-click → Open, to bypass the "unknown developer" warning)
- **Windows** — run `uv sync` once (see [Requirements](#requirements)),
  then double-click `Start Spotify Ad Mute (Windows).bat`
- **Browser** — go to `chrome://extensions`, enable **Developer mode**,
  click **Load unpacked**, and select the `extension` folder

Full setup details, permissions, and troubleshooting are in
[`README_technical.md`](./README_technical.md).

## If it gets stuck muted and nothing's running to fix it

This is rare — all three versions try to prevent it automatically — but if
you ever need to fix it by hand:

- **macOS**: drag Spotify's own volume slider (bottom-right of the Spotify
  window) back up. Or simpler — just quit and reopen Spotify; its volume
  resets to full on every fresh launch.
- **Windows**: right-click the speaker icon in the taskbar → **Open Volume
  mixer** → find Spotify → drag its slider back up.
- **Browser**: Chrome shows a small speaker icon directly on a tab it has
  muted — click it to unmute. Or right-click the tab → **Unmute site**.
