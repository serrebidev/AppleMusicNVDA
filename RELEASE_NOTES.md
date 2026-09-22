# Apple Music 0.4.8

Makes Enter on a track much faster.

- Enter on a track row double-clicks the row's title, as a mouse user would, and
  puts the mouse pointer back. This is about twice as fast as opening the More
  menu and no longer announces the menu.
- The click only happens when Windows confirms the point belongs to that title,
  so links, buttons and anything covering the row are never clicked. Otherwise
  the add-on uses the More menu as before.

Validation: 146 automated tests pass. Live NVDA MCP testing on NVDA 2027.1 in a
14,363-track playlist: Enter played the focused song, NVDA said only Playing
track. about 0.2 seconds after Enter (the More menu took about 0.8 seconds), and
focus stayed on the row. Album track lists were not tested live; they fall back
to the More menu if the click check fails. Braille was not tested.

Open AppleMusic-0.4.8.nvda-addon to install, then restart NVDA.

## Earlier 0.4.7

Adds a search shortcut and readable names for cards Apple Music leaves unlabeled.

- Control+S opens search and leaves focus in the search field, ready to type.
  A previous query is selected, so typing replaces it.
- Control+1 now opens Home, matching Control+2 and Control+3. All three land on
  the page's first item, even when that page is already open.
- Radio's On Air Now stations read their real names, such as Apple Music Hits,
  instead of AMP.Services.CommonModels.LiveRadioGridLockup. Home's Made for You
  playlists read their title and artists, such as Get Up!, featuring Brooks and
  more. Apple Music draws these titles only in artwork, so the add-on takes them
  from the page data Apple Music caches locally, matched by section and position.
  If the data is missing or does not match, it says Live radio station or reads
  the artists.

- Home's Top Picks read the cached title of Made for You cards, such as Your
  Essentials, Made for You, featuring Man With No Name and more.

Validation: 144 automated tests pass. Live NVDA MCP testing on NVDA 2027.1: all
six On Air Now cards read Apple Music 1, Apple Music Hits, Apple Music Country,
Apple Música Uno, Apple Music Club, and Apple Music Chill. Control+S opened
search, typing entered text, and a second press returned to the field. Control+3
on the open Radio page went straight to Apple Music 1. Top Picks read Your
Essentials. The Playlists Made for You row was covered by automated tests only.
Braille was not tested.

## Earlier 0.4.6

Makes section navigation faster and adds direct sidebar and account shortcuts.

- F6 skips Queue and Lyrics immediately when their exact toggle controls report
  that the panels are closed, avoiding a full scan of long playlists.
- Remembered section controls are refreshed before track discovery.
- Control+1 focuses Home without activating it.
- Control+2 through Control+5 open New, Radio, Library, and Playlists.
- Control+6 opens Settings through the account menu.

Validation: 132 automated tests pass. Live NVDA MCP testing on NVDA 2027.1:
F6 from a 14,363-track list to Search took 0.123 seconds (was 2.32 seconds).
Control+2 and Control+3 opened New and Radio, Control+4 and Control+5 expanded
Library and Playlists, and Control+6 opened Settings. Braille was not tested.

## Earlier 0.4.5

Fixes Home and End navigation in long Apple Music playlists.

- Home and End now wait briefly for Apple Music's virtualized track row to
  finish updating before NVDA announces it.
- A later user focus change cancels the refresh; no focus is moved by the add-on.
- Automated tests cover the stale-name refresh and cancellation path.

Validation: 125 automated tests pass. Live NVDA MCP testing on NVDA 2027.1 in a
229-track playlist confirmed that repeated Home and End presses announced the
settled first and last tracks. Page Up and Page Down announcements matched
refreshed focus reports at both ends. Fresh braille testing remains outstanding.

Open AppleMusic-0.4.5.nvda-addon to install, then restart NVDA.

## Earlier 0.4.4

Fixes Home cards that read an artist list without context and decorative icon
characters that leaked into album names. Includes the Home reading and track
playback improvements since the last GitHub release, 0.4.1.

- Personalized cards with an artist subtitle but no accessible title read
  "Made for You, featuring [artists]". Titles exposed by Apple Music are retained;
  missing artwork titles are not guessed from artists or list position.
- Removes decorative private-use icon-font characters from card text while
  preserving accented, non-Latin, and emoji titles.
- Reads Home card titles and metadata and suppresses duplicate grouping names.
- Enter on track rows uses the track's More button with Shift+F10 fallback;
  child controls keep their native action and delayed menus are guarded.

Validation: 123 automated tests pass; the subtitle correction and named stations
were checked against captured live UI Automation data. User speech logs confirmed
the earlier Home title and grouping improvements. Fresh speech/braille testing of
the latest correction and live verification of the track playback changes remain
outstanding. The package build validates archive contents and writes a SHA-256 file.

Open AppleMusic-0.4.4.nvda-addon to install, then restart NVDA.

## Earlier 0.4.3

Improves reading of Home cards and removes repeated grouping announcements.

- Includes titles and metadata exposed inside Home grid cards, followed by
  category context such as "Made for You". Duplicate labels are read once.
- Includes accessible text clipped below artwork. Retains the original name
  when no additional text is exposed or the card cannot be safely inspected.
- Omits Home grouping announcements already supplied by a nearer group or the
  focused link, while retaining distinct section names.
- Uses NVDA object names for speech and braille without changing card actions.

117 automated tests passed. Subsequent user speech logs confirmed the title and
grouping improvements and identified the two remaining issues addressed in 0.4.4.

Open AppleMusic-0.4.3.nvda-addon to install, then restart NVDA.

## Earlier 0.4.2

Fixes Enter playback from album, radio-show album, and playlist track rows.

- Uses the focused track's own More button after scrolling it into view, with
  Shift+F10 as a fallback when no unique usable More button is exposed.
- Enter on More and other child controls keeps its native action.
- Cancels playback when focus changes before opening the menu and rejects menus
  arriving after the playback timeout.
- Never selects Play Next or Play Last, another row's More button, or multiple tracks.

96 automated tests pass, including the reported Find Your Harmony track label.
The new playback path still needs live verification; the computer-use helper
could not connect during development. Earlier live checks are recorded below.

Open AppleMusic-0.4.2.nvda-addon to install, then restart NVDA.

## Earlier 0.4.1

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
