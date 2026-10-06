# -*- coding: utf-8 -*-
"""Tests for who may assign, see and change a todo on the kanban page.

The page is `erplite/www/todo/index.py`. Until these tests existed nothing
under tests/ loaded it, and its six whitelisted endpoints had no coverage at
all.

## The rule being tested

The owner's decision: anyone may assign a todo to anyone, from creation
onward, and whoever created or assigned it keeps track of it once it is with
someone else.

That is not a new rule. It is the rule Frappe already applies to ToDo:

    # frappe/desk/doctype/todo/todo.py
    def has_permission(doc, ptype="read", user=None):
        ...
        return doc.allocated_to == user or doc.assigned_by == user or doc.owner == user

and `get_permission_query_conditions` builds the same three-way OR in SQL.
ToDo's only non-automatic role is System Manager, so for everybody else that
OR is the whole of their access. The page had reimplemented a narrower rule by
hand -- allocated_to only -- in five places, and the two halves disagreed with
each other:

  * `create_todo` replaced a non-manager's chosen assignee with themselves and
    still returned `success: True`, so the person they picked was discarded in
    silence.
  * `update_todo` then let that same non-manager hand the todo to anyone, one
    call later -- and locked them out of it afterwards.

## Why the writes are safe to widen

`frappe.get_all` sets `ignore_permissions=True`, so Frappe's query conditions
never ran for this page's lists: the filters in `get_context` were the only
thing deciding what a non-manager saw, and widening them is a real change.
Saves and deletes go through `Document`, where Frappe's `has_permission` does
apply -- so widening the page's own write checks to the three-way rule cannot
reach past what Frappe already allows.

## The child link

Todos have children: Afterz's `Planner Entry` carries a `todo` field pointing
at its parent (afterz/beforez_api.py). Afterz also lists
`ignore_links_on_delete = ["Planner Entry", "Timesheet Entry"]`, so Frappe
will not stop a ToDo being deleted out from under one. Reassignment must
therefore leave `name` alone, which is what the last test here checks.
"""

import importlib.util
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from fake_frappe import (  # noqa: E402
    FakeFrappe, FakeUtils, ValidationError, _dict,
)

CREATOR = "ellis@company.test"
ASSIGNEE = "maya@company.test"
THIRD = "alex@company.test"
STRANGER = "robin@company.test"
BOSS = "pat@company.test"

PAGE = os.path.join(APP_ROOT, "erplite", "www", "todo", "index.py")
DATA_MANAGER = os.path.join(
    APP_ROOT, "erplite", "public", "js", "todo", "data", "TodoDataManager.js")


def load_page(frappe):
    """Load the todo page with `frappe` replaced by the stand-in.

    Loaded from its path rather than imported as erplite.www.todo.index,
    because erplite/__init__.py pulls in parts of Frappe that have nothing to
    do with this page.
    """
    for name in list(sys.modules):
        if name == "frappe" or name.startswith("frappe."):
            del sys.modules[name]

    frappe_pkg = types.ModuleType("frappe")
    frappe_pkg.__path__ = []
    for attr in dir(frappe):
        if not attr.startswith("__"):
            setattr(frappe_pkg, attr, getattr(frappe, attr))
    frappe_pkg._dict = _dict

    utils = FakeUtils()
    utils_mod = types.ModuleType("frappe.utils")
    for attr in ("getdate", "today", "formatdate", "get_system_timezone"):
        setattr(utils_mod, attr, getattr(utils, attr))
    frappe_pkg.utils = utils_mod

    sys.modules["frappe"] = frappe_pkg
    sys.modules["frappe.utils"] = utils_mod

    spec = importlib.util.spec_from_file_location("erplite_todo_page_under_test", PAGE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def world(session_user, manager=None):
    """A stand-in site with a directory of five people and one manager."""
    frappe = FakeFrappe(session_user=session_user, roles=[])
    frappe.tables["User"] = [
        _dict(name=email, full_name=name, user_image=None,
              enabled=1, user_type="System User")
        for email, name in [
            (CREATOR, "Ellis Vance"), (ASSIGNEE, "Maya Chen"),
            (THIRD, "Alex Morgan"), (STRANGER, "Robin Ward"),
            (BOSS, "Pat Quinn"),
        ]
    ]
    # Only the people named here are managers. `Has Role` is a child table, so
    # the user is in `parent` -- which is how the page queries it.
    #
    # Everybody else holds a role too, and that is deliberate. In a world where
    # non-managers held no role at all, "System Manager or Administrator" and
    # "any role whatsoever" answered the same for every user here, so a page
    # that stopped checking *which* role someone holds passed every test in
    # this file.
    managers = list(manager or [BOSS])
    frappe.tables["Has Role"] = [
        _dict(name="hr-%s" % email, parent=email, parenttype="User",
              parentfield="roles",
              role="System Manager" if email in managers else "Projects User")
        for email in (CREATOR, ASSIGNEE, THIRD, STRANGER, BOSS)
    ]
    frappe.tables["ToDo"] = []
    return frappe


def a_todo(name="TODO-0001", allocated_to=ASSIGNEE, assigned_by=CREATOR,
           owner=CREATOR, status="Open"):
    return _dict(
        name=name, description="Reconcile the quarter", status=status,
        priority="Medium", date=None, color=None, allocated_to=allocated_to,
        assigned_by=assigned_by, owner=owner, reference_type=None,
        reference_name=None, creation="2026-10-01 09:00:00",
        modified="2026-10-01 09:00:00",
    )


class CreateTestCase(unittest.TestCase):
    """create_todo must keep the assignee the user chose, whoever they are."""

    def test_a_non_manager_keeps_the_assignee_they_chose(self):
        frappe = world(CREATOR)
        page = load_page(frappe)

        result = page.create_todo("Reconcile the quarter", allocated_to=ASSIGNEE)

        self.assertTrue(result["success"], result)
        stored = frappe.tables["ToDo"][0]
        # Before this change the stored value was CREATOR and the call still
        # reported success, so the chosen assignee vanished without a word.
        self.assertEqual(stored["allocated_to"], ASSIGNEE)

    def test_a_manager_keeps_the_assignee_too(self):
        frappe = world(BOSS)
        page = load_page(frappe)

        page.create_todo("Reconcile the quarter", allocated_to=ASSIGNEE)

        self.assertEqual(frappe.tables["ToDo"][0]["allocated_to"], ASSIGNEE)

    def test_no_assignee_still_means_mine(self):
        """The quick-add buttons send no assignee and expect their own list."""
        frappe = world(CREATOR)
        page = load_page(frappe)

        page.create_todo("Reconcile the quarter")

        self.assertEqual(frappe.tables["ToDo"][0]["allocated_to"], CREATOR)

    def test_the_creator_is_recorded_as_having_assigned_it(self):
        frappe = world(CREATOR)
        page = load_page(frappe)

        page.create_todo("Reconcile the quarter", allocated_to=ASSIGNEE)

        stored = frappe.tables["ToDo"][0]
        self.assertEqual(stored["assigned_by"], CREATOR)
        # `owner` is Frappe's, set on insert and never changed afterwards.
        self.assertEqual(stored["owner"], CREATOR)

    def test_a_new_todo_starts_in_the_backlog(self):
        """Unchanged behaviour, pinned because `Backlog` is not stock Frappe."""
        frappe = world(CREATOR)
        page = load_page(frappe)

        page.create_todo("Reconcile the quarter", allocated_to=ASSIGNEE)

        self.assertEqual(frappe.tables["ToDo"][0]["status"], "Backlog")


class UpdateTestCase(unittest.TestCase):
    """Whoever created or handed on a todo keeps the right to update it."""

    def setUp(self):
        self.frappe = world(CREATOR)
        self.frappe.tables["ToDo"] = [a_todo()]

    def test_the_creator_can_still_update_after_handing_it_over(self):
        page = load_page(self.frappe)

        result = page.update_todo("TODO-0001", description="Reconcile Q1")

        # Before this change: {'success': False, 'message': "You don't have
        # permission to update this todo"} -- handing a todo on was a one-way
        # door that locked its creator out.
        self.assertTrue(result["success"], result)
        self.assertEqual(self.frappe.tables["ToDo"][0]["description"], "Reconcile Q1")

    def test_the_person_it_is_with_can_update_it(self):
        self.frappe.session.user = ASSIGNEE
        page = load_page(self.frappe)

        self.assertTrue(page.update_todo("TODO-0001", priority="High")["success"])

    def test_a_manager_can_update_anybody_s(self):
        self.frappe.session.user = BOSS
        page = load_page(self.frappe)

        self.assertTrue(page.update_todo("TODO-0001", priority="High")["success"])

    def test_someone_with_no_part_in_it_still_cannot(self):
        """The widening is to Frappe's rule, not to everyone."""
        self.frappe.session.user = STRANGER
        page = load_page(self.frappe)

        result = page.update_todo("TODO-0001", description="mine now")

        self.assertFalse(result["success"])
        self.assertIn("permission", result["message"])
        # And nothing was written: get_doc hands back a copy, so a refused
        # update leaves the stored document alone.
        self.assertEqual(
            self.frappe.tables["ToDo"][0]["description"], "Reconcile the quarter")

    def test_handing_it_on_records_who_did_so(self):
        """So the new assigner keeps track of it in turn."""
        self.frappe.session.user = ASSIGNEE
        page = load_page(self.frappe)

        self.assertTrue(page.update_todo("TODO-0001", allocated_to=THIRD)["success"])

        stored = self.frappe.tables["ToDo"][0]
        self.assertEqual(stored["allocated_to"], THIRD)
        self.assertEqual(stored["assigned_by"], ASSIGNEE)
        # The creator is still reachable through `owner`, which is why
        # overwriting assigned_by loses nobody who was involved.
        self.assertEqual(stored["owner"], CREATOR)

    def test_whoever_handed_it_on_can_still_update_it(self):
        self.frappe.session.user = ASSIGNEE
        page = load_page(self.frappe)
        page.update_todo("TODO-0001", allocated_to=THIRD)

        self.assertTrue(page.update_todo("TODO-0001", priority="High")["success"])

    def test_the_creator_can_still_update_it_two_hands_later(self):
        self.frappe.session.user = ASSIGNEE
        page = load_page(self.frappe)
        page.update_todo("TODO-0001", allocated_to=THIRD)

        self.frappe.session.user = CREATOR
        page = load_page(self.frappe)
        self.assertTrue(page.update_todo("TODO-0001", priority="Low")["success"])

    def test_a_manager_by_the_administrator_role_can_update_anybody_s(self):
        """MANAGER_ROLES names two roles, and only one of them was pinned.

        Dropping "Administrator" from that list changed nothing any test here
        noticed, so half of what decides who may manage anybody's todo was
        unguarded. THIRD has no part in this todo by name.
        """
        self.frappe.tables["Has Role"].append(
            _dict(name="hr-admin", parent=THIRD, parenttype="User",
                  parentfield="roles", role="Administrator"))
        self.frappe.session.user = THIRD
        page = load_page(self.frappe)

        self.assertTrue(page.update_todo("TODO-0001", priority="High")["success"])

    def test_editing_without_reassigning_leaves_assigned_by_alone(self):
        page = load_page(self.frappe)

        page.update_todo("TODO-0001", description="Reconcile Q1")

        self.assertEqual(self.frappe.tables["ToDo"][0]["assigned_by"], CREATOR)

    def test_editing_without_reassigning_leaves_the_assignee_alone(self):
        """A description-only edit must not unallocate the todo.

        `allocated_to is not None` is the whole of what makes that true, and
        dropping it passed every test here: the only thing checked after a
        plain edit was assigned_by, and this edit is made by the creator --
        who is also what assigned_by would have been overwritten with. So the
        wrong code and the right code agreed on the one field being read.
        """
        page = load_page(self.frappe)

        page.update_todo("TODO-0001", description="Reconcile Q1")

        self.assertEqual(self.frappe.tables["ToDo"][0]["allocated_to"], ASSIGNEE)

    def test_reassigning_to_the_same_person_leaves_assigned_by_alone(self):
        """Re-sending the current assignee is not a hand-over."""
        self.frappe.session.user = ASSIGNEE
        page = load_page(self.frappe)

        page.update_todo("TODO-0001", allocated_to=ASSIGNEE)

        self.assertEqual(self.frappe.tables["ToDo"][0]["assigned_by"], CREATOR)

    def test_the_name_survives_a_hand_over(self):
        """Afterz's Planner Entry points at its parent todo by name.

        `ignore_links_on_delete` in afterz/hooks.py covers Planner Entry, so
        Frappe will not catch a broken link for us. Reassignment must not
        touch the name, and this fails if anything here ever starts
        re-creating a todo instead of saving it.
        """
        page = load_page(self.frappe)

        page.update_todo("TODO-0001", allocated_to=THIRD)

        self.assertEqual([r["name"] for r in self.frappe.tables["ToDo"]], ["TODO-0001"])
        self.assertEqual(self.frappe.inserts, [])


class StatusTestCase(unittest.TestCase):
    """Dragging a card between columns goes through update_todo_status."""

    def setUp(self):
        self.frappe = world(CREATOR)
        self.frappe.tables["ToDo"] = [a_todo()]

    def test_the_creator_can_move_a_card_they_handed_over(self):
        page = load_page(self.frappe)

        result = page.update_todo_status("TODO-0001", "Planned")

        self.assertTrue(result["success"], result)
        self.assertEqual(self.frappe.tables["ToDo"][0]["status"], "Planned")

    def test_someone_with_no_part_in_it_cannot_move_it(self):
        self.frappe.session.user = STRANGER
        page = load_page(self.frappe)

        self.assertFalse(page.update_todo_status("TODO-0001", "Planned")["success"])
        self.assertEqual(self.frappe.tables["ToDo"][0]["status"], "Open")


class DeleteTestCase(unittest.TestCase):
    """Deleting stays narrower than updating, deliberately."""

    def setUp(self):
        self.frappe = world(CREATOR)
        self.frappe.tables["ToDo"] = [a_todo()]

    def test_the_creator_cannot_delete_what_they_handed_over(self):
        """Keeping track of a todo is not the same as being able to destroy it.

        A creator can still set it to Cancelled through update_todo. This test
        exists so that the asymmetry is a decision on the record rather than an
        oversight -- change it here first if the rule is ever widened.
        """
        page = load_page(self.frappe)

        result = page.delete_todo("TODO-0001")

        self.assertFalse(result["success"])
        self.assertEqual(len(self.frappe.tables["ToDo"]), 1)

    def test_the_person_it_is_with_can_delete_it(self):
        self.frappe.session.user = ASSIGNEE
        page = load_page(self.frappe)

        self.assertTrue(page.delete_todo("TODO-0001")["success"])
        self.assertEqual(self.frappe.tables["ToDo"], [])


class BoardTestCase(unittest.TestCase):
    """What get_context puts in front of a non-manager.

    This is the *second* copy of the three-way rule -- `or_filters` here,
    `_can_manage_todo` above -- and the two were not guarded equally. The
    server's copy is pinned clause by clause, because the update tests hand a
    todo on and so reach it as assigner and as creator separately. The board's
    copy was pinned only as a whole, by fixtures that matched all three clauses
    at once. `frappe.get_all` passes ignore_permissions=True, so these filters
    are the only thing deciding what a non-manager sees: there is nothing
    behind them to catch a clause that goes missing.
    """

    def setUp(self):
        self.frappe = world(CREATOR)
        self.frappe.tables["ToDo"] = [
            a_todo("TODO-MINE", allocated_to=CREATOR, assigned_by=CREATOR, owner=CREATOR),
            a_todo("TODO-HANDED-ON", allocated_to=ASSIGNEE, assigned_by=CREATOR, owner=CREATOR),
            # TODO-MINE and TODO-HANDED-ON are the creator's by all three
            # fields at once, so neither can tell the board's three-way OR
            # apart from any single clause of it: with only those two here,
            # dropping any one field from `or_filters` changed nothing this
            # file noticed. These three are reachable through exactly one
            # field each, and each is a real way a todo arrives.
            a_todo("TODO-ONLY-BY-ME", allocated_to=THIRD, assigned_by=CREATOR, owner=BOSS),
            a_todo("TODO-ONLY-FROM-ME", allocated_to=THIRD, assigned_by=ASSIGNEE, owner=CREATOR),
            a_todo("TODO-ONLY-WITH-ME", allocated_to=CREATOR, assigned_by=BOSS, owner=BOSS),
            a_todo("TODO-THEIRS", allocated_to=STRANGER, assigned_by=STRANGER, owner=STRANGER),
            a_todo("TODO-CANCELLED", allocated_to=CREATOR, status="Cancelled"),
        ]

    def board(self, user):
        self.frappe.session.user = user
        page = load_page(self.frappe)
        context = {}
        page.get_context(context)
        return context

    def test_the_board_shows_work_you_handed_on(self):
        names = [t["name"] for t in self.board(CREATOR)["todos"]]

        # TODO-HANDED-ON was invisible before this change: the filter was
        # allocated_to only, so giving work away meant losing sight of it.
        self.assertIn("TODO-HANDED-ON", names)
        self.assertIn("TODO-MINE", names)

    def test_a_todo_you_handed_on_but_did_not_create_is_still_yours(self):
        """Reachable through assigned_by alone: somebody else created it."""
        self.assertIn("TODO-ONLY-BY-ME",
                      [t["name"] for t in self.board(CREATOR)["todos"]])

    def test_a_todo_you_created_and_somebody_else_handed_on_is_still_yours(self):
        """Reachable through owner alone: assigned_by moved on with the hand-over."""
        self.assertIn("TODO-ONLY-FROM-ME",
                      [t["name"] for t in self.board(CREATOR)["todos"]])

    def test_a_todo_simply_given_to_you_is_yours(self):
        """Reachable through allocated_to alone: you neither created nor sent it."""
        self.assertIn("TODO-ONLY-WITH-ME",
                      [t["name"] for t in self.board(CREATOR)["todos"]])

    def test_the_board_does_not_show_other_people_s_work(self):
        names = [t["name"] for t in self.board(CREATOR)["todos"]]

        self.assertNotIn("TODO-THEIRS", names)

    def test_cancelled_todos_stay_off_the_board(self):
        """The status filter must still apply alongside the three-way OR."""
        names = [t["name"] for t in self.board(CREATOR)["todos"]]

        self.assertNotIn("TODO-CANCELLED", names)

    def test_a_manager_sees_everything_uncancelled(self):
        names = [t["name"] for t in self.board(BOSS)["todos"]]

        self.assertEqual(sorted(names), [
            "TODO-HANDED-ON", "TODO-MINE", "TODO-ONLY-BY-ME",
            "TODO-ONLY-FROM-ME", "TODO-ONLY-WITH-ME", "TODO-THEIRS"])

    def test_the_page_is_told_who_each_todo_is_with(self):
        """The three fields the page decides its own permissions from.

        None of them were sent before, so `todo.allocated_to` was undefined on
        every card and TodoDataManager.canEditTodo compared undefined with the
        current user. That is always false, which hid the edit, delete,
        assign, date and drag controls from every non-manager.
        """
        handed_on = [t for t in self.board(CREATOR)["todos"]
                     if t["name"] == "TODO-HANDED-ON"][0]

        self.assertEqual(handed_on["allocated_to"], ASSIGNEE)
        self.assertEqual(handed_on["assigned_by"], CREATOR)
        self.assertEqual(handed_on["owner"], CREATOR)

    def test_everyone_can_choose_from_the_whole_directory(self):
        """Anyone may assign to anyone, so anyone needs the full list.

        A non-manager used to be handed a list containing only themselves,
        which left `create_todo` honouring a choice the page could not offer.
        """
        users = self.board(CREATOR)["users"]

        self.assertEqual(
            sorted(u["name"] for u in users),
            sorted([CREATOR, ASSIGNEE, THIRD, STRANGER, BOSS]))

    def test_get_todos_agrees_with_the_board(self):
        """The endpoint the page refreshes through takes the same route."""
        self.frappe.session.user = CREATOR
        page = load_page(self.frappe)

        names = [t["name"] for t in page.get_todos()["todos"]]

        self.assertIn("TODO-HANDED-ON", names)
        self.assertNotIn("TODO-THEIRS", names)


class PageAndServerAgreeTestCase(unittest.TestCase):
    """A whole-file guard: the page's copy of the rule must match the server's.

    `canEditTodo` is the client-side half, and eight call sites gate the card's
    controls on it. Leaving one half of a client/server pair behind is the
    obvious way to get this wrong, and the symptom -- a control that is hidden,
    or shown and then refused -- appears only in the browser.
    """

    def test_can_edit_names_all_three_fields(self):
        with open(DATA_MANAGER, encoding="utf-8") as handle:
            source = handle.read()
        body = source.split("canEditTodo(todo) {", 1)[1].split("}", 1)[0]

        for field in ("allocated_to", "assigned_by", "owner"):
            self.assertIn(
                field, body,
                "canEditTodo does not consider todo.%s, so the page and "
                "_can_manage_todo in index.py disagree about who may edit" % field)

    def test_can_delete_stays_narrow(self):
        with open(DATA_MANAGER, encoding="utf-8") as handle:
            source = handle.read()
        body = source.split("canDeleteTodo(todo) {", 1)[1].split("}", 1)[0]

        self.assertIn("allocated_to", body)
        for field in ("assigned_by", "owner"):
            self.assertNotIn(
                field, body,
                "canDeleteTodo offers delete to %s, but delete_todo on the "
                "server refuses them -- the button would fail on the click" % field)

    def test_the_server_rule_names_all_three_fields(self):
        with open(PAGE, encoding="utf-8") as handle:
            source = handle.read()
        body = source.split("def _can_manage_todo(", 1)[1].split("\ndef ", 1)[0]

        for field in ("allocated_to", "assigned_by", "owner"):
            self.assertIn(field, body)


if __name__ == "__main__":
    unittest.main()
