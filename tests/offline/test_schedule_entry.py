# -*- coding: utf-8 -*-
"""Tests for the Schedule Entry controller after the Task -> Activity rename.

Background. Commit 98e9b04 ("stable with working task kanban", 23 Jul 2025)
renamed this DocType's `task` field to `activity` in place and repointed it
from the Task DocType to Activity. Commit 8126278 later removed the Task
DocType from the app altogether. The controller was not brought along, and
three references survived:

    validate_task_project_link   self.task, and get_value("Task", ...)
    update_task_progress         self.task, a filter on "task", and
                                 set_value("Task", ..., "progress_percent")
    get_overlapping_entries      raw SQL selecting the `task` column

The first one is the one that bites. `validate()` calls it on every save, and
a document built in memory has no attribute for a field the DocType does not
have (see make_doc in fake_frappe.py for the chain through Frappe's own
source), so `self.task` raised AttributeError. The whitelisted
`scheduler.api.create_schedule_entry` sets `doc.activity` and never
`doc.task`, then wraps `doc.insert()` in `except Exception`, so creating an
entry from the scheduler came back as
`{"success": false, "message": "'ScheduleEntry' object has no attribute 'task'"}`
and every attempt went to the error log.

Fixing only validate() would have moved the failure to on_update, where
set_value("Task", ...) targets a table that does not exist. Both had to go for
creation to work at all.

`progress_percent` has no successor: it was a field on Activity and 8126278
removed it, so there is nowhere to write progress back to. The calculation is
kept as get_activity_progress() and the write is gone rather than pointed at
an orphaned column.

What driving this file found (7 Oct 2026, tests/faultinject target
`schedule_entry`). Everything above was already true and already green, and
six edits to the controller went unnoticed under that green:

  * the link check unwired from validate() -- the file's headline claim is
    that validate() calls it on every save, and nothing asserted the call was
    still there. test_validate_itself_performs_the_link_check does now.
  * the `if not self.activity` guard removed from get_activity_progress. A
    query filtered on activity=None matches no row, so the answer was None
    either way; the test could not tell the guard from its absence. It now
    asserts that nothing is queried, as the validate() equivalent already did.
  * the clamp in `min(100, ...)` removed. Completed hours are a subset of the
    hours counted, so the fixture's completed == total made the ratio exactly
    100 with or without the clamp. See
    test_progress_is_clamped_when_the_rows_do_not_add_up for the one input
    that reaches it.
  * and three in the sweep for Task calls, which read one line at a time: it
    could not see a call whose DocType sat on the next line, and it counted a
    trailing comment and a docstring as calls -- so correct code was an
    offender. It reads Python's tokens now; TaskCallDetectorTest pins each
    case.
"""

import ast
import io
import os
import sys
import tokenize
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from fake_frappe import (  # noqa: E402
    FakeDocumentBase, FakeFrappe, UnknownField, ValidationError,
    doctype_fields, make_doc, _dict,
)

USER = "pat@company.test"


def load_schedule_entry(frappe):
    """Load the Schedule Entry controller with `frappe` replaced by the stand-in."""
    for name in list(sys.modules):
        if name == "frappe" or name.startswith("frappe."):
            del sys.modules[name]

    frappe_pkg = types.ModuleType("frappe")
    frappe_pkg.__path__ = []
    for attr in dir(frappe):
        if not attr.startswith("__"):
            setattr(frappe_pkg, attr, getattr(frappe, attr))
    frappe_pkg._dict = _dict

    model = types.ModuleType("frappe.model")
    model.__path__ = []
    document = types.ModuleType("frappe.model.document")
    document.Document = FakeDocumentBase
    model.document = document
    frappe_pkg.model = model

    sys.modules["frappe"] = frappe_pkg
    sys.modules["frappe.model"] = model
    sys.modules["frappe.model.document"] = document

    import importlib.util
    path = os.path.join(APP_ROOT, "erplite", "scheduler", "doctype",
                        "schedule_entry", "schedule_entry.py")
    spec = importlib.util.spec_from_file_location(
        "erplite_schedule_entry_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScheduleEntryTestCase(unittest.TestCase):
    def setUp(self):
        self.frappe = FakeFrappe(session_user=USER, roles=["System Manager"])
        self.frappe.tables["Project"] = [
            _dict(name="5gofgdoomv", project_name="Northwind", status="Open"),
            _dict(name="other01", project_name="Another project", status="Open"),
        ]
        self.frappe.tables["Activity"] = [
            _dict(name="g68cfomvvu", project="5gofgdoomv", status="Open",
                  activity_name="PO-0001 - Systems engineering support"),
            _dict(name="act_other_proj", project="other01", status="Open",
                  activity_name="Activity on another project"),
        ]
        self.module = load_schedule_entry(self.frappe)

    def entry(self, **data):
        return make_doc(self.module.ScheduleEntry, "Schedule Entry",
                        "scheduler", "schedule_entry", data)


class PremisesTest(ScheduleEntryTestCase):
    """The facts the fix rests on, read from the DocType JSONs themselves."""

    def test_schedule_entry_has_activity_and_not_task(self):
        fields = doctype_fields("scheduler", "schedule_entry")
        self.assertIn("activity", fields)
        self.assertNotIn("task", fields)

    def test_activity_has_project_so_the_check_has_a_successor(self):
        self.assertIn("project", doctype_fields("projects", "activity"))

    def test_activity_has_no_progress_percent_so_the_write_had_nowhere_to_go(self):
        self.assertNotIn("progress_percent", doctype_fields("projects", "activity"))

    def test_a_new_document_has_no_attribute_for_a_removed_field(self):
        """Why the old code broke creation rather than reading nonsense."""
        entry = self.entry(activity="g68cfomvvu", project="5gofgdoomv")
        self.assertEqual(entry.activity, "g68cfomvvu")
        with self.assertRaises(AttributeError):
            entry.task


class ValidateTest(ScheduleEntryTestCase):
    def test_validate_passes_for_a_matching_activity_and_project(self):
        entry = self.entry(activity="g68cfomvvu", project="5gofgdoomv")
        entry.validate_activity_project_link()

    def test_validate_rejects_an_activity_from_another_project(self):
        entry = self.entry(activity="act_other_proj", project="5gofgdoomv")
        with self.assertRaises(ValidationError) as caught:
            entry.validate_activity_project_link()
        self.assertIn("Activity", str(caught.exception))

    def test_validate_skips_the_check_when_the_activity_is_unset(self):
        entry = self.entry(project="5gofgdoomv")
        entry.validate_activity_project_link()
        self.assertEqual(self.frappe.queries, [])

    def test_the_project_lookup_reads_activity_not_task(self):
        entry = self.entry(activity="g68cfomvvu", project="5gofgdoomv")
        entry.validate_activity_project_link()
        # A lookup against the Task DocType would not survive the stand-in,
        # which knows only the DocTypes this app actually ships.
        with self.assertRaises(UnknownField):
            self.frappe.db.get_value("Task", "g68cfomvvu", "project")

    def test_whole_validate_runs_without_touching_the_removed_field(self):
        """The real entry point: validate() is what every save goes through."""
        entry = self.entry(activity="g68cfomvvu", project="5gofgdoomv",
                           duration=4.0, schedule_date="2026-10-05")
        entry.validate()

    def test_validate_itself_performs_the_link_check(self):
        """The call has to be wired into validate(), not just exist.

        Every test above calls validate_activity_project_link() directly, so
        deleting its line from validate() left them all green -- and that line
        is the whole reason the check runs on a save.
        """
        entry = self.entry(activity="act_other_proj", project="5gofgdoomv",
                           duration=4.0, schedule_date="2026-10-05")
        with self.assertRaises(ValidationError):
            entry.validate()

    def test_validate_refuses_a_duration_of_nought_or_less(self):
        """The other half of the clamp's reasoning, in ProgressTest below."""
        entry = self.entry(activity="g68cfomvvu", project="5gofgdoomv",
                           duration=-4.0, schedule_date="2026-10-05")
        with self.assertRaises(ValidationError):
            entry.validate()

    def test_the_old_method_name_is_gone(self):
        self.assertFalse(hasattr(self.module.ScheduleEntry,
                                 "validate_task_project_link"))
        self.assertTrue(hasattr(self.module.ScheduleEntry,
                                "validate_activity_project_link"))


class ProgressTest(ScheduleEntryTestCase):
    def schedule_rows(self):
        self.frappe.tables["Schedule Entry"] = [
            _dict(name="SCH-0001", activity="g68cfomvvu", status="Completed",
                  duration=4.0, docstatus=1),
            _dict(name="SCH-0002", activity="g68cfomvvu", status="Planned",
                  duration=4.0, docstatus=1),
            _dict(name="SCH-0003", activity="g68cfomvvu", status="Completed",
                  duration=2.0, docstatus=2),   # cancelled, must not count
            _dict(name="SCH-0004", activity="act_other_proj", status="Completed",
                  duration=8.0, docstatus=1),   # another activity
        ]

    def test_on_update_writes_nothing_at_all(self):
        entry = self.entry(activity="g68cfomvvu", project="5gofgdoomv")
        entry.on_update()
        self.assertEqual(self.frappe.values_set, [])

    def test_the_old_write_method_is_gone(self):
        self.assertFalse(hasattr(self.module.ScheduleEntry, "update_task_progress"))
        self.assertTrue(hasattr(self.module.ScheduleEntry, "get_activity_progress"))

    def test_progress_counts_completed_hours_and_excludes_cancelled(self):
        self.schedule_rows()
        entry = self.entry(activity="g68cfomvvu", project="5gofgdoomv")
        # 4 completed of 8 live hours; the cancelled 2 and the other activity's
        # 8 are both out.
        self.assertEqual(entry.get_activity_progress(), 50.0)

    def test_progress_filters_on_activity(self):
        self.schedule_rows()
        entry = self.entry(activity="g68cfomvvu", project="5gofgdoomv")
        entry.get_activity_progress()
        self.assertEqual(len(self.frappe.queries), 1)
        query = self.frappe.queries[0]
        self.assertEqual(query.doctype, "Schedule Entry")
        self.assertIn("activity", query.filters)
        self.assertNotIn("task", query.filters)

    def test_progress_is_none_without_an_activity(self):
        """And nothing is asked for: the guard answers, not an empty table.

        Without the assertion on queries this could not tell the guard from
        its absence. A query filtered on activity=None matches no row, so
        `if not entries: return None` gives the same None one line later.
        """
        entry = self.entry(project="5gofgdoomv")
        self.assertIsNone(entry.get_activity_progress())
        self.assertEqual(self.frappe.queries, [])

    def test_progress_is_none_with_no_entries(self):
        self.frappe.tables["Schedule Entry"] = []
        entry = self.entry(activity="g68cfomvvu", project="5gofgdoomv")
        self.assertIsNone(entry.get_activity_progress())

    def test_progress_is_none_when_nothing_is_scheduled(self):
        """Hours can be zero or unset; that is not 0% done, it is nothing to measure."""
        self.frappe.tables["Schedule Entry"] = [
            _dict(name="SCH-0001", activity="g68cfomvvu", status="Planned",
                  duration=None, docstatus=1),
        ]
        entry = self.entry(activity="g68cfomvvu", project="5gofgdoomv")
        self.assertIsNone(entry.get_activity_progress())

    def test_progress_is_one_hundred_when_every_hour_is_done(self):
        """The boundary. Named for what it measures: this is not the clamp."""
        self.frappe.tables["Schedule Entry"] = [
            _dict(name="SCH-0001", activity="g68cfomvvu", status="Completed",
                  duration=8.0, docstatus=1),
        ]
        entry = self.entry(activity="g68cfomvvu", project="5gofgdoomv")
        self.assertEqual(entry.get_activity_progress(), 100)

    def test_progress_is_clamped_when_the_rows_do_not_add_up(self):
        """What `min(100, ...)` is for, and the only input that reaches it.

        Completed hours are a subset of the hours counted, so for any row the
        controller would accept the ratio cannot exceed 100 -- which is why
        the test above, whose fixture has completed == total, reads the same
        with the clamp and without it. A negative duration is the case that
        gets past: validate_duration refuses one (pinned below), but a direct
        write, an import or a patch does not go through the controller.
        """
        self.frappe.tables["Schedule Entry"] = [
            _dict(name="SCH-0001", activity="g68cfomvvu", status="Completed",
                  duration=8.0, docstatus=1),
            _dict(name="SCH-0002", activity="g68cfomvvu", status="Planned",
                  duration=-4.0, docstatus=1),
        ]
        entry = self.entry(activity="g68cfomvvu", project="5gofgdoomv")
        self.assertEqual(entry.get_activity_progress(), 100)

    def test_a_write_to_a_removed_field_would_now_be_caught(self):
        """Proof that these tests bite: the old write is rejected if it returns."""
        with self.assertRaises(UnknownField):
            self.frappe.db.set_value("Activity", "g68cfomvvu", "progress_percent", 50)
        with self.assertRaises(UnknownField):
            self.frappe.db.set_value("Task", "g68cfomvvu", "progress_percent", 50)


TASK_DOCTYPE_CALLS = frozenset("""
    get_doc get_all get_list get_value get_single_value new_doc get_meta
    set_value delete_doc exists count
""".split())


def task_doctype_calls(text):
    """Line numbers of calls naming the Task DocType, read from Python's tokens.

    Tokens rather than a regex over single lines, because each of the three
    things a line cannot tell you was measured as a wrong answer from the
    version this replaced:

      * `frappe.db.get_value(` with `"Task"` on the following line was not
        found at all -- the formatting black produces for a long call.
      * `pass  # frappe.db.get_value("Task", ...)` was an offender. The old
        sweep skipped a line only when it *started* with `#`.
      * so was a docstring naming the call it replaced.

    A COMMENT token is dropped here, a docstring is a STRING with no call name
    and bracket in front of it, and the tokens of a call run on past the
    newlines inside its brackets.

    Not caught, by this version or the old one: a DocType named anywhere but
    the first argument, as in `frappe.get_doc({"doctype": "Task"})`, or held in
    a variable. The sweeps over Link fields and over `tabTask` cover the JSON
    and SQL routes; this one answers for a literal first argument.
    """
    tokens = [token for token in
              tokenize.generate_tokens(io.StringIO(text).readline)
              if token.type not in (tokenize.COMMENT, tokenize.NL,
                                    tokenize.NEWLINE, tokenize.INDENT,
                                    tokenize.DEDENT)]
    found = []
    for name, bracket, argument in zip(tokens, tokens[1:], tokens[2:]):
        if (name.type != tokenize.NAME
                or name.string not in TASK_DOCTYPE_CALLS
                or bracket.type != tokenize.OP or bracket.string != "("
                or argument.type != tokenize.STRING):
            continue
        try:
            doctype = ast.literal_eval(argument.string)
        except (ValueError, SyntaxError):
            continue        # an f-string or similar: not a plain DocType name
        if doctype == "Task":
            found.append(name.start[0])
    return found


class TaskCallDetectorTest(unittest.TestCase):
    """What the sweep below counts as a call.

    Pinned here as well as in tests/faultinject, because every case is one the
    line-based version got wrong and a detector that cannot find anything
    looks exactly like one that found nothing.
    """

    def calls(self, source):
        return task_doctype_calls(source)

    def test_a_call_is_found(self):
        self.assertEqual(
            self.calls('frappe.db.get_value("Task", x, "project")\n'), [1])

    def test_a_call_split_across_lines_is_found(self):
        self.assertEqual(
            self.calls('frappe.db.get_value(\n    "Task", x, "project")\n'), [1])

    def test_a_whole_line_comment_is_not_a_call(self):
        self.assertEqual(
            self.calls('# frappe.db.get_value("Task", x, "project")\n'), [])

    def test_a_comment_at_the_end_of_a_line_is_not_a_call(self):
        self.assertEqual(
            self.calls('pass  # frappe.db.get_value("Task", x)\n'), [])

    def test_a_docstring_is_not_a_call(self):
        self.assertEqual(
            self.calls('"""Was frappe.db.get_value("Task", x)."""\n'), [])

    def test_another_doctype_is_not_a_call(self):
        self.assertEqual(
            self.calls('frappe.db.get_value("Activity", x, "project")\n'), [])

    def test_a_doctype_held_in_a_variable_is_not_claimed(self):
        """Out of reach, and saying so beats a sweep that implies otherwise."""
        self.assertEqual(
            self.calls('frappe.db.get_value(doctype, x, "project")\n'), [])

    def test_every_line_of_a_call_is_reported_once(self):
        self.assertEqual(
            self.calls('get_doc("Task", a)\nget_all("Task", b)\n'), [1, 2])


class NoTaskDocTypeLeftTest(unittest.TestCase):
    """A sweep, so the next leftover reference fails here rather than in the app.

    The Task DocType is not in this app and is not on the site: it has no
    doctype directory, and rev_839b0d4133's read-only discovery confirmed the
    connected ERP exposes no Task DocType. Any call naming it cannot work.
    """

    def app_sources(self, suffix):
        for root, dirs, files in os.walk(os.path.join(APP_ROOT, "erplite")):
            # public/ holds built bundles, which are not source.
            dirs[:] = [d for d in dirs if d not in ("public", "node_modules", "__pycache__")]
            for name in files:
                if name.endswith(suffix):
                    yield os.path.join(root, name)

    def test_no_python_module_calls_the_task_doctype(self):
        offenders = []
        for path in self.app_sources(".py"):
            with open(path, "rb") as handle:
                text = handle.read().decode("utf-8", "replace")
            relative = os.path.relpath(path, APP_ROOT)
            try:
                numbers = task_doctype_calls(text)
            except (tokenize.TokenError, SyntaxError, IndentationError) as exc:
                # A file this cannot read is not a file with nothing in it.
                # Reporting it is what stops a sweep that swept nothing from
                # passing as a sweep that found nothing.
                offenders.append("%s: could not be read (%s)" % (relative, exc))
                continue
            offenders.extend("%s:%d" % (relative, number) for number in numbers)
        self.assertEqual(offenders, [], "Task DocType referenced at: %s" % offenders)

    def test_no_raw_sql_names_the_task_table(self):
        offenders = []
        for suffix in (".py", ".js", ".json"):
            for path in self.app_sources(suffix):
                with open(path, "rb") as handle:
                    text = handle.read().decode("utf-8", "replace")
                if "tabTask" in text:
                    offenders.append(os.path.relpath(path, APP_ROOT))
        self.assertEqual(offenders, [])

    def test_no_link_field_points_at_the_task_doctype(self):
        offenders = []
        for path in self.app_sources(".json"):
            with open(path, "rb") as handle:
                text = handle.read().decode("utf-8", "replace")
            if '"options": "Task"' in text:
                offenders.append(os.path.relpath(path, APP_ROOT))
        self.assertEqual(offenders, [])

    def test_the_projects_workspace_does_not_link_a_missing_doctype(self):
        path = os.path.join(APP_ROOT, "erplite", "config", "projects.py")
        with open(path, "rb") as handle:
            text = handle.read().decode("utf-8")
        self.assertNotIn('"name": "Task"', text)
        self.assertIn('"name": "Activity"', text)

    def test_the_overlap_query_does_not_select_the_removed_column(self):
        path = os.path.join(APP_ROOT, "erplite", "scheduler", "doctype",
                            "schedule_entry", "schedule_entry.py")
        with open(path, "rb") as handle:
            text = handle.read().decode("utf-8")
        self.assertNotIn(", project, task", text)
        self.assertIn("SELECT name, start_time, end_time, project", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
