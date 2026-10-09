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

## Release

- Before every release, install the built package into the owner's NVDA for
  testing: `python build.py`, then
  `Start-Process dist\AppleMusic-<version>.nvda-addon` and let the owner
  confirm NVDA's prompt and restart. Never use `pendingInstall` while NVDA runs.
  Wait for the owner's go-ahead before tagging or publishing.
- Every GitHub release also goes to the NVDA Add-on Store. After the release
  assets exist, open the store's web form pre-filled, for the owner to submit:
  `https://github.com/nvaccess/addon-datastore/issues/new?template=registerAddon.yml`
  plus `&title=`, `&download-url=` (the release asset), `&source-url=`,
  `&publisher=serrebidev`, `&channel=`, `&license-name=GPL+v2` and
  `&license-url=https://www.gnu.org/licenses/gpl-2.0.html`. Do not use
  `gh issue create`: only the form adds the `autoSubmissionFromIssue` label that
  starts the store's checks, and outside users cannot add it later.
  The Channel dropdown ignores `&channel=` and defaults to stable, so it must
  be picked by hand. Use channel `beta` while `lastTestedNVDAVersion` is experimental in
  `transform/nvdaAPIVersions.json` of that repo, `stable` otherwise. Confirm the
  bot's "has been accepted" comment, and never change a submitted package.

## Behavior to preserve

- Keep UI operations on NVDA's main thread. Use scheduled callbacks for waits
  so keyboard input and speech can continue.
- Use accessible names, roles, identifiers, and UI Automation patterns to locate
  controls and commands. Do not depend on fixed screen coordinates or menu
  positions. The one pointer action: Enter on a track row double-clicks a plain
  text cell of that row, at a point taken from UIA that must hit-test back to
  the same cell, then restores the pointer. Otherwise it uses the More menu.
- Favorite and Suggest Less must preserve an already-set preference. Never
  invoke removal or undo commands from them, and reject multiple selected items.
  Only the explicit Remove favorite command (Control+Alt+Shift+Up) may uncheck
  Favourite or invoke a removal command, and it must never add a favorite.
- Enter on a track row plays that track; child controls retain their native
  action. Do not substitute Play Next or Play Last for Play.
- Section navigation moves focus without activating controls. Respect user
  focus changes and cancel pending actions when Apple Music loses the foreground.
- Preserve meaningful names for both speech and braille. Do not invent titles
  that Apple Music does not expose through accessibility. The one exception:
  cards Apple Music names with an internal type name (AMP.Services...) may use
  Apple Music's own cached API responses in its INetCache, matched by shelf
  title and position, and only when the shelf sizes are equal. Never guess from
  OCR, artwork, or position alone.
- Keep runtime dependencies within NVDA and Python's standard library unless a
  requested feature requires otherwise.
