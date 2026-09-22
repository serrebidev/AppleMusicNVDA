"""Exercise the real app module with a deterministic NVDA/UIA test harness."""
import importlib.util
from pathlib import Path
import sys
import types
import os
import unittest
from unittest.mock import patch, Mock


class Node:
    counter = 0
    isPresentableFocusAncestor = True
    value = ""
    positionInfo = None

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def __new__(cls, *args, UIAElement=None, **kwargs):
        if UIAElement is not None:
            if not UIAElement.cacheBuilt:
                raise RuntimeError("UIA constructor requires NVDA's base property cache")
            return UIAElement
        return super().__new__(cls)

    def __init__(self, role=None, name="", children=(), processID=42, UIAElement=None):
        if UIAElement is not None:
            return
        Node.counter += 1
        self.identity = Node.counter
        self.role, self.name, self.processID = role, name, processID
        self.CurrentProcessId = processID
        self.cachedAutomationId = ""
        self.cachedClassName = ""
        self.cacheBuilt = False
        self.parent = self.firstChild = self.next = None
        self.states = set()
        self.UIAElement = self
        self.UIAInvokePattern = Mock()
        self.UIATogglePattern = None
        self.UIASelectionPattern = None
        self._getUIAPattern = Mock(return_value=None)
        self.setFocus = Mock()
        for index, child in enumerate(children):
            child.parent = self
            if index:
                children[index - 1].next = child
            else:
                self.firstChild = child

    def GetRuntimeId(self):
        return [self.identity]

    @property
    def cachedName(self):
        return self.name

    def BuildUpdatedCache(self, request):
        if request is not music.UIAHandler.handler.baseCacheRequest:
            raise RuntimeError("Wrong cache request")
        self.cacheBuilt = True
        return self


def installStubs():
    for name in ("api", "appModuleHandler", "controlTypes", "core", "eventHandler", "keyboardHandler", "mouseHandler", "winUser",
                 "UIAHandler", "ui", "logHandler", "NVDAObjects", "NVDAObjects.UIA", "scriptHandler"):
        sys.modules[name] = types.ModuleType(name)
    sys.modules["appModuleHandler"].AppModule = type("AppModule", (), {"terminate": lambda self: None})
    sys.modules["controlTypes"].Role = types.SimpleNamespace(**{
        name: name for name in ("LISTITEM", "TABLEROW", "DATAITEM", "POPUPMENU", "MENUITEM", "TREEVIEWITEM", "WINDOW", "BUTTON", "TOGGLEBUTTON", "SPLITBUTTON", "PANE", "GROUPING", "LIST", "DOCUMENT", "TREEVIEW", "EDITABLETEXT", "TOOLBAR", "SLIDER", "DIALOG", "TITLEBAR", "MENUBAR", "STATICTEXT", "LINK", "GRAPHIC")
    })
    sys.modules["controlTypes"].State = types.SimpleNamespace(**{
        name: name for name in ("INVISIBLE", "OFFSCREEN", "UNAVAILABLE", "CHECKED", "SELECTED")
    })
    sys.modules["NVDAObjects.UIA"].UIA = Node
    sys.modules["scriptHandler"].script = lambda **kwargs: lambda function: function
    sys.modules["logHandler"].log = Mock()
    location = Path(__file__).resolve().parents[1] / "addon/appModules/applemusic.py"
    spec = importlib.util.spec_from_file_location("applemusicUnderTest", location)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


music = installStubs()
# Never read the real Apple Music cache on the test machine.
music.SHELF_CACHE = os.path.join(os.path.dirname(__file__), "no-apple-music-cache")


class SuggestLessTests(unittest.TestCase):
    def setUp(self):
        self.app = music.AppModule()
        self.app.processID = 42
        self.focus = Node("LISTITEM", "Song")
        self.foreground = Node("WINDOW")
        self.foreground.windowHandle = 123
        self.selected = []
        self.root = types.SimpleNamespace(FindAllBuildCache=lambda *args: types.SimpleNamespace(
            Length=len(self.selected), GetElement=lambda index: self.selected[index].BuildUpdatedCache(music.UIAHandler.handler.baseCacheRequest),
        ))
        self.root.FindFirstBuildCache = lambda scope, condition, cache: next((
            obj.BuildUpdatedCache(cache) for obj in self.selected
            if obj.cachedAutomationId == condition[1] or obj.name == condition[1]
        ), None)
        self.pending, self.keys, self.messages = [], [], []
        self.onKey = lambda key: None
        music.api.getForegroundObject = lambda: self.foreground
        music.UIAHandler.handler = types.SimpleNamespace(
            clientObject=types.SimpleNamespace(
                GetFocusedElement=lambda: self.focus,
                ElementFromHandleBuildCache=lambda *args: self.root,
                CreatePropertyCondition=lambda *args: args,
                CreateOrCondition=lambda *args: args,
                CreateAndCondition=lambda *args: args,
            ),
            baseCacheRequest=object(),
        )
        music.log.reset_mock()
        music.UIAHandler.UIA_SelectionItemIsSelectedPropertyId = 30079
        music.UIAHandler.TreeScope_Descendants = 4
        music.UIAHandler.UIA_IsKeyboardFocusablePropertyId = 30009
        music.UIAHandler.UIA_AutomationIdPropertyId = 30011
        music.UIAHandler.UIA_ClassNamePropertyId = 30012
        music.UIAHandler.UIA_NamePropertyId = 30005
        music.UIAHandler.UIA_ControlTypePropertyId = 30003
        music.UIAHandler.UIA_ListItemControlTypeId = 50007
        music.UIAHandler.UIA_DataItemControlTypeId = 50029
        music.UIAHandler.ToggleState_Off = 0
        music.UIAHandler.ToggleState_On = 1
        music.UIAHandler.UIA_ScrollItemPatternId = 10017
        music.UIAHandler.IUIAutomationScrollItemPattern = object()
        music.core.callLater = lambda delay, callback: self.pending.append(callback)
        music.eventHandler.queueEvent = Mock()
        music.ui.message = self.messages.append

        def send(key):
            self.keys.append(key)
            self.onKey(key)

        music.keyboardHandler.KeyboardInputGesture = types.SimpleNamespace(
            fromName=lambda key: types.SimpleNamespace(send=lambda: send(key))
        )

    def tick(self):
        self.pending.pop(0)()

    def drain(self):
        for unused in range(2000):
            if not self.pending:
                return
            self.tick()
        self.fail("Callbacks did not finish")

    def until(self, predicate):
        for unused in range(2000):
            if predicate():
                return
            self.tick()
        self.fail("Expected asynchronous result was not reached")

    def start(self):
        self.app.script_suggestLess(None)
        self.tick()

    def openMenu(self, *commands):
        menu = Node("POPUPMENU", children=commands)
        self.focus = commands[0] if commands else menu
        return menu

    def test_focused_child_uses_own_row(self):
        child = Node("BUTTON", "More")
        row = Node("DATAITEM", children=[child])
        self.focus = child
        self.start()
        self.assertEqual(self.keys, ["shift+f10"])
        self.assertEqual(self.app._operation["target"], tuple(row.GetRuntimeId()))

    def test_exact_command_invoked_once(self):
        self.start()
        command = Node("MENUITEM", "Suggest Less")
        self.openMenu(command)
        self.tick()
        command.UIAInvokePattern.Invoke.assert_called_once_with()
        self.tick()
        self.assertEqual(self.messages[-1], "Suggest less.")
        self.assertIsNone(self.app._operation)

    def test_undo_wins_even_when_both_exposed(self):
        self.start()
        command = Node("MENUITEM", "Suggest Less")
        undo = Node("MENUITEM", "Undo Suggest Less")
        self.openMenu(command, undo)
        self.tick()
        command.UIAInvokePattern.Invoke.assert_not_called()
        undo.UIAInvokePattern.Invoke.assert_not_called()
        self.assertEqual(self.messages[-1], "Already set to suggest less.")

    def test_normalization_does_not_turn_undo_into_action(self):
        self.assertEqual(music.normalizedName(" &Suggest   Less… "), "suggest less")
        self.assertNotEqual(music.normalizedName("Undo Suggest Less"), "suggest less")

    def test_unrelated_or_hidden_menu_commands_ignored(self):
        self.start()
        similar = Node("MENUITEM", "Suggest Less Like This")
        hidden = Node("MENUITEM", "Suggest Less")
        hidden.states.add("INVISIBLE")
        foreign = Node("MENUITEM", "Suggest Less", processID=99)
        self.openMenu(similar, hidden, foreign)
        self.app._operation["deadline"] = 0
        self.tick()
        for node in (similar, hidden, foreign):
            node.UIAInvokePattern.Invoke.assert_not_called()
        self.assertEqual(self.messages[-1], "Suggest Less not available.")

    def test_player_reveals_song_then_restores(self):
        player = self.focus = Node("BUTTON", "Pause")
        self.start()
        self.assertEqual(self.keys, ["control+l"])
        self.focus = Node("LISTITEM", "Current song")
        self.tick()
        command = Node("MENUITEM", "Suggest Less")
        self.openMenu(command)
        self.tick()
        self.tick()
        player.setFocus.assert_called_once_with()
        command.UIAInvokePattern.Invoke.assert_called_once_with()

    def test_ctrl_l_timeout_never_uses_stale_selection(self):
        self.focus = Node("BUTTON", "Play")
        self.start()
        self.app._operation["deadline"] = 0
        self.tick()
        self.assertEqual(self.keys, ["control+l"])
        self.assertIn("did not expose the current song", self.messages[-1])

    def test_switching_apps_cancels_without_escape_or_focus_restore(self):
        player = self.focus = Node("BUTTON", "Pause")
        self.start()
        self.foreground = Node("WINDOW", processID=99)
        self.tick()
        self.assertEqual(self.keys, ["control+l"])
        player.setFocus.assert_not_called()
        self.assertIsNone(self.app._operation)

    def test_inactive_app_ignores_shortcut(self):
        self.foreground.processID = 99
        self.app.script_suggestLess(None)
        self.assertFalse(self.pending or self.keys or self.messages)

    def test_repeated_shortcut_does_not_start_another_operation(self):
        self.start()
        self.app.script_suggestLess(None)
        self.assertEqual(self.keys, ["shift+f10"])
        self.assertIn("already in progress", self.messages[-1])

    def test_disabled_action_not_invoked(self):
        self.start()
        command = Node("MENUITEM", "Suggest Less")
        command.states.add("UNAVAILABLE")
        self.openMenu(command)
        self.tick()
        command.UIAInvokePattern.Invoke.assert_not_called()
        self.assertIn("unavailable", self.messages[-1])

    def test_no_invoke_pattern_never_uses_toggle(self):
        self.start()
        command = Node("MENUITEM", "Suggest Less")
        command.UIAInvokePattern = None
        command.doAction = Mock()
        self.openMenu(command)
        self.tick()
        command.doAction.assert_not_called()
        self.assertIn("supported action", self.messages[-1])

    def test_multiple_selection_is_rejected(self):
        container = Node("LIST", children=[self.focus])
        container.UIASelectionPattern = types.SimpleNamespace(
            GetCurrentSelection=lambda: types.SimpleNamespace(Length=2)
        )
        self.start()
        self.assertEqual(self.keys, [])
        self.assertIn("only one", self.messages[-1])

    def test_existing_menu_is_not_repurposed(self):
        self.openMenu(Node("MENUITEM", "Suggest Less"))
        self.start()
        self.assertEqual(self.keys, [])
        self.assertIn("Close the menu", self.messages[-1])

    def test_changed_focus_before_menu_cancels(self):
        self.start()
        self.focus = Node("LISTITEM", "A different song")
        self.tick()
        self.assertEqual(self.keys, ["shift+f10"])
        self.assertIn("focus changed", self.messages[-1])

    def test_duplicate_commands_are_not_guessed(self):
        self.start()
        commands = [Node("MENUITEM", "Suggest Less") for unused in range(2)]
        self.openMenu(*commands)
        self.tick()
        for command in commands:
            command.UIAInvokePattern.Invoke.assert_not_called()
        self.assertIn("ambiguous", self.messages[-1])

    def test_provider_failure_releases_busy_state(self):
        self.start()
        command = Node("MENUITEM", "Suggest Less")
        command.UIAInvokePattern.Invoke.side_effect = RuntimeError("Stale element")
        self.openMenu(command)
        self.tick()
        self.assertIsNone(self.app._operation)
        self.assertIn("failed", self.messages[-1])

    def test_termination_invalidates_pending_callback(self):
        self.app.script_suggestLess(None)
        self.app.terminate()
        self.tick()
        self.assertEqual(self.keys, [])

    def test_missing_uia_focus_explained(self):
        self.focus = None
        self.start()
        self.assertIn("not available through UI Automation", self.messages[-1])
        self.assertEqual(self.keys, [])

    def test_tree_navigation_item_is_not_a_song(self):
        self.focus = Node("TREEVIEWITEM", "Library")
        self.start()
        self.assertEqual(self.keys, ["control+l"])

    def test_focus_element_is_cached_before_wrapping(self):
        self.assertFalse(self.focus.cacheBuilt)
        self.assertIs(self.app._focus(), self.focus)
        self.assertTrue(self.focus.cacheBuilt)

    def test_initial_focus_failure_does_not_retry_during_cleanup(self):
        getter = Mock(side_effect=RuntimeError("Invalid parameter"))
        music.UIAHandler.handler.clientObject.GetFocusedElement = getter
        self.start()
        getter.assert_called_once_with()
        self.assertEqual(self.keys, [])
        self.assertNotIn("restored", self.messages[-1])
        music.log.debugWarning.assert_not_called()
        self.assertIsNone(self.app._operation)

    def test_favorite_labels_invoke_only_favorite(self):
        for label in ("Favorite", "Favourite", "Add to Favorites", "Add to Favourites"):
            with self.subTest(label=label):
                self.setUp()
                self.app.script_favorite(None)
                self.tick()
                favorite = Node("MENUITEM", label)
                less = Node("MENUITEM", "Suggest Less")
                self.openMenu(favorite, less)
                self.tick()
                self.tick()
                favorite.UIAInvokePattern.Invoke.assert_called_once_with()
                less.UIAInvokePattern.Invoke.assert_not_called()
                self.assertEqual(self.messages[-1], "Added to favorites.")

    def test_remove_favorite_is_never_invoked(self):
        for label in music.ACTIONS["favorite"]["undo"]:
            with self.subTest(label=label):
                self.setUp()
                self.app.script_favorite(None)
                self.tick()
                remove = Node("MENUITEM", label)
                favorite = Node("MENUITEM", "Favorite")
                self.openMenu(remove, favorite)
                self.tick()
                remove.UIAInvokePattern.Invoke.assert_not_called()
                favorite.UIAInvokePattern.Invoke.assert_not_called()
                self.assertEqual(self.messages[-1], "Already a favorite.")

    def test_checked_favorite_is_not_toggled_off(self):
        self.app.script_favorite(None)
        self.tick()
        favorite = Node("MENUITEM", "Favorite")
        favorite.states.add("CHECKED")
        self.openMenu(favorite)
        self.tick()
        favorite.UIAInvokePattern.Invoke.assert_not_called()
        self.assertEqual(self.messages[-1], "Already a favorite.")

    def test_favorite_player_route_restores_focus(self):
        player = self.focus = Node("BUTTON", "Pause")
        self.app.script_favorite(None)
        self.tick()
        self.assertEqual(self.keys, ["control+l"])
        self.focus = Node("LISTITEM", "Current song")
        self.tick()
        favorite = Node("MENUITEM", "Favorite")
        self.openMenu(favorite)
        self.tick()
        self.tick()
        favorite.UIAInvokePattern.Invoke.assert_called_once_with()
        player.setFocus.assert_called_once_with()

    def test_two_commands_cannot_overlap(self):
        self.start()
        self.app.script_favorite(None)
        self.assertEqual(self.app._operation["action"], "suggestLess")
        self.assertEqual(self.keys, ["shift+f10"])

    def test_favorite_missing_does_not_invoke_suggest_less(self):
        self.app.script_favorite(None)
        self.tick()
        less = Node("MENUITEM", "Suggest Less")
        self.openMenu(less)
        self.app._operation["deadline"] = 0
        self.tick()
        less.UIAInvokePattern.Invoke.assert_not_called()
        self.assertEqual(self.messages[-1], "Favorite not available.")

    def test_menu_read_failure_does_not_prevent_player_restoration(self):
        player = self.focus = Node("BUTTON", "Pause")
        self.start()
        self.app._operation["openedMenu"] = True
        music.UIAHandler.handler.clientObject.GetFocusedElement = Mock(side_effect=RuntimeError("Stale menu"))
        self.app._finish("Failed.")
        player.setFocus.assert_called_once_with()
        self.assertIn("menu could not be closed", self.messages[-1])
        self.assertNotIn("focus could not be restored", self.messages[-1])

    def test_player_more_preferred_to_ctrl_l_for_both_commands(self):
        for action in ("suggestLess", "favorite"):
            with self.subTest(action=action):
                self.setUp()
                shuffle = self.focus = Node("TOGGLEBUTTON", "Shuffle")
                more = Node("BUTTON", "More")
                player = Node("GROUPING", children=[shuffle, Node("BUTTON", "Pause"), more])
                self.app._begin(action)
                self.tick()
                self.until(lambda: more.UIAInvokePattern.Invoke.called)
                more.UIAInvokePattern.Invoke.assert_called_once_with()
                self.assertEqual(self.keys, [])
                command = Node("MENUITEM", "Suggest Less" if action == "suggestLess" else "Favorite")
                self.openMenu(command)
                self.tick()
                self.tick()
                command.UIAInvokePattern.Invoke.assert_called_once_with()
                shuffle.setFocus.assert_called_once_with()

    def test_page_more_is_not_mistaken_for_player_more(self):
        self.focus = Node("TOGGLEBUTTON", "Shuffle")
        more = Node("BUTTON", "More")
        root = Node("GROUPING", children=[self.focus, Node("BUTTON", "Pause"), Node("LISTITEM", "Other album", [more])])
        self.start()
        self.until(lambda: bool(self.keys))
        more.UIAInvokePattern.Invoke.assert_not_called()
        self.assertEqual(self.keys, ["control+l"])

    def test_ambiguous_player_more_uses_fallback(self):
        self.focus = Node("BUTTON", "Pause")
        buttons = [Node("BUTTON", "More") for unused in range(2)]
        player = Node("GROUPING", children=[self.focus, Node("BUTTON", "Shuffle"), *buttons])
        self.start()
        self.until(lambda: bool(self.keys))
        for button in buttons:
            button.UIAInvokePattern.Invoke.assert_not_called()
        self.assertEqual(self.keys, ["control+l"])

    def test_new_selection_without_focus_is_focused_before_menu(self):
        self.focus = Node("BUTTON", "Shuffle")
        self.start()
        song = Node("DATAITEM", "Revealed song")
        self.selected = [song]
        self.tick()
        song.setFocus.assert_called_once_with()
        self.assertEqual(self.keys, ["control+l"])
        self.focus = song
        self.tick()
        self.assertEqual(self.keys, ["control+l", "shift+f10"])

    def test_unchanged_selection_is_never_used_as_current_song(self):
        self.focus = Node("BUTTON", "Shuffle")
        old = Node("LISTITEM", "Previously selected song")
        self.selected = [old]
        self.start()
        self.app._operation["deadline"] = 0
        self.tick()
        old.setFocus.assert_not_called()
        self.assertEqual(self.keys, ["control+l"])

    def test_selected_target_focus_failure_never_opens_menu(self):
        self.focus = Node("BUTTON", "Shuffle")
        self.start()
        self.selected = [Node("LISTITEM", "Current song")]
        self.tick()
        self.app._operation["deadline"] = 0
        self.tick()
        self.assertEqual(self.keys, ["control+l"])
        self.assertIn("could not focus it", self.messages[-1])

    def test_multiple_new_selections_do_not_pick_arbitrarily(self):
        self.focus = Node("BUTTON", "Pause")
        self.start()
        self.selected = [Node("LISTITEM", "One"), Node("LISTITEM", "Two")]
        self.app._operation["deadline"] = 0
        self.tick()
        self.assertEqual(self.keys, ["control+l"])
        for song in self.selected:
            song.setFocus.assert_not_called()

    def navigationFixture(self):
        self.search = Node("EDITABLETEXT", "Search")
        self.sidebar = Node("TREEVIEWITEM", "Home")
        self.player = Node("BUTTON", "Pause")
        self.song = Node("DATAITEM", "Song")
        self.selected = [self.search, self.sidebar, self.player, self.song]
        for node in self.selected:
            node.setFocus.side_effect = lambda node=node: setattr(self, "focus", node)

    def test_f6_cycles_sections_and_wraps(self):
        self.navigationFixture()
        self.focus = self.search
        for expected, label in ((self.sidebar, "Sidebar"), (self.player, "Player"), (self.song, "Main content"), (self.search, "Search")):
            self.app.script_nextSection(None)
            self.drain()
            self.assertIs(self.focus, expected)
            self.assertEqual(self.messages[-1], label)
            expected.UIAInvokePattern.Invoke.assert_not_called()
        self.assertEqual(self.keys, [])

    def test_shift_f6_cycles_backwards(self):
        self.navigationFixture()
        self.focus = self.search
        self.app.script_previousSection(None)
        self.drain()
        self.assertIs(self.focus, self.song)

    def test_navigation_remembers_previous_control_in_section(self):
        self.navigationFixture()
        nextButton = Node("BUTTON", "Next")
        nextButton.setFocus.side_effect = lambda: setattr(self, "focus", nextButton)
        self.selected.append(nextButton)
        self.focus = nextButton
        self.app.script_nextSection(None)
        self.drain()
        self.app.script_previousSection(None)
        self.drain()
        self.assertIs(self.focus, nextButton)

    def test_navigation_skips_hidden_sections(self):
        self.navigationFixture()
        self.sidebar.states.add("OFFSCREEN")
        self.focus = self.search
        self.app.script_nextSection(None)
        self.drain()
        self.assertIs(self.focus, self.player)

    def test_navigation_preserves_open_menu(self):
        self.navigationFixture()
        self.openMenu(Node("MENUITEM", "Favorite"))
        self.app.script_nextSection(None)
        self.drain()
        self.assertIn("Close the menu", self.messages[-1])
        self.assertEqual(self.keys, [])

    def test_navigation_does_not_interrupt_preference(self):
        self.start()
        self.app.script_nextSection(None)
        self.assertIn("Wait", self.messages[-1])
        self.assertIsNotNone(self.app._operation)

    def test_navigation_explains_focus_failure(self):
        self.navigationFixture()
        self.sidebar.setFocus.side_effect = None
        self.focus = self.search
        self.app.script_nextSection(None)
        self.drain()
        self.assertIn("could not focus sidebar", self.messages[-1])

    def test_queue_and_lyrics_panel_classification(self):
        for name, expected in (("Playing Next", "Queue"), ("Lyrics", "Lyrics")):
            with self.subTest(name=name):
                item = Node("LISTITEM", "Line or song")
                container = Node("PANE", name, [item])
                self.assertEqual(music.sectionFor(item, 42), expected)

    def test_null_selection_array_is_empty(self):
        self.app._operation = {"root": types.SimpleNamespace(FindAllBuildCache=lambda *args: None)}
        self.assertEqual(self.app._selectedItems(), {})

    def test_focused_action_opens_menu_without_player_scan(self):
        for action in ("suggestLess", "favorite"):
            with self.subTest(action=action):
                self.setUp()
                button = self.focus = Node("BUTTON", "Action")
                self.app._begin(action)
                self.tick()
                button.UIAInvokePattern.Invoke.assert_called_once_with()
                self.assertNotIn("playerSearch", self.app._operation)
                self.assertEqual(self.keys, [])
                command = Node("MENUITEM", "Suggest Less" if action == "suggestLess" else "Favorite")
                self.openMenu(command)
                self.tick()
                self.tick()
                command.UIAInvokePattern.Invoke.assert_called_once_with()
                button.setFocus.assert_called_once_with()

    def test_navigation_skips_track_wrapper_and_position_slider(self):
        self.navigationFixture()
        action = Node("BUTTON", "Action")
        action.setFocus.side_effect = lambda: setattr(self, "focus", action)
        wrapper = Node("GROUPING", "Track Artist — Album", [action])
        self.selected = [self.search, self.sidebar, self.player, wrapper, action, Node("SLIDER"), self.song]
        self.focus = action
        self.app.script_nextSection(None)
        self.drain()
        self.assertIs(self.focus, self.song)
        wrapper.setFocus.assert_not_called()

    def test_navigation_yields_before_scanning(self):
        self.navigationFixture()
        self.focus = self.search
        self.app.script_nextSection(None)
        self.assertIs(self.focus, self.search)
        self.assertTrue(self.pending)
        self.drain()
        self.assertIs(self.focus, self.sidebar)

    def test_new_navigation_request_reuses_scan_and_changes_direction(self):
        self.navigationFixture()
        self.focus = self.search
        self.app.script_nextSection(None)
        generation = self.app._navigationGeneration
        self.app.script_previousSection(None)
        self.assertEqual(self.app._navigationGeneration, generation)
        self.drain()
        self.assertIs(self.focus, self.song)
        self.sidebar.setFocus.assert_not_called()
        self.assertEqual(self.messages, ["Main content"])

    def test_navigation_does_not_steal_changed_focus(self):
        self.navigationFixture()
        self.focus = self.search
        self.app.script_nextSection(None)
        self.focus = self.player
        self.drain()
        self.assertIs(self.focus, self.player)
        self.assertEqual(self.messages, [])

    def test_checkable_preferences_without_invoke_are_set_once(self):
        for action, label in (("suggestLess", "Suggest Less"), ("favorite", "Favourite")):
            with self.subTest(action=action):
                self.setUp()
                self.app._begin(action)
                self.tick()
                command = Node("MENUITEM", label)
                command.UIAInvokePattern = None
                command.UIATogglePattern = Mock(CurrentToggleState=0)
                self.openMenu(command)
                self.tick()
                self.tick()
                command.UIATogglePattern.Toggle.assert_called_once_with()
                self.assertEqual(self.messages[-1], music.ACTIONS[action]["success"])

    def test_live_checked_state_wins_over_stale_unchecked_state(self):
        for action, label in (("suggestLess", "Suggest Less"), ("favorite", "Favourite")):
            with self.subTest(action=action):
                self.setUp()
                self.app._begin(action)
                self.tick()
                command = Node("MENUITEM", label)
                command.UIATogglePattern = Mock(CurrentToggleState=1)
                self.openMenu(command)
                self.tick()
                command.UIATogglePattern.Toggle.assert_not_called()
                command.UIAInvokePattern.Invoke.assert_not_called()
                self.assertEqual(self.messages[-1], music.ACTIONS[action]["already"])

    def test_indeterminate_toggle_state_is_not_changed(self):
        self.start()
        command = Node("MENUITEM", "Suggest Less")
        command.UIATogglePattern = Mock(CurrentToggleState=2)
        self.openMenu(command)
        self.tick()
        command.UIATogglePattern.Toggle.assert_not_called()
        self.assertIn("uncertain checked state", self.messages[-1])

    def test_f6_stops_after_finding_next_section(self):
        self.navigationFixture()
        self.focus = self.search
        self.selected.extend(Node("LISTITEM", str(index)) for index in range(800))
        originalGet = self.root.FindAllBuildCache
        calls = []
        def read(*args):
            result = originalGet(*args)
            originalElement = result.GetElement
            result.GetElement = lambda index: (calls.append(index), originalElement(index))[1]
            return result
        self.root.FindAllBuildCache = read
        self.app.script_nextSection(None)
        self.drain()
        self.assertIs(self.focus, self.sidebar)
        self.assertLess(len(calls), 5)

    def test_open_navigation_is_sidebar_not_main_content(self):
        self.navigationFixture()
        opener = Node("BUTTON", "Open Navigation")
        opener.setFocus.side_effect = lambda: setattr(self, "focus", opener)
        self.selected = [opener, self.search, self.player, self.song]
        self.focus = self.player
        self.app.script_nextSection(None)
        self.drain()
        self.assertIs(self.focus, self.song)
        opener.setFocus.assert_not_called()
        self.app.script_previousSection(None)
        self.drain()
        self.assertIs(self.focus, self.player)
        self.app.script_previousSection(None)
        self.drain()
        self.assertIs(self.focus, opener)
        self.assertEqual(self.messages[-1], "Sidebar")

    def test_rapid_f6_does_not_restart_scan(self):
        self.navigationFixture()
        self.focus = self.player
        # Make Main content occur beyond several batches, like the real Home page.
        self.selected = [Node("BUTTON", "Open Navigation"), self.search] + [Node("BUTTON", "Pause") for unused in range(80)] + [self.song]
        reads = Mock(wraps=self.root.FindAllBuildCache)
        self.root.FindAllBuildCache = reads
        self.app.script_nextSection(None)
        generation = self.app._navigationGeneration
        for unused in range(8):
            self.tick()
            self.app.script_nextSection(None)
            self.assertEqual(self.app._navigationGeneration, generation)
        self.drain()
        self.assertIs(self.focus, self.song)
        # One track-only probe and one fallback scan, shared by every repeat.
        self.assertEqual(reads.call_count, 2)

    def test_live_search_button_name_and_identifier(self):
        self.assertEqual(music.sectionFor(Node("BUTTON", "Click to search"), 42), "Search")
        button = Node("BUTTON", "Localized search")
        button.cachedAutomationId = "Search_Button"
        self.assertEqual(music.sectionFor(button, 42), "Search")

    def test_winui_sidebar_listitems_are_not_page_content(self):
        self.navigationFixture()
        home = Node("LISTITEM", "Home")
        home.cachedAutomationId = "Sidebar_Home"
        home.cachedClassName = "Microsoft.UI.Xaml.Controls.NavigationViewItem"
        home.setFocus.side_effect = lambda: setattr(self, "focus", home)
        self.selected = [self.search, home, self.player, self.song]
        self.focus = self.player
        self.app.script_nextSection(None)
        self.drain()
        self.assertIs(self.focus, self.song)
        self.assertIsNone(music.focusedItem(home, 42))
        self.app.script_previousSection(None)
        self.drain()
        self.app.script_previousSection(None)
        self.drain()
        self.assertIs(self.focus, home)
        self.assertEqual(self.messages[-1], "Sidebar")

    def test_unlabelled_navigation_entry_uses_winui_class(self):
        item = Node("LISTITEM", "Custom playlist")
        item.cachedClassName = "Microsoft.UI.Xaml.Controls.NavigationViewItem"
        self.assertEqual(music.sectionFor(item, 42), "Sidebar")
        self.assertIsNone(music.focusedItem(item, 42))

    def test_player_auxiliary_controls_do_not_become_main_content(self):
        for role, name in (("BUTTON", "Lossless"), ("BUTTON", "Favourite"), ("TOGGLEBUTTON", "Queue"), ("SLIDER", "")):
            with self.subTest(role=role, name=name):
                self.assertEqual(music.sectionFor(Node(role, name), 42), "Player")

    def test_repeat_button_uses_identity_across_state_labels(self):
        for name in ("Do Not Repeat", "Repeat All", "Repeat One"):
            button = Node("BUTTON", name)
            button.cachedAutomationId = "RepeatButton"
            self.assertEqual(music.sectionFor(button, 42), "Player")

    def test_player_identifiers_and_open_panel_are_distinct(self):
        for identifier in music.PLAYER_IDS:
            button = Node("BUTTON", "Localized label")
            button.cachedAutomationId = identifier
            self.assertEqual(music.sectionFor(button, 42), "Player")
        panel = Node("PANE", "Queue")
        item = Node("LISTITEM", "Queued song")
        item.parent = panel
        self.assertEqual(music.sectionFor(item, 42), "Queue")

    def test_queue_panel_tabs_are_separate_from_player_opener(self):
        for name in ("Playing Next", "History"):
            self.assertEqual(music.sectionFor(Node("TOGGLEBUTTON", name), 42), "Queue")
        self.assertEqual(music.sectionFor(Node("TOGGLEBUTTON", "Queue"), 42), "Player")

    def test_favorite_from_queue_finds_verified_player_action(self):
        self.focus = Node("TOGGLEBUTTON", "History")
        action = Node("BUTTON", "Action")
        action.cachedAutomationId = "ActionButton"
        pause = Node("BUTTON", "Pause")
        pause.cachedAutomationId = "TransportControl_PlayPauseStop"
        shuffle = Node("TOGGLEBUTTON", "Shuffle")
        shuffle.cachedAutomationId = "ShuffleButton"
        airplay = Node("BUTTON", "AirPlay")
        airplay.cachedAutomationId = "AirPlayButton"
        self.selected = [action, pause, shuffle, airplay]
        self.app._begin("favorite")
        self.until(lambda: action.UIAInvokePattern.Invoke.called)
        self.assertNotIn("control+l", self.keys)
        airplay.UIAInvokePattern.Invoke.assert_not_called()
        command = Node("MENUITEM", "Favourite")
        command.UIATogglePattern = Mock(CurrentToggleState=0)
        self.openMenu(command)
        self.drain()
        command.UIATogglePattern.Toggle.assert_called_once()

    def test_identified_player_lookup_rejects_row_action_and_duplicates(self):
        for duplicate in (False, True):
            self.setUp()
            self.focus = Node("TOGGLEBUTTON", "History")
            action = Node("BUTTON", "Action")
            action.cachedAutomationId = "ActionButton"
            pause = Node("BUTTON", "Pause")
            pause.cachedAutomationId = "TransportControl_PlayPauseStop"
            repeat = Node("BUTTON", "Do Not Repeat")
            repeat.cachedAutomationId = "RepeatButton"
            self.selected = [action, pause, repeat]
            if duplicate:
                other = Node("BUTTON", "Action")
                other.cachedAutomationId = "ActionButton"
                self.selected.append(other)
            else:
                action.parent = Node("LISTITEM", "Unrelated song")
            self.start()
            self.until(lambda: "control+l" in self.keys)
            action.UIAInvokePattern.Invoke.assert_not_called()

    def trackFixture(self):
        self.track = Node("LISTITEM", "Track 1 Example song Artist Album 3 minutes")
        self.trackList = Node("LIST", children=[self.track])
        self.content = Node("GROUPING", "Content", children=[self.trackList])
        self.content.cachedClassName = "LandmarkTarget"
        self.track.setFocus.side_effect = lambda: setattr(self, "focus", self.track)
        self.selected = [self.track]

    def test_enter_on_track_uses_named_play_menu(self):
        self.trackFixture()
        self.focus = self.track
        gesture = Mock()
        self.app.script_playTrack(gesture)
        self.tick()
        self.assertEqual(self.keys, ["shift+f10"])
        command = Node("MENUITEM", "Play")
        self.openMenu(command)
        self.drain()
        command.UIAInvokePattern.Invoke.assert_called_once()
        gesture.send.assert_not_called()

    def clickableTrack(self, hitTitle=True):
        self.trackFixture()
        title = Node("STATICTEXT", "Example song")
        title.location = (100, 200, 80, 20)
        link = Node("LINK", "Artist")
        link.location = (300, 200, 40, 20)
        grid = Node("GROUPING", children=[link, title])
        grid.parent, self.track.firstChild = self.track, grid
        cover = Node("WINDOW", "Pop-up")
        client = music.UIAHandler.handler.clientObject
        client.ElementFromPointBuildCache = Mock(side_effect=lambda point, cache: (title if hitTitle else cover).BuildUpdatedCache(cache))
        music.winUser.getCursorPos = Mock(return_value=[5, 6])
        music.winUser.setCursorPos = Mock()
        music.mouseHandler.doPrimaryClick = Mock()
        self.focus = self.track
        return title

    def test_enter_on_track_double_clicks_its_title(self):
        self.clickableTrack()
        gesture = Mock()
        self.app.script_playTrack(gesture)
        self.drain()
        self.assertEqual(music.mouseHandler.doPrimaryClick.call_count, 2)
        self.assertEqual(music.winUser.setCursorPos.call_args_list[0].args, (110, 210))
        self.assertEqual(music.winUser.setCursorPos.call_args_list[-1].args, (5, 6))
        self.assertEqual(self.keys, [])
        self.assertEqual(self.messages[-1], "Playing track.")
        gesture.send.assert_not_called()

    def test_covered_track_falls_back_to_play_menu(self):
        self.clickableTrack(hitTitle=False)
        self.app.script_playTrack(Mock())
        self.tick()
        self.tick()
        music.mouseHandler.doPrimaryClick.assert_not_called()
        self.assertEqual(self.keys, ["shift+f10"])

    def test_enter_on_other_control_passes_through(self):
        self.focus = Node("BUTTON", "Filter")
        gesture = Mock()
        self.app.script_playTrack(gesture)
        gesture.send.assert_called_once()
        self.assertIsNone(self.app._operation)

    def test_new_content_focus_moves_into_track_list(self):
        self.trackFixture()
        self.focus = Node("BUTTON", "Playlist heading")
        self.app.event_gainFocus(self.focus, Mock())
        self.drain()
        self.assertIs(self.focus, self.track)

    def test_track_focus_handles_more_than_1000_controls(self):
        self.trackFixture()
        self.selected = [Node("BUTTON", "Header") for _ in range(1100)] + [self.track]
        self.focus = Node("BUTTON", "Playlist heading")
        self.app.event_gainFocus(self.focus, Mock())
        self.drain()
        self.assertIs(self.focus, self.track)

    def test_playlist_track_without_number_receives_focus(self):
        self.trackFixture()
        self.track.name = "Without You Here 3 minutes, 49 seconds"
        self.focus = Node("BUTTON", "Playlist heading")
        self.app.event_gainFocus(self.focus, Mock())
        self.drain()
        self.assertIs(self.focus, self.track)

    def test_home_end_reports_refreshed_virtualized_track(self):
        self.trackFixture()
        self.focus = self.track
        gesture = Mock()
        self.app.script_trackBoundary(gesture)
        gesture.send.assert_called_once_with()
        target = Node("LISTITEM", "Track 1 stale song Artist Album 3 minutes")
        target.parent = self.trackList
        self.focus = target
        nextHandler = Mock()
        self.app.event_gainFocus(target, nextHandler)
        nextHandler.assert_not_called()
        target.name = "Track 1 final song Artist Album 3 minutes"
        self.tick()
        music.eventHandler.queueEvent.assert_called_once_with("gainFocus", target)

    def test_home_end_cancels_refresh_after_another_focus_event(self):
        self.trackFixture()
        self.focus = self.track
        self.app.script_trackBoundary(Mock())
        target = Node("LISTITEM", "Track 2 target song Artist Album 3 minutes")
        target.parent = self.trackList
        self.focus = target
        self.app.event_gainFocus(target, Mock())
        changed = Node("LISTITEM", "Track 3 changed song Artist Album 3 minutes")
        changed.parent = self.trackList
        self.focus = changed
        nextHandler = Mock()
        self.app.event_gainFocus(changed, nextHandler)
        nextHandler.assert_called_once_with()
        self.tick()
        music.eventHandler.queueEvent.assert_not_called()

    def test_duration_in_sidebar_name_is_not_a_track(self):
        sidebar = Node("LISTITEM", "My playlist 3 minutes, 49 seconds")
        sidebar.cachedAutomationId = "Sidebar_Playlist"
        self.assertIsNone(music.trackRow(sidebar, 42))

    def test_track_below_fold_is_revealed_and_focused(self):
        self.trackFixture()
        self.track.states.add("OFFSCREEN")
        self.track._getUIAPattern.return_value = Mock()
        self.focus = Node("BUTTON", "Album heading")
        self.app.event_gainFocus(self.focus, Mock())
        self.drain()
        self.track._getUIAPattern.return_value.ScrollIntoView.assert_called_once()
        self.assertIs(self.focus, self.track)

    def test_reused_list_with_new_tracks_receives_focus(self):
        self.trackFixture()
        self.app._trackPage = tuple(self.trackList.GetRuntimeId())
        self.app._trackPageName = "track 1 previous album song"
        self.focus = Node("BUTTON", "New album heading")
        self.app.event_gainFocus(self.focus, Mock())
        self.drain()
        self.assertIs(self.focus, self.track)

    def test_f6_known_player_id_avoids_global_scan(self):
        self.focus = Node("BUTTON", "Open Navigation")
        player = Node("BUTTON", "Pause")
        player.cachedAutomationId = "TransportControl_PlayPauseStop"
        player.setFocus.side_effect = lambda: setattr(self, "focus", player)
        self.selected = [player]
        self.root.FindAllBuildCache = Mock(side_effect=AssertionError("Global scan"))
        self.app.script_nextSection(None)
        self.drain()
        self.assertIs(self.focus, player)
        self.root.FindAllBuildCache.assert_not_called()

    def test_f6_remembered_target_is_refreshed_without_global_scan(self):
        self.navigationFixture()
        self.focus = self.search
        self.app.script_nextSection(None)
        self.drain()
        self.root.FindAllBuildCache = Mock(side_effect=AssertionError("Global scan"))
        self.app.script_previousSection(None)
        self.drain()
        self.assertIs(self.focus, self.search)
        self.root.FindAllBuildCache.assert_not_called()

    def test_f6_skips_closed_queue_and_lyrics_without_global_scan(self):
        self.trackFixture()
        self.focus = self.track
        search = Node("BUTTON", "Click to search")
        search.cachedAutomationId = "Search_Button"
        search.setFocus.side_effect = lambda: setattr(self, "focus", search)
        queue = Node("TOGGLEBUTTON", "Queue")
        queue.cachedAutomationId = "PlayQueueToggleButton"
        queue.UIATogglePattern = Mock(CurrentToggleState=music.UIAHandler.ToggleState_Off)
        lyrics = Node("TOGGLEBUTTON", "Lyrics")
        lyrics.cachedAutomationId = "LyricsToggleButton"
        lyrics.UIATogglePattern = Mock(CurrentToggleState=music.UIAHandler.ToggleState_Off)
        self.selected = [search, queue, lyrics, self.track]
        self.root.FindAllBuildCache = Mock(side_effect=AssertionError("Global scan"))
        self.app.script_nextSection(None)
        self.drain()
        self.assertIs(self.focus, search)
        self.root.FindAllBuildCache.assert_not_called()

    def test_f6_keeps_open_queue_before_search(self):
        self.trackFixture()
        self.focus = self.track
        queueButton = Node("TOGGLEBUTTON", "Queue")
        queueButton.cachedAutomationId = "PlayQueueToggleButton"
        queueButton.UIATogglePattern = Mock(CurrentToggleState=music.UIAHandler.ToggleState_On)
        lyricsButton = Node("TOGGLEBUTTON", "Lyrics")
        lyricsButton.cachedAutomationId = "LyricsToggleButton"
        lyricsButton.UIATogglePattern = Mock(CurrentToggleState=music.UIAHandler.ToggleState_Off)
        queueItem = Node("LISTITEM", "Queued song")
        queueItem.parent = Node("PANE", "Queue")
        queueItem.setFocus.side_effect = lambda: setattr(self, "focus", queueItem)
        self.selected = [queueButton, lyricsButton, self.track, queueItem]
        self.app.script_nextSection(None)
        self.drain()
        self.assertIs(self.focus, queueItem)

    def test_control_1_opens_home(self):
        home = Node("LISTITEM", "Home")
        home.cachedAutomationId = "Sidebar_Home"
        home.setFocus.side_effect = lambda: setattr(self, "focus", home)
        self.selected = [home]
        self.app.script_focusHome(None)
        self.assertIs(self.focus, home)
        self.drain()
        self.assertEqual(self.keys, ["enter"])

    def test_control_3_on_open_radio_page_lands_on_first_card(self):
        radio = Node("LISTITEM", "Radio")
        radio.cachedAutomationId = "Sidebar_Radio"
        radio.states.add("SELECTED")
        card = Node("LISTITEM", "Apple Music 1")
        card.setFocus.side_effect = lambda: setattr(self, "focus", card)
        player = Node("GROUPING")
        player.cachedAutomationId = "TransportBar"
        player.FindFirstBuildCache = Mock(side_effect=AssertionError("searched the player"))
        content = Node("GROUPING", "Radio")
        content.FindFirstBuildCache = lambda scope, condition, cache: card.BuildUpdatedCache(cache)
        self.selected = [radio]
        self.root.FindAllBuildCache = lambda *args: types.SimpleNamespace(
            Length=2, GetElement=[player, content].__getitem__)
        self.app.script_focusRadio(None)
        self.drain()
        self.assertIs(self.focus, card)
        self.assertEqual(self.keys, [])

    def test_control_s_presses_search_button(self):
        button = Node("BUTTON", "Click to search")
        button.cachedAutomationId = "Search_Button"
        button.setFocus.side_effect = lambda: setattr(self, "focus", button)
        self.selected = [button]
        self.app.script_focusSearch(None)
        self.assertIs(self.focus, button)
        self.drain()
        self.assertEqual(self.keys, ["enter"])

    def test_control_s_focuses_open_search_field_and_selects_old_query(self):
        field = Node("EDITABLETEXT", "Search")
        field.cachedAutomationId = "TextBox"
        field.value = "abba"
        field.setFocus.side_effect = lambda: setattr(self, "focus", field)
        self.selected = [field]
        self.app.script_focusSearch(None)
        self.assertIs(self.focus, field)
        self.drain()
        self.assertEqual(self.keys, ["control+a"])

    def test_control_s_leaves_empty_new_search_field_alone(self):
        button = Node("BUTTON", "Click to search")
        button.cachedAutomationId = "Search_Button"
        button.setFocus.side_effect = lambda: setattr(self, "focus", button)
        field = Node("EDITABLETEXT", "Search")
        self.selected = [button]
        self.onKey = lambda key: setattr(self, "focus", field) if key == "enter" else None
        self.app.script_focusSearch(None)
        self.drain()
        self.assertIs(self.focus, field)
        self.assertEqual(self.keys, ["enter"])

    def test_control_1_reports_missing_home(self):
        self.selected = []
        self.app.script_focusHome(None)
        self.assertIn("Home option is unavailable", self.messages[-1])

    def test_control_2_through_5_open_sidebar_options(self):
        shortcuts = (
            (self.app.script_focusNew, "Sidebar_New", "New"),
            (self.app.script_focusRadio, "Sidebar_Radio", "Radio"),
            (self.app.script_focusLibrary, "Sidebar_Header_Library", "Library"),
            (self.app.script_focusPlaylists, "Sidebar_Header_Playlists", "Playlists"),
        )
        for command, identifier, name in shortcuts:
            with self.subTest(name=name):
                self.keys.clear()
                control = Node("LISTITEM", name)
                control.cachedAutomationId = identifier
                control.setFocus.side_effect = lambda control=control: setattr(self, "focus", control)
                self.selected = [control]
                command(None)
                self.assertIs(self.focus, control)
                self.drain()
                self.assertEqual(self.keys, ["enter"])

    def test_control_2_skips_enter_after_user_moves_focus(self):
        control = Node("LISTITEM", "New")
        control.cachedAutomationId = "Sidebar_New"
        control.setFocus.side_effect = lambda: setattr(self, "focus", control)
        self.selected = [control]
        self.app.script_focusNew(None)
        self.focus = Node("LISTITEM", "Radio")
        self.drain()
        self.assertEqual(self.keys, [])

    def test_control_6_opens_account_and_focuses_settings(self):
        account = Node("LISTITEM", "Person")
        account.cachedClassName = "Microsoft.UI.Xaml.Controls.NavigationViewItem"
        account.setFocus.side_effect = lambda: setattr(self, "focus", account)
        settings = Node("BUTTON", "Settings")
        settings.setFocus.side_effect = lambda: setattr(self, "focus", settings)
        self.selected = [account]

        def openAccount(key):
            if key == "enter" and self.focus is account:
                self.focus = Node("BUTTON", "View Profile")
                self.selected = [account, settings]

        self.onKey = openAccount
        self.app.script_focusAccountSettings(None)
        self.drain()
        self.assertEqual(self.keys, ["enter", "enter"])
        self.assertIs(self.focus, settings)

    def test_existing_page_does_not_pull_focus_back(self):
        self.trackFixture()
        self.app._trackPage = tuple(self.trackList.GetRuntimeId())
        self.focus = Node("BUTTON", "Filter")
        self.app.event_gainFocus(self.focus, Mock())
        self.drain()
        self.track.setFocus.assert_not_called()

    def test_track_focus_poll_cancels_after_user_moves(self):
        self.trackFixture()
        self.focus = Node("BUTTON", "Playlist heading")
        self.app.event_gainFocus(self.focus, Mock())
        self.focus = Node("BUTTON", "Volume")
        self.drain()
        self.track.setFocus.assert_not_called()

    def test_manual_section_destination_is_not_overridden(self):
        self.trackFixture()
        self.focus = Node("BUTTON", "Open Navigation")
        self.app._manualSectionTarget = tuple(self.focus.GetRuntimeId())
        self.app.event_gainFocus(self.focus, Mock())
        self.drain()
        self.track.setFocus.assert_not_called()

    def test_content_play_button_is_not_player(self):
        button = Node("BUTTON", "Play")
        content = Node("GROUPING", "Content", children=[button])
        content.cachedClassName = "LandmarkTarget"
        self.assertEqual(music.sectionFor(button, 42), "Main content")

    def test_f6_prefers_track_over_playlist_header_controls(self):
        self.trackFixture()
        self.focus = Node("BUTTON", "Pause")
        header = Node("BUTTON", "Filter")
        self.selected = [header, self.track]
        self.app.script_nextSection(None)
        self.drain()
        self.assertIs(self.focus, self.track)

    def test_quoted_play_command_excludes_play_next(self):
        self.trackFixture()
        self.focus = self.track
        self.app.script_playTrack(Mock())
        self.tick()
        play = Node("MENUITEM", 'Play \u201cExample song\u201d')
        nextPlay = Node("MENUITEM", "Play Next")
        self.openMenu(play, nextPlay)
        self.drain()
        play.UIAInvokePattern.Invoke.assert_called_once()
        nextPlay.UIAInvokePattern.Invoke.assert_not_called()

    def test_scroll_before_track_menu_and_cancel_if_focus_changes(self):
        self.trackFixture()
        self.focus = self.track
        scroll = Mock()
        self.track._getUIAPattern.return_value = scroll
        self.app.script_playTrack(Mock())
        self.tick()
        scroll.ScrollIntoView.assert_called_once()
        self.assertEqual(self.keys, [])
        self.focus = Node("BUTTON", "Volume")
        self.drain()
        self.assertEqual(self.keys, [])

    def test_play_waits_for_popup_window_to_expose_menu(self):
        self.trackFixture()
        self.focus = self.track
        self.app.script_playTrack(Mock())
        self.tick()
        self.focus = Node("WINDOW", "Pop-up")
        self.tick()
        self.assertIsNotNone(self.app._operation)
        command = Node("MENUITEM", 'Play "Example song"')
        self.openMenu(command)
        self.drain()
        command.UIAInvokePattern.Invoke.assert_called_once()

    def test_album_and_radio_rows_open_their_own_more_button(self):
        for name in (
            "Track 1 Example song Artist Album 3 minutes",
            "Track 1 Find Your Harmony Intro (FYH510) 2 minutes, 17 seconds",
            "Without You Here 3 minutes, 49 seconds",
        ):
            with self.subTest(name=name):
                self.setUp()
                more = Node("BUTTON", "More")
                row = Node("LISTITEM", name, children=[Node("GROUPING", children=[more])])
                self.focus = row
                play = Node("MENUITEM", 'Play "Example song"')
                playNext = Node("MENUITEM", "Play Next")
                playLast = Node("MENUITEM", "Play Last")
                more.UIAInvokePattern.Invoke.side_effect = lambda: self.openMenu(play, playNext, playLast)
                self.app.script_playTrack(Mock())
                self.drain()
                more.UIAInvokePattern.Invoke.assert_called_once()
                play.UIAInvokePattern.Invoke.assert_called_once()
                playNext.UIAInvokePattern.Invoke.assert_not_called()
                playLast.UIAInvokePattern.Invoke.assert_not_called()
                self.assertNotIn("shift+f10", self.keys)
                self.assertEqual(self.messages[-1], "Playing track.")

    def test_enter_on_track_child_controls_keeps_native_action(self):
        for role, name in (("BUTTON", "More"), ("SPLITBUTTON", "More options"), ("BUTTON", "Favorite")):
            with self.subTest(role=role, name=name):
                self.setUp()
                self.focus = Node(role, name)
                Node("LISTITEM", "Track 1 Example song", children=[self.focus])
                gesture = Mock()
                self.app.script_playTrack(gesture)
                gesture.send.assert_called_once()
                self.assertIsNone(self.app._operation)
                self.assertEqual(self.keys, [])

    def test_play_does_not_retarget_during_deferred_start(self):
        self.trackFixture()
        self.focus = self.track
        self.app.script_playTrack(Mock())
        self.focus = Node("LISTITEM", "Track 2 Another song")
        self.drain()
        self.assertEqual(self.keys, [])
        self.assertIn("focus changed", self.messages[-1])

    def test_play_resolves_more_after_scrolling(self):
        self.trackFixture()
        self.focus = self.track
        more = Node("BUTTON", "More")
        more.parent = self.track
        scroll = Mock()
        scroll.ScrollIntoView.side_effect = lambda: setattr(self.track, "firstChild", more)
        self.track._getUIAPattern.return_value = scroll
        play = Node("MENUITEM", "Play")
        more.UIAInvokePattern.Invoke.side_effect = lambda: self.openMenu(play)
        self.app.script_playTrack(Mock())
        self.drain()
        scroll.ScrollIntoView.assert_called_once()
        more.UIAInvokePattern.Invoke.assert_called_once()
        play.UIAInvokePattern.Invoke.assert_called_once()

    def test_track_more_does_not_use_header_sibling_or_nested_row(self):
        ownMore = Node("BUTTON", "More")
        nestedMore = Node("BUTTON", "More")
        row = Node("LISTITEM", "Track 1 Example", children=[
            ownMore, Node("LISTITEM", "Track 2 Nested", children=[nestedMore]),
        ])
        siblingMore = Node("BUTTON", "More")
        headerMore = Node("BUTTON", "More")
        Node("GROUPING", "Content", children=[headerMore, row, Node("LISTITEM", "Track 3 Other", children=[siblingMore])])
        self.assertIs(music.trackMoreButton(row, 42), ownMore)
        for other in (nestedMore, siblingMore, headerMore):
            other.UIAInvokePattern.Invoke.assert_not_called()

    def test_unusable_and_ambiguous_more_buttons_fall_back_to_keyboard(self):
        for variant in ("INVISIBLE", "OFFSCREEN", "UNAVAILABLE", "foreign", "noInvoke", "duplicate"):
            with self.subTest(variant=variant):
                self.setUp()
                more = Node("BUTTON", "More")
                children = [more]
                if variant == "foreign":
                    more.processID = 99
                elif variant == "noInvoke":
                    more.UIAInvokePattern = None
                elif variant == "duplicate":
                    children.append(Node("BUTTON", "More"))
                else:
                    more.states.add(variant)
                self.focus = Node("LISTITEM", "Track 1 Example", children=children)
                self.app.script_playTrack(Mock())
                self.tick()
                self.assertEqual(self.keys, ["shift+f10"])
                for button in children:
                    if button.UIAInvokePattern:
                        button.UIAInvokePattern.Invoke.assert_not_called()

    def test_track_more_incomplete_or_cyclic_tree_is_not_used(self):
        for cyclic in (False, True):
            with self.subTest(cyclic=cyclic):
                more = Node("BUTTON", "More")
                row = Node("LISTITEM", "Track 1 Example", children=[more])
                if cyclic:
                    more.next = more
                else:
                    row = Node("LISTITEM", "Track 1 Example", children=[more] + [Node("GROUPING") for _ in range(41)])
                self.assertIsNone(music.trackMoreButton(row, 42))

    def test_tabbing_to_more_while_scroll_pending_cancels_play(self):
        more = Node("BUTTON", "More")
        self.focus = Node("LISTITEM", "Track 1 Example", children=[more])
        self.focus._getUIAPattern.return_value = Mock()
        self.app.script_playTrack(Mock())
        self.tick()
        self.focus = more
        self.drain()
        more.UIAInvokePattern.Invoke.assert_not_called()
        self.assertEqual(self.keys, [])
        self.assertIn("focus changed", self.messages[-1])

    def test_tabbing_to_more_after_keyboard_fallback_cancels_play(self):
        self.trackFixture()
        self.focus = self.track
        self.app.script_playTrack(Mock())
        self.tick()
        more = Node("BUTTON", "More")
        more.parent = self.track
        self.focus = more
        self.tick()
        self.assertIsNone(self.app._operation)
        self.assertIn("focus changed", self.messages[-1])
        gesture = Mock()
        self.app.script_playTrack(gesture)
        gesture.send.assert_called_once()
        play = Node("MENUITEM", "Play")
        self.openMenu(play)
        self.drain()
        play.UIAInvokePattern.Invoke.assert_not_called()

    def test_invoked_more_can_receive_focus_while_its_menu_loads(self):
        more = Node("BUTTON", "More")
        self.focus = Node("LISTITEM", "Track 1 Example", children=[more])
        more.UIAInvokePattern.Invoke.side_effect = lambda: setattr(self, "focus", more)
        self.app.script_playTrack(Mock())
        self.tick()
        self.tick()
        self.assertIsNotNone(self.app._operation)
        play = Node("MENUITEM", "Play")
        self.openMenu(play)
        self.drain()
        play.UIAInvokePattern.Invoke.assert_called_once()

    def test_late_menu_is_not_used_after_play_deadline(self):
        self.trackFixture()
        self.focus = self.track
        self.app.script_playTrack(Mock())
        self.tick()
        self.app._operation["deadline"] = 0
        play = Node("MENUITEM", "Play")
        self.openMenu(play)
        self.drain()
        play.UIAInvokePattern.Invoke.assert_not_called()
        self.assertEqual(self.keys, ["shift+f10"])
        self.assertEqual(self.messages[-1], "Play not available.")

    def test_timed_out_play_does_not_consume_manually_opened_menu(self):
        self.trackFixture()
        self.focus = self.track
        self.app.script_playTrack(Mock())
        self.tick()
        self.app._operation["deadline"] = 0
        self.tick()
        play = Node("MENUITEM", "Play")
        self.openMenu(play)
        self.drain()
        play.UIAInvokePattern.Invoke.assert_not_called()
        self.assertIsNone(self.app._operation)

    def test_play_more_refuses_multiple_selection(self):
        more = Node("BUTTON", "More")
        self.focus = Node("LISTITEM", "Track 1 Example", children=[more])
        container = Node("LIST", children=[self.focus])
        container.UIASelectionPattern = types.SimpleNamespace(
            GetCurrentSelection=lambda: types.SimpleNamespace(Length=2)
        )
        self.app.script_playTrack(Mock())
        self.drain()
        more.UIAInvokePattern.Invoke.assert_not_called()
        self.assertEqual(self.keys, [])
        self.assertIn("only one", self.messages[-1])


class HomeReadingTests(unittest.TestCase):
    def card(self, name="Made for You", children=(), home=True):
        card = music.HomeCard("LISTITEM", name, children=children)
        card.cachedClassName = "GridViewItem"
        Node("GROUPING", "Home" if home else "Browse", children=[
            Node("GROUPING", "Top Picks for You", children=[Node("LIST", children=[card])])
        ])
        return card

    def onAirCard(self, index, count=6):
        card = music.HomeCard("LISTITEM", "AMP.Services.CommonModels.LiveRadioGridLockup",
                              children=[Node("GRAPHIC", "")])
        card.cachedClassName = "GridViewItem"
        card.positionInfo = {"indexInGroup": index, "similarItemsInGroup": count}
        Node("GROUPING", "Radio", children=[
            Node("GROUPING", "On Air Now", children=[Node("LIST", children=[card])])
        ])
        return card

    def test_on_air_card_uses_apple_music_cached_station_name(self):
        stations = ["Apple Music 1", "Apple Music Hits", "Apple Music Country",
                    "Apple Música Uno", "Apple Music Club", "Apple Music Chill"]
        with patch.object(music, "cachedShelves", return_value={"On Air Now": stations}):
            self.assertEqual(self.onAirCard(2)._get_name(), "Apple Music Hits")
            self.assertEqual(self.onAirCard(6)._get_name(), "Apple Music Chill")

    def test_cached_name_ignored_when_shelf_size_differs(self):
        with patch.object(music, "cachedShelves", return_value={"On Air Now": ["Apple Music 1"]}):
            self.assertEqual(self.onAirCard(1)._get_name(), "Live radio station")

    def test_poster_gets_cached_title_and_artists(self):
        card = self.card("AMP.Services.CommonModels.TallArtworkPosterLockup",
                         [Node("STATICTEXT", "Brooks, 4 Strings and more")])
        card.positionInfo = {"indexInGroup": 2, "similarItemsInGroup": 2}
        with patch.object(music, "cachedShelves", return_value={"Top Picks for You": ["Your Essentials", "Get Up!"]}):
            self.assertEqual(card._get_name(), "Get Up!, featuring Brooks, 4 Strings and more")

    def test_made_for_you_artist_card_gets_cached_title(self):
        subtitle = Node("STATICTEXT", "Man With No Name, The WLT and more")
        subtitle.cachedAutomationId = "SubtitleTextBlock"
        card = self.card(children=[Node("STATICTEXT", "Made for You"), subtitle])
        card.positionInfo = {"indexInGroup": 2, "similarItemsInGroup": 2}
        with patch.object(music, "cachedShelves", return_value={"Top Picks for You": ["Prism Journey", "Your Essentials"]}):
            self.assertEqual(card._get_name(),
                             "Your Essentials, Made for You, featuring Man With No Name, The WLT and more")

    def test_shelf_names_parse_editorial_and_recommendation_responses(self):
        grouping = {"resources": {
            "editorial-elements": {
                "1": {"attributes": {"title": "On Air Now"}, "relationships": {"children": {"data": [
                    {"id": "2", "type": "editorial-elements"}]}}},
                "2": {"relationships": {"contents": {"data": [{"id": "ra.1", "type": "stations"}]}}},
            },
            "stations": {"ra.1": {"attributes": {"name": "Apple Music 1"}}},
        }}
        recommendations = {"resources": {
            "personal-recommendation": {"r": {
                "attributes": {"title": {"stringForDisplay": "Playlists Made for You"}},
                "relationships": {"contents": {"data": [{"id": "pl.1", "type": "playlists"}]}}}},
            "playlists": {"pl.1": {"attributes": {"name": "Get Up!"}}},
        }}
        self.assertEqual(music.shelfNamesFromResponse(grouping), {"On Air Now": ["Apple Music 1"]})
        self.assertEqual(music.shelfNamesFromResponse(recommendations), {"Playlists Made for You": ["Get Up!"]})

    def test_type_name_radio_card_reads_as_live_station(self):
        card = self.card("AMP.Services.CommonModels.LiveRadioGridLockup",
                         [Node("GRAPHIC", "")], home=False)
        self.assertEqual(card._get_name(), "Live radio station")

    def test_type_name_poster_reads_its_artists(self):
        card = self.card("AMP.Services.CommonModels.TallArtworkPosterLockup",
                         [Node("STATICTEXT", "Brooks, 4 Strings, Roman Messer and more")])
        self.assertEqual(card._get_name(), "Featuring Brooks, 4 Strings, Roman Messer and more")

    def test_unknown_empty_type_name_is_untitled(self):
        self.assertEqual(self.card("AMP.Services.CommonModels.NewLockup", home=False)._get_name(), "Untitled item")

    def test_card_announces_title_artist_and_category(self):
        card = self.card("New Release 2026", [Node("GROUPING", children=[
            Node("STATICTEXT", "New Release 2026"),
            Node("LINK", "An Album"), Node("STATICTEXT", "An Artist"),
        ])])
        self.assertEqual(card._get_name(), "An Album, An Artist, New Release 2026")

    def test_made_for_you_cards_have_distinct_titles(self):
        for title in ("Favorites Mix", "New Music Mix", "Get Up! Mix"):
            with self.subTest(title=title):
                card = self.card(children=[Node("STATICTEXT", title)])
                self.assertEqual(card._get_name(), f"{title}, Made for You")

    def test_offscreen_card_text_is_still_read(self):
        title = Node("STATICTEXT", "Focus Radio Station")
        title.states.add("OFFSCREEN")
        self.assertEqual(self.card("Mood for You", [title])._get_name(),
                         "Focus Radio Station, Mood for You")

    def test_duplicate_artwork_and_link_labels_read_once(self):
        card = self.card(children=[Node("GRAPHIC", "Favorites Mix"),
                                   Node("LINK", "Favorites Mix", [Node("STATICTEXT", "Favorites Mix")])])
        self.assertEqual(card._get_name(), "Favorites Mix, Made for You")

    def test_complete_existing_album_name_is_preserved(self):
        name = "KWEEN Young M.A Explicit"
        card = self.card(name, [Node("STATICTEXT", "KWEEN"),
                                Node("STATICTEXT", "Young M.A"), Node("STATICTEXT", "Explicit")])
        self.assertEqual(card._get_name(), name)

    def test_artist_subtitle_without_title_has_category_and_context(self):
        subtitle = Node("STATICTEXT", "Sublab, Portair, MTNS, Nathyn, ARTO, Drove, Novra, SINTUS and\u00a0more")
        subtitle.cachedAutomationId = "SubtitleTextBlock"
        card = self.card(children=[Node("GRAPHIC"), Node("STATICTEXT", "Made for You"), subtitle])
        self.assertEqual(card._get_name(),
                         "Made for You, featuring Sublab, Portair, MTNS, Nathyn, ARTO, Drove, Novra, SINTUS and more")

    def test_station_title_is_retained_with_artist_subtitle(self):
        title = Node("STATICTEXT", "A Station")
        title.cachedAutomationId = "TitleTextBlock"
        subtitle = Node("STATICTEXT", "Artist A, Artist B and more")
        subtitle.cachedAutomationId = "SubtitleTextBlock"
        card = self.card(children=[title, subtitle])
        self.assertEqual(card._get_name(), "A Station, Artist A, Artist B and more, Made for You")

    def test_named_artwork_still_provides_a_title(self):
        subtitle = Node("STATICTEXT", "Artist A, Artist B and more")
        subtitle.cachedAutomationId = "SubtitleTextBlock"
        card = self.card(children=[Node("GRAPHIC", "A Mix"), subtitle])
        self.assertEqual(card._get_name(), "A Mix, Artist A, Artist B and more, Made for You")

    def test_editorial_subtitle_is_not_called_an_artist_list(self):
        subtitle = Node("STATICTEXT", "Music selected for you.")
        subtitle.cachedAutomationId = "SubtitleTextBlock"
        card = self.card(children=[subtitle])
        self.assertEqual(card._get_name(), "Made for You, Music selected for you.")

    def test_private_use_icon_glyphs_are_not_spoken(self):
        name = "Lil Herb: Lil Heroin Edition G Herbo Explicit"
        for glyph in ("\ue09d", "\U000f009d", "\U0010009d"):
            with self.subTest(glyph=repr(glyph)):
                card = self.card(name, [Node("STATICTEXT", glyph), Node("STATICTEXT", name)])
                self.assertEqual(card._get_name(), name)

    def test_real_unicode_titles_remain_intact(self):
        card = self.card(children=[Node("STATICTEXT", "VOILÀ & 東京 \U0001f499")])
        self.assertEqual(card._get_name(), "VOILÀ & 東京 \U0001f499, Made for You")

    def test_punctuation_ampersands_and_accents_preserved(self):
        card = self.card("Featuring VOILÀ", [Node("STATICTEXT", "This & That...")])
        self.assertEqual(card._get_name(), "This & That..., Featuring VOILÀ")

    def test_does_not_treat_partial_word_as_duplicate(self):
        card = self.card(children=[Node("STATICTEXT", "Rain"), Node("STATICTEXT", "Rainbow")])
        self.assertEqual(card._get_name(), "Rain, Rainbow, Made for You")

    def test_missing_or_unexposed_text_keeps_original(self):
        for children in ([], [Node("STATICTEXT", "Made for You")], [Node("STATICTEXT", " ")]):
            self.assertEqual(self.card(children=children)._get_name(), "Made for You")

    def test_unnamed_card_uses_child_title(self):
        self.assertEqual(self.card("", [Node("STATICTEXT", "Favorites Mix")])._get_name(), "Favorites Mix")

    def test_hidden_foreign_and_nested_control_content_excluded(self):
        hidden = Node("GROUPING", children=[Node("STATICTEXT", "Hidden")])
        hidden.states.add("INVISIBLE")
        card = self.card(children=[Node("STATICTEXT", "Favorites Mix"), hidden,
            Node("STATICTEXT", "Foreign", processID=99),
            Node("LISTITEM", "Other card", [Node("STATICTEXT", "Other title")]),
            Node("LIST", children=[Node("STATICTEXT", "Other list")]),
            Node("BUTTON", "More", [Node("STATICTEXT", "Command")]),
        ])
        self.assertEqual(card._get_name(), "Favorites Mix, Made for You")

    def test_adjacent_card_never_borrowed(self):
        card = self.card()
        card.next = Node("LISTITEM", "Another card", [Node("STATICTEXT", "Wrong title")])
        self.assertEqual(card._get_name(), "Made for You")

    def test_large_or_cyclic_card_falls_back(self):
        card = self.card(children=[Node("STATICTEXT", str(i)) for i in range(70)])
        self.assertEqual(card._get_name(), "Made for You")
        card = self.card(children=[Node("STATICTEXT", "Favorites Mix")])
        card.firstChild.next = card.firstChild
        self.assertEqual(card._get_name(), "Made for You")

    def test_stale_card_falls_back_without_warning(self):
        card = self.card(children=[Node("STATICTEXT", "Favorites Mix")])
        card.firstChild.GetRuntimeId = Mock(side_effect=RuntimeError("Stale element"))
        music.log.reset_mock()
        self.assertEqual(card._get_name(), "Made for You")
        music.log.warning.assert_not_called()
        music.log.exception.assert_not_called()

    def test_card_text_refreshes_for_reused_item(self):
        child = Node("STATICTEXT", "First Mix")
        card = self.card(children=[child])
        self.assertEqual(card._get_name(), "First Mix, Made for You")
        child.name = "Second Mix"
        self.assertEqual(card._get_name(), "Second Mix, Made for You")

    def test_other_pages_and_sidebar_unchanged(self):
        card = self.card(children=[Node("STATICTEXT", "Title")], home=False)
        self.assertEqual(card._get_name(), "Made for You")
        card = self.card(children=[Node("STATICTEXT", "Title")])
        card.cachedAutomationId = "Sidebar_Home"
        self.assertEqual(card._get_name(), "Made for You")

    def test_overlay_selection_uses_observed_grid_class(self):
        app = music.AppModule()
        card = self.card()
        for obj, expected in ((card, music.HomeCard), (Node("GROUPING"), music.HomeGrouping)):
            classes = [Node]
            app.chooseNVDAObjectOverlayClasses(obj, classes)
            self.assertEqual(classes, [expected, Node])
        classes = [Node]
        app.chooseNVDAObjectOverlayClasses(Node("LISTITEM", "Track 1"), classes)
        self.assertEqual(classes, [Node])

    def groups(self, focusName="Recently Played", outerName="Recently Played", innerName="Recently Played", page="Home"):
        focus = Node("LINK", focusName)
        inner = music.HomeGrouping("GROUPING", innerName, [focus])
        outer = music.HomeGrouping("GROUPING", outerName, [inner])
        home = music.HomeGrouping("GROUPING", page, [outer])
        music.api.getFocusObject = lambda: focus
        return focus, inner, outer, home

    def test_link_does_not_repeat_two_group_names(self):
        focus, inner, outer, home = self.groups()
        self.assertFalse(inner._get_isPresentableFocusAncestor())
        self.assertFalse(outer._get_isPresentableFocusAncestor())
        self.assertTrue(home._get_isPresentableFocusAncestor())
        self.assertEqual(focus.name, "Recently Played")
        self.assertEqual(focus.role, "LINK")

    def test_distinct_section_name_retained_once(self):
        focus, inner, outer, home = self.groups(focusName="An Album")
        self.assertTrue(inner._get_isPresentableFocusAncestor())
        self.assertFalse(outer._get_isPresentableFocusAncestor())

    def test_unique_group_names_retained(self):
        focus, inner, outer, home = self.groups(focusName="An Album", innerName="Featured", outerName="Top Picks for You")
        self.assertTrue(inner._get_isPresentableFocusAncestor())
        self.assertTrue(outer._get_isPresentableFocusAncestor())

    def test_grouping_outside_home_unchanged(self):
        focus, inner, outer, home = self.groups(page="Browse")
        self.assertTrue(inner._get_isPresentableFocusAncestor())
        self.assertTrue(outer._get_isPresentableFocusAncestor())

    def test_grouping_not_in_focus_ancestry_unchanged(self):
        focus, inner, outer, home = self.groups()
        music.api.getFocusObject = lambda: Node("LINK", "Recently Played")
        self.assertTrue(inner._get_isPresentableFocusAncestor())


if __name__ == "__main__":
    unittest.main()
