# -*- coding: utf-8 -*-
"""Guard: a server method named in an `/api/method/` URL must exist and be whitelisted.

`test_string_references.py` already judges every dotted method path the app writes -- but
only where the dotted path is the WHOLE quoted string (`DOTTED` at :361 anchors on the
opening quote), which is the shape `frappe.call({method: "..."})` uses.
`test_endpoint_wiring.py` judges the same shape through `CALL_METHOD` (:75), and walks
`erplite/` only. A method named inside a URL -- `fetch('/api/method/erplite.x.y')` -- is
neither: the string starts with `/api/method/`, so the anchored pattern cannot match it,
and three of the sites are under `frontend/`, which `test_endpoint_wiring.py` never walks.
So this shape was judged by nobody, and that is what this file does.

Four of its sites name a module that was deleted a year ago. See `UNRESOLVED` below.

WHAT FRAPPE DOES WITH THE URL, read off frappe version-15 rather than from memory:

  * `/api/method/<path:method>` is a werkzeug rule (`frappe/api/v1.py:145`) bound to
    `handle_rpc_call`, which puts the path in `frappe.form_dict.cmd` and calls
    `frappe.handler.handle()` (`:34-41`). That reaches `execute_cmd`, which resolves the
    path with `get_attr` and, on any failure, throws *Failed to get method for command
    {0} with {1}* (`frappe/handler.py:74-77`) -- a ValidationError, so HTTP 417 with a JSON
    body. It then calls `is_whitelisted(method)` (`:83`), which raises PermissionError
    ("Method Not Allowed") for a function with no `@frappe.whitelist()`.

  * So the failure is loud at the HTTP layer and **silent in the page** wherever the
    caller reads the response rather than its status. `Scheduler.vue:308-320` is exactly
    that: `fetch`, then `if (data.message && data.message.success)`. A 417 body parses as
    JSON perfectly well and has no `message`, so the condition is false, the list stays
    empty, the `catch` never fires (there was no network error) and nothing is logged. A
    user sees a scheduler with no tasks in it.

  * `/api/resource/<doctype>` is the sibling rule (`:146-151`) and names a DocType rather
    than a method. The app has none today; it is judged here anyway so that the first one
    written is judged, and `test_the_resource_sweep_finds_a_url_put_in_front_of_it` is
    what keeps that rule from passing by finding nothing.

  * **The version segment is optional, and v2 spells the same things differently.** v1's
    rule table is mounted at BOTH `/api` and `/api/v1` (`frappe/api/__init__.py:78-84`),
    so `/api/v1/method/x` is the same endpoint as `/api/method/x`; v2 adds
    `/api/v2/method/x`, renames `resource` to `document`, and adds
    `/api/v2/doctype/<doctype>/meta` and `/count` (`frappe/api/v2.py:192-217`). All of
    those are swept. The app writes only the unversioned form today, so this is a shape
    that would otherwise arrive unjudged rather than a count that can regress -- which is
    why the two self-tests below assert it on synthetic source instead.

WHAT IS SWEPT, and the one composed shape that is followed rather than skipped.

Seven URL literals in the app's own source (`walk_sources`: the installed module plus the
un-built Vue source), and one in the frontend's README. Six of the seven name a method
outright. The seventh is a base URL:

    this.baseUrl = '/api/method/erplite.www.todo.index';     TodoDataManager.js:7
    const url = `${this.baseUrl}.${method}`;                 TodoDataManager.js:289

A sweep that only reads whole method paths sees a module there and stops, and the five
methods the todo board actually calls go unjudged. So this file follows the composition
instead, and derives every part of it from the source rather than naming `makeRequest` in
a constant: the template literal gives the base variable and the interpolated parameter,
the enclosing method definition gives the method's name and is required to *declare that
parameter*, and the literals passed to `this.<that method>(...)` are then judged against
the base module. `test_the_composed_sweep_follows_a_base_url_renamed_end_to_end` proves
the derivation by renaming all four parts at once in synthetic source.

Restricting the final step to `this.<name>(` rather than any call to `<name>(` is what
makes it exact here: a sweep for bare identifier literals after `(` or `,` in that file
returns the five method names AND `getAttribute('content')` at :322, a DOM attribute. One
false positive in six is the direction that costs somebody a day.

NOT COVERED HERE, so the next reader knows where to look:

  * A method path built from pieces that are not literals, or composed in a shape other
    than the one above -- `'/api/method/' + name`, or a base joined with `+` rather than
    interpolated. The counts below are what notice if a literal becomes one.
  * The method half of `/api/v2/method/<doctype>/<method>` (`frappe/api/v2.py:202`): that
    is a method on the document, which `frappe.get_attr` never resolves, so nothing here
    can judge it. The DocType half IS judged. The app writes none of these today.
  * Whether the arguments sent match the signature, and whether a called function has a
    positional-only parameter. Both are `test_string_references.py`
    (`test_called_arguments_are_accepted`, `test_required_arguments_are_passed`).
  * Methods belonging to frappe rather than to this app -- `/api/method/logout` is the
    only one, named in `FRAPPE_METHODS` with where it is defined, and
    `test_every_frappe_method_named_here_is_still_called` keeps that list from growing
    into a blanket.
  * The built bundle under `erplite/public/frontend/assets`: gitignored, not in the tree.
"""

import os
import re
import sys
import unittest
from urllib.parse import unquote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_doctype_metadata import DOCTYPES  # noqa: E402
from test_endpoint_wiring import FRAPPE_DOCTYPES  # noqa: E402
from test_string_references import (  # noqa: E402
    APP,
    APP_ROOT,
    SKIP_DIRS,
    live_source,
    python_surface,
    strip_js_comments,
    walk_sources,
)

CODE_EXTS = {".py", ".js", ".vue", ".html"}

# frappe's own whitelisted methods this app's front end calls by URL. Each is recorded with
# where it is defined in frappe version-15, so the excuse carries its provenance rather than
# being "it looked like frappe's".
FRAPPE_METHODS = {
    "logout": "frappe/handler.py:logout, @frappe.whitelist(allow_guest=True)",
}

# Measured 6 Oct 2026, and a defect rather than a gap. `erplite/vue_test/api.py` is not in
# the tree: it was removed in the repository's first commit (8126278, 214 lines deleted; it
# was last present in 42cd436, "example vue"). Three live call sites in the Vue app still
# name it -- Home.vue's `testAPI`, and Scheduler.vue's `loadTasks` and `addTask`, which are
# the `/` and `/scheduler` routes of the app served at `/erplite` (frontend/src/router.js) --
# and the frontend README still tells a developer to call one of them.
#
# They are listed here, with their sites, so that the rule below is green on a tree that
# still has the defect and red the moment a fifth site appears. Fixing one means deleting
# its line here: `test_the_unresolved_methods_are_still_exactly_these` requires every entry
# to still be findable, so the list can only shrink.
UNRESOLVED = {
    ("erplite.vue_test.api.test_connection", "frontend/src/pages/Home.vue"),
    ("erplite.vue_test.api.get_tasks", "frontend/src/pages/Scheduler.vue"),
    ("erplite.vue_test.api.create_task", "frontend/src/pages/Scheduler.vue"),
    ("erplite.vue_test.api.get_tasks", "frontend/README.md"),
}

# Floors, not round numbers below the real count: slack in a floor is room for a site to
# leave the sweep unnoticed. Measured 6 Oct 2026.
EXPECTED_URL_METHODS = 7          # literal /api/method/ URLs in the app's own source
EXPECTED_COMPOSED_METHODS = 5     # methods reached through the one base URL
EXPECTED_DOC_METHODS = 1          # /api/method/erplite.* named in the app's documentation

# Every URL frappe routes to a method or a DocType, off its own rule tables. v1's rules are
# mounted at both `/api/...` and `/api/v1/...` (frappe/api/__init__.py:78-84), so the version
# segment is optional; v2 renamed `resource` to `document` and added `doctype/<x>/meta`.
URL_METHOD = re.compile(
    r"""/api/(?:v[12]/)?method/([A-Za-z_][\w.]*(?:/[A-Za-z_]\w*)?)""")
URL_DOCTYPE = re.compile(
    r"""/api/(?:(?:v1/)?resource|v2/document|v2/doctype)/([A-Za-z][A-Za-z0-9%+_ -]*)""")

# `${this.baseUrl}.${method}` -- the base variable and the interpolated parameter.
COMPOSE = re.compile(r"""\$\{(?:this\.)?([A-Za-z_]\w*)\}\s*\.\s*\$\{(?:this\.)?([A-Za-z_]\w*)\}""")
# `this.baseUrl = '/api/method/erplite.www.todo.index'`
BASE_ASSIGN = r"""(?:this\.)?%s\s*=\s*['"`]/api/method/(%s[\w.]*)['"`]"""
# The nearest enclosing method definition, e.g. `async makeRequest(method, params = {}) {`
METHOD_DEF = re.compile(r"""(?:async\s+)?([A-Za-z_]\w*)\s*\(([^()]*)\)\s*\{""")


def _sources():
    """(rel, comment-stripped text) for every file of the app's own source."""
    for path, rel in walk_sources(CODE_EXTS):
        yield rel, live_source(path, rel)


def _docs():
    """(rel, text) for every markdown file in the repository."""
    for dirpath, dirnames, filenames in os.walk(APP_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not name.endswith(".md"):
                continue
            full = os.path.join(dirpath, name)
            with open(full, encoding="utf-8", errors="replace") as handle:
                yield os.path.relpath(full, APP_ROOT).replace(os.sep, "/"), handle.read()


def _url_methods(pairs):
    """[(dotted path, rel, line)] for every /api/method/ URL in `pairs`."""
    found = []
    for rel, text in pairs:
        for match in URL_METHOD.finditer(text):
            found.append((match.group(1), rel, text.count("\n", 0, match.start()) + 1))
    return found


def _resource_doctypes(pairs):
    """[(DocType, rel, line)] for every DocType-naming API URL in `pairs`."""
    found = []
    for rel, text in pairs:
        for match in URL_DOCTYPE.finditer(text):
            found.append((unquote(match.group(1).replace("+", " ")).strip(), rel,
                          text.count("\n", 0, match.start()) + 1))
    return found


def _is_module(dotted):
    """Does this dotted path name a module in the tree, rather than something in one?"""
    return os.path.isfile(os.path.join(APP_ROOT, *dotted.split(".")) + ".py")


def _composed(rel, text):
    """[(dotted path, rel, line)] for methods reached through a base URL in `text`.

    Every part is read out of the source: the template literal names the base variable and
    the parameter interpolated after it, the enclosing definition names the method and must
    declare that parameter, and the literals passed to `this.<method>(` are the call sites.
    """
    found = []
    for compose in COMPOSE.finditer(text):
        base_var, param = compose.group(1), compose.group(2)
        base = re.search(BASE_ASSIGN % (re.escape(base_var), re.escape(APP + ".")), text)
        if not base:
            continue
        definitions = list(METHOD_DEF.finditer(text, 0, compose.start()))
        if not definitions:
            continue
        name, parameters = definitions[-1].group(1), definitions[-1].group(2)
        if param not in re.findall(r"[A-Za-z_]\w*", parameters):
            continue
        call = re.compile(r"""this\.%s\(\s*['"]([^'"]+)['"]""" % re.escape(name))
        for match in call.finditer(text):
            found.append((base.group(1) + "." + match.group(1), rel,
                          text.count("\n", 0, match.start()) + 1))
    return found


def _all_composed(pairs):
    found = []
    for rel, text in pairs:
        found.extend(_composed(rel, text))
    return found


def _why_unresolved(dotted, module_level, class_methods):
    """None if the path resolves to a whitelisted module-level function; else why not."""
    if dotted in module_level:
        if not module_level[dotted].whitelisted:
            func = module_level[dotted]
            return ("%s:%d has no @frappe.whitelist(), so frappe.handler.is_whitelisted "
                    "raises PermissionError" % (func.rel, func.lineno))
        return None
    if dotted in class_methods:
        rel, lineno, classname = class_methods[dotted]
        return ("%s:%d defines it on class %s, which frappe.get_attr cannot reach "
                "(it does getattr(module, name))" % (rel, lineno, classname))
    module, _, function = dotted.rpartition(".")
    if not _is_module(module):
        return "there is no module %s.py" % module.replace(".", "/")
    return "%s.py defines no %s() at module level" % (module.replace(".", "/"), function)


class TestEveryMethodNamedInAUrlResolves(unittest.TestCase):
    """A method named in a URL fails at request time, and often invisibly in the page.

    `execute_cmd` throws for a path it cannot resolve and raises PermissionError for one
    that is not whitelisted (frappe/handler.py:74-83). Either way the response is JSON
    with no `message`, so a caller that tests the body rather than the status -- which is
    what this app's Vue pages do -- shows an empty screen and logs nothing.
    """

    def test_the_sweep_found_urls_to_judge(self):
        found = _url_methods(_sources())
        self.assertGreaterEqual(
            len(found), EXPECTED_URL_METHODS,
            "the /api/method/ sweep found %d URLs, fewer than the %d measured on 6 Oct "
            "2026, so the rules below would pass by finding nothing. Either a call was "
            "deleted (lower this floor and say so) or the sweep has stopped reaching a "
            "file." % (len(found), EXPECTED_URL_METHODS))

    def test_the_composed_sweep_still_follows_the_base_url(self):
        found = _all_composed(_sources())
        self.assertGreaterEqual(
            len(found), EXPECTED_COMPOSED_METHODS,
            "the base-URL sweep found %d composed methods, fewer than the %d measured. "
            "TodoDataManager.js builds its URLs from a base and a method name; if that "
            "shape has changed, follow the new one rather than lowering this."
            % (len(found), EXPECTED_COMPOSED_METHODS))

    def test_every_method_named_in_a_url_exists_and_is_whitelisted(self):
        module_level, class_methods = python_surface()
        failures = []
        for dotted, rel, line in sorted(set(_url_methods(_sources()))
                                        | set(_all_composed(_sources()))):
            if "/" in dotted:
                continue  # a v2 doc-method; its DocType half is judged by the rule below
            if "." not in dotted:
                self.assertIn(
                    dotted, FRAPPE_METHODS,
                    "%s:%d calls /api/method/%s, which is not one of this app's methods "
                    "and is not named in FRAPPE_METHODS" % (rel, line, dotted))
                continue
            if not dotted.startswith(APP + "."):
                continue
            if _is_module(dotted):
                continue  # a base URL; its methods are judged through _composed
            if (dotted, rel) in UNRESOLVED:
                continue
            why = _why_unresolved(dotted, module_level, class_methods)
            if why:
                failures.append("%s:%d calls /api/method/%s but %s" % (rel, line, dotted, why))
        self.assertEqual(
            [], failures,
            "\n".join(["a URL names a server method that cannot be called:"] + failures))

    def test_every_base_url_is_followed_rather_than_skipped(self):
        """A base URL is only allowed to be skipped above because it IS judged below."""
        composed = {rel for _dotted, rel, _line in _all_composed(_sources())}
        for dotted, rel, line in _url_methods(_sources()):
            if dotted.startswith(APP + ".") and _is_module(dotted):
                self.assertIn(
                    rel, composed,
                    "%s:%d names the module %s in an /api/method/ URL, so it is building "
                    "a method path from pieces -- but no composed call was found in that "
                    "file, which means the methods it calls are judged by nobody. Follow "
                    "the shape it uses (see _composed)." % (rel, line, dotted))


class TestTheRecordedDefectCanOnlyShrink(unittest.TestCase):
    """`UNRESOLVED` excuses four sites. It has to stay exactly the set that needs excusing.

    An allowlist larger than the set of things actually using it is a blanket, and that is
    how an exception list becomes a way of silencing the rule it belongs to.
    """

    def _sites(self):
        sites = {(dotted, rel) for dotted, rel, _line in
                 _url_methods(_sources()) + _all_composed(_sources())}
        sites |= {(dotted, rel) for dotted, rel, _line in _url_methods(_docs())}
        return sites

    def test_the_unresolved_methods_are_still_exactly_these(self):
        present = {entry for entry in self._sites() if entry in UNRESOLVED}
        self.assertEqual(
            UNRESOLVED, present,
            "UNRESOLVED names a site that is no longer there: %s. If the call has been "
            "fixed or deleted, delete its line from UNRESOLVED -- that is this test's "
            "whole job." % sorted(UNRESOLVED - present))

    def test_every_unresolved_method_really_does_not_resolve(self):
        module_level, class_methods = python_surface()
        for dotted, rel in sorted(UNRESOLVED):
            self.assertIsNotNone(
                _why_unresolved(dotted, module_level, class_methods),
                "%s (named at %s) resolves and is whitelisted now, so it is not a defect "
                "any more: delete its line from UNRESOLVED." % (dotted, rel))

    def test_every_frappe_method_named_here_is_still_called(self):
        called = {dotted for dotted, _rel, _line in _url_methods(_sources())}
        for name in sorted(FRAPPE_METHODS):
            self.assertIn(
                name, called,
                "FRAPPE_METHODS excuses %s but no URL names it any more; delete the "
                "entry rather than leaving a standing excuse." % name)


class TestTheDocumentationNamesMethodsThatExist(unittest.TestCase):
    """A README that tells a developer to call a method that is not there costs them an hour.

    Same rule as above, applied to the app's own markdown. `VUE_FRAPPE_INTEGRATION_GUIDE.md`
    writes its examples against `your_app.`, a placeholder, so it is out of scope by the
    `erplite.` prefix rather than by an exception.
    """

    def test_the_doc_sweep_found_urls_to_judge(self):
        found = [entry for entry in _url_methods(_docs())
                 if entry[0].startswith(APP + ".")]
        self.assertGreaterEqual(
            len(found), EXPECTED_DOC_METHODS,
            "the markdown sweep found %d /api/method/erplite.* URLs, fewer than the %d "
            "measured, so the rule below would pass by finding nothing."
            % (len(found), EXPECTED_DOC_METHODS))

    def test_every_method_the_documentation_names_exists(self):
        module_level, class_methods = python_surface()
        failures = []
        for dotted, rel, line in sorted(set(_url_methods(_docs()))):
            if not dotted.startswith(APP + ".") or _is_module(dotted):
                continue
            if (dotted, rel) in UNRESOLVED:
                continue
            why = _why_unresolved(dotted, module_level, class_methods)
            if why:
                failures.append("%s:%d documents /api/method/%s but %s"
                                % (rel, line, dotted, why))
        self.assertEqual(
            [], failures,
            "\n".join(["documentation names a server method that cannot be called:"]
                      + failures))


class TestADoctypeNamedInAResourceUrlExists(unittest.TestCase):
    """`/api/resource/<doctype>` queries a table (frappe/api/v1.py:146-151).

    The app writes none today. The rule is here so that the first one is judged rather
    than arriving in a shape nobody reads, and the self-test below is what distinguishes
    "none written" from "the sweep stopped working".
    """

    def test_the_resource_sweep_finds_a_url_put_in_front_of_it(self):
        synthetic = [("synthetic.js", """
            fetch('/api/resource/Supplier%20Quote?limit_page_length=0');
            fetch("/api/resource/Activity/" + name);
            fetch(`/api/v1/resource/Timesheet+Entry`);
            fetch('/api/v2/document/Project');
            fetch('/api/v2/doctype/Trip/meta');
        """)]
        self.assertEqual(
            [("Supplier Quote", "synthetic.js", 2),
             ("Activity", "synthetic.js", 3),
             ("Timesheet Entry", "synthetic.js", 4),
             ("Project", "synthetic.js", 5),
             ("Trip", "synthetic.js", 6)],
            _resource_doctypes(synthetic))

    def test_a_v2_doc_method_url_is_split_so_its_doctype_half_is_judged(self):
        """`/api/v2/method/<doctype>/<method>` (frappe/api/v2.py:202) names a DocType and a
        controller method. The DocType half is judged with the rule above; the method half
        is a method ON the document, which `frappe.get_attr` never sees, so nothing static
        here can judge it. The app writes none of these today."""
        self.assertEqual(
            [("Activity/recalculate", "a.js", 1)],
            _url_methods([("a.js", "fetch('/api/v2/method/Activity/recalculate')")]))

    def test_the_version_segment_is_optional_in_a_method_url(self):
        for url in ("/api/method/erplite.x.y", "/api/v1/method/erplite.x.y",
                    "/api/v2/method/erplite.x.y"):
            self.assertEqual([("erplite.x.y", "a.js", 1)],
                             _url_methods([("a.js", "fetch('%s')" % url)]), url)

    def test_every_doctype_in_a_resource_url_exists(self):
        known = set(DOCTYPES) | set(FRAPPE_DOCTYPES)
        sites = list(_resource_doctypes(_sources()))
        sites += [(dotted.split("/")[0], rel, line)
                  for dotted, rel, line in _url_methods(_sources()) if "/" in dotted]
        for doctype, rel, line in sorted(sites):
            self.assertIn(
                doctype, known,
                "%s:%d queries /api/resource/%s, and no DocType of that name is declared "
                "by this app or known to be one of frappe's. frappe answers an unknown "
                "DocType with DoesNotExistError." % (rel, line, doctype))


class TestTheSweepsReadWhatFrappeWouldRead(unittest.TestCase):
    """Controls. Each one is a shape that was got wrong on the way to writing this file."""

    def test_a_method_url_in_a_comment_is_not_judged(self):
        source = "// fetch('/api/method/erplite.gone.missing');\nx();\n"
        self.assertEqual([], _url_methods([("a.js", strip_js_comments(source))]))

    def test_a_url_inside_a_template_literal_is_still_found(self):
        self.assertEqual(
            [("erplite.www.todo.index.get_todos", "a.js", 1)],
            _url_methods([("a.js", "fetch(`/api/method/erplite.www.todo.index.get_todos`)")]))

    def test_a_trailing_query_string_is_not_part_of_the_method_name(self):
        self.assertEqual(
            [("erplite.x.y", "a.js", 1)],
            _url_methods([("a.js", "fetch('/api/method/erplite.x.y?project=P-1')")]))

    def test_the_composed_sweep_follows_a_base_url_renamed_end_to_end(self):
        """Every part is derived, so renaming all four at once must change nothing."""
        source = (
            "class C {\n"
            "  constructor() {\n"
            "    this.endpoint = '/api/method/erplite.www.todo.index';\n"
            "  }\n"
            "  async send(fn, params = {}) {\n"
            "    const url = `${this.endpoint}.${fn}`;\n"
            "    return fetch(url);\n"
            "  }\n"
            "  load() { return this.send('get_todos'); }\n"
            "}\n")
        self.assertEqual(
            [("erplite.www.todo.index.get_todos", "a.js", 9)],
            _composed("a.js", source))

    def test_a_composed_call_whose_parameter_is_not_the_methods_own_is_not_followed(self):
        """The parameter check is what stops the sweep guessing which call site is which."""
        source = (
            "  constructor() { this.base = '/api/method/erplite.www.todo.index'; }\n"
            "  helper(other) {\n"
            "    const url = `${this.base}.${method}`;\n"
            "    return this.helper('not_a_method');\n"
            "  }\n")
        self.assertEqual([], _composed("a.js", source))

    def test_a_class_method_is_reported_as_unreachable_not_as_unwhitelisted(self):
        """frappe.get_attr does getattr(module, name), so it cannot reach a class method."""
        module_level, class_methods = python_surface()
        if not class_methods:
            self.skipTest("the app defines no class methods to check this against")
        dotted = sorted(class_methods)[0]
        why = _why_unresolved(dotted, module_level, class_methods)
        self.assertIsNotNone(why)
        self.assertIn("frappe.get_attr cannot reach", why)


if __name__ == "__main__":
    unittest.main()
