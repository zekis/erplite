# -*- coding: utf-8 -*-
"""Guard: a DocType named in client-side JavaScript must be a DocType that exists.

The Python side of this rule is swept twice over: `test_query_fields.py` walks every
`frappe.get_all`/`get_list`/`get_value`/`count`/`exists`, `test_read_shapes.py` judges the
shape of each one against the kind of DocType, and `test_endpoint_wiring.py` pins how many
DocType-naming sites there are in `.py` and which undeclared names are known. None of them
reaches a `.js` file for this: `test_endpoint_wiring.py` walks `.js` only for the dotted
method paths behind `frappe.call`, and `test_client_scripts.py` walks `.js` only for the
FIELD half (`frm.set_value('gone', x)`), saying so in its own docstring. So the DocType half
of the browser side was judged by nobody, and that is what this file does.

WHY IT IS WORTH A TEST: TWO OF THESE SHAPES FAIL IN COMPLETE SILENCE.

Read off frappe version-15, not from memory:

  * `frappe.ui.form.on(doctype, ...)` pushes its handlers into
    `frappe.ui.form.handlers[doctype]` via `get_event_handler_list`, which CREATES the bucket
    if it is not there (`frappe/public/js/frappe/form/script_manager.js:14-22`, called from
    `:24-26`). Handlers are only ever run through `get_handlers`, which looks up
    `frappe.ui.form.handlers[doctype][event_name]` with the doctype of the form being opened
    (`:154-155`). A misspelt DocType therefore registers every handler in the file into a
    bucket nothing will ever read: no error, no warning, no console line. The form simply
    does nothing it was written to do.

  * `frappe.listview_settings[doctype]` is read as
    `this.settings = frappe.listview_settings[this.doctype] || {}`
    (`frappe/public/js/frappe/list/base_list.js:43`). A settings object registered under a
    name no list view asks for is silently replaced by `{}` -- the indicators, buttons and
    formatters are all just absent.

That is the opposite of the field half in `test_client_scripts.py`, where `frm.set_value` on
a missing field throws and puts a modal on the user's screen. A loud bug gets reported on the
first click. These two do not, which is exactly why a static rule has to carry them.

The other four shapes (`frappe.set_route('Form'|'List', X)`, `frappe.db.*` reads, a
`doctype:` key in a `frappe.call` args object, `frappe.new_doc`) surface at runtime when the
code path is exercised -- loudly, but only then, and only for whoever exercises it.

WHAT IS MEASURED, as of 6 Oct 2026 (every count below came from a sweep of the tree, and is
asserted as a floor so that a site cannot leave the sweep's reach without a word being said):

    form.on       22      set_route     16      doctype: key  18
    listview       6      frappe.db.*    6      new_doc        0
    Link options   7      desk URL       8                 ----
                                                       total  83

Those eight shapes are not all asserted together, and the two totals below are not in conflict:
83 is every site in the table, while EXPECTED_TOTAL is 75 -- the seven shapes collected into
SITES. Desk URLs are the eighth, swept separately into DESK_URLS and judged by their own test
class at the foot of this file, because six of the eight live in `.vue` files that the rest of
this sweep does not read. 83 = 75 + 8, and the two are counted against different standards:
the sentence below is about the 75, because a desk URL is allowed to name a desk page
(`user-profile`) or one of frappe's own DocTypes (`todo`, `user`), and three of the eight do.

All 75 name a DocType this app declares (47 of them). Not one needs frappe's own names today,
and FRAPPE_DOCTYPES is imported from `test_endpoint_wiring.py` rather than copied, so there is
one such list in the suite and it stays where its provenance is recorded.

COMMENTS, AND WHY THIS FILE STRIPS THEM WITH A SCANNER RATHER THAN A PATTERN.

The app carries nine commented-out `frappe.ui.form.on("X", {...})` blocks -- frappe's own
`bench new-doctype` scaffold, left in place in nine DocType folders. A sweep that reads the
file as text finds 31 `form.on` sites; 22 are real. So this is not a hypothetical: judging
comments here would mean judging more scaffold than code, and `test_string_references.py`
already carries a control for the same trap on the Python side ("a dotted path that resolves
to nothing, in a Python comment"). `_strip_comments` below blanks `//` and `/* */` while
tracking `'`, `"` and backtick strings, so a `//` inside a string literal (an http:// URL,
say) does not start a comment. `test_comments_are_not_judged` proves it on synthetic source
AND asserts the nine real scaffold blocks are still there and still unjudged, so the stripper
cannot quietly stop working against the tree it was written for.

One thing the scanner deliberately does NOT do: track regular-expression literals. The first
version did, and it was measurably worse. `</div>` inside a nested template literal
(a `${x ? ... }` holding another backtick string, TimeBlockManager.js:149) desynchronises any flat string
scanner, and with a regex heuristic on top the `/` of `</div>` was taken as the start of a
regex literal, which swallowed the rest as code -- leaving three real `//` comments and two
`/* */` blocks UNSTRIPPED further down the same file. Both versions happened to agree on all
75 sites, which is the point: the broken one looked right. The per-shape floors below are
what would catch the other direction, a regex literal eating real sites.

NOT COVERED HERE, so the next reader knows where to look:

  * `.vue` and `.html` carry none of the six shapes above -- the Vue scheduler reaches the
    API through `frontend/src/components/scheduler/composables/useSchedulerAPI.js`, whose
    eight `doctype:` keys ARE judged here because that is a `.js` file. That zero is asserted
    below rather than written down here, so if the Vue app starts naming DocTypes in one of
    these shapes the rule gets extended instead of silently not applying.

    But `.vue` is NOT free of DocType references, and saying otherwise would be the
    overclaim this file exists to replace. A desk URL names a DocType by its slug, and there
    are eight: six in `.vue` (`/app/project/...`, `/app/user`) and two in `.js`
    (`/app/supplier-quote/...`, `/app/todo`). Those are judged below, by slug, which is why
    `_files` is swept for all three extensions for that one rule.
  * A DocType held in a variable (`frappe.set_route('Form', dt)`) or built by concatenation.
    Nothing static can judge those; the floors are what notice if a literal becomes one.
  * The built bundles under `erplite/public/frontend/assets` -- build output, not source.
  * Whether a Link's target is the RIGHT DocType, or whether a field exists on it. That is
    `test_doctype_metadata.py` (the JSON side) and `test_client_scripts.py` (the field side).
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from test_doctype_metadata import DOCTYPES, FIELDS, CHILD_FIELDTYPES  # noqa: E402
from test_endpoint_wiring import FRAPPE_DOCTYPES  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "dist", "assets", "__pycache__"}

# Fieldtypes whose `options` names a DocType. Dynamic Link is NOT one of them: its options
# names a FIELD on the same record that holds the DocType name, so judging it would reject
# correct code. Select, Data (Email/Phone/URL) and Icon all put other things in `options`.
DOCTYPE_OPTION_FIELDTYPES = {"Link", "Table", "Table MultiSelect"}

# Measured 6 Oct 2026 by sweeping the tree. Floors, not round numbers below the real count:
# slack in a floor is room for a site to leave the sweep unnoticed.
EXPECTED_SITES = {
    "form.on": 22,
    "listview_settings": 6,
    "set_route": 16,
    "frappe.db read": 6,
    "doctype: key": 18,
    "new_doc": 0,
    "Link options": 7,
}
EXPECTED_TOTAL = 75

# The nine commented-out scaffold blocks (see the docstring). A floor again: the point is that
# the stripper has real work to do in this tree, not that there are exactly nine.
EXPECTED_COMMENTED_FORM_ON = 9

SHAPES = {
    "form.on": re.compile(r"""frappe\.ui\.form\.on\(\s*['"]([^'"]+)['"]"""),
    "listview_settings": re.compile(
        r"""frappe\.listview_settings\[\s*['"]([^'"]+)['"]\s*\]"""),
    "set_route": re.compile(
        r"""frappe\.set_route\(\s*['"](?:Form|List)['"]\s*,\s*['"]([^'"]+)['"]"""),
    "frappe.db read": re.compile(
        r"""frappe\.db\.(?:get_value|get_list|get_doc|exists|count|insert)"""
        r"""\(\s*['"]([^'"]+)['"]"""),
    "doctype: key": re.compile(r"""[\{,\s]['"]?doctype['"]?\s*:\s*['"]([^'"]+)['"]"""),
    "new_doc": re.compile(r"""frappe\.new_doc\(\s*['"]([^'"]+)['"]"""),
}

OPTIONS = re.compile(r"""[\{,\s]options\s*:\s*['"]([^'"]+)['"]""")
FIELDTYPE = re.compile(r"""[\{,\s]fieldtype\s*:\s*['"]([^'"]+)['"]""")

_CODE, _SQ, _DQ, _TPL, _LINE, _BLOCK = range(6)


def _scan(src, blank_strings=False):
    """`src` with comments blanked out, every other byte and every newline kept in place.

    With blank_strings, string BODIES are blanked too, which leaves a skeleton whose braces
    can be matched without a `'{'` inside a string throwing the count off. Offsets are
    identical in both, so a match found in one can be located in the other.
    """
    out = list(src)
    state = _CODE
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if state == _CODE:
            if c == "/" and nxt == "/":
                out[i] = out[i + 1] = " "
                state, i = _LINE, i + 2
                continue
            if c == "/" and nxt == "*":
                out[i] = out[i + 1] = " "
                state, i = _BLOCK, i + 2
                continue
            if c == "'":
                state = _SQ
            elif c == '"':
                state = _DQ
            elif c == "`":
                state = _TPL
            i += 1
            continue
        if state == _LINE:
            if c == "\n":
                state = _CODE
            else:
                out[i] = " "
            i += 1
            continue
        if state == _BLOCK:
            if c == "*" and nxt == "/":
                out[i] = out[i + 1] = " "
                state, i = _CODE, i + 2
                continue
            if c != "\n":
                out[i] = " "
            i += 1
            continue
        # inside a string
        if c == "\\":
            if blank_strings:
                out[i] = " "
                if i + 1 < n and src[i + 1] != "\n":
                    out[i + 1] = " "
            i += 2
            continue
        if (state == _SQ and c == "'") or (state == _DQ and c == '"') \
                or (state == _TPL and c == "`"):
            state = _CODE
        elif blank_strings and c != "\n":
            out[i] = " "
        i += 1
    return "".join(out)


def _strip_comments(src):
    return _scan(src)


def _files(ext):
    out = []
    for dirpath, dirs, names in os.walk(APP_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(names):
            if name.endswith(ext):
                out.append(os.path.join(dirpath, name))
    return sorted(out)


def _enclosing_object(skeleton, index):
    """(start, end) of the innermost `{...}` around `index` in a brace-matched skeleton."""
    depth, start = 0, None
    for i in range(index, -1, -1):
        c = skeleton[i]
        if c == "}":
            depth += 1
        elif c == "{":
            if depth == 0:
                start = i
                break
            depth -= 1
    if start is None:
        return None
    depth = 0
    for i in range(start, len(skeleton)):
        c = skeleton[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
    return None


def _sites():
    """[(shape, relative path, line, DocType)] for every DocType literal in the app's .js."""
    found = []
    for path in _files(".js"):
        rel = os.path.relpath(path, APP_ROOT)
        with open(path, encoding="utf-8", errors="replace", newline="") as fh:
            raw = fh.read()
        code = _strip_comments(raw)
        skeleton = _scan(raw, blank_strings=True)
        for shape, pattern in SHAPES.items():
            for match in pattern.finditer(code):
                found.append((shape, rel, code.count("\n", 0, match.start()) + 1,
                              match.group(1)))
        for match in OPTIONS.finditer(code):
            bounds = _enclosing_object(skeleton, match.start())
            if bounds is None:
                continue
            fieldtypes = set(FIELDTYPE.findall(code[bounds[0]:bounds[1]]))
            if fieldtypes & DOCTYPE_OPTION_FIELDTYPES:
                found.append(("Link options", rel,
                              code.count("\n", 0, match.start()) + 1, match.group(1)))
    return found


SITES = _sites()
KNOWN = set(DOCTYPES) | set(FRAPPE_DOCTYPES)


def _doctype_of_folder(rel):
    """The DocType whose folder this .js file sits in, or None if it is not in one."""
    parts = rel.replace(os.sep, "/").split("/")
    if "doctype" not in parts:
        return None
    i = parts.index("doctype")
    if i + 1 >= len(parts) - 1:
        return None
    folder = parts[i + 1]
    for name, (jpath, _doc) in DOCTYPES.items():
        if os.path.basename(os.path.dirname(jpath)) == folder:
            return name
    return None


def _child_tables(doctype):
    return {f["options"] for f in FIELDS.get(doctype, {}).values()
            if f.get("fieldtype") in CHILD_FIELDTYPES and f.get("options")}


class TestEveryClientDoctypeExists(unittest.TestCase):
    """A DocType named in the browser must be one that exists somewhere."""

    def test_the_sweep_found_sites_to_judge(self):
        """An empty sweep passes every other test in this file."""
        self.assertGreaterEqual(
            len(_files(".js")), 50,
            "found almost no .js files; the walk is wrong, not the app")
        self.assertGreaterEqual(
            len(SITES), EXPECTED_TOTAL,
            "the sweep found %d DocType-naming sites, fewer than the %d measured on "
            "6 Oct 2026. A site has left its reach: a literal replaced by a variable, a "
            "shape written a way the patterns do not read, or a comment stripper eating "
            "code. Find out which before lowering this number."
            % (len(SITES), EXPECTED_TOTAL))

    def test_every_literal_names_a_doctype_that_exists(self):
        """The rule. Nothing in the browser may name a DocType that is nowhere declared."""
        bad = ["%s %s:%d names %r" % (shape, rel, line, name)
               for shape, rel, line, name in SITES if name not in KNOWN]
        self.assertEqual(
            [], sorted(bad),
            "a client script names a DocType that neither this app nor frappe declares. "
            "In a form.on or listview_settings that fails in complete silence (see this "
            "file's docstring); everywhere else it fails when the path is exercised:\n  "
            + "\n  ".join(sorted(bad)))

    def test_the_measured_site_counts_are_still_met(self):
        """Per-shape floors: what notices a site leaving the sweep's reach.

        A whole-file count cannot do this on its own. Six literals moving into variables
        while seven new ones arrive is a total that has not moved, and the per-shape counts
        are what make that visible.
        """
        counted = {shape: 0 for shape in EXPECTED_SITES}
        for shape, _rel, _line, _name in SITES:
            counted[shape] += 1
        short = ["%s: %d, was %d" % (s, counted[s], EXPECTED_SITES[s])
                 for s in sorted(EXPECTED_SITES) if counted[s] < EXPECTED_SITES[s]]
        self.assertEqual(
            [], short,
            "fewer DocType-naming sites than were measured on 6 Oct 2026:\n  "
            + "\n  ".join(short)
            + "\nSites are allowed to go, but not quietly: say why here when they do.")


class TestAFormScriptNamesItsOwnDoctype(unittest.TestCase):
    """Stronger than existence, and exact: where the file lives says what it may name.

    `erplite/<module>/doctype/<x>/*.js` is the client script for the DocType declared by
    `<x>.json` beside it. `frappe.ui.form.on` and `frappe.listview_settings` there may name
    that DocType or one of its child tables (a `Table` field's target, whose rows are edited
    in the parent's grid and whose handlers belong in the parent's script). Anything else is
    a typo that registers handlers nothing reads.
    """

    SHAPES = ("form.on", "listview_settings")

    def test_the_sweep_found_form_scripts_in_doctype_folders(self):
        inside = [s for s in SITES
                  if s[0] in self.SHAPES and _doctype_of_folder(s[1]) is not None]
        self.assertGreaterEqual(
            len(inside), 28,
            "found %d form.on/listview_settings sites inside a doctype folder, fewer than "
            "the 28 measured on 6 Oct 2026" % len(inside))

    def test_every_handler_is_registered_under_a_doctype_the_form_can_ask_for(self):
        bad = []
        for shape, rel, line, name in SITES:
            if shape not in self.SHAPES:
                continue
            owner = _doctype_of_folder(rel)
            if owner is None:
                continue
            allowed = {owner} | _child_tables(owner)
            if name not in allowed:
                bad.append("%s %s:%d registers under %r; this folder declares %r "
                           "(child tables: %s)"
                           % (shape, rel, line, name, owner,
                              ", ".join(sorted(_child_tables(owner))) or "none"))
        self.assertEqual(
            [], sorted(bad),
            "a client script registers handlers under a DocType whose form will never ask "
            "for them, so every handler in the file is dead and nothing says so:\n  "
            + "\n  ".join(sorted(bad)))


class TestTheSweepReadsCodeAndNotComments(unittest.TestCase):
    """The stripper, against synthetic source and against the tree.

    Both halves matter. The synthetic cases say what the stripper is for; the count against
    the real tree says it is still doing it. A stripper that quietly stopped stripping would
    pass the first half of this class on its own.
    """

    def _names(self, source, shape="form.on"):
        return SHAPES[shape].findall(_strip_comments(source))

    def test_a_line_comment_is_not_code(self):
        self.assertEqual([], self._names('// frappe.ui.form.on("Nowhere", {});\n'))

    def test_a_trailing_comment_is_not_code(self):
        self.assertEqual(
            ["Real"],
            self._names('frappe.ui.form.on("Real", {});  '
                        '// frappe.ui.form.on("Nowhere", {});\n'))

    def test_a_block_comment_is_not_code(self):
        self.assertEqual(
            [], self._names('/*\n * frappe.ui.form.on("Nowhere", {});\n */\n'))

    def test_code_after_a_block_comment_is_still_code(self):
        self.assertEqual(
            ["Real"],
            self._names('/* frappe.ui.form.on("Nowhere", {}); */\n'
                        'frappe.ui.form.on("Real", {});\n'))

    def test_two_slashes_inside_a_string_do_not_start_a_comment(self):
        """The trap that makes a naive stripper eat real code: a URL in a string."""
        self.assertEqual(
            ["Real"],
            self._names('const u = "http://example.test/x";\n'
                        'frappe.ui.form.on("Real", {});\n'))

    def test_a_comment_marker_inside_a_template_literal_is_not_a_comment(self):
        self.assertEqual(
            ["Real"],
            self._names('const h = `<a href="//x">${y}</a>`;\n'
                        'frappe.ui.form.on("Real", {});\n'))

    def test_line_numbers_survive_stripping(self):
        """Offsets are kept so a reported line number is the line in the file."""
        source = ('// one\n/* two\n   three */\nfrappe.ui.form.on("Real", {});\n')
        stripped = _strip_comments(source)
        self.assertEqual(len(source), len(stripped))
        self.assertEqual(4, stripped.count("\n", 0, stripped.index("frappe.ui.form.on")) + 1)

    def test_the_apps_commented_out_scaffold_is_still_there_and_still_unjudged(self):
        """Nine `// frappe.ui.form.on(...)` scaffold blocks: real, and not judged.

        If the stripper ever stops working, the 31 sites in the raw text get judged. Nine of
        them name DocTypes that do exist, so `test_every_literal_names_a_doctype_that_exists`
        would stay green and only this test would notice.
        """
        raw_total = judged_total = 0
        for path in _files(".js"):
            with open(path, encoding="utf-8", errors="replace", newline="") as fh:
                raw = fh.read()
            raw_total += len(SHAPES["form.on"].findall(raw))
            judged_total += len(SHAPES["form.on"].findall(_strip_comments(raw)))
        commented = raw_total - judged_total
        self.assertGreaterEqual(
            commented, EXPECTED_COMMENTED_FORM_ON,
            "the tree had %d commented-out form.on blocks and now has %d. If they were "
            "deleted, lower the number here and say so; if the stripper stopped stripping, "
            "fix the stripper." % (EXPECTED_COMMENTED_FORM_ON, commented))
        self.assertEqual(
            EXPECTED_SITES["form.on"],
            len([s for s in SITES if s[0] == "form.on"]),
            "the judged form.on count moved; the raw text has %d" % raw_total)


class TestOptionsIsJudgedOnlyWhereItNamesADoctype(unittest.TestCase):
    """`options` is a DocType on a Link or Table field and something else everywhere else.

    This is the half of the rule that could reject correct code, so the controls are the
    point of the class. On a Select it is a list of values; on Data it is Email/Phone/URL; on
    a Dynamic Link it is the FIELDNAME holding the DocType, not a DocType at all.
    """

    def _judged(self, source):
        code = _strip_comments(source)
        skeleton = _scan(source, blank_strings=True)
        out = []
        for match in OPTIONS.finditer(code):
            bounds = _enclosing_object(skeleton, match.start())
            if bounds is None:
                continue
            if set(FIELDTYPE.findall(code[bounds[0]:bounds[1]])) & DOCTYPE_OPTION_FIELDTYPES:
                out.append(match.group(1))
        return out

    def test_a_link_fields_options_is_judged(self):
        self.assertEqual(
            ["Project"],
            self._judged("{ fieldtype: 'Link', fieldname: 'p', options: 'Project' }"))

    def test_a_selects_options_are_not_judged(self):
        self.assertEqual(
            [], self._judged("{ fieldtype: 'Select', fieldname: 's', "
                             "options: 'Draft\\nSubmitted' }"))

    def test_a_data_fields_options_is_not_judged(self):
        self.assertEqual(
            [], self._judged("{ fieldtype: 'Data', fieldname: 'e', options: 'Email' }"))

    def test_a_dynamic_links_options_is_not_judged(self):
        """It names a field on the record, so judging it would reject correct code."""
        self.assertEqual(
            [], self._judged("{ fieldtype: 'Dynamic Link', fieldname: 'd', "
                             "options: 'reference_type' }"))

    def test_the_nearest_object_decides_not_the_nearest_fieldtype(self):
        """Two field objects in one array: the Select must not borrow the Link's fieldtype."""
        self.assertEqual(
            ["Project"],
            self._judged("fields: [\n"
                         "  { fieldtype: 'Link', fieldname: 'p', options: 'Project' },\n"
                         "  { fieldtype: 'Select', fieldname: 's', options: 'Yes' }\n"
                         "]"))

    def test_a_brace_inside_a_string_does_not_break_the_object_bounds(self):
        self.assertEqual(
            ["Project"],
            self._judged("{ fieldtype: 'Link', description: 'use {0} here', "
                         "options: 'Project' }"))

    def test_the_apps_own_link_options_are_all_judged_and_all_declared(self):
        judged = [s for s in SITES if s[0] == "Link options"]
        self.assertEqual(
            EXPECTED_SITES["Link options"], len(judged),
            "the app had %d Link `options` sites in .js and now has %d"
            % (EXPECTED_SITES["Link options"], len(judged)))
        self.assertEqual([], [s for s in judged if s[3] not in KNOWN])


# A desk URL names a DocType by its slug: frappe's router lowercases the name and joins its
# words with hyphens, so `/app/supplier-quote/SQ-0001` opens a Supplier Quote. A slug that
# names nothing gives the user a "Not found" desk page.
#
# `/app/<x>` is not always a DocType, though, and that is the half that could reject correct
# code: frappe serves desk PAGES on the same prefix. The app links to one, `/app/user-profile`.
# So the rule flags a slug that is neither a known DocType nor a page named here, and
# `test_every_listed_desk_page_is_still_linked_to` keeps this list from growing into a blanket.
DESK_PAGES = {"user-profile"}

DESK_URL = re.compile(r"""/app/([a-z0-9][a-z0-9-]*)""")

EXPECTED_DESK_URLS = 8


def _slug(doctype):
    return doctype.lower().replace(" ", "-")


def _desk_urls():
    """[(relative path, line, slug)] for every /app/<slug> in the front end."""
    found = []
    for ext in (".js", ".vue", ".html"):
        for path in _files(ext):
            with open(path, encoding="utf-8", errors="replace", newline="") as fh:
                code = _strip_comments(fh.read())
            for match in DESK_URL.finditer(code):
                found.append((os.path.relpath(path, APP_ROOT),
                              code.count("\n", 0, match.start()) + 1, match.group(1)))
    return found


DESK_URLS = _desk_urls()
KNOWN_SLUGS = {_slug(name) for name in KNOWN}


class TestADeskUrlNamesADoctypeOrAPageWeHaveNamed(unittest.TestCase):
    """The shape that is a DocType reference without looking like one.

    This is the one found by asking what the six patterns above do NOT see, rather than by
    imagining another typo: six of these eight sites are in `.vue` files, which the rest of
    this file does not judge at all.
    """

    def test_the_sweep_found_desk_urls(self):
        self.assertGreaterEqual(
            len(DESK_URLS), EXPECTED_DESK_URLS,
            "found %d /app/ URLs, fewer than the %d measured on 6 Oct 2026"
            % (len(DESK_URLS), EXPECTED_DESK_URLS))

    def test_every_desk_url_resolves(self):
        bad = ["%s:%d opens /app/%s" % (rel, line, slug)
               for rel, line, slug in DESK_URLS
               if slug not in KNOWN_SLUGS and slug not in DESK_PAGES]
        self.assertEqual(
            [], sorted(bad),
            "a link opens a desk route whose slug is neither a DocType this app or frappe "
            "declares nor a desk page named in DESK_PAGES. If it is a page rather than a "
            "DocType, add it there and say so:\n  " + "\n  ".join(sorted(bad)))

    def test_every_listed_desk_page_is_still_linked_to(self):
        """An allowlist longer than the links that need it is a blanket, not an exception."""
        linked = {slug for _rel, _line, slug in DESK_URLS}
        self.assertEqual(
            set(), DESK_PAGES - linked,
            "DESK_PAGES names a desk page nothing links to any more: %s. Remove it, so the "
            "list stays the size of the problem." % sorted(DESK_PAGES - linked))


class TestTheBlindSpotsAreStillBlind(unittest.TestCase):
    """What this rule does not reach, asserted rather than written down.

    `.vue` and `.html` carry none of the SIX SHAPES above today, which is why that half of
    the sweep is `.js` only. They do carry desk URLs, which the class above judges. This is a
    measurement, and a measurement that is only in a docstring is one nobody re-takes: if the
    Vue app starts naming DocTypes in one of these shapes, this goes red and the rule gets
    extended rather than silently not applying to a growing part of the front end.
    """

    def test_no_doctype_literal_has_appeared_in_a_vue_or_html_file(self):
        found = []
        for ext in (".vue", ".html"):
            for path in _files(ext):
                with open(path, encoding="utf-8", errors="replace", newline="") as fh:
                    code = _strip_comments(fh.read())
                for shape, pattern in SHAPES.items():
                    for match in pattern.finditer(code):
                        found.append("%s %s names %r"
                                     % (shape, os.path.relpath(path, APP_ROOT),
                                        match.group(1)))
        self.assertEqual(
            [], sorted(found),
            "a DocType literal has appeared outside .js, where this file's sweep does not "
            "look. Extend _files() to this extension and re-measure the floors:\n  "
            + "\n  ".join(sorted(found)))

    def test_the_vue_app_was_actually_swept(self):
        self.assertGreaterEqual(
            len(_files(".vue")), 20,
            "found %d .vue files; the walk is wrong, not the app" % len(_files(".vue")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
