# Copyright (C) 2026 serrebidev
# SPDX-License-Identifier: GPL-2.0-or-later
"""Apple Music's preference commands, scoped to AppleMusic.exe.

All UI operations run on NVDA's main thread. Timed polls let NVDA process
focus events without sleeping. Menus are matched by name; toggles check state.
"""

import time
import re
import unicodedata
from collections import deque

import api
import appModuleHandler
import controlTypes
import core
import eventHandler
import keyboardHandler
import UIAHandler
import ui
from logHandler import log
from NVDAObjects.UIA import UIA
from scriptHandler import script


Role = controlTypes.Role
State = controlTypes.State
ITEM_ROLES = {Role.LISTITEM, Role.TABLEROW, Role.DATAITEM}
MENU_ROLES = {Role.POPUPMENU, Role.MENUITEM}
ACTIONS = {
	"play": {
		"label": "Play", "names": {"play"}, "undo": set(),
		"already": "", "success": "Playing track.",
	},
	"suggestLess": {
		"label": "Suggest Less",
		"names": {"suggest less"},
		"undo": {"undo suggest less"},
		"already": "Already set to suggest less.",
		"success": "Suggest less.",
	},
	"favorite": {
		"label": "Favorite",
		"names": {"favorite", "favourite", "add to favorites", "add to favourites"},
		"undo": {"undo favorite", "undo favourite", "remove from favorites", "remove from favourites", "unfavorite", "unfavourite", "favorited", "favourited"},
		"already": "Already a favorite.",
		"success": "Added to favorites.",
	},
}
COMMAND_NAMES = set().union(*(action["names"] | action["undo"] for action in ACTIONS.values()))
MORE_NAMES = {"action", "more", "more options", "more actions"}
TRANSPORT_NAMES = {"shuffle", "repeat", "play", "pause", "play/pause", "skip forwards", "skip backwards", "next", "previous"}
SECTION_ORDER = ("Search", "Sidebar", "Player", "Main content", "Queue", "Lyrics")
PLAYER_NAMES = TRANSPORT_NAMES | {
	"volume", "airplay", "mute", "lyrics", "queue", "playing next", "lossless",
	"hi-res lossless", "high-resolution lossless", "audio quality",
	"favorite", "favourite", "undo favorite", "undo favourite",
}
PLAYER_IDS = {
	"ShuffleButton", "RepeatButton", "TransportControl_PlayPauseStop",
	"TransportControl_SkipForward", "TransportControl_SkipBack", "AudioBadgeButton", "VolumeButton",
	"AirPlayButton", "LyricsToggleButton", "PlayQueueToggleButton",
}


def isSidebarItem(obj):
	"""WinUI navigation entries are exposed as ListItem, not TreeViewItem."""
	if not isinstance(obj, UIA):
		return obj.role in {Role.TREEVIEW, Role.TREEVIEWITEM}
	return (
		obj.role in {Role.TREEVIEW, Role.TREEVIEWITEM}
		or (obj.UIAElement.cachedAutomationId or "").startswith("Sidebar_")
		or (obj.UIAElement.cachedClassName or "").rsplit(".", 1)[-1] == "NavigationViewItem"
	)


def sectionFor(obj, processID, lineage=None):
	"""Classify focus using accessible roles and named ancestors, not geometry."""
	if lineage is None:
		lineage = []
		for parent in ancestors(obj):
			if parent.processID != processID:
				break
			lineage.append(parent)
	for parent in lineage:
		if isinstance(parent, UIA) and parent.UIAElement.cachedAutomationId == "TransportBar":
			return "Player"
	for parent in lineage:
		if parent.role in {Role.PANE, Role.GROUPING, Role.LIST, Role.DOCUMENT}:
			name = normalizedName(parent.name)
			if name in {"queue", "playing next", "up next"}:
				return "Queue"
			if name == "lyrics":
				return "Lyrics"
	if any(isSidebarItem(parent) for parent in lineage):
		return "Sidebar"
	if isinstance(obj, UIA) and obj.UIAElement.cachedAutomationId == "NavigationViewBackButton":
		return "Sidebar"
	if obj.role == Role.TOGGLEBUTTON and normalizedName(obj.name) in {"playing next", "history"}:
		return "Queue"
	if obj.role == Role.EDITABLETEXT and normalizedName(obj.name) in {"search", "search apple music", "search field"}:
		return "Search"
	if obj.role == Role.BUTTON and normalizedName(obj.name) in {"search", "search apple music", "click to search"}:
		return "Search"
	if isinstance(obj, UIA) and obj.UIAElement.cachedAutomationId == "Search_Button":
		return "Search"
	if obj.role == Role.BUTTON and normalizedName(obj.name) in {"sidebar", "sidebar actions", "navigation menu", "open navigation", "close navigation"}:
		return "Sidebar"
	if any(parent.role == Role.GROUPING and parent.name == "Content" and isinstance(parent, UIA) and parent.UIAElement.cachedClassName == "LandmarkTarget" for parent in lineage):
		return "Main content"
	if any(parent.role in ITEM_ROLES for parent in lineage):
		return "Main content"
	# Observed player identifiers survive changing state labels/localization.
	if isinstance(obj, UIA) and obj.UIAElement.cachedAutomationId in PLAYER_IDS:
		return "Player"
	if any(parent.role in {Role.PANE, Role.GROUPING, Role.TOOLBAR} and normalizedName(parent.name) in {"player", "now playing", "playback controls", "transport controls"} for parent in lineage):
		return "Player"
	if obj.role in {Role.BUTTON, Role.TOGGLEBUTTON, Role.SLIDER, Role.SPLITBUTTON}:
		if obj.role == Role.SLIDER and not obj.name:
			return "Player"
		if normalizedName(obj.name) in PLAYER_NAMES:
			return "Player"
		if normalizedName(obj.name) == "action":
			return "Player"
	return "Main content"


def isTrackName(name):
	name = normalizedName(name)
	return bool(re.match(r"^track\s+\d+\b", name) or re.search(
		r"\S.+\s\d+\s+(?:hours?|minutes?|seconds?)(?:,?\s+\d+\s+(?:minutes?|seconds?))*$", name,
	))


def trackRow(obj, processID):
	"""Identify numbered album rows and duration-labelled playlist rows."""
	for candidate in ancestors(obj):
		if candidate.processID != processID or candidate.role in MENU_ROLES:
			return None
		if candidate.role in ITEM_ROLES:
			if not isSidebarItem(candidate) and isTrackName(candidate.name):
				return candidate
			return None
	return None


def revealTrack(row):
	"""SetFocus alone does not scroll Apple's partly visible rows into view."""
	try:
		pattern = row._getUIAPattern(UIAHandler.UIA_ScrollItemPatternId, UIAHandler.IUIAutomationScrollItemPattern)
		if pattern:
			pattern.ScrollIntoView()
			return True
	except Exception:
		log.debug("Apple Music: track has no usable ScrollItem pattern", exc_info=True)
	return False


def trackMoreButton(row, processID):
	"""Find one usable More button inside this row, never another track's menu."""
	pending = deque([row])
	seen = set()
	buttons = []
	for unused in range(40):
		if not pending:
			return buttons[0] if len(buttons) == 1 else None
		obj = pending.popleft()
		if not isinstance(obj, UIA) or obj.processID != processID:
			continue
		identity = tuple(obj.UIAElement.GetRuntimeId())
		if identity in seen:
			return None
		seen.add(identity)
		if obj is not row and obj.role in ITEM_ROLES | MENU_ROLES:
			continue
		if obj.states & {State.INVISIBLE, State.OFFSCREEN, State.UNAVAILABLE}:
			continue
		if obj.role in {Role.BUTTON, Role.SPLITBUTTON}:
			if normalizedName(obj.name) in MORE_NAMES and obj.UIAInvokePattern:
				buttons.append(obj)
			continue
		child = obj.firstChild
		for childIndex in range(40):
			if child is None:
				break
			pending.append(child)
			child = child.next
		if child is not None:
			return None
	return None


def playerMoreSteps(focus, processID):
	"""Find More in a small player container, never an arbitrary page More button.

	Require multiple transport controls and reject content rows/navigation trees.
	A bounded complete scan avoids guessing when only part of a tree was read.
	"""
	# Queue/Lyrics controls can live outside the player's ancestor chain.
	# Match the observed player ActionButton identity, never an arbitrary More.
	client = UIAHandler.handler.clientObject
	root = client.ElementFromHandleBuildCache(api.getForegroundObject().windowHandle, UIAHandler.handler.baseCacheRequest)
	condition = client.CreatePropertyCondition(UIAHandler.UIA_IsKeyboardFocusablePropertyId, True)
	elements = root.FindAllBuildCache(UIAHandler.TreeScope_Descendants, condition, UIAHandler.handler.baseCacheRequest)
	identified = []
	transportIDs = set()
	if elements and elements.Length <= 1000:
		for index in range(elements.Length):
			yield
			obj = UIA(UIAElement=elements.GetElement(index))
			identifier = obj.UIAElement.cachedAutomationId
			if identifier not in PLAYER_IDS | {"ActionButton"}:
				continue
			if obj.processID != processID or obj.states & {State.INVISIBLE, State.OFFSCREEN, State.UNAVAILABLE}:
				continue
			lineage = list(ancestors(obj))
			if any(parent.role in ITEM_ROLES | MENU_ROLES | {Role.DIALOG} or isSidebarItem(parent) for parent in lineage):
				continue
			if identifier == "ActionButton" and obj.role in {Role.BUTTON, Role.SPLITBUTTON} and normalizedName(obj.name) in MORE_NAMES:
				identified.append(obj)
			elif identifier in {"ShuffleButton", "RepeatButton", "TransportControl_PlayPauseStop", "TransportControl_SkipForward"}:
				transportIDs.add(identifier)
		if len(identified) == 1 and len(transportIDs) >= 2:
			return identified[0]
		if len(identified) > 1:
			return None
	for depth, parent in enumerate(ancestors(focus)):
		if depth >= 7 or parent.processID != processID or parent.role == Role.WINDOW:
			break
		if parent.role in ITEM_ROLES or parent.role in MENU_ROLES:
			return None
		pending = deque([parent])
		buttons = []
		transport = set()
		unsafe = False
		for unused in range(120):
			yield
			if not pending:
				break
			obj = pending.popleft()
			if obj.processID != processID:
				continue
			if obj.role in ITEM_ROLES or obj.role == Role.TREEVIEWITEM:
				unsafe = True
				break
			if State.INVISIBLE in obj.states or State.OFFSCREEN in obj.states:
				continue
			if obj.role in {Role.BUTTON, Role.TOGGLEBUTTON, Role.SPLITBUTTON}:
				name = normalizedName(obj.name)
				if name in MORE_NAMES and State.UNAVAILABLE not in obj.states:
					buttons.append(obj)
				if name in TRANSPORT_NAMES:
					transport.add(name)
			child = obj.firstChild
			for childIndex in range(120):
				yield
				if child is None:
					break
				pending.append(child)
				child = child.next
			if child is not None:
				unsafe = True
				break
		if not unsafe and not pending and len(buttons) == 1 and len(transport) >= 2:
			return buttons[0]
	return None


def normalizedName(name):
	"""Allow access-key markers, whitespace and trailing menu ellipses only."""
	return " ".join((name or "").replace("&", "").split()).rstrip(".\u2026").strip().casefold()


def ancestors(obj, cache=None):
	seen = set()
	visited = []
	for unused in range(24):
		if obj is None:
			break
		key = tuple(obj.UIAElement.GetRuntimeId()) if isinstance(obj, UIA) else id(obj)
		if key in seen:
			break
		seen.add(key)
		if cache is not None and key in cache:
			for parent in cache[key]:
				yield parent
			visited.extend(cache[key])
			break
		visited.append(obj)
		yield obj
		obj = obj.parent
	if cache is not None:
		for index, parent in enumerate(visited):
			key = tuple(parent.UIAElement.GetRuntimeId()) if isinstance(parent, UIA) else id(parent)
			cache[key] = visited[index:]


def focusedItem(obj, processID):
	"""A row/card containing focus, never an arbitrary selected item elsewhere."""
	for candidate in ancestors(obj):
		if candidate.processID != processID:
			break
		if candidate.role in MENU_ROLES or isSidebarItem(candidate):
			return None
		if candidate.role in ITEM_ROLES:
			return candidate
	return None


def focusedMenu(obj, processID):
	for candidate in ancestors(obj):
		if candidate.processID != processID:
			break
		if candidate.role == Role.POPUPMENU:
			return candidate
	return None


def menuCommands(root, processID):
	"""Inspect only the open menu. Never open submenus or scan the app globally."""
	commands = {}
	pending = [root]
	for unused in range(150):
		if not pending:
			break
		obj = pending.pop()
		if obj.processID != processID:
			continue
		if State.INVISIBLE in obj.states or State.OFFSCREEN in obj.states:
			continue
		if obj.role == Role.MENUITEM:
			name = normalizedName(obj.name)
			if re.fullmatch(r'play ["\u201c].+["\u201d]', name):
				name = "play"
			if name in COMMAND_NAMES:
				commands.setdefault(name, []).append(obj)
			# Do not descend into unopened submenu items.
			continue
		child = obj.firstChild
		for childIndex in range(100):
			if child is None:
				break
			pending.append(child)
			child = child.next
		if child is not None:
			raise RuntimeError("Apple Music menu has too many children to inspect safely")
	if pending:
		raise RuntimeError("Apple Music menu is too large to inspect safely")
	return commands


def homeContent(obj):
	"""Use provider names so checking ancestry cannot recurse into our overlays."""
	for parent in ancestors(obj):
		if parent.processID != obj.processID or isSidebarItem(parent):
			return False
		if isinstance(parent, UIA) and parent.role in {Role.GROUPING, Role.PANE, Role.DOCUMENT} and parent.UIAElement.cachedName == "Home":
			return True
	return False


def homeCardName(card, original):
	"""Read this card's labels, including text clipped below its artwork."""
	labels = []
	subtitles = []
	hasTitle = False
	seen = set()
	pending = [(card.firstChild, 0)]
	for unused in range(64):
		if not pending:
			break
		obj, depth = pending.pop()
		if obj is None:
			continue
		identity = tuple(obj.UIAElement.GetRuntimeId()) if isinstance(obj, UIA) else id(obj)
		if identity in seen:
			return original
		seen.add(identity)
		pending.append((obj.next, depth))
		if obj.processID != card.processID or State.INVISIBLE in obj.states:
			continue
		if obj.role in {Role.STATICTEXT, Role.LINK, Role.GRAPHIC}:
			# XAML icon fonts expose private-use glyphs as text (including
			# supplementary-plane characters). They are not music metadata.
			label = " ".join("".join(char for char in (obj.name or "") if unicodedata.category(char) != "Co").split())
			if label:
				labels.append(label)
				identifier = obj.UIAElement.cachedAutomationId if isinstance(obj, UIA) else ""
				if identifier == "TitleTextBlock":
					hasTitle = True
				elif identifier == "SubtitleTextBlock":
					subtitles.append(label)
		elif obj.role not in {Role.PANE, Role.GROUPING}:
			# Never borrow from a nested list, a menu, or a control's popup.
			continue
		if depth < 6:
			pending.append((obj.firstChild, depth + 1))
		elif obj.firstChild is not None:
			return original
	else:
		return original
	# Preserve punctuation and ampersands in music titles. Remove only complete
	# repeated labels, or labels already contained as words in a richer label.
	def contains(text, fragment):
		return f" {fragment.casefold()} " in f" {text.casefold()} "
	base = " ".join((original or "").split())
	if not labels or all(contains(base, label) for label in labels):
		return original
	# Some personalized cards put their title only in unlabeled artwork.
	# Do not present SubtitleTextBlock's artist list as the missing title or
	# guess which mix/station it is from artists or its position on Home.
	if base == "Made for You" and not hasTitle and len(subtitles) == 1 and all(label in {base, subtitles[0]} for label in labels):
		subtitle = subtitles[0]
		if "," in subtitle and subtitle.casefold().endswith(" and more"):
			subtitle = "featuring " + subtitle
		return f"{base}, {subtitle}"
	parts = []
	for label in labels + [base]:
		if not label or any(contains(part, label) for part in parts):
			continue
		parts = [part for part in parts if not contains(label, part)]
		parts.append(label)
	# The provider's short category is context, not the identity of the music.
	if base in parts and len(parts) > 1:
		parts.remove(base)
		parts.append(base)
	return ", ".join(parts)


class HomeCard(UIA):
	def _get_name(self):
		original = super().name
		try:
			if homeContent(self):
				return homeCardName(self, original)
		except Exception:
			# Virtualized cards may disappear during a property read.
			log.debug("Apple Music: Home card text unavailable", exc_info=True)
		return original


class HomeGrouping(UIA):
	def _get_isPresentableFocusAncestor(self):
		try:
			name = self.UIAElement.cachedName
			if name and homeContent(self):
				focus = api.getFocusObject()
				duplicate = False
				for obj in ancestors(focus):
					if not isinstance(obj, UIA) or obj.processID != self.processID:
						break
					if tuple(obj.UIAElement.GetRuntimeId()) == tuple(self.UIAElement.GetRuntimeId()):
						if duplicate:
							return False
						break
					if obj.UIAElement.cachedName == name:
						duplicate = True
		except Exception:
			log.debug("Apple Music: Home grouping unavailable", exc_info=True)
		return super().isPresentableFocusAncestor


class AppModule(appModuleHandler.AppModule):
	scriptCategory = "Apple Music"
	_operation = None
	_generation = 0
	_navigationGeneration = 0
	_trackFocusGeneration = 0
	_trackPage = None
	_trackBoundary = None

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		if not isinstance(obj, UIA):
			return
		if obj.role in ITEM_ROLES and obj.UIAElement.cachedClassName == "GridViewItem":
			clsList.insert(0, HomeCard)
		elif obj.role == Role.GROUPING:
			clsList.insert(0, HomeGrouping)

	def _trackRows(self, root=None):
		"""Only one row is needed; do not wrap/classify every song on the page."""
		client = UIAHandler.handler.clientObject
		if root is None:
			root = client.ElementFromHandleBuildCache(api.getForegroundObject().windowHandle, UIAHandler.handler.baseCacheRequest)
		condition = client.CreateAndCondition(
			client.CreatePropertyCondition(UIAHandler.UIA_IsKeyboardFocusablePropertyId, True),
			client.CreateOrCondition(
				client.CreatePropertyCondition(UIAHandler.UIA_ControlTypePropertyId, UIAHandler.UIA_ListItemControlTypeId),
				client.CreatePropertyCondition(UIAHandler.UIA_ControlTypePropertyId, UIAHandler.UIA_DataItemControlTypeId),
			),
		)
		elements = root.FindAllBuildCache(UIAHandler.TreeScope_Descendants, condition, UIAHandler.handler.baseCacheRequest)
		rows = []
		if elements:
			for index in range(elements.Length):
				element = elements.GetElement(index)
				if not isTrackName(element.cachedName):
					continue
				obj = UIA(UIAElement=element)
				if obj.processID == self.processID and not obj.states & {State.INVISIBLE, State.UNAVAILABLE} and trackRow(obj, self.processID) is obj and sectionFor(obj, self.processID) == "Main content":
					rows.append(obj)
					break
		return rows

	def _rememberTrackPage(self, row):
		page = tuple(row.parent.UIAElement.GetRuntimeId())
		if page != self._trackPage:
			self._trackPageName = None
		self._trackPage = page

	def event_gainFocus(self, obj, nextHandler):
		pending = self._trackBoundary
		if pending is not None:
			if self._active() and isinstance(obj, UIA) and trackRow(obj, self.processID) is obj and pending["target"] is None:
				pending["target"] = tuple(obj.UIAElement.GetRuntimeId())
				self._trackFocusGeneration += 1
				self._rememberTrackPage(obj)
				return
			self._trackBoundary = None
		nextHandler()
		self._trackFocusGeneration += 1
		if isinstance(obj, UIA) and tuple(obj.UIAElement.GetRuntimeId()) == getattr(self, "_manualSectionTarget", None):
			self._manualSectionTarget = None
			row = trackRow(obj, self.processID)
			if row:
				self._rememberTrackPage(row)
			return
		if not self._active() or self._operation is not None or not isinstance(obj, UIA):
			return
		row = trackRow(obj, self.processID)
		if row:
			self._rememberTrackPage(row)
			return
		if sectionFor(obj, self.processID) in {"Player", "Queue", "Lyrics"} or any(parent.role in MENU_ROLES | {Role.DIALOG} for parent in ancestors(obj)):
			return
		self._scheduleTrackFocus(obj)

	def _scheduleTrackFocus(self, original):
		generation = self._trackFocusGeneration
		originalID = tuple(original.UIAElement.GetRuntimeId())
		attempts = 0
		def check():
			nonlocal attempts
			if generation != self._trackFocusGeneration or not self._active() or self._operation is not None:
				return
			try:
				focus = self._focus()
				if focus is None or tuple(focus.UIAElement.GetRuntimeId()) != originalID:
					return
				rows = self._trackRows()
				if rows:
					page = tuple(rows[0].parent.UIAElement.GetRuntimeId())
					name = normalizedName(rows[0].name)
					previousName = getattr(self, "_trackPageName", None)
					if page != self._trackPage or (previousName is not None and name != previousName):
						revealTrack(rows[0])
						rows[0].setFocus()
						self._trackPage = page
						self._trackPageName = name
						return
					self._trackPageName = name
					return
				attempts += 1
				if attempts < 16:
					core.callLater(250, check)
			except Exception:
				log.debugWarning("Apple Music: track-list focus unavailable", exc_info=True)
		core.callLater(100, check)

	@script(description="Move to the first or last track", gestures=["kb:home", "kb:end"])
	def script_trackBoundary(self, gesture):
		try:
			focus = self._focus() if self._active() else None
		except Exception:
			focus = None
		if focus is None or focus.role not in ITEM_ROLES or trackRow(focus, self.processID) is not focus:
			gesture.send()
			return
		pending = {"original": tuple(focus.UIAElement.GetRuntimeId()), "target": None}
		self._trackBoundary = pending
		gesture.send()

		def report():
			if self._trackBoundary is not pending:
				return
			self._trackBoundary = None
			if not self._active():
				return
			try:
				focus = self._focus()
				if focus is None or focus.role not in ITEM_ROLES or trackRow(focus, self.processID) is not focus:
					return
				identity = tuple(focus.UIAElement.GetRuntimeId())
				if pending["target"] is not None and identity != pending["target"]:
					return
				if pending["target"] is None and identity == pending["original"]:
					return
				eventHandler.queueEvent("gainFocus", focus)
			except Exception:
				log.debug("Apple Music: track boundary refresh unavailable", exc_info=True)

		core.callLater(200, report)

	@script(description="Play the focused track, or activate the focused control", gestures=["kb:enter", "kb:numpadEnter"])
	def script_playTrack(self, gesture):
		focus = self._focus() if self._active() else None
		# More and other child controls keep their native Enter action.
		if focus is not None and focus.role in ITEM_ROLES and trackRow(focus, self.processID) is not None:
			self._begin("play", focus)
		else:
			gesture.send()
			if focus is not None:
				self._trackFocusGeneration += 1
				self._scheduleTrackFocus(focus)

	def _active(self):
		foreground = api.getForegroundObject()
		return foreground is not None and foreground.processID == self.processID

	def _focus(self):
		# Ask UIA directly: NVDA's focus event may still be queued after Ctrl+L.
		element = UIAHandler.handler.clientObject.GetFocusedElement()
		if element and element.CurrentProcessId == self.processID:
			# NVDA's UIA constructor reads cached properties (including the
			# framework ID). A raw GetFocusedElement result lacks that cache.
			return UIA(UIAElement=element.BuildUpdatedCache(UIAHandler.handler.baseCacheRequest))
		return None

	def _action(self):
		return ACTIONS[self._operation["action"]]

	def _selectedItems(self):
		"""Query selected rows within the original window, with NVDA's cache."""
		client = UIAHandler.handler.clientObject
		root = self._operation["root"]
		condition = client.CreatePropertyCondition(UIAHandler.UIA_SelectionItemIsSelectedPropertyId, True)
		elements = root.FindAllBuildCache(UIAHandler.TreeScope_Descendants, condition, UIAHandler.handler.baseCacheRequest)
		items = {}
		if not elements or elements.Length > 100:
			return items
		for index in range(elements.Length):
			element = elements.GetElement(index)
			if element.CurrentProcessId != self.processID:
				continue
			obj = UIA(UIAElement=element)
			if obj.role in ITEM_ROLES and State.INVISIBLE not in obj.states and State.OFFSCREEN not in obj.states:
				items[tuple(element.GetRuntimeId())] = obj
		return items

	def _later(self, callback, delay=100):
		generation = self._generation

		def run():
			if self._operation is None or generation != self._generation:
				return
			try:
				if not self._active():
					self._finish(f"{self._action()['label']} cancelled: Apple Music is no longer active.", restore=False)
					return
				callback()
			except Exception:
				log.exception("Apple Music Suggest Less: UI Automation operation failed")
				self._finish(f"{self._action()['label']} failed. Apple Music's controls could not be accessed.")

		core.callLater(delay, run)

	@script(
		description="Suggest less of the focused song or album, or the current song from the player",
		gesture="kb:control+alt+downArrow",
	)
	def script_suggestLess(self, gesture):
		self._begin("suggestLess")

	@script(
		description="Favorite the focused song or album, or the current song from the player",
		gesture="kb:control+alt+upArrow",
	)
	def script_favorite(self, gesture):
		self._begin("favorite")

	@script(description="Move to the next Apple Music section", gesture="kb:f6")
	def script_nextSection(self, gesture):
		self._switchSection(1)

	@script(description="Move to the previous Apple Music section", gesture="kb:shift+f6")
	def script_previousSection(self, gesture):
		self._switchSection(-1)

	def _enterWhenFocused(self, targetID, generation, then=None):
		"""Press Enter once focus settles on the target; drop it if the user moved on."""
		def press():
			if generation != self._navigationGeneration or not self._active():
				return
			try:
				focus = self._focus()
				if focus is None or tuple(focus.UIAElement.GetRuntimeId()) != targetID:
					return
				keyboardHandler.KeyboardInputGesture.fromName("enter").send()
				if then is not None:
					core.callLater(100, then)
			except Exception:
				log.exception("Apple Music: Enter on shortcut target failed")

		core.callLater(50, press)

	def _focusSidebarControl(self, identifier, label, activate=False):
		self._trackFocusGeneration += 1
		self._navigationGeneration += 1
		generation = self._navigationGeneration
		if not self._active():
			return
		if self._operation is not None:
			ui.message("Wait for the current Apple Music command to finish.")
			return
		try:
			client = UIAHandler.handler.clientObject
			root = client.ElementFromHandleBuildCache(api.getForegroundObject().windowHandle, UIAHandler.handler.baseCacheRequest)
			control = self._controlByID(root, identifier)
			if control is None or not isSidebarItem(control):
				ui.message(f"Apple Music's {label} option is unavailable.")
				return
			targetID = tuple(control.UIAElement.GetRuntimeId())
			self._manualSectionTarget = targetID
			control.setFocus()
		except Exception:
			log.exception("Apple Music: %s focus failed", label)
			ui.message(f"Apple Music's {label} option could not be focused.")
			return
		if activate:
			self._enterWhenFocused(targetID, generation)

	@script(description="Focus Home in the Apple Music sidebar", gesture="kb:control+1")
	def script_focusHome(self, gesture):
		self._focusSidebarControl("Sidebar_Home", "Home")

	@script(description="Open New in the Apple Music sidebar", gesture="kb:control+2")
	def script_focusNew(self, gesture):
		self._focusSidebarControl("Sidebar_New", "New", activate=True)

	@script(description="Open Radio in the Apple Music sidebar", gesture="kb:control+3")
	def script_focusRadio(self, gesture):
		self._focusSidebarControl("Sidebar_Radio", "Radio", activate=True)

	@script(description="Open Library in the Apple Music sidebar", gesture="kb:control+4")
	def script_focusLibrary(self, gesture):
		self._focusSidebarControl("Sidebar_Header_Library", "Library", activate=True)

	@script(description="Open Playlists in the Apple Music sidebar", gesture="kb:control+5")
	def script_focusPlaylists(self, gesture):
		self._focusSidebarControl("Sidebar_Header_Playlists", "Playlists", activate=True)

	@script(description="Open Apple Music Settings from the account menu", gesture="kb:control+6")
	def script_focusAccountSettings(self, gesture):
		self._trackFocusGeneration += 1
		self._navigationGeneration += 1
		generation = self._navigationGeneration
		if not self._active():
			return
		if self._operation is not None:
			ui.message("Wait for the current Apple Music command to finish.")
			return
		try:
			client = UIAHandler.handler.clientObject
			root = client.ElementFromHandleBuildCache(api.getForegroundObject().windowHandle, UIAHandler.handler.baseCacheRequest)
			condition = client.CreatePropertyCondition(
				UIAHandler.UIA_ClassNamePropertyId,
				"Microsoft.UI.Xaml.Controls.NavigationViewItem",
			)
			elements = root.FindAllBuildCache(UIAHandler.TreeScope_Descendants, condition, UIAHandler.handler.baseCacheRequest)
			account = next((
				obj for obj in (UIA(UIAElement=elements.GetElement(index)) for index in range(elements.Length))
				if obj.processID == self.processID
				and isSidebarItem(obj)
				and not obj.UIAElement.cachedAutomationId
				and not obj.states & {State.INVISIBLE, State.OFFSCREEN, State.UNAVAILABLE}
			), None)
			if account is None:
				ui.message("Apple Music's account option is unavailable.")
				return
			accountID = tuple(account.UIAElement.GetRuntimeId())
			self._manualSectionTarget = accountID
			account.setFocus()
		except Exception:
			log.exception("Apple Music: account focus failed")
			ui.message("Apple Music's account option could not be focused.")
			return

		def focusSettings(attempt=0):
			if generation != self._navigationGeneration or not self._active():
				return
			try:
				root = client.ElementFromHandleBuildCache(api.getForegroundObject().windowHandle, UIAHandler.handler.baseCacheRequest)
				condition = client.CreatePropertyCondition(UIAHandler.UIA_NamePropertyId, "Settings")
				element = root.FindFirstBuildCache(UIAHandler.TreeScope_Descendants, condition, UIAHandler.handler.baseCacheRequest)
				if element:
					settings = UIA(UIAElement=element)
					if settings.processID == self.processID and normalizedName(settings.name) == "settings":
						settingsID = tuple(settings.UIAElement.GetRuntimeId())
						self._manualSectionTarget = settingsID
						settings.setFocus()
						self._enterWhenFocused(settingsID, generation)
						return
			except Exception:
				log.debug("Apple Music: Settings lookup failed", exc_info=True)
			if attempt < 4:
				core.callLater(100, lambda: focusSettings(attempt + 1))
			else:
				ui.message("Apple Music's Settings option is unavailable.")

		self._enterWhenFocused(accountID, generation, then=focusSettings)

	def _switchSection(self, direction):
		self._trackFocusGeneration += 1
		if not self._active():
			return
		if self._operation is not None:
			ui.message("Wait for the current Apple Music command to finish.")
			return
		# Key repeat must not starve discovery by restarting it every 200 ms.
		# Keep one scan and let the newest press choose its travel direction.
		if getattr(self, "_navigationScan", None) == self._navigationGeneration:
			self._navigationDirection = direction
			return
		self._navigationGeneration += 1
		generation = self._navigationGeneration
		self._navigationStarted = time.monotonic()
		self._navigationDirection = direction
		try:
			original = self._focus()
			originalID = tuple(original.UIAElement.GetRuntimeId()) if original else None
		except Exception:
			ui.message("Apple Music's focused control is unavailable.")
			return
		steps = self._navigationSteps(direction, originalID)
		self._navigationScan = generation

		def advance():
			if generation != self._navigationGeneration or not self._active():
				if self._navigationScan == generation:
					self._navigationScan = None
				steps.close()
				return
			try:
				# No fixed delay for every control: process a small time-limited
				# batch, then yield to NVDA. This also avoids seconds of timer delay.
				deadline = time.monotonic() + 0.025
				for unused in range(8):
					next(steps)
					if time.monotonic() >= deadline:
						break
			except StopIteration:
				if self._navigationScan == generation:
					self._navigationScan = None
				return
			core.callLater(1, advance)

		core.callLater(1, advance)

	def _controlByID(self, root, identifier):
		client = UIAHandler.handler.clientObject
		condition = client.CreatePropertyCondition(UIAHandler.UIA_AutomationIdPropertyId, identifier)
		element = root.FindFirstBuildCache(UIAHandler.TreeScope_Descendants, condition, UIAHandler.handler.baseCacheRequest)
		if not element:
			return None
		obj = UIA(UIAElement=element)
		if obj.processID == self.processID and not obj.states & {State.INVISIBLE, State.OFFSCREEN, State.UNAVAILABLE}:
			return obj
		return None

	def _openOptionalSections(self, root):
		"""Return known open panels, or None when their toggle state is unavailable."""
		try:
			openSections = set()
			for section, identifier in (("Queue", "PlayQueueToggleButton"), ("Lyrics", "LyricsToggleButton")):
				button = self._controlByID(root, identifier)
				toggle = button.UIATogglePattern if button is not None else None
				if toggle is None:
					return None
				state = toggle.CurrentToggleState
				if state not in {UIAHandler.ToggleState_Off, UIAHandler.ToggleState_On}:
					return None
				if state == UIAHandler.ToggleState_On:
					openSections.add(section)
			return openSections
		except Exception:
			log.debug("Apple Music: optional panel state unavailable", exc_info=True)
			return None

	def _quickSection(self, section, root):
		"""Try a live remembered control or an exact ID before global discovery."""
		try:
			old = getattr(self, "_sectionObjects", {}).get(section)
			if old is not None:
				obj = UIA(UIAElement=old.UIAElement.BuildUpdatedCache(UIAHandler.handler.baseCacheRequest))
				if obj.processID == self.processID and not obj.states & {State.INVISIBLE, State.OFFSCREEN, State.UNAVAILABLE} and sectionFor(obj, self.processID) == section:
					if section != "Main content" or trackRow(obj, self.processID) is obj:
						return obj
		except Exception:
			# Navigation destroys content controls; a stale reference is normal.
			pass
		rows = self._trackRows(root) if section == "Main content" else None
		if rows:
			return rows[0]
		identifier = {"Search": "Search_Button", "Sidebar": "NavigationViewBackButton", "Player": "TransportControl_PlayPauseStop"}.get(section)
		if identifier is None:
			return None
		obj = self._controlByID(root, identifier)
		return obj if obj is not None and sectionFor(obj, self.processID) == section else None

	def _navigationSteps(self, direction, originalID):
		try:
			focus = self._focus()
			if focus is None:
				ui.message("Apple Music's focused control is unavailable.")
				return
			if tuple(focus.UIAElement.GetRuntimeId()) != originalID:
				return
			if any(obj.role in MENU_ROLES or obj.role == Role.DIALOG for obj in ancestors(focus)):
				ui.message("Close the menu or dialog before switching sections.")
				return
			focusID = tuple(focus.UIAElement.GetRuntimeId())
			current = sectionFor(focus, self.processID)
			remembered = getattr(self, "_sectionFocus", {})
			remembered[current] = focusID
			self._sectionFocus = remembered
			objects = getattr(self, "_sectionObjects", {})
			objects[current] = focus
			self._sectionObjects = objects
			yield
			client = UIAHandler.handler.clientObject
			root = client.ElementFromHandleBuildCache(api.getForegroundObject().windowHandle, UIAHandler.handler.baseCacheRequest)
			sections = {}
			openOptional = self._openOptionalSections(root)

			def preferredSection():
				for offset in range(1, len(SECTION_ORDER)):
					name = SECTION_ORDER[(SECTION_ORDER.index(current) + self._navigationDirection * offset) % len(SECTION_ORDER)]
					if openOptional is None or name not in {"Queue", "Lyrics"} or name in openOptional:
						return name
			preferred = preferredSection()
			quick = self._quickSection(preferred, root)
			if quick is not None:
				sections[preferred] = [quick]
				elements = None
			else:
				condition = client.CreatePropertyCondition(UIAHandler.UIA_IsKeyboardFocusablePropertyId, True)
				elements = root.FindAllBuildCache(UIAHandler.TreeScope_Descendants, condition, UIAHandler.handler.baseCacheRequest)
			lineageCache = {}
			if elements:
				for index in range(elements.Length):
					yield
					obj = UIA(UIAElement=elements.GetElement(index))
					if obj.processID != self.processID or obj.states & {State.INVISIBLE, State.OFFSCREEN, State.UNAVAILABLE}:
						continue
					if obj.role in {Role.WINDOW, Role.TITLEBAR, Role.MENUBAR, Role.GROUPING, Role.PANE}:
						continue
					# An unnamed player position slider is not a main-content destination.
					if obj.role == Role.SLIDER and not obj.name:
						continue
					lineage = list(ancestors(obj, lineageCache))
					if any(parent.role == Role.TITLEBAR for parent in lineage):
						continue
					section = sectionFor(obj, self.processID, lineage)
					log.debug("Apple Music section candidate: %s; role=%s; id=%s; section=%s", obj.name, obj.role, obj.UIAElement.cachedAutomationId, section)
					sections.setdefault(section, []).append(obj)
					preferred = preferredSection()
					# As soon as the next section is found, further content rows
					# cannot improve the destination (unless restoring a saved control).
					if section == preferred and (preferred != "Main content" or trackRow(obj, self.processID) is not None) and (preferred not in remembered or tuple(obj.UIAElement.GetRuntimeId()) == remembered[preferred]):
						break
			available = [name for name in SECTION_ORDER if name in sections]
			direction = self._navigationDirection
			preferred = preferredSection()
			if not any(name != current for name in available):
				ui.message("No other Apple Music section is available.")
				return
			if preferred in available:
				destination = preferred
			elif current in available:
				destination = available[(available.index(current) + direction) % len(available)]
			else:
				destination = available[0 if direction > 0 else -1]
			candidates = sections[destination]
			if destination == "Main content":
				tracks = [obj for obj in candidates if isTrackName(obj.name) and trackRow(obj, self.processID) is obj]
				if tracks:
					candidates = tracks
			target = next((obj for obj in candidates if tuple(obj.UIAElement.GetRuntimeId()) == remembered.get(destination)), candidates[0])
			actual = self._focus()
			if actual is None or tuple(actual.UIAElement.GetRuntimeId()) != focusID:
				return
			generation = self._navigationGeneration
			targetID = tuple(target.UIAElement.GetRuntimeId())
			self._manualSectionTarget = targetID
			if trackRow(target, self.processID):
				revealTrack(target)
			target.setFocus()
			log.info("Apple Music: section focus requested in %.3f seconds (%s)", time.monotonic() - self._navigationStarted, destination)

			def report():
				if generation != self._navigationGeneration or not self._active():
					return
				try:
					actual = self._focus()
					if actual and tuple(actual.UIAElement.GetRuntimeId()) == targetID:
						ui.message(destination)
					else:
						ui.message(f"Apple Music could not focus {destination.lower()}.")
				except Exception:
					log.debugWarning("Apple Music: section focus verification failed", exc_info=True)
					ui.message("Apple Music could not confirm section focus.")

			core.callLater(150, report)
		except Exception:
			log.exception("Apple Music: section navigation failed")
			ui.message("Apple Music's sections could not be accessed.")

	def _begin(self, action, expectedFocus=None):
		if not self._active():
			return
		if self._operation is not None:
			ui.message(f"{self._action()['label']} is already in progress.")
			return
		self._generation += 1
		self._navigationGeneration += 1
		self._operation = {"action": action, "original": None, "restore": False, "openedMenu": False}
		if expectedFocus is not None:
			self._operation["expectedFocus"] = tuple(expectedFocus.UIAElement.GetRuntimeId())
		# Defer to avoid injecting keys inside the triggering script.
		self._later(self._start)

	def _start(self):
		focus = self._focus()
		if focus is None:
			self._finish("Apple Music's focused control is not available through UI Automation.")
			return
		expectedFocus = self._operation.get("expectedFocus")
		if expectedFocus is not None and tuple(focus.UIAElement.GetRuntimeId()) != expectedFocus:
			self._finish("Apple Music command cancelled: focus changed.", restore=False)
			return
		self._operation["original"] = focus
		if any(obj.role in MENU_ROLES for obj in ancestors(focus)):
			self._finish("Close the menu and focus a song, album, or player control first.")
			return
		item = focusedItem(focus, self.processID)
		if item is not None:
			self._openMenu(item)
			return
		self._operation["restore"] = True
		# Apple Music exposes the player's More button as "Action". A focused
		# menu button is already an explicit target; do not search its siblings.
		if focus.role in {Role.BUTTON, Role.SPLITBUTTON} and normalizedName(focus.name) in MORE_NAMES:
			self._usePlayerMore(focus)
			return
		self._operation["playerSearch"] = playerMoreSteps(focus, self.processID)
		self._operation["searchDeadline"] = time.monotonic() + 3.0
		self._findPlayerMore()

	def _findPlayerMore(self):
		try:
			# Small batches allow NVDA to handle focus, speech and input between reads.
			for unused in range(8):
				next(self._operation["playerSearch"])
		except StopIteration as result:
			self._usePlayerMore(result.value)
			return
		if time.monotonic() >= self._operation["searchDeadline"]:
			self._usePlayerMore(None)
		else:
			self._later(self._findPlayerMore, 20)

	def _usePlayerMore(self, more):
		focus = self._operation["original"]
		actual = self._focus()
		if actual is None or tuple(actual.UIAElement.GetRuntimeId()) != tuple(focus.UIAElement.GetRuntimeId()):
			self._finish("Apple Music command cancelled: focus changed.", restore=False)
			return
		if more is not None and isinstance(more, UIA) and more.UIAInvokePattern:
			log.debug("Apple Music preferences: invoking Action/More button")
			self._operation["playerMenu"] = True
			self._operation["target"] = tuple(focus.UIAElement.GetRuntimeId())
			more.UIAInvokePattern.Invoke()
			self._operation["openedMenu"] = True
			self._operation["deadline"] = time.monotonic() + 2.0
			self._later(self._waitForMenu, 150)
			return
		self._revealSong()

	def _revealSong(self):
		client = UIAHandler.handler.clientObject
		self._operation["root"] = client.ElementFromHandleBuildCache(
			api.getForegroundObject().windowHandle, UIAHandler.handler.baseCacheRequest,
		)
		self._operation["beforeSelection"] = set(self._selectedItems())
		log.debug("Apple Music preferences: trying Ctrl+L, checking focus and newly selected rows")
		keyboardHandler.KeyboardInputGesture.fromName("control+l").send()
		self._operation["deadline"] = time.monotonic() + 3.0
		self._later(self._waitForSong, 200)

	def _waitForSong(self):
		focus = self._focus()
		item = focusedItem(focus, self.processID) if focus else None
		if item is not None:
			self._openMenu(item)
			return
		selected = self._selectedItems()
		newItems = set(selected) - self._operation["beforeSelection"]
		if len(selected) == 1 and len(newItems) == 1:
			item = selected[newItems.pop()]
			self._operation["pendingTarget"] = tuple(item.UIAElement.GetRuntimeId())
			item.setFocus()
			self._later(self._waitForTargetFocus)
			return
		if time.monotonic() < self._operation["deadline"]:
			self._later(self._waitForSong)
		else:
			log.debug("Apple Music preferences: Ctrl+L did not expose a focused or newly selected song")
			self._finish("Apple Music did not expose the current song. Focus the song or its More button and try again.")

	def _waitForTargetFocus(self):
		focus = self._focus()
		item = focusedItem(focus, self.processID) if focus else None
		if item is not None and tuple(item.UIAElement.GetRuntimeId()) == self._operation["pendingTarget"]:
			self._openMenu(item)
		elif time.monotonic() < self._operation["deadline"]:
			self._later(self._waitForTargetFocus)
		else:
			self._finish("Apple Music selected the current song but could not focus it.")

	def _openMenu(self, item):
		# A context menu can affect every selected row. Refuse bulk actions.
		for parent in ancestors(item.parent):
			if parent.processID != self.processID:
				break
			if isinstance(parent, UIA) and parent.UIASelectionPattern:
				selection = parent.UIASelectionPattern.GetCurrentSelection()
				if selection and selection.Length > 1:
					self._finish(f"Select only one song or album before using {self._action()['label']}.")
					return
				break
		# Focus stays within this item; Shift+F10 is Apple's documented shortcut.
		self._operation["target"] = tuple(item.UIAElement.GetRuntimeId())
		if trackRow(item, self.processID) and revealTrack(item):
			self._later(self._sendTrackMenu, 150)
			return
		self._sendTrackMenu()

	def _sendTrackMenu(self):
		focus = self._focus()
		item = focusedItem(focus, self.processID) if focus else None
		expectedFocus = self._operation.get("expectedFocus")
		if item is None or tuple(item.UIAElement.GetRuntimeId()) != self._operation["target"] or (expectedFocus is not None and tuple(focus.UIAElement.GetRuntimeId()) != expectedFocus):
			self._finish("Apple Music command cancelled: focus changed.", restore=False)
			return
		# Some album/radio track rows ignore Shift+F10 while their own More
		# button works. Resolve it after scrolling, since children may change.
		more = trackMoreButton(item, self.processID) if self._operation["action"] == "play" else None
		actual = self._focus()
		if not self._active() or actual is None or tuple(actual.UIAElement.GetRuntimeId()) != tuple(focus.UIAElement.GetRuntimeId()):
			self._finish("Apple Music command cancelled: focus changed.", restore=False)
			return
		if more is not None:
			log.debug("Apple Music: opening focused track's More button")
			self._operation["menuButton"] = tuple(more.UIAElement.GetRuntimeId())
			more.UIAInvokePattern.Invoke()
		else:
			log.debug("Apple Music: opening focused item's menu with Shift+F10")
			keyboardHandler.KeyboardInputGesture.fromName("shift+f10").send()
		self._operation["openedMenu"] = True
		self._operation["deadline"] = time.monotonic() + 2.0
		self._later(self._waitForMenu, 150)

	def _waitForMenu(self):
		action = self._action()
		label = action["label"]
		# A delayed callback must not consume a menu the user opened after
		# the operation timed out.
		if self._operation["action"] == "play" and time.monotonic() >= self._operation["deadline"]:
			self._finish(f"{label} not available.", restore=False)
			return
		focus = self._focus()
		menu = focusedMenu(focus, self.processID) if focus else None
		openingPopup = focus is not None and focus.role == Role.WINDOW and normalizedName(focus.name) in {"pop-up", "popup"}
		if focus and menu is None and not openingPopup and self._operation.get("expectedFocus") is not None:
			allowedFocus = {self._operation["expectedFocus"], self._operation.get("menuButton")}
			if tuple(focus.UIAElement.GetRuntimeId()) not in allowedFocus:
				self._finish(f"{label} cancelled: focus changed.", restore=False)
				return
		if focus and menu is None and not openingPopup and not self._operation.get("playerMenu"):
			item = focusedItem(focus, self.processID)
			if item is None or tuple(item.UIAElement.GetRuntimeId()) != self._operation["target"]:
				self._finish(f"{label} cancelled: focus changed.", restore=False)
				return
		if menu is not None:
			commands = menuCommands(menu, self.processID)
			# Undo wins even if a provider momentarily exposes both states.
			if any(commands.get(name) for name in action["undo"]):
				self._finish(action["already"])
				return
			suggestions = [command for name in action["names"] for command in commands.get(name, [])]
			if len(suggestions) > 1:
				self._finish(f"{label} is ambiguous in this menu.")
				return
			if suggestions:
				command = suggestions[0]
				if State.CHECKED in command.states:
					self._finish(action["already"])
					return
				if State.UNAVAILABLE in command.states:
					self._finish(f"{label} is unavailable for this item.")
					return
				# Apple's checkable menu items expose Toggle instead of Invoke.
				# Read the live toggle state, not just NVDA's cached CHECKED state.
				toggle = command.UIATogglePattern if isinstance(command, UIA) else None
				pattern = command.UIAInvokePattern if isinstance(command, UIA) else None
				if not toggle and not pattern:
					self._finish(f"Apple Music does not expose a supported action for {label}.")
					return
				if not self._active():
					self._finish(f"{label} cancelled.", restore=False)
					return
				if toggle:
					state = toggle.CurrentToggleState
					if state == UIAHandler.ToggleState_On:
						self._finish(action["already"])
						return
					if state != UIAHandler.ToggleState_Off:
						self._finish(f"{label} has an uncertain checked state; no change made.")
						return
					toggle.Toggle()
				else:
					pattern.Invoke()
				# Give the popup time to close before restoring player focus.
				self._later(lambda: self._finish(action["success"]), 200)
				return
		if time.monotonic() < self._operation["deadline"]:
			self._later(self._waitForMenu)
		else:
			self._finish(f"{label} not available.")

	def _finish(self, message, restore=True):
		operation = self._operation
		self._operation = None
		self._generation += 1
		if operation is None:
			return
		if restore and (operation["openedMenu"] or operation["restore"]) and self._active():
			try:
				if operation["openedMenu"]:
					focus = self._focus()
					if focus and focusedMenu(focus, self.processID):
						keyboardHandler.KeyboardInputGesture.fromName("escape").send()
			except Exception:
				log.debugWarning("Apple Music preferences: could not close menu", exc_info=True)
				message += " The menu could not be closed."
			try:
				if operation["restore"] and operation["original"]:
					operation["original"].setFocus()
			except Exception:
				log.debugWarning("Apple Music preferences: could not restore focus", exc_info=True)
				message += " Original focus could not be restored."
		ui.message(message)

	def terminate(self):
		self._trackBoundary = None
		self._trackFocusGeneration += 1
		self._navigationGeneration += 1
		self._generation += 1
		self._operation = None
		super().terminate()
