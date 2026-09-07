# Apple Music for NVDA

Press **Control+Alt+Down Arrow** in the Windows Apple Music app to invoke
**Suggest Less** for the song or album containing keyboard focus. From player
controls, a focused Action/More button is used directly. Otherwise the add-on
looks for the verified player Action button across the window, including when
focus is in Queue, then checks a small group of transport controls and invokes
it. If no suitable button is exposed, **Control+L** is used
to reveal the current song. Both routes find the command by accessible name.

Press **Control+Alt+Up Arrow** to **Favorite** the focused song/album or current
song using the same player fallback. Repeating this shortcut does not remove
an existing favorite: removal commands and checked Favorite items are detected
and announced as “Already a favorite.” Both American and British English menu
spellings are supported. Checkable commands use Toggle only when their live
state is explicitly off. Commands that expose Invoke are also supported.

This is a native Python NVDA app module. AutoHotkey, UIA-v2, a mouse, and
additional Python packages are not required.

## Section navigation

Press **F6** for the next section or **Shift+F6** for the previous section.
The order is Search, Sidebar, Player, Main content, Queue, Lyrics, then back to
the first available section. Hidden or unavailable sections are skipped.
The add-on remembers the last control left in each section when you use F6.
Known controls and remembered destinations are queried directly. Fallback
discovery shares parent classifications to reduce repeated accessibility calls.
It changes keyboard focus without activating buttons, starting playback, or
selecting a new sidebar page. Use Tab or the arrow keys within a section.

Sections are detected from accessible roles, English names, identifiers, and parent
containers. Queue's Playing Next and History tabs are recognized; other Queue
and Lyrics content must be exposed as named containers to be separate
sections. Unsupported controls are grouped into Main content. If a menu or
dialog is open, close it before switching sections. All shortcuts can be changed
under Apple Music in NVDA's Input gestures dialog.

## Album and playlist tracks

When a newly exposed track list receives attention after navigation, the add-on
focuses a track and scrolls it into view. It recognizes Apple's English numbered
album rows and playlist rows ending with a spoken duration, such as
“Without You Here 3 minutes, 49 seconds”. It will not repeatedly pull you back to the same
list when you move to its header controls. Moving focus elsewhere cancels a
pending automatic move. F6's Main content destination prefers available track
rows over album/playlist header controls.

Press **Enter** or **Numpad Enter** on a track to play it. The add-on opens that
track's context menu and finds **Play “song title”** or **Play** by accessible
name. It does not select Play Next or Play Last. Enter on other controls keeps
its normal behavior. Multiple selected tracks are refused.

The focused track may be the previously selected row, rather than the first
track in the album. Pages that reuse the same list control without a focus event,
non-English track names, and unexposed virtual rows can require manual navigation.

## Installation and use

1. Download the add-on from [GitHub releases](https://github.com/serrebidev/AppleMusicNVDA/releases/latest), or run `python build.py` to build it in `dist`.
2. Open `AppleMusic-0.4.1.nvda-addon` and confirm NVDA's installation prompt.
3. Restart NVDA when prompted.
4. In Apple Music, focus one song/album or a player control and press
   **Control+Alt+Down Arrow** for Suggest Less or **Control+Alt+Up Arrow** for
   Favorite. Keep focus in place until feedback is spoken.

Installing 0.4.1 upgrades the existing add-on. The display name is Apple Music;
the internal ID remains `appleMusicSuggestLess` to preserve the upgrade path.

NVDA says “Suggest less” or “Added to favorites” after UI Automation accepts the action. This
does not independently confirm Apple's server has saved your preference.
An existing **Undo Suggest Less** command produces “Already set to suggest less”
and is never invoked. Unavailable commands and timeouts produce spoken and
braille feedback through NVDA's standard message function.

To reassign the shortcut, open NVDA's **Preferences → Input gestures** while
Apple Music is active, and find the command in **Apple Music**. The shortcut is
scoped to AppleMusic.exe; it is not intercepted in other applications.

## Behavior and limitations

- English Apple Music menu names are supported. Case, access-key markers,
  whitespace, and trailing ellipses are normalized; substring matches are not used.
- Focused UIA list items, data items, and table rows, including their child
  controls, are candidates. The actual open menu must expose the requested command.
- Multiple selections exposed by UIA are refused to avoid changing several items.
- From controls outside a recognized row/card, a uniquely identified player More
  button is tried first, then Control+L if that button is not exposed. If Control+L
  changes selection without moving focus, the add-on focuses the newly selected
  row and confirms focus before opening its menu. If no identifiable song appears
  within three seconds, nothing is invoked.
  The add-on does not guess from a stale selection or infer playback from a
  localized Play/Pause label. Paused tracks work if Apple Music reveals them.
- Original focus is restored after the current-song route where the control
  still exists. If Apple Music leaves the foreground, pending work is cancelled
  without sending keys or stealing focus back.
- Menu lookup waits up to two seconds and inspects only the focused popup.
  Unsupported layouts, menus without keyboard focus, and selections that were
  already present before Control+L may require manual navigation.
- Discovery of an unfocused player Action/More button requires its observed identifier
  and at least two recognized transport identifiers, or a unique More button in
  the same small transport container. It rejects content rows and sidebar
  tree items. No screen coordinates or positional menu navigation are used.
- Compatibility metadata targets NVDA 2025.1 through 2026.1. It is not a claim
  of live testing on every release. This version has 83 automated mock tests and
  the live checks described below.

## Verification

Run `python -m unittest discover -s tests -v` and `python build.py`.
The build validates archive contents and produces a SHA-256 checksum alongside it.

Version 0.4.1 live checks on Apple Music 1.1540.23042.0 confirmed that clicking
Deep Blue focuses its first album track and clicking Get Up! focuses its first
playlist track. NVDA developer information confirmed keyboard focus on both rows.
Album-page F6 focus requests measured 0.221 seconds to Player, 0.303 seconds to
Main content, and 0.579 seconds for wraparound to Search. These timings end at
the focus request and exclude speech completion; they are not performance guarantees.

Live checks completed for this development series: forward/reverse Home-page
section cycling and wraparound; playlist track focus; Enter starting the focused
song through its menu; the player Favorite route returning focus to Shuffle.
Earlier user testing confirmed Suggest Less and Favorite menu activation.
The open Queue-tab correction, complete Lyrics-panel cycling, and entering a
different album/playlist still need full live regression testing. Computer-use
capture failed before these final checks, so 0.4.0 is published as a preview.

Live test checklist:

1. Focus a song, invoke the shortcut, then reopen the menu and verify its state.
2. Repeat on that song and verify **Undo Suggest Less** is never activated.
3. Repeat for an album and a child More button within a row/card.
4. From Pause, Next, Previous, volume and track information, verify the current
   song is affected and original focus is restored.
5. Test no playback, unavailable items, multiple selections, and a slow menu.
6. Switch apps during a pending operation; verify no keys are sent to the other app.
7. Test the shortcut outside Apple Music; verify normal keyboard behavior.
8. Repeat the song, album and player tests with Control+Alt+Up Arrow. Verify a
   favorite is added, then press it again and confirm the favorite remains set.
9. Test F6 and Shift+F6 from Search, Sidebar, Player and content. Verify wrapping,
   remembered controls, hidden panels, and navigation with Queue or Lyrics open.

## Changes in 0.4.1

- Uses direct control lookup and refreshed remembered controls for faster F6.
- Shares ancestor information during fallback section discovery.
- Removes the 1,000-control limit and stops track classification after one usable row.
- Recognizes playlist tracks without a “Track 1” prefix and reveals offscreen rows.
- Detects changed first-track names when a page reuses its list control.
- Checks for arriving tracks sooner while allowing up to four seconds for loading.
- 83 automated tests pass; album and playlist click focus verified live.

## Changes in 0.4.0

- Adds automatic track-list focus and Enter/Numpad Enter playback.
- Scrolls partially visible tracks into view before opening their menus.
- Matches Play with a quoted song title and waits through Apple's popup-window
  transition while the menu is being created.
- Uses the observed TransportBar and Content containers to separate player
  controls from album/playlist header buttons.
- Recognizes Back, Skip Back, Repeat, Queue, Playing Next, and History correctly.
- Finds the player Action button from controls outside its ancestor chain.
- Recognizes Favorited/Favourited as an existing favorite without reversing it.
- Adds regression tests for these behaviors; 76 tests pass.

## Changes in 0.3.5

- Recognizes the live player identifiers, including RepeatButton and
  PlayQueueToggleButton. Do Not Repeat and Queue no longer become Main content.
- Keeps the Queue opener in Player, distinct from an open Queue panel.
- 62 automated tests pass. Live forward/reverse cycle verification is pending.

## Changes in 0.3.4

- Uses the live-inspected Sidebar_Home automation ID family and WinUI
  NavigationViewItem class to recognize sidebar entries exposed as list items.
  Home, library entries, and sidebar playlists no longer masquerade as page content.
- Recognizes Click to search and the Search_Button automation ID.
- Keeps player audio-quality, favorite and unnamed position controls in Player.
- Debug logging identifies section candidates to diagnose unsupported layouts.
- 60 automated tests pass. The sidebar and search identifiers were inspected in
  the live app; full section-cycle verification remains outstanding.

## Changes in 0.3.3

- Classifies Open Navigation and Close Navigation as Sidebar controls, preventing
  F6 from selecting the navigation opener as Main content.
- Rapid F6/Shift+F6 presses share the running discovery scan. The newest press
  chooses its direction; holding a key no longer continually restarts the scan.
  During discovery, repeated presses are coalesced into one section move.
- 56 automated tests pass, including rapid keypresses across multiple scan batches.
  Preference commands are unchanged from 0.3.2.

## Changes in 0.3.2

- Supports Apple's checkable Favourite and Suggest Less menu items through
  Toggle. It checks CurrentToggleState immediately before acting and never
  toggles an already-on or indeterminate item. Undo/removal labels remain protected.
- F6 scans in small time-limited batches instead of waiting 20 ms per element,
  stops when the next section is found, and excludes title-bar controls.
- Recognizes the collapsed Search and Sidebar buttons as navigation destinations.
- 54 automated tests pass, including checkable menu actions and early stopping
  in an 800-row navigation fixture. Live verification is recorded separately.

## Changes in 0.3.1

- Recognizes the player's More button under its actual accessible name, Action.
  A focused Action/More button opens directly without scanning for the player.
- Runs player discovery and section classification in scheduled steps so NVDA
  can process input and speech between reads. Individual UIA provider calls can
  still be slow; this is not a hard timeout on Windows accessibility calls.
- Treats Action as a player control and skips focusable wrapper groups and
  unnamed sliders as section-navigation destinations.
- Cancels older section scans when another F6/Shift+F6 request arrives and avoids
  moving focus if the user has moved it during a scan.
- 50 automated tests pass, including cases based on the reported Action button
  and track-wrapper focus. Live validation of this version is still required.

## Changes in 0.3.0

- Renamed the displayed add-on and package to Apple Music.
- Added F6 and Shift+F6 section navigation with focus memory.
- Added player More-menu discovery for both preference commands.
- Added support for a newly selected song when Control+L leaves focus in the player.
- Replaced the misleading no-playback announcement with a target-discovery failure.
- Expanded automated coverage to 45 tests. The new player and navigation behavior
  has not yet been verified end to end in the live Apple Music app.

## Changes in 0.2.0

- Fixed the invalid-parameter COM error while reading focus by building NVDA's
  required UIA property cache before constructing the NVDA object.
- Avoided retrying a failed initial focus lookup during cleanup and reporting
  that focus could not be restored when no focus change occurred.
- Added the Favorite shortcut, existing-favorite protection, and shared busy-state
  protection so the two commands cannot run concurrently.
- Added regression tests for the cache requirement, cleanup, and favorites.

If a layout fails, report the Apple Music and NVDA versions, focus information
from **NVDA+F1**, and relevant NVDA log entries. Do not include private account data.

## Source and license

Source is included in the package at `appModules/applemusic.py` and in this
project. Licensed under GPL version 2 or later; see [LICENSE](LICENSE).
No network requests are made by the add-on.

API and behavior references:

- [Apple Music Windows keyboard shortcuts](https://support.apple.com/en-nz/guide/music-windows/mus1019/windows)
- [Tell Apple Music what you like](https://support.apple.com/en-gb/guide/music-windows/musf7da17c25/windows)
- [NVDA UIA object implementation](https://github.com/nvaccess/nvda/blob/master/source/NVDAObjects/UIA/__init__.py)
