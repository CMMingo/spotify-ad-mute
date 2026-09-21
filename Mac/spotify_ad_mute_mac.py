#!/usr/bin/env python3
"""
Mutes ONLY Spotify's playback volume while an ad is playing (macOS desktop app).

Detection: Spotify's AppleScript API exposes `spotify url` of the current
track. Ad "tracks" have a URL starting with "spotify:ad:" instead of the
normal "spotify:track:...". We poll this, and toggle Spotify's own
`sound volume` (not the system volume) accordingly.

Safety: on exit (Ctrl+C, normal shutdown, or most crashes) this script
restores Spotify's volume if it was the one that muted it. It also
self-heals a "stray mute" — e.g. left over from a previous crash, or
Spotify reopened after being closed — both on startup and continuously
while running. A hard kill (`kill -9`) can't be caught by any process, so
it can't guarantee an unmute in that one case; the next run's startup
check (or the next ad-free poll) will fix it.

First run: macOS will prompt you to allow Automation access to
"System Events" and "Spotify" — approve both (System Settings >
Privacy & Security > Automation).
"""

import atexit
import signal
import subprocess
import sys
import time
from datetime import datetime

POLL_INTERVAL = 1.0    # seconds between checks
FALLBACK_VOLUME = 100  # used when we have no better "safe" volume to restore to


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def run_applescript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def spotify_is_running() -> bool:
    out = run_applescript(
        'tell application "System Events" to (name of processes) contains "Spotify"'
    )
    return out == "true"


def get_status():
    """One AppleScript round-trip for both track URL and volume, instead of
    two separate calls — halves the subprocess overhead per check."""
    out = run_applescript(
        'tell application "Spotify" to (spotify url of current track) '
        '& "|||" & (sound volume as string)'
    )
    url, _, vol_str = out.partition("|||")
    vol_str = vol_str.strip()
    volume = int(vol_str) if vol_str.lstrip("-").isdigit() else FALLBACK_VOLUME
    return url, volume


def set_volume(vol: int) -> None:
    run_applescript(f'tell application "Spotify" to set sound volume to {vol}')


def main():
    log("Watching for Spotify ads... (Ctrl+C to stop)")

    was_ad = False
    saved_volume = FALLBACK_VOLUME

    def restore_on_exit():
        try:
            if was_ad and spotify_is_running():
                set_volume(saved_volume if saved_volume > 0 else FALLBACK_VOLUME)
                log("🔊 Exiting — restoring volume.")
        except Exception:
            pass

    atexit.register(restore_on_exit)
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    # Startup safeguard: fix a stuck mute left over from a previous crash.
    if spotify_is_running():
        _, current_volume = get_status()
        if current_volume == 0:
            set_volume(FALLBACK_VOLUME)
            log("🔊 Startup check — Spotify was muted, restoring volume.")

    while True:
        try:
            if spotify_is_running():
                url, current_volume = get_status()
                is_ad = url.startswith("spotify:ad:")

                if is_ad and not was_ad:
                    saved_volume = current_volume
                    if saved_volume > 0:
                        set_volume(0)
                        log("🔇 Ad detected — muting Spotify.")
                elif not is_ad and was_ad:
                    set_volume(saved_volume)
                    log("🔊 Ad over — restoring volume.")
                elif not is_ad and current_volume == 0:
                    # Self-heal: muted with no ad playing (stray mute).
                    set_volume(FALLBACK_VOLUME)
                    log("🔊 Detected stray mute — restoring volume.")

                was_ad = is_ad
        except Exception as e:
            log(f"⚠️ Error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
