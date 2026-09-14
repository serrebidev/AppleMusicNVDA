# Technical notes and verification

Implementation details and historical validation notes for contributors.
For installation and everyday use, see the [README](../README.md).

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

## Reading Home cards

Home grid cards include titles and metadata exposed inside the card, followed
by context such as "Made for You" or "New Release 2026". Duplicate artwork and
text labels are read once. Text clipped below the artwork can still be included
when Apple Music exposes it through accessibility. If no additional text is
available, the original name is retained.

Some personalized cards expose only an artist subtitle and leave their artwork
unlabeled. These read "Made for You, featuring [artists]"; the add-on cannot
recover a title Apple Music does not expose. Decorative icon-font characters
are excluded from card labels.

Home grouping names are omitted from focus announcements when a nearer group
or the focused control already has that name. Distinct section names remain.
The corrected card name is available to both speech and braille.

## Album, radio show, and playlist tracks

When a newly exposed track list receives attention after navigation, the add-on
focuses a track and scrolls it into view. It recognizes Apple's English numbered
album rows and playlist rows ending with a spoken duration, such as
“Without You Here 3 minutes, 49 seconds”. It will not repeatedly pull you back to the same
list when you move to its header controls. Moving focus elsewhere cancels a
pending automatic move. F6's Main content destination prefers available track
rows over album/playlist header controls.

Press **Enter** or **Numpad Enter** on a track row to play it. The add-on scrolls
the row into view and invokes its own **More** button when one is exposed.
Otherwise it tries Shift+F10. It finds **Play “song title”** or **Play** in that
menu by accessible name, never Play Next or Play Last. This also applies to radio
shows presented as album tracks, such as Find Your Harmony episodes.
Enter on a track's More button opens that menu normally; other child controls
also keep their native action. Multiple selected tracks are refused.
Moving focus before the menu opens cancels playback. Menus arriving after the
playback timeout are not acted on; a manually opened menu is left for you to use.

The focused track may be the previously selected row, rather than the first
track in the album. Pages that reuse the same list control without a focus event,
non-English track names, and unexposed virtual rows can require manual navigation.

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
  of live testing on every release. This version has 123 automated mock tests.
  User logs verified the 0.4.3 Home titles and grouping fixes. The 0.4.4 subtitle
  correction was checked against captured live controls; its speech/braille output
  and the 0.4.2 playback changes still need live verification.

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

## Add-on identity

The display name is Apple Music. The internal ID remains
`appleMusicSuggestLess` to preserve upgrades from earlier versions.

## References

API and behavior references:

- [Apple Music Windows keyboard shortcuts](https://support.apple.com/en-nz/guide/music-windows/mus1019/windows)
- [Tell Apple Music what you like](https://support.apple.com/en-gb/guide/music-windows/musf7da17c25/windows)
- [NVDA UIA object implementation](https://github.com/nvaccess/nvda/blob/master/source/NVDAObjects/UIA/__init__.py)
