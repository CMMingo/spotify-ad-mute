# Spotify Ad Mute — Technical README

How each version detects and mutes ads, what's tunable, and the
trade-offs behind the defaults.

---

## How it works

### macOS (`spotify_ad_mute_mac.py`)
- **Detection**: polls the current track's `spotify url` via AppleScript.
  Ads report a URL starting with `spotify:ad:` instead of `spotify:track:...`
  — an exact signal from Spotify itself, not a guess.
- **Muting**: sets Spotify's own AppleScript `sound volume` property to `0`.
  This is Spotify's internal, app-level volume (the same one behind its
  in-app slider) — separate from the macOS system volume. Community
  testing confirms it resets to `100` on every fresh launch of the app,
  which is why quitting and reopening Spotify self-resolves a stuck mute.
- **Efficiency detail**: track URL and volume are fetched in a single
  AppleScript round-trip (one `osascript` subprocess spawn per check),
  instead of two separate calls.

### Windows (`spotify_ad_mute_windows.py`)
- **Detection**: polls the Spotify window title via `pywin32`. A real track
  shows `"Artist - Song"`; ads, pauses, and idle states all fall back to a
  generic title (`"Spotify"`, `"Spotify Free"`, `"Advertisement"`, or
  empty) — Windows has no official "this is an ad" flag, so this is a
  heuristic, not an exact signal like macOS's.
- **Muting**: uses `pycaw` to mute Spotify's entry in the Windows Core
  Audio per-app volume mixer — a real OS-level mute of just that process,
  independent of the volume level (so no saved-volume bookkeeping needed).

### Browser extension (`extension/`)
- **Detection**: a content script watches `document.title` via a
  `MutationObserver`. Normal playback titles look like `"Song • Artist"`;
  ads/pauses drop that pattern. Event-driven, not polling — the browser
  only wakes the script when the title actually changes.
- **Muting**: the background service worker calls
  `chrome.tabs.update(tabId, { muted })` on that one tab only.

---

## Tunable parameters

| Parameter | Where | Default | Effect |
|---|---|---|---|
| `POLL_INTERVAL` | mac/Windows scripts | `1.0`s | How often it checks. Lower = faster reaction, more overhead. |
| `FALLBACK_VOLUME` | mac/Windows scripts | `100` | Volume restored to when there's no better "before ad" value to fall back on. |
| `NON_TRACK_TITLES` | Windows script | 5 known titles | Titles treated as "not a real track." Add any others you observe. |
| `" • "` title check | browser `content.js` | — | The substring that identifies a normal "Song • Artist" title. Would need updating if Spotify changes its title format. |

## Cost vs. precision

- **Polling cost** (mac/Windows only — the extension has none, since it's
  event-driven): each cycle spawns a subprocess (mac) or queries the OS
  (Windows). Lowering `POLL_INTERVAL` catches ad start/end faster but
  increases that overhead; raising it reduces overhead but you'll hear
  slightly more of the ad before it mutes.
- **Detection precision**: macOS reads Spotify's real ad flag — no false
  positives. Windows and the browser extension both infer "ad" from "no
  track title showing," which is also true when you simply pause — a
  harmless false-positive mute, not a bug to chase.

---

## Safety & self-heal design

All three versions guard against ending up stuck muted:

- **On exit** (Ctrl+C, normal shutdown, most crashes) — restores volume if
  it was the one that muted it.
- **On startup** (scripts) / **on browser restart or extension reload**
  (extension) — force-unmutes if it finds Spotify already muted.
- **Continuously while running** — if it ever sees "no ad, but still
  muted," it self-heals immediately.

**Limitation**: a hard kill — `kill -9` (mac), Task Manager "End task" /
`taskkill /F` (Windows), or force-removing the browser extension mid-ad —
can't be caught by any process, so cleanup code never runs. It resolves
itself the next time the watcher starts, or (mac) the next time Spotify
itself is relaunched, since its volume resets to 100 on launch regardless
of this script.

---

## Building a standalone executable

The included `.command` / `.bat` launchers still need Python and the
dependencies installed. For a true standalone binary (shareable with
someone who has no Python installed), build it **on the OS you're
targeting** — PyInstaller doesn't cross-compile:

```bash
uv sync --group build

# macOS — run on a Mac:
uv run pyinstaller --onefile --name "SpotifyAdMute" spotify_ad_mute_mac.py

# Windows — run on Windows, from the Windows/ folder.
# --noconsole hides the terminal window so it can run silently in the background.
uv run pyinstaller --onefile --noconsole --name "SpotifyAdMute" spotify_ad_mute_windows.py
```

Output lands in `dist/` (`dist/SpotifyAdMute` or `dist\SpotifyAdMute.exe`)
— double-click to run, nothing else to install. `dist/` and `build/` are
gitignored, so the binary is never committed; rebuild it whenever the
script changes.

### How the Windows exe works

- **Single file, ~8 MB.** `--onefile` bundles the Python 3.12 interpreter,
  `pycaw`, `pywin32`, `comtypes` and the script into one exe. On launch it
  unpacks itself into a temp folder (`%TEMP%\_MEIxxxxxx`) and runs from
  there, so first start takes a second or two longer than a plain script.
- **No console window.** `--noconsole` builds a "windowed" exe, so nothing
  pops up — no terminal, no tray icon. The only sign it's running is
  `SpotifyAdMute.exe` in Task Manager.
- **Logging goes to a file.** In a windowed exe `sys.stdout` is `None`, so
  `print()` would have nowhere to go. The script checks for that at import
  time and, if there's no interactive console, appends log lines to
  `%LOCALAPPDATA%\SpotifyAdMute\spotify_ad_mute.log` instead (creating the
  folder if needed). Run from a terminal, it still prints as usual. Lines
  are timestamped `YYYY-MM-DD HH:MM:SS` since the file spans many sessions.
- **Stopping it.** Ending the process in Task Manager is a hard kill — the
  `atexit` unmute handler can't run. If it was mid-ad, Spotify stays muted
  until the next launch's startup check or the volume mixer (see below).
  This is the same limitation as `taskkill /F` described earlier.
- **Multiple instances aren't prevented.** Launching it twice gives you two
  pollers. They don't fight (both set the same mute state) but it's wasted
  CPU — check Task Manager before adding it to Startup a second time.
- **SmartScreen / antivirus.** Windows may show "Windows protected your PC"
  on first run, and some antivirus tools flag PyInstaller binaries. This is
  a well-known false positive — unsigned self-extracting exes look like
  packers to heuristics — not specific to this script. Click **More info →
  Run anyway**. Worth a heads-up to anyone you share it with.
- **Rebuilding.** `--clean` clears PyInstaller's cache; add it if a rebuild
  picks up a stale copy of the script.

The browser extension has no single-file executable equivalent. To share
it, zip the `extension` folder and have the recipient load it the
same way you did (`chrome://extensions` → Developer mode → Load unpacked).
Packaging as `.crx` isn't practical for casual sharing — Chrome blocks
installing `.crx` files from outside the Web Store unless Developer mode
is already on.

---

## Autostart: install & remove

### macOS (launchd)

Before installing, edit `com.user.spotifyadmute.plist`: both `<string>`
values under `ProgramArguments` need to point to real, existing paths —
your Python (`which python3`) and this script's absolute path.

Install — runs the script automatically at login, in the background.
Run as yourself, **not with `sudo`** — `sudo` runs launchctl as root
trying to register into your non-root GUI session, which fails with a
vague I/O error rather than a clear permissions message:
```bash
cp com.user.spotifyadmute.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.spotifyadmute.plist
```
Confirm it's running:
```bash
launchctl print gui/$(id -u)/com.user.spotifyadmute
```

View its logs (background mode doesn't print to a terminal):
```bash
tail -f /tmp/spotify_ad_mute.log
```

**Remove it:**
```bash
launchctl bootout gui/$(id -u)/com.user.spotifyadmute
rm ~/Library/LaunchAgents/com.user.spotifyadmute.plist
```
Both lines matter — `bootout` stops the currently running instance;
`rm` deletes the file so it won't restart at your next login. If you skip
`bootout` and just delete the file, the already-running process keeps going
until you quit it manually or log out/restart.

To temporarily pause it without fully removing it, `bootout` on its own is
enough — the plist file stays, so `bootstrap` brings it back later without
re-copying anything.

> **If `bootstrap` fails with `5: Input/output error`:** three confirmed
> causes so far, and `plutil -lint` catches none of them:
> 1. A `ProgramArguments` path that doesn't actually exist — double-check
>    with `ls`.
> 2. An XML comment (`<!-- ... -->`) placed *inside* the `<array>` between
>    elements. `plutil -lint` says `OK` regardless — launchd's own parser
>    is stricter. Keep the plist comment-free to be safe.
> 3. **The script or plist still has a `com.apple.quarantine` attribute** —
>    macOS tags anything downloaded through a browser this way (an `@`
>    after the permissions in `ls -l` is the tell). It's normally cleared
>    by opening the file once via Finder with the security prompt, but a
>    `.py`/`.plist` never gets that prompt, so it silently blocks launchd
>    from spawning it. Fix:
>    ```bash
>    xattr -cr ~/Documents/path/to/your/script/folder
>    xattr -c ~/Library/LaunchAgents/com.user.spotifyadmute.plist
>    ```

`launchctl load`/`unload` (the older commands) still exist but might be
deprecated and can throw the same vague error even when everything's
correct — `bootstrap`/`bootout` above are the current, more reliable way.

### Windows (Startup folder)

Install — build `SpotifyAdMute.exe` (see [Building a standalone
executable](#building-a-standalone-executable)), then:

1. Press `Win+R`, type `shell:startup`, hit Enter — this opens your
   Startup folder.
2. Copy `Windows\dist\SpotifyAdMute.exe` there (or put the exe somewhere
   permanent and drop a **shortcut** to it in the Startup folder).

It starts silently on every login — no window, no tray icon. To check it's
running, look for `SpotifyAdMute.exe` in Task Manager, or tail the log at
`%LOCALAPPDATA%\SpotifyAdMute\spotify_ad_mute.log`.

**Remove it:** delete the exe/shortcut from `shell:startup`. To stop it
right now rather than at next reboot, end `SpotifyAdMute.exe` in Task
Manager (if Spotify was muted at that moment, it'll unmute itself on the
next track anyway — or use the volume mixer, see main README).

### Browser extension

There's no separate "autostart" toggle — an installed extension runs
automatically on every matching page until removed. To disable/remove:
`chrome://extensions` → toggle it off, or click **Remove**.



- **Windows / browser**: the title heuristic can't tell "ad" from "paused"
  — both mute. Cosmetic, not a functional issue.
- **macOS**: requires one-time Automation permission for "System Events"
  and "Spotify" (System Settings > Privacy & Security > Automation).
- **All three**: a hard kill of the watcher process bypasses cleanup (see
  Safety section above).
- **Browser**: if the extension is disabled/removed while a tab is
  mid-ad-mute, no code can run afterward to fix that specific tab — a
  page refresh or the next title change clears it.
