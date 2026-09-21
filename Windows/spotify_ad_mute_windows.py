#!/usr/bin/env python3
"""
Mutes ONLY Spotify's audio session while an ad is playing (Windows desktop app).

Detection: polls the Spotify window title via the Win32 API. When a track
is playing, the title is always "Artist - Song". Ads have no artist, so the
title is just the advertiser name (e.g. "Don Omar"), and when paused/idle it
falls back to "Spotify Free" / "Spotify Premium" / "Advertisement". So the
rule is: no " - " separator => not a real track => mute. This is a heuristic
— Windows exposes no official "is this an ad" flag (unlike macOS, whose
AppleScript API reports a "spotify:ad:" URL), and the "Anuncio" label in the
now-playing bar is not exposed via UI Automation — so pausing playback will
also trigger a mute. That's harmless in practice: you're paused either way,
so nothing is lost. Local files with no artist tag will also be muted.

Muting: uses pycaw to mute Spotify's own entry in the Windows per-app
volume mixer — a real OS-level mute of just that process.

Safety: on exit (Ctrl+C, normal shutdown, or most crashes) this script
unmutes Spotify if it was the one that muted it. It also self-heals a
stray mute (e.g. left over from a previous crash, or Spotify reopened)
on every poll, so the first poll after startup fixes one too. A hard kill via Task
Manager "End task" or `taskkill /F` can't be caught by any process, so
it can't guarantee an unmute in that one case; the next run's first
poll will fix it.

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

import win32gui
import win32process
from pycaw.pycaw import AudioUtilities

POLL_INTERVAL = 1.0  # seconds between checks

# Real tracks are titled "Artist - Song"; anything without this separator is
# an ad (advertiser name only), or the paused/idle fallback title.
TRACK_SEPARATOR = " - "

# When built with PyInstaller --noconsole there is no stdout, so log to a file.
LOG_FILE: Path | None = None
if sys.stdout is None or not sys.stdout.isatty():
    LOG_FILE = Path(os.environ.get("LOCALAPPDATA", ".")) / "SpotifyAdMute" / "spotify_ad_mute.log"


def log(message: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    if LOG_FILE is None:
        print(line)
        return
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def get_spotify_sessions() -> list:
    """Spotify's entries in the Windows volume mixer (empty if not running).

    Spotify is Chromium-based and runs several Spotify.exe processes; the UI
    process and the audio process each get their own session, so we must
    treat them as a group and mute/unmute all of them.
    """
    return [
        s for s in AudioUtilities.GetAllSessions()
        if s.Process and s.Process.name() == "Spotify.exe"
    ]


def get_window_title(pids: set[int]) -> str | None:
    """Title of the visible top-level window owned by one of `pids`, or None.

    Spotify's main window class is the generic Chromium "Chrome_WidgetWin_1"
    rather than the old "SpotifyMainWindow", so we match on the owning process
    instead: Spotify's only *visible* top-level window is the player window.
    """
    titles: list[str] = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32process.GetWindowThreadProcessId(hwnd)[1] in pids:
            titles.append(win32gui.GetWindowText(hwnd))
        return True

    win32gui.EnumWindows(callback, None)
    return titles[0] if titles else None


def is_muted(sessions: list) -> bool:
    return any(s.SimpleAudioVolume.GetMute() for s in sessions)


def set_mute(sessions: list, muted: bool) -> None:
    for s in sessions:
        s.SimpleAudioVolume.SetMute(1 if muted else 0, None)


def main():
    log("Watching for Spotify ads... (Ctrl+C to stop)")

    was_ad = False

    def restore_on_exit():
        try:
            if was_ad and (sessions := get_spotify_sessions()):
                set_mute(sessions, False)
                log("🔊 Exiting — restoring volume.")
        except Exception:
            pass

    atexit.register(restore_on_exit)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGBREAK):
        signal.signal(sig, lambda *_: sys.exit(0))

    while True:
        try:
            sessions = get_spotify_sessions()
            if sessions:
                title = get_window_title({s.Process.pid for s in sessions})
                is_ad = title is not None and TRACK_SEPARATOR not in title
                muted = is_muted(sessions)

                if is_ad and not muted:
                    set_mute(sessions, True)
                    log("🔇 Ad (or pause) detected — muting Spotify.")
                elif not is_ad and muted:
                    # Also self-heals a stray mute (previous crash, Spotify reopened).
                    set_mute(sessions, False)
                    log("🔊 Track playing — restoring volume.")

                was_ad = is_ad
        except Exception as e:
            log(f"⚠️ Error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
