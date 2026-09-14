# Project instructions

## Project layout

- `addon/appModules/applemusic.py` contains the NVDA app module for Apple Music
  on Windows. Keep its commands scoped to Apple Music.
- `addon/manifest.ini` defines the add-on identity, version, and NVDA compatibility.
  Preserve the internal name `appleMusicSuggestLess` so existing installations
  continue to upgrade correctly.
- `addon/doc/en/readme.html` is the help document shipped inside the add-on.
- `tests/test_applemusic.py` tests the real app module with mocked NVDA and
  UI Automation objects.
- `build.py` packages the add-on using Python's standard library. Generated
  archives and SHA-256 files go in the ignored `dist/` directory.

## Validation

- For app-module changes, run `python -m unittest discover -s tests -v`.
- For packaging or shipped-file changes, run `python build.py`. The build checks
  ZIP integrity and required archive entries and writes a SHA-256 checksum.
- Run `git diff --check` before committing.
- Mock tests do not establish live Apple Music compatibility. Report automated
  and live testing separately; only claim speech, braille, or focus behavior was
  verified live when it was actually exercised with NVDA and Apple Music.

## Behavior to preserve

- Keep UI operations on NVDA's main thread. Use scheduled callbacks for waits
  so keyboard input and speech can continue.
- Use accessible names, roles, identifiers, and UI Automation patterns to locate
  controls and commands. Do not depend on screen coordinates or menu positions.
- Favorite and Suggest Less must preserve an already-set preference. Never
  invoke removal or undo commands, and reject multiple selected items.
- Enter on a track row plays that track; child controls retain their native
  action. Do not substitute Play Next or Play Last for Play.
- Section navigation moves focus without activating controls. Respect user
  focus changes and cancel pending actions when Apple Music loses the foreground.
- Preserve meaningful names for both speech and braille. Do not invent titles
  that Apple Music does not expose through accessibility.
- Keep runtime dependencies within NVDA and Python's standard library unless a
  requested feature requires otherwise.
