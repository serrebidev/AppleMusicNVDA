# Apple Music for NVDA

A free NVDA add-on for Apple Music on Windows, built for quicker keyboard
navigation, clearer Home card announcements, and easy access to Favorite and
Suggest Less.

## Features

- Move between Search, Sidebar, Player, Main content, and supported open Queue
  and Lyrics panels with F6 and Shift+F6.
- Return to the last control you left in a section when using section navigation.
- Move into newly opened album and playlist track lists and bring the focused
  track into view.
- Play the focused album, playlist, or radio-show track with Enter.
- Favorite a song or album, or suggest less of it, with a keyboard shortcut.
  The same commands work on the current song from player controls.
- Keep existing favorites and Suggest Less preferences when you repeat a shortcut.
- Read titles and metadata exposed inside Home cards, with fewer duplicate
  labels and grouping announcements. Improved names work with speech and braille.
- Reassign the add-on's shortcuts in NVDA's Input gestures dialog.

The add-on runs inside NVDA. No mouse, AutoHotkey, or extra Python packages are
needed. It works with the Windows Apple Music app; its shortcuts only apply
while that app is active.

## Help

The [add-on user guide](addon/doc/en/readme.html) covers navigation, playback,
Home cards, and preference commands. A copy is included in the installed add-on
for offline use. The shortcuts and basic steps are also listed below.

## Download and install

Grab the latest build from the
[Releases page](https://github.com/serrebidev/AppleMusicNVDA/releases/latest).
For a version-by-version history, see the [changelog](CHANGELOG.md).

You need NVDA and the Windows Apple Music app. The current compatibility
metadata targets NVDA 2025.1 through 2026.1. English Apple Music menus are
supported, including both Favorite and Favourite spellings.

1. Download the `.nvda-addon` file.
2. Open it and confirm NVDA's installation prompt.
3. Restart NVDA when prompted, then open Apple Music.

Installing a newer version upgrades the existing add-on, including earlier
versions named Apple Music Suggest Less.

## Keyboard shortcuts

These are the add-on's default shortcuts.

| Shortcut | Action |
| --- | --- |
| F6 | Move to the next available section. |
| Shift+F6 | Move to the previous available section. |
| Enter or Numpad Enter | Play the focused track row. Other controls keep their normal Enter action. |
| Control+Alt+Up Arrow | Favorite the focused song or album, or the current song from player controls. |
| Control+Alt+Down Arrow | Suggest less of the focused song or album, or the current song from player controls. |

To change a shortcut, open NVDA's **Preferences > Input gestures** while Apple
Music is active, then find the command under **Apple Music**.

## Using the add-on

### Moving between sections

Press **F6** to move through Search, Sidebar, Player, Main content, Queue, and
Lyrics. **Shift+F6** moves in reverse. Navigation wraps around and skips hidden
or unavailable sections.

The add-on remembers the last control you left in each section. Moving between
sections does not activate buttons or start playback. Use **Tab** or the arrow
keys within a section, and close any open menu or dialog before switching sections.

### Playing tracks

When you open a supported album or playlist track list, the add-on focuses a
track and brings it into view. This may be the previously selected track.
**F6** also prefers tracks over header controls when moving to Main content.

Press **Enter** or **Numpad Enter** on a track row to play it. This also works
with radio shows presented as album tracks. Enter on a track's More button
opens its menu normally, and other child controls keep their usual action.

### Favorite and Suggest Less

Focus one song or album and press **Control+Alt+Up Arrow** to favorite it, or
**Control+Alt+Down Arrow** to suggest less of it. From player controls, the
add-on tries to apply the command to the current song and restore your original
focus afterward. Keep focus in place until NVDA announces the result.

Repeating a shortcut keeps the preference set. NVDA tells you when the item is
already a favorite, already set to Suggest Less, or the command is unavailable.
Select only one song or album at a time.

### Reading Home cards

Home cards include titles and metadata Apple Music exposes through accessibility.
Repeated artwork labels and grouping names are removed from announcements, and
the improved names work with both speech and braille.

When a personalized card exposes artists but no title, it reads
“Made for You, featuring [artists].” The add-on cannot recover a title Apple Music
does not expose.

## Known limitations

- Some layouts, track lists, and Queue or Lyrics panels still need manual
  navigation. Section and track detection relies partly on English labels.
- If the current song cannot be found from the player, focus the song or its
  More button and try again.
- Moving focus during a pending command can cancel it. Switching to another app
  cancels pending work.
- Success feedback means Apple Music accepted the action through accessibility;
  it does not independently confirm that Apple's server saved the preference.
- Compatibility metadata and mock tests do not establish live testing on every
  supported version. Some playback and Queue/Lyrics navigation changes still
  need full live verification. See the
  [technical notes and testing record](docs/technical-notes.md) for details.

## Building

The build uses Python's standard library. From the repository folder, run:

```console
python build.py
```

The installable add-on and its SHA-256 checksum are written to `dist/`.
The build checks the archive's integrity and required files. Open the resulting
`.nvda-addon` file to install it in NVDA.

## Debug logging

When reporting a problem, include your Apple Music and NVDA versions, focus
information from **NVDA+F1**, and relevant NVDA log entries. Leave out private
account data.

## Contributing

Pull requests are welcome. Include what changed and how you checked it.
For app-module changes, run:

```console
python -m unittest discover -s tests -v
```

These tests use mocked NVDA and UI Automation objects. For navigation, playback,
speech, or braille changes, describe any testing you completed in the live app.
See the [technical notes](docs/technical-notes.md) for implementation details
and the live test checklist.

## License

Apple Music for NVDA is licensed under
[GPL version 2 or later](LICENSE). Source is included in this repository and
in the add-on package at `appModules/applemusic.py`.
The add-on makes no network requests.

## Community and support

Report bugs and request features in
[Issues](https://github.com/serrebidev/AppleMusicNVDA/issues).
For questions, feedback, and release news, join the
[SerrebiProjects Telegram group](https://t.me/SerrebiProjects).
