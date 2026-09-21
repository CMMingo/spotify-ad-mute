// content.js
//
// Detects Spotify Web Player ad state via the browser tab title, and
// notifies the background service worker to mute/unmute this tab.
//
// Spotify sets the tab title to "Song • Artist" during normal playback,
// and to something without that pattern (usually just "Spotify") during
// ads, on pause, or while idle. This is a heuristic — Spotify could change
// the exact wording — but it needs no fragile CSS class selectors, which
// tend to break every time Spotify redesigns the web player.
//
// Uses a MutationObserver instead of setInterval: the browser only wakes
// this code up when the title actually changes, rather than us polling
// every second regardless of activity.

function isAdOrPaused(title) {
  return !title.includes(" • ");
}

function reportState() {
  const isAd = isAdOrPaused(document.title);
  chrome.runtime.sendMessage({ type: "SPOTIFY_AD_STATE", isAd });
}

const titleEl = document.querySelector("title");
if (titleEl) {
  const observer = new MutationObserver(reportState);
  observer.observe(titleEl, { childList: true, characterData: true, subtree: true });
}

reportState(); // report initial state on page load
