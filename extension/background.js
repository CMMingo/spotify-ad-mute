// background.js
//
// Mutes or unmutes only the Spotify tab that reports an ad — every other
// tab and system audio is untouched.
//
// Safety: a muted tab's state is owned by Chrome, not by this extension —
// if the extension is reloaded, updated, or the browser restarts while a
// tab is muted, nothing runs to undo it automatically. onInstalled (covers
// extension install/update/reload) and onStartup (covers browser restart)
// sweep all open Spotify tabs and force-unmute any that are stuck. Note:
// if the extension is disabled/removed mid-ad, no code can run afterward
// to fix that tab — the next title change (or a manual refresh) clears it.

function unmuteAllSpotifyTabs() {
  chrome.tabs.query({ url: "https://open.spotify.com/*" }, (tabs) => {
    for (const tab of tabs) {
      if (tab.mutedInfo?.muted) {
        chrome.tabs.update(tab.id, { muted: false });
      }
    }
  });
}

chrome.runtime.onInstalled.addListener(unmuteAllSpotifyTabs);
chrome.runtime.onStartup.addListener(unmuteAllSpotifyTabs);

chrome.runtime.onMessage.addListener((message, sender) => {
  if (message.type === "SPOTIFY_AD_STATE" && sender.tab?.id) {
    chrome.tabs.update(sender.tab.id, { muted: message.isAd });
  }
});
