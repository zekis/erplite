# -*- coding: utf-8 -*-
"""Whole-app guards on the app's *string* references: asset URLs and dotted method paths.

The other sweeps in this folder all answer one question -- does this code name a field its
DocType declares? This file answers a different one: **does this string name something that
exists at all?** Frappe resolves a lot of wiring by string at request time, so a name that is
wrong is not a syntax error and not a failed import. It is a working app with a dead button.

Four surfaces, and as with the field sweeps each has its own symptom:

  * `app_include_css` / `app_include_js` in `hooks.py` pointing at a file that is not shipped.
    `frappe/www/app.py:48` collects them, `app.html:25` renders each through
    `jinja_globals.include_style`, and `bundled_asset` passes a path that starts with `/assets`
    and has no `.bundle.` in it straight through to `abs_url`. So the desk emits
    `<link rel="stylesheet" href="...">` for a file that is not there, and because
    `include_style` defaults to `preload=True` the path is *also* added to
    `frappe.local.preload_assets["style"]`, which `frappe/website/utils.py:586` turns into an
    HTTP `Link: ...; rel=preload; as=style` header. **Two 404s on every desk page load, for
    every user.** No exception, nothing in the Error Log -- the mildest symptom of any surface
    swept so far and by far the widest blast radius. `sites/assets/<app>` is a symlink to
    `<app>/<app>/public` (`frappe/build.py`), so a file missing from the repo is missing on the
    live site too; it is not a build-staleness question.

  * A dotted method path that does not resolve. `frappe.handler.execute_cmd` does
    `method = get_attr(cmd)` and, on any exception, `frappe.throw(_("Failed to get method for
    command {0} with {1}"))`. `frappe.get_attr` is
    `getattr(get_module(modulename), methodname)` -- so the name must exist **at module level**.
    A perfectly good *class* method is not reachable this way, which is a trap worth naming
    because the code looks right.

  * A path that resolves but is not whitelisted. `execute_cmd` then calls `is_whitelisted`,
    which raises `frappe.PermissionError` titled "Method Not Allowed".

  * A patch entry in `patches.txt` that does not resolve. `execute_patch`
    (`frappe/modules/patch_handler.py:157`) does `get_attr(f"{entry.split()[0]}.execute")`
    before it runs anything and lets the exception out, so **`bench migrate` stops** --
    part-way through the patch run, with the entries before it already committed. The worst
    symptom of the four: the other three are a broken page, this one is a failed deploy.
    This surface was added when the fault-injection target for this file was written: pass B
    swept `.py`, `.js`, `.vue` and `.html`, and `patches.txt` is none of those, so the one
    patch this app ships was resolved by nothing at all.

The middle two reach the user as a modal error dialog, so that class fails loudly.

What this found when it was written (5 Oct 2026):

  * `app_include_css = "/assets/erplite/css/timesheet-calendar.css"` -- commit 8126278 deleted
    the whole timesheet-calendar feature (its CSS, its JS and its `www/` page) and left the
    global include behind, so every desk page had been requesting a deleted stylesheet twice.
  * `erplite.scheduler.api.create_bulk_schedule_entries`, called by the **deployed** Vue
    scheduler bundle, does not exist -- `bulk_create_entries` does. The words are transposed.
    And the argument name differs too (`entries` vs `entries_data`), so fixing only the name
    would have moved the failure from "Failed to get method" to a missing-argument `TypeError`.
  * `erplite...schedule_entry.update_activity_progress`, called whenever a Schedule Entry's
    status changes, has never existed in any commit.
  * `erplite...schedule_row.extend_entries` is a class method with no module-level wrapper, so
    the "Extend" dialog on Schedule Row could never have worked.

What the fault-injection target for this file found (6 Oct 2026), which is why it has four
passes and eight tests rather than three and five: ten regressions that the five original
tests did not notice. Five of them were patch entries, because `patches.txt` was swept by
nothing; the others were a missing asset referenced from the un-built Vue source (swept by
pass B, not by pass A), an asset path naming a directory, a wrong argument in a call that
writes `args` before `method`, a wrong argument in a call whose `args` holds a nested
object, and a positional-only parameter. None of them is exotic; all five of the patch ones
are a typo in a text file.

Comments are stripped before anything is matched. That is not a detail: the first draft of this
sweep reported 26 missing methods, and 24 of them were Frappe's own commented-out boilerplate in
`hooks.py`. A sweep that cannot tell code from a comment is a sweep that gets ignored.

KNOWN BLIND SPOTS, stated so they are places to look rather than places to stop. Each one
below is a fault in `tests/faultinject/faults.py` marked KNOWN BLIND SPOT, so it is a thing
that has been run and watched stay green, not a thing that is believed:

  * A method path assembled at runtime -- from a variable, or a template literal with an
    interpolation in it -- is invisible to every pass. There is no string to read.
  * Pass C reads the two call forms whose arguments can be read exactly:
    `frappe.call({method: "...", args: {...}})` in either key order, with nested objects
    inside `args` allowed, and `call("...", {...})`. An `args` object holding a spread
    (`...rest`), an ES2015 shorthand property (`{docname}`) or a computed key is **skipped
    whole**. Reading it partly would mean reporting the entries it could not see as
    arguments the caller never sends, which is a false missing-required-argument finding
    against correct code.
  * Pass A only resolves `/assets/<app>/...`; a reference to another app's assets is skipped.
  * A dotted path inside a `.json` file is not swept. Frappe resolves a method path out of
    some DocType *records* (a Dashboard Chart's `method`, a Notification, a Server Script),
    and this app ships none of them -- only DocType definitions and fixtures, measured. The
    knowledge of which JSON field in which doctype is a method path lives in frappe, not
    here, so guessing at it would be the confidently-wrong kind of sweep.
  * **The minified bundle is not in the repository.** `erplite/public/frontend/` is
    gitignored (commit b95a358, "Ignore generated frontend build output"), so `BUNDLE_DIRS`
    matches nothing in any checkout and `_is_bundle` never fires. The handling is kept
    because it is correct where a bundle exists -- a built bench, the live site -- but
    offline, both the strength and the weakness it describes are empty. This file used to
    claim the opposite: that pass B "does cover the bundles, because the bundle is what is
    deployed -- that is how the transposed name above was found". The finding was real; the
    attribution was not, and a sentence about coverage that the tree cannot provide is worse
    than no sentence, because it reads as a reason to stop looking.
"""

import ast
import configparser
import json
import os
import re
import tokenize
import unittest
from collections import namedtuple
from io import StringIO

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
APP = "erplite"
MODULE_ROOT = os.path.join(APP_ROOT, APP)

# Built output: deployed, but minified. Readable-source passes skip it; pass B does not.
BUNDLE_DIRS = (os.path.join("public", "frontend", "assets"),)
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv"}


def _walk(root, exts):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if os.path.splitext(name)[1] in exts:
                full = os.path.join(dirpath, name)
                yield full, os.path.relpath(full, APP_ROOT).replace(os.sep, "/")


def _is_bundle(rel):
    return any(d.replace(os.sep, "/") in rel for d in BUNDLE_DIRS)


def source_roots():
    """Every tree this app's own source lives in.

    There are two: the installed module, and the un-built Vue source beside it.
    This is one function rather than a line in each pass **because it was a
    line in each pass, and one of them was missing `frontend/src`** -- so an
    asset reference written in the Vue source was swept by pass B and invisible
    to pass A, in a file whose two passes look symmetric. Anything added here
    is seen by every pass at once.
    """
    roots = [MODULE_ROOT]
    frontend_src = os.path.join(APP_ROOT, "frontend", "src")
    if os.path.isdir(frontend_src):
        roots.append(frontend_src)
    return roots


def walk_sources(exts):
    for root in source_roots():
        for path, rel in _walk(root, exts):
            yield path, rel


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


# --------------------------------------------------------------------------- #
# Comment stripping.  Newlines are preserved so line numbers stay true.
# --------------------------------------------------------------------------- #


def strip_python_comments(source):
    """Blank out `#` comments using the real tokenizer, not a regex.

    A regex cannot tell `# a comment` from `"#hash-in-a-string"`.
    """
    try:
        tokens = list(tokenize.generate_tokens(StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return source
    lines = source.splitlines(keepends=True)
    for tok in tokens:
        if tok.type != tokenize.COMMENT:
            continue
        row = tok.start[0] - 1
        if 0 <= row < len(lines):
            line = lines[row]
            keep = line[: tok.start[1]]
            lines[row] = keep + "\n" if line.endswith("\n") else keep
    return "".join(lines)


def strip_js_comments(source):
    """Blank out `//` and `/* */` comments, honouring string and template literals.

    A naive `//` strip would eat the rest of any line containing `https://`, which is most of
    the interesting ones.
    """
    out = []
    i, n = 0, len(source)
    quote = None
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(nxt)
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'`":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            while i < n and not (source[i] == "*" and i + 1 < n and source[i + 1] == "/"):
                if source[i] == "\n":
                    out.append("\n")
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def strip_html_comments(source):
    def blank(match):
        return "\n" * match.group(0).count("\n")

    return re.sub(r"<!--.*?-->", blank, source, flags=re.S)


def live_source(path, rel):
    """File contents with comments removed, chosen by extension."""
    text = _read(path)
    ext = os.path.splitext(rel)[1]
    if ext == ".py":
        return strip_python_comments(text)
    if ext in (".js", ".vue"):
        return strip_js_comments(text)
    if ext == ".html":
        # .html here is a Jinja/Frappe template: both comment styles can appear.
        return strip_js_comments(strip_html_comments(text))
    return text


# --------------------------------------------------------------------------- #
# The app's own Python surface: what exists, at module level, and whitelisted?
# --------------------------------------------------------------------------- #


def _module_name(rel):
    mod = rel[:-3].replace("/", ".")
    if mod.endswith(".__init__"):
        mod = mod[: -len(".__init__")]
    return mod


Func = namedtuple(
    "Func", "rel lineno whitelisted args accepts_kwargs required posonly_required"
)


def _signature(node):
    """The part of a signature `frappe.call` can reach, and the part it cannot.

    `frappe.call` passes `form_dict` **by keyword only** (`frappe/__init__.py:1765` ->
    `get_newargs` at `:1778`), which splits a signature in three:

      * `args` -- the names a caller may send: the ordinary positional parameters plus the
        keyword-only ones. Anything else sent is dropped by `get_newargs`.
      * `required` -- those of them with no default. An unsent one is a `TypeError`
        server-side; an unsent optional one is simply its default.
      * `posonly_required` -- parameters before a `/` that have no default. These can
        **never** be filled, so the function is not callable by `frappe.call` at all:
        Python answers a keyword for a positional-only parameter with `TypeError: f() got
        some positional-only arguments passed as keyword arguments`. A positional-only
        parameter that *has* a default is harmless (it keeps the default), so it is not
        reported.

    Reading `posonlyargs` matters for the arithmetic as well as for the new finding.
    `node.args.defaults` covers `posonlyargs + args` as one right-aligned list, so a
    signature with a `/` in it made `len(positional) - ndefaults` the wrong subtraction --
    `def f(a="1", /, b="2", c="3")` was reported as requiring `b`, which has a default.
    Measured, not reasoned: the app has no positional-only parameter today
    (`test_no_front_end_call_reaches_a_positional_only_parameter` is what keeps that a
    measurement rather than a sentence) and no `*args` either -- a `*args` is unfillable
    too, but harmlessly, because it is never required.
    """
    posonly = [a.arg for a in node.args.posonlyargs]
    positional = [a.arg for a in node.args.args]
    kwonly = [a.arg for a in node.args.kwonlyargs]
    ndefaults = len(node.args.defaults)
    filled = posonly + positional
    # A slice of 0 defaults is the whole list, so this needs no special case.
    no_default = filled[: len(filled) - ndefaults] if ndefaults <= len(filled) else []
    required = no_default[len(posonly):]
    required += [
        a.arg
        for a, default in zip(node.args.kwonlyargs, node.args.kw_defaults)
        if default is None
    ]
    return positional + kwonly, required, no_default[: len(posonly)]


def python_surface():
    """-> (module_level, class_methods) dotted-path maps.

    `module_level[path]` is a `Func`; see `_signature` for what each field means and why
    the positional-only ones are kept apart.
    `class_methods[path] = (rel, lineno, classname)` -- recorded *separately*, because
    `frappe.get_attr` does `getattr(module, name)` and so cannot reach them. An earlier draft
    used `ast.walk`, which descends into classes, and mis-reported an unreachable class method
    as "exists but is not whitelisted" -- a much milder and quite wrong diagnosis.
    """
    module_level, class_methods = {}, {}
    for path, rel in _walk(MODULE_ROOT, {".py"}):
        try:
            tree = ast.parse(_read(path))
        except SyntaxError:
            continue
        mod = _module_name(rel)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                whitelisted = any(
                    "whitelist" in ast.unparse(dec) for dec in node.decorator_list
                )
                args, required, posonly_required = _signature(node)
                module_level.setdefault(
                    mod + "." + node.name,
                    Func(
                        rel,
                        node.lineno,
                        whitelisted,
                        args,
                        node.args.kwarg is not None,
                        required,
                        posonly_required,
                    ),
                )
            elif isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        class_methods.setdefault(
                            mod + "." + sub.name, (rel, sub.lineno, node.name)
                        )
    return module_level, class_methods


# --------------------------------------------------------------------------- #
# Call sites
# --------------------------------------------------------------------------- #

DOTTED = re.compile(r"""["'`](%s\.[A-Za-z_][\w.]*)["'`]""" % APP)
FRONTEND_EXTS = {".js", ".vue", ".html"}


def method_call_sites():
    """-> {dotted path: [(rel, lineno, from_frontend)]}"""
    found = {}
    for path, rel in walk_sources(FRONTEND_EXTS | {".py"}):
        frontend = os.path.splitext(rel)[1] in FRONTEND_EXTS
        text = _read(path) if _is_bundle(rel) else live_source(path, rel)
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in DOTTED.finditer(line):
                name = match.group(1)
                # A dotted path needs at least module + attribute.
                if name.count(".") < 1:
                    continue
                found.setdefault(name, []).append((rel, lineno, frontend))
    return found


CALL_POSITIONAL = re.compile(r"""\bcall\s*\(\s*["'`](%s\.[\w.]+)["'`]\s*,\s*""" % APP)
METHOD_STRING = re.compile(r"""^["'`](%s\.[\w.]+)["'`]$""" % APP)
ENTRY_KEY = re.compile(r"""(?:(["'`])([A-Za-z_]\w*)\1|([A-Za-z_]\w*))\s*:""")


def _balanced_object(text, start):
    """The `{...}` beginning at `start`, or None if there is none or it never closes.

    Strings (including template literals) and nested braces are skipped -- the same
    string-aware scan `strip_js_comments` above already does. That is what makes this exact
    rather than a guess.
    """
    if start >= len(text) or text[start] != "{":
        return None
    depth, i, quote = 0, start, None
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'`":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    return None


def _own_entries(obj):
    """-> {key: value text} for an object literal's **own** entries, or None.

    None means "this object cannot be read exactly", and it is returned for the whole object
    as soon as one entry has a key this cannot read: a spread (`...rest`), an ES2015
    shorthand property (`{docname}`), a computed key (`[k]:`). All-or-nothing on purpose. A
    partly-read object would report the entries it could not see as arguments the caller
    never sends -- a false missing-required-argument finding against correct code, and a
    sweep that argues with correct code gets switched off.

    Nested objects, arrays and function bodies are skipped over rather than descended into,
    so `{role: x, filters: {enabled: 1}}` reads as two keys. The pattern this replaces
    matched an args object with `[^{}]*`, so **any** nested object -- a `filters`, which is
    the ordinary shape of a frappe.call -- made the whole call unreadable and silently
    unchecked.
    """
    body = obj[1:-1]
    entries, i, n = {}, 0, len(body)
    while i < n:
        while i < n and (body[i].isspace() or body[i] == ","):
            i += 1
        if i >= n:
            break
        match = ENTRY_KEY.match(body, i)
        if not match:
            return None
        key = match.group(2) or match.group(3)
        i = match.end()
        start, depth, quote = i, 0, None
        while i < n:
            ch = body[i]
            if quote:
                if ch == "\\":
                    i += 2
                    continue
                if ch == quote:
                    quote = None
            elif ch in "\"'`":
                quote = ch
            elif ch in "{[(":
                depth += 1
            elif ch in "}])":
                depth -= 1
            elif ch == "," and depth == 0:
                break
            i += 1
        if depth != 0:
            return None  # unbalanced: read nothing rather than read it wrong
        entries[key] = body[start:i].strip()
    return entries


def _entries_of_object_value(value):
    """`_own_entries` for a value that must itself be a whole object literal."""
    value = (value or "").strip()
    obj = _balanced_object(value, 0)
    if obj is None or obj != value:
        return None  # a variable, a call, a spread: not readable
    return _own_entries(obj)


def kwarg_call_sites():
    """-> [(dotted path, rel, set(kwargs))] for every frappe.call that can be read exactly.

    Two call forms: the object form, `frappe.call({method: "...", args: {...}})`, and the
    positional one, `call("...", {...})`.

    The object form is found by parsing the object, not by a regex that spelled out `method`
    then `args` in that order. **Order is not meaning** -- `args` before `method` is the same
    call to frappe -- and the pattern this replaces silently skipped every call written the
    other way round. Two keys have exactly two orders, so this is not a wider net; it is the
    same net, cast at the object rather than at a character sequence.

    An `args` object that is literally empty IS covered, and means what it says: the call
    sends nothing, so a function with a required parameter is still flagged. An `args` whose
    value is a variable, or whose entries cannot all be read, is skipped -- and listed under
    KNOWN BLIND SPOTS rather than left implied.
    """
    sites = []
    for path, rel in walk_sources(FRONTEND_EXTS):
        if _is_bundle(rel):
            continue  # minified: not readable exactly, documented above
        text = live_source(path, rel)

        for index, char in enumerate(text):
            if char != "{":
                continue
            obj = _balanced_object(text, index)
            if obj is None:
                continue
            entries = _own_entries(obj)
            if entries is None or "method" not in entries or "args" not in entries:
                continue
            match = METHOD_STRING.match(entries["method"])
            if not match:
                continue
            args = _entries_of_object_value(entries["args"])
            if args is not None:
                sites.append((match.group(1), rel, set(args)))

        for match in CALL_POSITIONAL.finditer(text):
            obj = _balanced_object(text, match.end())
            if obj is None:
                continue
            args = _own_entries(obj)
            if args is not None:
                sites.append((match.group(1), rel, set(args)))
    return sites


ASSET_REF_EXTS = {".py", ".js", ".vue", ".html", ".css", ".json"}
ASSET_REF = re.compile(r"/assets/%s/([A-Za-z0-9/._-]+)" % APP)


class AssetReferencesResolve(unittest.TestCase):
    """Pass A: every /assets/<app>/... in live code is a file the app ships."""

    def test_every_asset_reference_exists(self):
        bad = []
        for path, rel in walk_sources(ASSET_REF_EXTS):
            if _is_bundle(rel):
                continue
            text = live_source(path, rel)
            for lineno, line in enumerate(text.splitlines(), 1):
                for match in ASSET_REF.finditer(line):
                    ref = match.group(1)
                    if ref.endswith("/"):
                        continue
                    # sites/assets/<app> is a symlink to <app>/<app>/public
                    target = os.path.join(MODULE_ROOT, "public", ref)
                    where = "%s:%d -> /assets/%s/%s" % (rel, lineno, APP, ref)
                    # isfile, not exists: a directory exists happily and is not a thing
                    # the web server will serve. The symptom is the same 404.
                    if os.path.isdir(target):
                        bad.append(where + " -- that is a directory, not a file")
                    elif not os.path.isfile(target):
                        bad.append(where)
        self.assertEqual(
            [],
            sorted(set(bad)),
            "Asset reference(s) in live code point at something the app does not ship as a "
            "file. sites/assets/%s symlinks to %s/public, so these 404 on the live site, "
            "once for the <link>/<script> tag and again for the rel=preload header."
            % (APP, APP),
        )


# --------------------------------------------------------------------------- #
# patches.txt: the dotted paths `bench migrate` resolves, before it does anything.
# --------------------------------------------------------------------------- #


def patch_entries():
    """-> [(section, lineno, entry)] for every patch frappe would run.

    Parsed the way frappe parses it (`frappe/modules/patch_handler.py:166`,
    `parse_as_configfile`): a `ConfigParser` with `allow_no_value=True` because a patch is
    not a key/value pair, `delimiters="\n"` so a `:` inside an `execute:` line is not read
    as one, and `optionxform=str` so case is kept. `#` comments are dropped by configparser,
    which is the same rule the rest of this file applies to code.

    Both sections are read because both are run: `migrate` runs `pre_model_sync` before the
    DocTypes are synced and `post_model_sync` after, and `get_all_patches` with no patch
    type returns the two concatenated.

    The line number is recovered from the raw text, because configparser does not keep it
    and a finding that cannot be navigated to is half a finding.
    """
    path = os.path.join(MODULE_ROOT, "patches.txt")
    if not os.path.exists(path):
        return []
    parser = configparser.ConfigParser(allow_no_value=True, delimiters="\n")
    parser.optionxform = str
    parser.read(path)
    lines = _read(path).splitlines()
    found = []
    for section in parser.sections():
        for entry in parser[section]:
            lineno = next(
                (i for i, line in enumerate(lines, 1) if line.strip() == entry.strip()), 0
            )
            found.append((section, lineno, entry))
    return found


def patch_module_paths():
    """-> [(section, lineno, entry, the dotted path frappe will resolve)].

    `execute_patch` (`patch_handler.py:157`) does

        patch = f"{patchmodule.split(maxsplit=1)[0]}.execute"
        _patch = frappe.get_attr(patch)

    before it runs anything, and `migrate` lets the exception out. So what must exist is a
    module-level `execute` in the module named by the entry's **first whitespace-delimited
    token** -- frappe's own patches.txt writes a date after that token, and the date is not
    part of the path.

    Two entry forms are not paths and are not resolved:

      * `execute:...` -- frappe `exec()`s the rest of the line as Python
        (`patch_handler.py:161-163`). There is no path here to check.
      * a `finally:` prefix only defers the run to the end, so it is stripped. (v15's
        `execute_patch` resolves the prefixed string *before* it checks for the prefix, so
        such an entry would fail there first; stripping it is what the entry means, and this
        file reports on the app rather than on frappe.)

    Another app's patches are skipped: resolving them would need that app's source.
    """
    paths = []
    for section, lineno, entry in patch_entries():
        if entry.startswith("execute:"):
            continue
        name = entry[len("finally:"):] if entry.startswith("finally:") else entry
        token = name.split(maxsplit=1)[0] if name.split() else ""
        if not token.startswith(APP + "."):
            continue
        paths.append((section, lineno, entry, token + ".execute"))
    return paths


class PatchPathsResolve(unittest.TestCase):
    """Pass B2: every patch in patches.txt resolves to a module-level execute().

    The same bug class as pass B -- a string that names nothing -- on the surface with the
    worst symptom of the four. A dead button is a dead button; a dead patch entry raises
    inside `bench migrate`, which means **the deploy stops**, after the pre-model patches
    before it have already run and committed. It is also the surface a person is most likely
    to get wrong by hand, because the entry is typed into a text file with no import to
    check it and no editor that can follow it.

    This pass did not exist until the fault-injection target for this file was written. Pass
    B swept `.py`, `.js`, `.vue` and `.html`; `patches.txt` is none of those, so the one
    patch this app ships was never resolved by anything. Five separate faults in it -- a
    misspelt module, a module with no `execute`, a renamed `execute`, a path one element
    short, a misspelt module carrying frappe's usual trailing date -- were all invisible.
    """

    def test_every_patch_resolves_to_a_module_level_execute(self):
        module_level, class_methods = python_surface()
        bad = []
        for section, lineno, entry, dotted in patch_module_paths():
            if dotted in module_level:
                continue
            where = "patches.txt:%d [%s] %r" % (lineno, section, entry)
            if dotted in class_methods:
                rel, line, cls = class_methods[dotted]
                bad.append(
                    "%s -- %s exists only as a method of class %s (%s:%d), which "
                    "frappe.get_attr cannot reach" % (where, dotted, cls, rel, line)
                )
            else:
                bad.append("%s -- no %s anywhere" % (where, dotted))
        self.assertEqual(
            [],
            bad,
            "Patch entr(ies) in patches.txt do not resolve. frappe.modules.patch_handler."
            "execute_patch does get_attr('<entry>.execute') and lets the exception out, so "
            "`bench migrate` stops -- the deploy fails, part-way through the patch run.",
        )

    def test_the_patch_entries_this_app_ships_are_the_ones_expected(self):
        """What the test above is actually chewing on.

        A sweep over an empty set is green, and a deleted entry would make the test above
        vacuously green while quietly dropping a migration the live database needs. So the
        entries are named here. Adding a patch means adding it here too, which is the point:
        this is the line that makes someone look.
        """
        self.assertEqual(
            ["erplite.patches.declare_todo_status_options.execute"],
            [dotted for _s, _l, _e, dotted in patch_module_paths()],
            "The set of patches this app ships has changed. If you added one, add it here "
            "as well; if one vanished, the live database may be expecting it.",
        )


class DottedMethodPathsResolve(unittest.TestCase):
    """Pass B: every erplite.* dotted path resolves to a module-level function."""

    def test_every_called_method_exists_at_module_level(self):
        module_level, class_methods = python_surface()
        sites = method_call_sites()
        bad = []
        for name in sorted(sites):
            if name in module_level:
                continue
            where = ", ".join(
                "%s:%d" % (rel, line) for rel, line, _ in sorted(set(sites[name]))
            )
            if name in class_methods:
                rel, line, cls = class_methods[name]
                bad.append(
                    "%s -- exists only as a method of class %s (%s:%d), which "
                    "frappe.get_attr cannot reach; called from %s"
                    % (name, cls, rel, line, where)
                )
            else:
                bad.append("%s -- no such function anywhere; called from %s" % (name, where))
        self.assertEqual(
            [],
            bad,
            "Dotted method path(s) do not resolve. frappe.handler.execute_cmd does "
            "get_attr(cmd) and throws 'Failed to get method for command ...' -- a modal error "
            "dialog for the user.",
        )

    def test_every_method_called_from_the_front_end_is_whitelisted(self):
        module_level, _ = python_surface()
        sites = method_call_sites()
        bad = []
        for name in sorted(sites):
            if name not in module_level:
                continue  # the test above owns that case
            func = module_level[name]
            if func.whitelisted:
                continue
            frontend = [(f, l) for f, l, is_fe in sorted(set(sites[name])) if is_fe]
            if not frontend:
                continue  # a hooks.py target is resolved server-side; no whitelist needed
            bad.append(
                "%s (defined %s:%d) is called from %s but has no @frappe.whitelist()"
                % (name, func.rel, func.lineno,
                   ", ".join("%s:%d" % fl for fl in frontend))
            )
        self.assertEqual(
            [],
            bad,
            "frappe.is_whitelisted raises PermissionError ('Method Not Allowed') for these.",
        )


class CallArgumentsMatchSignatures(unittest.TestCase):
    """Pass C: the arguments a readable call passes line up with the signature, both ways.

    This is the pass that matters once pass B is green: renaming a method to the one that
    exists is not enough if the argument names do not match. But what goes wrong is not what
    this pass claimed when it was written.

    What frappe actually does, read off `frappe/handler.py:86` -> `frappe.call`
    (`frappe/__init__.py:1719`) -> `get_newargs` (`:1729`, "Remove any kwargs that are not
    supported by the function"), then confirmed by lifting that function out of the v15.52.0
    source and running it against these real signatures:

      * `{doc_name: ...}` sent to `send_to_xero(docname)` -- the unknown name is **dropped**,
        and the call then raises `TypeError: send_to_xero() missing 1 required positional
        argument: docname`. It is **not** an unexpected-keyword error, which is what this
        pass used to say in its failure message.
      * A required parameter the caller never sends -- the same `TypeError`, and the only
        shape that reliably raises without any name being wrong. The live instance is a
        parameter *added* to an endpoint whose callers were not updated:
        `bulk_create_entries(entries_data)` gaining a second required parameter is a fault
        in `tests/faultinject/faults.py`, and it goes red.
      * `{proj: ...}` where the parameter it was meant to fill **has a default** -- returns
        normally, with the default in place. The value the caller sent is discarded in
        silence: no exception, nothing in the Error Log, and a wrong answer on the screen.
        The quietest of the three, and the reason the unknown-name test below stays.

    This paragraph used to name `get_supplier_quotes_for_comparison(item_name, project)` as
    its second example. **That signature has never existed in this repository** -- it has
    been `(item_name=None, project=None)` since the file was created in 98e9b04 -- so
    against the real one, `{item_name: ...}` runs to completion with `project` as `None`.
    Checked by running frappe's own `get_newargs` against both. The general claim was right
    and the example was invented, which is the more dangerous way for a docstring to be
    wrong: it reads as evidence, in a paragraph that says it was measured.

    So the two tests below are halves of one check, and the loud half is the second one.

    BLIND SPOTS: `*args` can never be filled by `frappe.call`, which passes by keyword only,
    and is harmlessly unfillable: it is never required. A positional-only parameter is not
    harmless, and `test_no_called_function_has_a_positional_only_parameter` below owns it.
    Both tests here inherit the readable-call-form limits documented at the top of this
    file. An `args` object that is literally empty IS covered; one whose entries cannot all
    be read exactly is skipped; a call with no `args` key at all is not matched.
    """

    def test_called_arguments_are_accepted(self):
        module_level, _ = python_surface()
        bad = []
        for name, rel, keys in kwarg_call_sites():
            if name not in module_level:
                continue  # pass B owns that
            func = module_level[name]
            if func.accepts_kwargs:
                continue
            unknown = sorted(k for k in keys if k not in func.args)
            if unknown:
                bad.append(
                    "%s called from %s with argument(s) %s; it accepts %s"
                    % (name, rel, ", ".join(unknown), ", ".join(func.args) or "(none)")
                )
        self.assertEqual(
            [],
            sorted(set(bad)),
            "frappe.get_newargs drops an argument the function does not declare, so this is "
            "not an unexpected-keyword TypeError. If the parameter it was meant to fill has a "
            "default, the function runs silently with that default and the sent value is "
            "lost. If it has no default, the failure arrives as the missing-required-argument "
            "TypeError that test_required_arguments_are_passed owns.",
        )

    def test_required_arguments_are_passed(self):
        """Every parameter without a default is one the caller actually sends.

        This is the half that raises. See the class docstring for the three outcomes and
        where each was verified in the frappe source.
        """
        module_level, _ = python_surface()
        bad = []
        for name, rel, keys in kwarg_call_sites():
            if name not in module_level:
                continue  # pass B owns that
            func = module_level[name]
            missing = sorted(a for a in func.required if a not in keys)
            if missing:
                bad.append(
                    "%s (defined %s:%d) is called from %s without %s; it requires %s"
                    % (name, func.rel, func.lineno, rel, ", ".join(missing),
                       ", ".join(func.required))
                )
        self.assertEqual(
            [],
            sorted(set(bad)),
            "frappe.call passes form_dict by keyword, so a required parameter the caller "
            "never sends raises TypeError server-side -- a modal error dialog for the user.",
        )

    def test_no_called_function_has_a_positional_only_parameter(self):
        """A positional-only parameter with no default cannot be filled by frappe.call.

        `frappe.call` passes `form_dict` **by keyword** (`frappe/__init__.py:1765`), and
        Python answers a keyword given for a positional-only parameter with
        `TypeError: f() got some positional-only arguments passed as keyword arguments: 'a'`
        -- lifted out of the v15.52.0 source and run, not reasoned about. So a `/` in the
        signature of a method called by string is not a style question: the method stops
        being callable at all, from every caller, on every call. One of the loudest
        regressions in this file and the cheapest to write by accident.

        Only parameters before the `/` that have **no default** are reported. A
        positional-only parameter that has one is harmless: nothing can fill it, and
        nothing needs to. `*args` is in the same harmless class -- unfillable, never
        required -- and is not reported either.

        This is the test that keeps a measurement from decaying into a sentence. The file
        used to say positional-only parameters "can never be filled by frappe.call. The app
        has none of either (measured: 0 of 114 module-level functions), so neither is
        handled here rather than guessed at." The reasoning was sound and the arithmetic
        underneath it was not: `node.args.defaults` is right-aligned over
        `posonlyargs + args` together, so once a `/` appeared, `required` was computed off
        the wrong list -- `def f(a="1", /, b="2", c="3")` was reported as requiring `b`,
        which has a default. The measurement is now asserted and the signature is read in
        full, so both the blind spot and the false positive are closed by the same change.
        """
        module_level, _ = python_surface()
        sites = method_call_sites()
        bad = []
        for name in sorted(sites):
            if name not in module_level:
                continue  # the resolution test owns that
            func = module_level[name]
            if not func.posonly_required:
                continue
            bad.append(
                "%s (defined %s:%d) takes %s before a `/`, so frappe.call can never fill "
                "%s; called from %s"
                % (name, func.rel, func.lineno, ", ".join(func.posonly_required),
                   "them" if len(func.posonly_required) > 1 else "it",
                   ", ".join("%s:%d" % (rel, line)
                             for rel, line, _fe in sorted(set(sites[name]))))
            )
        self.assertEqual(
            [],
            bad,
            "frappe.call passes arguments by keyword only, and Python refuses a keyword for "
            "a positional-only parameter. These endpoints cannot be called by name at all.",
        )


if __name__ == "__main__":
    unittest.main()
