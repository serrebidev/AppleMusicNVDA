# Changelog

Release history previously recorded in the README. Test results and outstanding
live checks describe each release at the time they were recorded.

## Changes in 0.4.6

- Skips known-closed Queue and Lyrics panels through their exact toggle controls,
  avoiding a full playlist-tree scan when F6 moves from Main content to Search.
- Refreshes remembered section controls before searching for track rows.
- Adds Control+1 to focus Home. Control+2 through Control+5 open New, Radio,
  Library, and Playlists. Control+6 opens Settings through the account menu.
- 132 automated tests pass. Live NVDA MCP: F6 to Search from a 14,363-track list
  took 0.123 seconds, down from 2.32; Control+2 through Control+6 verified.

## Changes in 0.4.5

- Makes Home and End announce the settled first or last playlist track instead
  of a stale name from Apple Music's recycled list row.
- Cancels the delayed refresh when focus changes again or Apple Music loses the
  foreground.
- 125 automated tests pass. Live NVDA MCP testing on NVDA 2027.1 verified Home
  and End in a 229-track playlist; Page Up and Page Down remained accurate.

## Changes in 0.4.4

- Labels the artist-only personalized card as "Made for You, featuring [artists]"
  when Apple exposes no title. Uses the observed SubtitleTextBlock identifier;
  no mix or station title is guessed from artists or list position.
- Excludes decorative private-use icon-font glyphs, including the reported
  supplementary-plane character, while preserving ordinary Unicode titles.
- 123 automated tests pass. Captured live data verified the subtitle fallback
  and preservation of named stations. Fresh speech/braille verification is pending.

## Changes in 0.4.3

- Reads text exposed inside Home grid cards to supplement category-only names.
- Removes repeated artwork/text labels and duplicate Home grouping announcements.
- Keeps original names when cards lack text, become unavailable, or exceed the
  bounded inspection limit. Sidebar entries and other pages retain their names.
- 117 automated tests passed. Subsequent user speech logs confirmed Home titles
  and removal of duplicate grouping announcements. Artist-only cards and an icon
  glyph found in those logs are addressed in 0.4.4.

## Changes in 0.4.2

- Enter on an album, radio-show album, or playlist track invokes its own More
  button, falling back to Shift+F10 when no unique usable button is exposed.
- Enter on More and other track child controls keeps its native action.
- Playback stays tied to the row focused when Enter was pressed, including
  while waiting for scrolling, and ignores menus arriving after its timeout.
- 96 automated tests pass, including the reported Find Your Harmony row label,
  menu isolation, multiple selections, child controls, and delayed playback.
- Live verification of these changes remains outstanding: the computer-use
  helper could not connect during development.

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
