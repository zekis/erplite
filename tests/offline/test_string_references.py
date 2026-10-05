# -*- coding: utf-8 -*-
"""Whole-app guards on the app's *string* references: asset URLs and dotted method paths.

The other sweeps in this folder all answer one question -- does this code name a field its
DocType declares? This file answers a different one: **does this string name something that
exists at all?** Frappe resolves a lot of wiring by string at request time, so a name that is
wrong is not a syntax error and not a failed import. It is a working app with a dead button.

Three surfaces, and as with the field sweeps each has its own symptom:

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

Both of the last two reach the user as a modal error dialog, so this class fails loudly.

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

Comments are stripped before anything is matched. That is not a detail: the first draft of this
sweep reported 26 missing methods, and 24 of them were Frappe's own commented-out boilerplate in
`hooks.py`. A sweep that cannot tell code from a comment is a sweep that gets ignored.

KNOWN BLIND SPOTS, stated so they are places to look rather than places to stop:

  * Pass C (argument names) is applied only to readable sources, not to the minified bundles
    under `public/frontend/assets/`, and only to the two call forms that can be read exactly:
    `frappe.call({method: "...", args: {...}})` and `call("...", {...})` with a literal object.
    Anything else is skipped rather than guessed at. Pass B *does* cover the bundles, because
    the bundle is what is deployed -- that is how the transposed name above was found.
  * A method path assembled at runtime from a variable is invisible to all three passes.
  * Pass A only resolves `/assets/<app>/...`; a reference to another app's assets is skipped.
"""

import ast
import json
import os
import re
import tokenize
import unittest
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


def python_surface():
    """-> (module_level, class_methods) dotted-path maps.

    `module_level[path] = (rel, lineno, whitelisted, argnames, accepts_kwargs, required)`
    where `required` is the parameters with no default. frappe.call supplies arguments by
    keyword only, so an unsent required parameter is a TypeError and an unsent optional one
    is simply its default.
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
                positional = [a.arg for a in node.args.args]
                args = positional + [a.arg for a in node.args.kwonlyargs]
                ndefaults = len(node.args.defaults)
                # A slice of 0 defaults is the whole list, so this needs no special case.
                required = positional[: len(positional) - ndefaults]
                required += [
                    a.arg
                    for a, default in zip(node.args.kwonlyargs, node.args.kw_defaults)
                    if default is None
                ]
                module_level.setdefault(
                    mod + "." + node.name,
                    (
                        rel,
                        node.lineno,
                        whitelisted,
                        args,
                        node.args.kwarg is not None,
                        required,
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
    for root_exts in (FRONTEND_EXTS, {".py"}):
        for path, rel in _walk(MODULE_ROOT, root_exts):
            frontend = os.path.splitext(rel)[1] in FRONTEND_EXTS
            text = _read(path) if _is_bundle(rel) else live_source(path, rel)
            for lineno, line in enumerate(text.splitlines(), 1):
                for match in DOTTED.finditer(line):
                    name = match.group(1)
                    # A dotted path needs at least module + attribute.
                    if name.count(".") < 1:
                        continue
                    found.setdefault(name, []).append((rel, lineno, frontend))
    # Also sweep the un-built Vue source, which lives outside the module root.
    frontend_src = os.path.join(APP_ROOT, "frontend", "src")
    if os.path.isdir(frontend_src):
        for path, rel in _walk(frontend_src, {".js", ".vue"}):
            text = live_source(path, rel)
            for lineno, line in enumerate(text.splitlines(), 1):
                for match in DOTTED.finditer(line):
                    found.setdefault(match.group(1), []).append((rel, lineno, True))
    return found


ARGS_OBJECT = re.compile(
    r"""method\s*:\s*["'`](%s\.[\w.]+)["'`]\s*,\s*args\s*:\s*\{(?P<body>[^{}]*)\}""" % APP,
    re.S,
)
CALL_POSITIONAL = re.compile(
    r"""\bcall\s*\(\s*["'`](%s\.[\w.]+)["'`]\s*,\s*\{(?P<body>[^{}]*)\}""" % APP, re.S
)
KEY = re.compile(r"""(?:^|,)\s*(?:["'`]?)([A-Za-z_]\w*)(?:["'`]?)\s*:""")


def kwarg_call_sites():
    """-> [(path, rel, set(kwargs))] for the two call forms that can be read exactly."""
    sites = []
    roots = [(MODULE_ROOT, FRONTEND_EXTS)]
    frontend_src = os.path.join(APP_ROOT, "frontend", "src")
    if os.path.isdir(frontend_src):
        roots.append((frontend_src, {".js", ".vue"}))
    for root, exts in roots:
        for path, rel in _walk(root, exts):
            if _is_bundle(rel):
                continue  # minified: not readable exactly, documented above
            text = live_source(path, rel)
            for pattern in (ARGS_OBJECT, CALL_POSITIONAL):
                for match in pattern.finditer(text):
                    body = match.group("body")
                    keys = set(KEY.findall(body))
                    # An empty body is readable, and means what it says: this call sends
                    # nothing. Record it, so a function with a required parameter is still
                    # flagged. A body with text in it but no key KEY can read is NOT
                    # readable (a spread, a variable), so it stays skipped: flagging it
                    # would report every required parameter as missing.
                    if keys or not body.strip():
                        sites.append((match.group(1), rel, keys))
    return sites


class AssetReferencesResolve(unittest.TestCase):
    """Pass A: every /assets/<app>/... in live code is a file the app ships."""

    def test_every_asset_reference_exists(self):
        exts = {".py", ".js", ".vue", ".html", ".css", ".json"}
        pattern = re.compile(r"/assets/%s/([A-Za-z0-9/._-]+)" % APP)
        bad = []
        for path, rel in _walk(MODULE_ROOT, exts):
            if _is_bundle(rel):
                continue
            text = live_source(path, rel)
            for lineno, line in enumerate(text.splitlines(), 1):
                for match in pattern.finditer(line):
                    ref = match.group(1)
                    if ref.endswith("/"):
                        continue
                    # sites/assets/<app> is a symlink to <app>/<app>/public
                    target = os.path.join(MODULE_ROOT, "public", ref)
                    if not os.path.exists(target):
                        bad.append("%s:%d -> /assets/%s/%s" % (rel, lineno, APP, ref))
        self.assertEqual(
            [],
            sorted(set(bad)),
            "Asset reference(s) in live code point at a file the app does not ship. "
            "sites/assets/%s symlinks to %s/public, so these 404 on the live site, once for "
            "the <link>/<script> tag and again for the rel=preload header." % (APP, APP),
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
            rel, line, whitelisted, _args, _kw, _req = module_level[name]
            if whitelisted:
                continue
            frontend = [(f, l) for f, l, is_fe in sorted(set(sites[name])) if is_fe]
            if not frontend:
                continue  # a hooks.py target is resolved server-side; no whitelist needed
            bad.append(
                "%s (defined %s:%d) is called from %s but has no @frappe.whitelist()"
                % (name, rel, line, ", ".join("%s:%d" % fl for fl in frontend))
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
      * `{item_name: ...}` sent to `get_supplier_quotes_for_comparison(item_name, project)`
        -- the same `TypeError`, for `project`. No name here is wrong; the fault is an
        argument that was never sent at all. **Nothing covered this until now**, and it is
        the only shape that reliably raises.
      * `{proj: ...}` where the parameter it was meant to fill **has a default** -- returns
        normally, with the default in place. The value the caller sent is discarded in
        silence: no exception, nothing in the Error Log, and a wrong answer on the screen.
        The quietest of the three, and the reason the unknown-name test below stays.

    So the two tests below are halves of one check, and the loud half is the second one.

    BLIND SPOTS: positional-only parameters and `*args` can never be filled by `frappe.call`,
    which passes by keyword only. The app has none of either (measured: 0 of 114 module-level
    functions), so neither is handled here rather than guessed at. Both tests inherit the
    readable-call-form limits documented at the top of this file. An `args` object that is
    literally empty IS covered; one whose contents cannot be read exactly is skipped, and a
    call with no `args` key at all is not matched by either pattern.
    """

    def test_called_arguments_are_accepted(self):
        module_level, _ = python_surface()
        bad = []
        for name, rel, keys in kwarg_call_sites():
            if name not in module_level:
                continue  # pass B owns that
            _f, _l, _wl, args, accepts_kwargs, _req = module_level[name]
            if accepts_kwargs:
                continue
            unknown = sorted(k for k in keys if k not in args)
            if unknown:
                bad.append(
                    "%s called from %s with argument(s) %s; it accepts %s"
                    % (name, rel, ", ".join(unknown), ", ".join(args) or "(none)")
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
            where, line, _wl, _args, _kw, required = module_level[name]
            missing = sorted(a for a in required if a not in keys)
            if missing:
                bad.append(
                    "%s (defined %s:%d) is called from %s without %s; it requires %s"
                    % (name, where, line, rel, ", ".join(missing), ", ".join(required))
                )
        self.assertEqual(
            [],
            sorted(set(bad)),
            "frappe.call passes form_dict by keyword, so a required parameter the caller "
            "never sends raises TypeError server-side -- a modal error dialog for the user.",
        )


if __name__ == "__main__":
    unittest.main()
