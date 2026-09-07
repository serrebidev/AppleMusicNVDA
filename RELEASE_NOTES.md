# Apple Music 0.4.1

Faster F6 navigation and more reliable album/playlist track focus.

- Known controls and remembered destinations use direct, refreshed UI Automation lookup.
- Fallback navigation shares ancestor information instead of repeatedly reading it.
- Track discovery supports pages with more than 1,000 controls, stops at one usable
  track, and scrolls tracks below the header into view.
- Playlist rows without track numbers are recognized by their spoken duration.
- Track loading checks start sooner; reused lists are checked for changed first tracks.

83 automated tests pass. Live computer-use checks with NVDA confirmed first-track
focus after clicking an album and a playlist. Album-page section focus requests
took 0.221–0.579 seconds in three checks; speech completion is excluded.
Full Queue/Lyrics-panel regression testing remains outstanding.

Open AppleMusic-0.4.1.nvda-addon to install, then restart NVDA.

## Earlier 0.4.0 preview

Native NVDA support for Apple Music on Windows.

- F6 and Shift+F6 move between Search, Sidebar, Player, Main content, and supported open Queue/Lyrics panels.
- Newly exposed album/playlist track lists receive focus. Main content prefers tracks over header controls.
- Enter and Numpad Enter play the focused track through its named context-menu command.
- Control+Alt+Down suggests less; Control+Alt+Up favorites the focused item or current song.
- Existing favorites and Suggest Less preferences are preserved. Player commands restore focus.
- Fixes player/sidebar classification, partly hidden track rows, quoted Play labels, and popup timing.

## Validation

76 automated tests pass. Package contents and ZIP integrity checked; SHA-256 included.
Live testing confirmed Home-page section cycling in both directions, playlist track focus,
Enter playback, and player Favorite focus restoration. Earlier user testing confirmed
Suggest Less and Favorite activation.

This is a preview: full transitions into different albums/playlists and the final open
Queue/Lyrics navigation changes still require live regression testing. Computer-use
capture failed before those checks. English menu labels and numbered track names are
required; unsupported layouts may need manual navigation.

## Install

Download and open AppleMusic-0.4.0.nvda-addon, then restart NVDA.
It upgrades the older Apple Music Suggest Less add-on using the same internal ID.
Target compatibility: NVDA 2025.1 through 2026.1.
