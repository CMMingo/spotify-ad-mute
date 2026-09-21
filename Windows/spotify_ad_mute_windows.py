#!/usr/bin/env python3
"""
Mutes ONLY Spotify's audio session while an ad is playing (Windows desktop app).

Detection: polls the Spotify window title via the Win32 API. When a track
is playing, the title is "Artist - Song". When there's no track info (ads,
paused, idle, loading), it falls back to "Spotify Free" / "Spotify Premium"
/ "Advertisement" / empty. This is a heuristic — Windows exposes no official
"is this an ad" flag — so pausing playback will also trigger a mute. That's
harmless in practice: you're paused either way, so nothing is lost.

Muting: uses pycaw to mute Spotify's own entry in the Windows per-app
volume mixer — a real OS-level mute of just that process.

Safety: on exit (Ctrl+C, normal shutdown, or most crashes) this script
unmutes Spotify if it was the one that muted it. It also self-heals a
stray mute (e.g. left over from a previous crash, or Spotify reopened)
on both startup and continuously while running. A hard kill via Task
Manager "End task" or `taskkill /F` can't be caught by any process, so
it can't guarantee an unmute in that one case; the next run's startup
check (or the next ad-free poll) will fix it.

Install dependencies first (from the project folder):
    uv sync

Or build a standalone SpotifyAdMute.exe (no console window, suitable for the
Startup folder) — see README_technical.md. When running without a console,
log lines go to %LOCALAPPDATA%/SpotifyAdMute/spotify_ad_mute.log instead.
"""

import atexit
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import win32gui
from pycaw.pycaw import AudioUtilities

POLL_INTERVAL = 1.0  # seconds between checks

# Window titles that mean "no real track is playing" (ad, paused, idle, loading)
NON_TRACK_TITLES = {"", "Spotify", "Spotify Free", "Spotify Premium", "Advertisement"}


# When built with PyInstaller --noconsole there is no stdout, so log to a file.
LOG_FILE: Optional[Path] = None
if sys.stdout is None or not sys.stdout.isatty():
    LOG_FILE = Path(os.environ.get("LOCALAPPDATA", ".")) / "SpotifyAdMute" / "spotify_ad_mute.log"


def log(message: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    if LOG_FILE is not None:
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
    else:
        print(line)


def get_spotify_window_title() -> Optional[str]:
    """Return the Spotify main window title, or None if Spotify isn't running."""
    result: dict[str, Optional[str]] = {"title": None}

    def callback(hwnd, _):
        if win32gui.GetClassName(hwnd) == "SpotifyMainWindow":
            result["title"] = win32gui.GetWindowText(hwnd)
        return True

    win32gui.EnumWindows(callback, None)
    return result["title"]


def get_spotify_session():
    for session in AudioUtilities.GetAllSessions():
        if session.Process and session.Process.name() == "Spotify.exe":
            return session
    return None


def is_spotify_muted() -> Optional[bool]:
    session = get_spotify_session()
    if session:
        return bool(session.SimpleAudioVolume.GetMute())
    return None


def set_spotify_mute(muted: bool) -> None:
    session = get_spotify_session()
    if session:
        session.SimpleAudioVolume.SetMute(1 if muted else 0, None)


def main():
    log("Watching for Spotify ads... (Ctrl+C to stop)")

    was_ad = False

    def restore_on_exit():
        try:
            if was_ad:
                set_spotify_mute(False)
                log("🔊 Exiting — restoring volume.")
        except Exception:
            pass

    atexit.register(restore_on_exit)
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    for sig_name in ("SIGTERM", "SIGBREAK"):
        if hasattr(signal, sig_name):
            signal.signal(getattr(signal, sig_name), lambda *_: sys.exit(0))

    # Startup safeguard: fix a stuck mute left over from a previous crash.
    if is_spotify_muted():
        set_spotify_mute(False)
        log("🔊 Startup check — Spotify was muted, restoring volume.")

    while True:
        try:
            title = get_spotify_window_title()
            if title is not None:
                is_ad = title in NON_TRACK_TITLES

                if is_ad and not was_ad:
                    set_spotify_mute(True)
                    log("🔇 Ad (or pause) detected — muting Spotify.")
                elif not is_ad and was_ad:
                    set_spotify_mute(False)
                    log("🔊 Track resumed — restoring volume.")
                elif not is_ad and is_spotify_muted():
                    # Self-heal: muted with no ad playing (stray mute).
                    set_spotify_mute(False)
                    log("🔊 Detected stray mute — restoring volume.")

                was_ad = is_ad
        except Exception as e:
            log(f"⚠️ Error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
