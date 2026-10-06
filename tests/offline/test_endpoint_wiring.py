# -*- coding: utf-8 -*-
"""A button must call a method that exists, and new_doc must name a real DocType.

Two whole-app rules and one narrow guard, all from review item **rev_0ee5b675ce**.

## What this found (5 Oct 2026)

`supplier_quote.py` whitelisted `create_purchase_order_from_quote`, which opened
with `frappe.new_doc("Purchase Order")`. **No app on this bench declares a
Purchase Order DocType** -- not erplite, not afterz, not frappe itself (it is an
ERPNext DocType, and this is not ERPNext). So `new_doc` raised
`DoesNotExistError` before the first assignment: a whitelisted endpoint that
could not succeed for any input, reached by a "Create Purchase Order" button that
`supplier_quote.js` showed on every Accepted quote. Its own comment admitted it:
*"this would need the Purchase Order doctype to exist"*.

The owner's decision was to remove the endpoint and the button rather than build
the DocType. Removing one half and leaving the other is the obvious way to get
this wrong in either direction, so `TestEveryClientCallResolves` below pins both
halves to each other.

`activity.js` carried the other half of the same item: a `progress_percent` form
handler, a validation branch and a list-view formatter for a field the Activity
DocType does not declare. The owner decided an Activity should not get one, so
they are gone rather than kept as a record of what was intended.

## Why these are rules and not three assertions

A client script naming a server method it cannot reach, and a controller naming a
DocType nothing declares, are both statically decidable and neither is specific to
Supplier Quote. Across the app that is 22 `frappe.call` methods and 209 DocType
literals checked -- the 7 `new_doc` ones among them -- and either goes red the day
somebody deletes a function a button still points at.

The `new_doc` rule began here as its own regex sweep. It is now one case of
`TestEveryDoctypeLiteralNamesADoctypeThatExists` below, which reads the DocType
off the AST for every call that names one, `new_doc` included. The regex is kept
and judges nothing: it is the independent instrument that proves the walker still
reaches all 7 of those sites.

## What these rules do NOT cover

* **Dynamic method names.** Only `method: 'erplite....'` string literals are
  readable. `frappe.call` with a built string, and calls into frappe's own
  endpoints, are skipped -- the second deliberately, since frappe's source is not
  in this tree.
* **Whether the method is whitelisted.** The rule proves the function exists, not
  that `@frappe.whitelist()` is on it. A missing decorator is a permission error
  rather than an "attribute does not exist" error, and it is a different class.
* **`new_doc` with a variable**, and `get_doc({...})` dict literals, which
  `test_mandatory_fields_on_insert.py` covers from the mandatory-field angle.
* **The other three undeclared fields activity.js still reads.** `priority`,
  `due_date` and `estimated_hours` are not fields on Activity either. They are
  inert (`undefined` is falsy, so their branches never run) and whether Activity
  should have them is a product question the owner has not been asked. Only
  `progress_percent` was decided, so only `progress_percent` is asserted here.
  `test_client_scripts.py` records the full list.

Runs without a bench.
"""

import ast
import collections
import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
ERPLITE = os.path.join(APP_ROOT, "erplite")

SKIP_DIRS = ("__pycache__", "node_modules", "public", "dist")

CALL_METHOD = re.compile(r"""method\s*:\s*['"](erplite\.[\w.]+)['"]""")
NEW_DOC = re.compile(r"""new_doc\(\s*['"]([^'"]+)['"]""")


# Where a DocType name can sit as the first argument. Deliberately keyed by the
# receiver as well as the method: `frappe.db.count("X", ...)` names a DocType and
# `date_str.count("-")` does not, and matching on the method name alone reports
# the second. Every name here was read off the app's own calls, not off frappe's
# API surface -- the question is which shapes this app writes.
DOCTYPE_FIRST_ARG = {
    "frappe": {
        "get_doc", "get_cached_doc", "get_last_doc", "new_doc", "get_all",
        "get_list", "get_value", "get_cached_value", "get_single",
        "get_single_value", "get_meta", "delete_doc", "has_permission",
        "rename_doc",
    },
    "frappe.db": {
        "get_value", "get_values", "get_all", "get_list", "exists", "count",
        "set_value", "get_single_value", "delete", "get_cached_value",
    },
}

# DocTypes frappe itself declares. Their JSONs are not in this tree, so this app
# cannot check them and must say so by name instead of by silence.
#
# All six were read off frappe/frappe version-15 on 6 Oct 2026, each from its own
# <dir>/<dir>.json under frappe/, and in each file the DocType's own `name` is the
# string used here:
#
#   User             core/doctype/user/user.json
#   ToDo             desk/doctype/todo/todo.json
#   File             core/doctype/file/file.json
#   Workspace        desk/doctype/workspace/workspace.json
#   Has Role         core/doctype/has_role/has_role.json              istable=1
#   System Settings  core/doctype/system_settings/system_settings.json  issingle=1
#
# The last two kinds are recorded because they decide whether a read is correct,
# not just whether the name resolves. A Single keeps no rows of its own, so
# `frappe.get_all("System Settings")` raises `frappe.db.TableMissingError` --
# a wrong read that this sweep, which judges the name only, would pass.
#
# An earlier version of this comment said that call "would return nothing rather
# than raise". That was written from memory and it is backwards: `get_all` goes
# to `DatabaseQuery`, which asks for the table's columns (db_query.py:422) and
# re-raises `TableMissingError` unless `ignore_ddl` is set (db_query.py:924-931,
# database.py:1344). It is `frappe.db.get_value` that does not mind, falling back
# to the singles table (database.py:648-656). The correction is the point of the
# comment rather than an aside: a claim about what the framework does belongs
# next to the line of framework source it came from, and this one did not have
# one. `test_read_shapes.py` now judges the shape of every Single and child-table
# read, with the source line for each verified shape beside it. The app's two
# System Settings reads use `frappe.get_single` (erplite/www/erplite.py) and its
# `Has Role` reads use `frappe.db.exists` with a `parent` filter, both right.
# Nothing *here* judges shape; that is not a claim this file makes.
FRAPPE_DOCTYPES = {"User", "ToDo", "File", "Has Role", "System Settings",
                   "Workspace"}

# Reads of a DocType that NOTHING declares -- not this app, not frappe. These
# are not exemptions: each one raises on the live site. `Resource Role` has no
# table, so `get_role_resources` and `get_role_statistics` fail rather than
# return nothing, and the owner left them because what a resource-for-a-role
# means without a join table is a product question, not a bug to patch.
# test_scheduler_role_delete.py pins which two functions read it; this pins how
# many read sites there are, so a third cannot arrive quietly.
KNOWN_UNDECLARED_READS = {"Resource Role": 2}

# The DocType-naming sites in the app today. An exact floor, measured, not a
# round number below it: a floor set under the real count is slack, and a site
# can leave the walker's reach without a word being said.
EXPECTED_DOCTYPE_SITES = 209


def _receiver_and_method(call):
    """('frappe' | 'frappe.db' | None, method name or None) for a Call node.

    None for the receiver means this sweep declines to say what the object is.
    Deciding whether some arbitrary object is a frappe handle needs exactly the
    dataflow analysis these static rules exist to avoid, and it would be wrong
    in both directions. So the sweep judges only the two receivers it can read
    by name, and `test_no_module_aliases_frappe` below refuses to be silent
    about the blind spot that leaves.
    """
    func = call.func
    if not isinstance(func, ast.Attribute):
        return None, None
    base = func.value
    if isinstance(base, ast.Name) and base.id == "frappe":
        return "frappe", func.attr
    if (isinstance(base, ast.Attribute) and base.attr == "db"
            and isinstance(base.value, ast.Name) and base.value.id == "frappe"):
        return "frappe.db", func.attr
    return None, func.attr


def _literal(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _doctype_sites():
    """(relpath, line, 'frappe.get_all', 'Activity') for every literal swept.

    The DocType is the first positional or the `doctype` keyword: a call written
    entirely in keywords has no positional arguments at all, and reading only
    args[0] made every one of those invisible to test_query_fields until it was
    fixed there. Same trap, same fix.
    """
    sites = []
    for path in _walk(".py"):
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        rel = os.path.relpath(path, APP_ROOT)
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            receiver, method = _receiver_and_method(node)
            if method not in DOCTYPE_FIRST_ARG.get(receiver, ()):
                continue
            argument = node.args[0] if node.args else None
            if argument is None:
                for keyword in node.keywords:
                    if keyword.arg == "doctype":
                        argument = keyword.value
            doctype = _literal(argument) if argument is not None else None
            if doctype is None:
                continue
            sites.append((rel, node.lineno,
                          "%s.%s" % (receiver, method), doctype))
    return sites


def _frappe_aliases():
    """Every `x = frappe` or `x = frappe.db` in the app, with where it is."""
    found = []
    for path in _walk(".py"):
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        rel = os.path.relpath(path, APP_ROOT)
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Assign):
                continue
            value = node.value
            if isinstance(value, ast.Name) and value.id == "frappe":
                found.append("%s:%d aliases frappe" % (rel, node.lineno))
            elif (isinstance(value, ast.Attribute) and value.attr == "db"
                  and isinstance(value.value, ast.Name)
                  and value.value.id == "frappe"):
                found.append("%s:%d aliases frappe.db" % (rel, node.lineno))
    return found


def _walk(ext):
    for root, dirs, files in os.walk(ERPLITE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith(ext):
                yield os.path.join(root, name)


def _declared_doctypes():
    """Every DocType name this app declares, from <dir>/<dir>.json."""
    names = set()
    for path in _walk(".json"):
        if os.path.basename(path)[:-5] != os.path.basename(os.path.dirname(path)):
            continue
        with open(path, encoding="utf-8") as fh:
            try:
                doc = json.load(fh)
            except ValueError:
                continue
        if doc.get("doctype") == "DocType" and doc.get("name"):
            names.add(doc["name"])
    return names


def _module_level_functions(path):
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    return {node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _client_calls():
    """(js file, dotted method) for every erplite method a client script calls."""
    found = set()
    for path in _walk(".js"):
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        for match in CALL_METHOD.finditer(source):
            found.add((os.path.relpath(path, APP_ROOT), match.group(1)))
    return found


def _resolve(dotted):
    """None if the method resolves; otherwise why it does not."""
    module, _, function = dotted.rpartition(".")
    rel = os.path.join(*module.split(".")) + ".py"
    path = os.path.join(APP_ROOT, rel)
    if not os.path.exists(path):
        return "there is no module %s" % rel
    if function not in _module_level_functions(path):
        return "%s defines no %s()" % (rel, function)
    return None


class TestEveryClientCallResolves(unittest.TestCase):
    """A button that calls a method that is not there fails only when clicked.

    `frappe.call` resolves the dotted path at request time, so a button pointing
    at a deleted function raises `AttributeError` server-side on the click and
    nothing before it. Nothing in a build, a migrate or a test run notices.
    """

    def test_the_walker_found_calls_to_check(self):
        calls = _client_calls()
        self.assertGreaterEqual(len(calls), 20,
                                "the frappe.call walker is broken, so the rule "
                                "below would pass by finding nothing")

    def test_every_method_a_client_script_calls_exists(self):
        failures = []
        for rel, dotted in sorted(_client_calls()):
            why = _resolve(dotted)
            if why:
                failures.append(
                    "%s calls %s and %s -- the button will raise on the click "
                    "and nowhere else" % (rel, dotted, why))
        self.assertEqual(failures, [], "\n" + "\n".join(failures))

    def test_no_button_is_left_pointing_at_the_removed_purchase_order_endpoint(self):
        """The specific half-removal this item was about, from both sides."""
        name = "create_purchase_order_from_quote"
        controller = os.path.join(
            ERPLITE, "accounts", "doctype", "supplier_quote", "supplier_quote.py")
        self.assertNotIn(name, _module_level_functions(controller),
                         "the endpoint was removed by rev_0ee5b675ce; adding it "
                         "back needs a Purchase Order DocType first")
        for rel, dotted in _client_calls():
            self.assertNotIn(name, dotted,
                             "%s still calls the removed endpoint" % rel)


class TestEveryNewDocIsSweptWithTheRest(unittest.TestCase):
    """`new_doc` is judged by the DocType-literal rule below, not twice.

    This class used to hold a second copy of that rule: a regex over
    `new_doc("X")` checking X against the app's DocType JSONs. The AST walker
    below reads the same literal, because `new_doc` is in DOCTYPE_FIRST_ARG, so
    the two were one rule written twice -- and the copies had already drifted.
    The regex knew nothing of FRAPPE_DOCTYPES, so a correct
    `frappe.new_doc("ToDo")` would have passed the walker and failed the regex,
    and whichever message was read first would have been believed.

    Two copies of a rule do not make it twice as strict. They make it two things
    to keep in step, and the one that drifts is the one nobody edited.

    What the regex is still good for is what the walker cannot do for itself:
    say whether it reached everything. It is an independent instrument -- text,
    not the AST -- so the equality below goes red if the walker stops seeing a
    site, or if a `new_doc` is written on a receiver the walker does not read.
    """

    def test_every_new_doc_in_the_app_is_reached_by_the_doctype_walker(self):
        text = []
        for path in _walk(".py"):
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            rel = os.path.relpath(path, APP_ROOT)
            text += [(rel, source[:m.start()].count("\n") + 1, m.group(1))
                     for m in NEW_DOC.finditer(source)]
        walked = [(rel, line, doctype)
                  for rel, line, callee, doctype in _doctype_sites()
                  if callee == "frappe.new_doc"]
        self.assertEqual(
            sorted(walked), sorted(text),
            "the 7 `new_doc` literals in this app are swept by the DocType "
            "walker below, and the regex is here to prove it still reaches all "
            "of them. The two disagree now. A site only the regex sees is a "
            "`new_doc` the walker misses -- most likely on a receiver other "
            "than `frappe`, which _receiver_and_method declines to read -- and "
            "it is unjudged until the walker is widened to it.")
        self.assertEqual(len(text), 7,
                         "the regex reaches %d `new_doc` sites and 7 were "
                         "measured; a regex that matches nothing agrees with a "
                         "walker that reaches nothing" % len(text))

    def test_purchase_order_is_still_not_a_doctype_anywhere_in_this_app(self):
        """So the rule above is testing something, not passing vacuously."""
        self.assertNotIn("Purchase Order", _declared_doctypes(),
                         "if a Purchase Order DocType is added, the endpoint "
                         "this item removed becomes buildable and the removal "
                         "is worth revisiting")


class TestAnActivityDoesNotTrackProgress(unittest.TestCase):
    """The owner's answer: no progress field on Activity (rev_0ee5b675ce)."""

    ACTIVITY_DIR = os.path.join(ERPLITE, "projects", "doctype", "activity")

    def _js(self):
        with open(os.path.join(self.ACTIVITY_DIR, "activity.js"),
                  encoding="utf-8") as fh:
            return fh.read()

    def test_the_doctype_declares_no_progress_field(self):
        with open(os.path.join(self.ACTIVITY_DIR, "activity.json"),
                  encoding="utf-8") as fh:
            fields = {f["fieldname"] for f in json.load(fh)["fields"]}
        self.assertNotIn("progress_percent", fields)
        self.assertFalse([f for f in fields if "progress" in f],
                         "the owner's answer was that an Activity does not "
                         "track progress; a new progress field means that "
                         "decision changed and this file should change with it")

    def test_the_client_script_has_no_progress_handler_or_formatter(self):
        """Checked against code lines only, so the comment saying why may stay.

        Deliberately matched on `progress_percent` and `add_progress` rather
        than on "progress": the status indicator maps still contain the string
        `In Progress`, so a bare substring check would pass or fail on
        capitalisation rather than on anything real.
        """
        offenders = []
        for number, line in enumerate(self._js().splitlines(), start=1):
            if line.strip().startswith("//"):
                continue
            for needle in ("progress_percent", "add_progress"):
                if needle in line:
                    offenders.append("line %d names %s" % (number, needle))
        self.assertEqual(
            offenders, [],
            "activity.js must not watch, validate or format a field the "
            "DocType does not declare: " + "; ".join(offenders))

    def test_add_fields_no_longer_asks_the_list_view_for_it(self):
        """`add_fields` goes into the list query, so a dead name is not inert.

        This is the part that was not merely dead code: frappe's
        `DatabaseQuery` does not check field names against the DocType, so the
        name reached the SQL and what happened next was the database's decision.
        """
        match = re.search(r"add_fields\s*:\s*\[([^\]]*)\]", self._js())
        self.assertIsNotNone(match, "activity.js has no listview add_fields; if "
                                    "it was restructured, re-check this by hand")
        requested = re.findall(r"""['"](\w+)['"]""", match.group(1))
        self.assertNotIn("progress_percent", requested)
        self.assertIn("status", requested,
                      "the list view still needs status for its indicator")


class TestEveryDoctypeLiteralNamesADoctypeThatExists(unittest.TestCase):
    """A read naming a DocType nothing declares, which nothing else judges.

    `test_query_fields.py` walks the same calls to check their FIELD names, and
    at the point where it has the DocType in its hand it does:

        if doctype not in doctypes:
            continue

    That is the right answer to its own question -- it cannot know a frappe
    DocType's field list -- and `test_an_unknown_doctype_is_not_judged` pins it
    as correct. But the effect is that a read of a DocType that exists NOWHERE
    is skipped by the field sweep for the same reason a legitimate read of
    `User` is -- and before this rule the only DocType-name check in this app
    was the `new_doc` one, which does not see a read. So the one case where the
    DocType name itself is wrong was the one case nothing looked at.

    `frappe.get_all("Resource Role")` is that case, live in this app twice. It
    does not return nothing: `frappe.db` raises on the missing table, so the
    endpoint fails for every input -- the same symptom as the Purchase Order
    `new_doc` that the rule above exists for, reached through a read instead of
    an insert.

    This is a sweep declining to judge something and being the only thing that
    looked, which is the defect `test_raw_sql.py` was carrying when its skipped
    receivers were counted into a variable nothing printed. Refusing to be
    silent needs no new analysis: it needs somebody to own the leftovers.
    """

    def test_the_walker_found_the_doctype_sites_to_check(self):
        sites = _doctype_sites()
        self.assertGreaterEqual(
            len(sites), EXPECTED_DOCTYPE_SITES,
            "the DocType-literal walker reaches %d sites and %d were measured. "
            "If a read was deliberately removed, re-measure and change the "
            "number; a walker that quietly reaches fewer sites passes this "
            "rule by finding nothing."
            % (len(sites), EXPECTED_DOCTYPE_SITES))

    def test_no_read_names_a_doctype_nothing_declares(self):
        declared = _declared_doctypes()
        self.assertGreaterEqual(len(declared), 40,
                                "the DocType index collapsed, so this rule "
                                "would fail for the wrong reason")
        known = collections.Counter()
        failures = []
        for rel, line, callee, doctype in sorted(_doctype_sites()):
            if doctype in declared or doctype in FRAPPE_DOCTYPES:
                continue
            if doctype in KNOWN_UNDECLARED_READS:
                known[doctype] += 1
                continue
            failures.append(
                "%s:%d calls %s(%r), and neither this app nor FRAPPE_DOCTYPES "
                "declares it -- frappe raises on the missing table, so the call "
                "fails for every input. Either the name is wrong, or it is a "
                "frappe DocType and belongs in FRAPPE_DOCTYPES, or it is a real "
                "defect being left in place and belongs in "
                "KNOWN_UNDECLARED_READS with a reason."
                % (rel, line, callee, doctype))
        self.assertEqual(failures, [], "\n" + "\n".join(failures))
        self.assertEqual(
            dict(known), KNOWN_UNDECLARED_READS,
            "the reads of a DocType nothing declares are recorded as %s and are "
            "now %s. A new one is a new endpoint that cannot work; a vanished "
            "one is good news that should be taken off this list."
            % (KNOWN_UNDECLARED_READS, dict(known)))

    def test_no_module_aliases_frappe(self):
        """The blind spot, refused rather than documented.

        This sweep reads `frappe.x(...)` and `frappe.db.x(...)` and nothing
        else, so `db = frappe.db` then `db.get_all("Nope")` would pass. There
        are no such aliases in the app today. The moment there is one, this rule
        has a hole, and the person writing it is the only one who will know --
        which is exactly the shape of the `handle = frappe.db` injection that
        `test_raw_sql.py` reported as `0 findings`.

        Stated as an empty exception list rather than a prose blind spot,
        because a prose claim about what a tool covers is not a test.
        """
        self.assertEqual(
            _frappe_aliases(), [],
            "nothing in this app aliases frappe or frappe.db, and the DocType "
            "sweep above reads those two receivers by name only. An alias is "
            "not wrong, but it is invisible to the sweep: widen "
            "_receiver_and_method to follow it, then list it here.")

    def test_the_frappe_doctype_list_is_still_needed_and_still_small(self):
        """So FRAPPE_DOCTYPES cannot quietly become a way to silence the rule."""
        named = {doctype for _, _, _, doctype in _doctype_sites()}
        for doctype in FRAPPE_DOCTYPES:
            self.assertIn(
                doctype, named,
                "%s is excused but nothing in the app names it any more; take "
                "it out of FRAPPE_DOCTYPES. A list of allowed names that is "
                "larger than the set of names actually used is a blanket."
                % doctype)
        self.assertFalse(
            FRAPPE_DOCTYPES & _declared_doctypes(),
            "a name in FRAPPE_DOCTYPES is now declared by this app too, so the "
            "excuse is hiding a real check: take it out.")

    def test_resource_role_is_still_declared_by_nothing(self):
        """So the KNOWN_UNDECLARED_READS entry cannot go vacuous.

        The mirror of test_purchase_order_is_still_not_a_doctype_anywhere: if a
        Resource Role DocType is added, those two endpoints start working and
        this entry is a lie rather than a record.
        """
        self.assertNotIn("Resource Role", _declared_doctypes())
        self.assertNotIn("Resource Role", FRAPPE_DOCTYPES)


if __name__ == "__main__":
    unittest.main()
