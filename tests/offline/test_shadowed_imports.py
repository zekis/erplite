# -*- coding: utf-8 -*-
"""Whole-app guard: a function must not shadow a module-level import it also uses.

A sixth surface for the same habit of mind as the other sweeps here, and the first one that is
about **Python's own scoping rules** rather than about Frappe's schema or its string wiring.

The rule being enforced is Python's, not Frappe's: **a name assigned anywhere in a function body
is local for the whole of that body**, from the first line, regardless of where the assignment
sits. So a function that imports a name at module level, *uses* it, and only later assigns it
raises `UnboundLocalError: cannot access local variable 'x' where it is not associated with a
value` -- even though the module-level name is perfectly fine and the code reads correctly
top-to-bottom.

Why this is worth a guard rather than a one-line fix:

  * **It compiles, it imports, and it passes a linter's name resolution.** There is no undefined
    name anywhere; the name exists at module level and it exists locally. Only the *order* is
    wrong, and only on the path that reaches the earlier use.
  * **The idiom that causes it is extremely common.** `mime_type, _ = mimetypes.guess_type(x)`,
    `value, _ = something()`, `for _ in range(n)` -- throwing a value away into `_` is normal
    Python, and in a Frappe app `_` is *also* the translation function, imported in almost every
    module as `from frappe import _`.
  * **The symptom misdirects.** In the case this was written for, the shadowed `_` sat inside a
    `try: ... except Exception as e:` that reports `str(e)` to the browser, so the user asking
    for a file with no path got `Download failed: cannot access local variable '_' where it is
    not associated with a value` instead of the intended "File path is required". The real
    message was written, translated and never reachable.

What this found when it was written (5 Oct 2026), swept across every .py file in the app:

  * `erplite/everything_search/api.py:download_file()` -- calls `_("File path is required")` at
    line 274 and assigns `mime_type, _ = mimetypes.guess_type(filename)` at line 298. **Live**:
    the only path that calls `_()` is the one that raises.
  * `erplite/everything_search/api.py:get_file_info()` -- assigns `_` the same way at line 363
    and happens never to call `_()`. **Latent**: harmless today, and a single future line using
    `_()` above the assignment turns it into the one above with no visible cause.

Exactly two functions in the app assign `_` at all, so the class is small and now bounded. Both
are fixed by naming the discarded value (`_encoding`), which is also clearer than discarding it.

Pass B is deliberately stricter than pass A: it fails on *any* shadowing of `_`, reachable or
not, because `_` is special here -- it is the translation function in every Frappe module, and
the distance between "latent" and "live" is one added line that nobody would think to check.

KNOWN BLIND SPOTS, stated so they are places to look rather than places to stop:

  * Pass A compares **line numbers**, not control flow. A use that is textually after the
    assignment but reached first at runtime (a use inside a loop body, re-entered before the
    assignment on a later iteration) is not flagged. Line order is sound for the "definitely
    unbound on first reach" case, which is what pass A claims; it is not a proof of safety.
  * A name bound by a parameter, a `global`/`nonlocal` declaration, a `for` target, a `with ...
    as`, an `except ... as` or a walrus is handled, but a name bound only by `exec`/`locals()`
    tricks is invisible -- as it is to the interpreter's own analysis.
  * Only module-level `import`/`from ... import` names are considered. A name shadowing a
    module-level *assignment* (a constant) has the same failure, and is not swept here because
    the app has none; the pass would extend to it by collecting module-level Assign targets.
  * Nested functions are swept as their own scope, which is correct, but a nested function that
    shadows a name from the *enclosing function* rather than from module level is not covered.
  * A nested `def _()` or `class _` inside a function also binds that name locally, and the name
    binding itself is skipped along with the nested scope, so that (absurd but legal) spelling of
    the same bug is not flagged. Only assignments, loop targets, `with`/`except ... as` and
    walrus bindings are.
"""

import ast
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MODULE_ROOT = os.path.join(APP_ROOT, "erplite")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "frontend"}


def _python_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                path = os.path.join(dirpath, fn)
                yield path, os.path.relpath(path, APP_ROOT).replace(os.sep, "/")


def _module_level_imports(tree):
    """Names the module binds with an import at its top level."""
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    names.add(alias.asname or alias.name)
    return names


def _bound_names(fn):
    """Names the function signature itself binds, which are never unbound."""
    args = fn.args
    bound = {a.arg for a in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)}
    if args.vararg:
        bound.add(args.vararg.arg)
    if args.kwarg:
        bound.add(args.kwarg.arg)
    return bound


SEPARATE_SCOPE = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _own_scope(fn):
    """Walk fn's body but stop at a nested function or class: those are separate scopes.

    The skip has to apply to a nested def that is a direct statement of fn.body as well as to
    one buried deeper. The first version of this walker only checked children while expanding,
    so a nested def written at the top of a function had its whole body attributed to the
    enclosing one -- which reported the outer function's perfectly good `_()` call as a
    use-before-assignment. `test_a_nested_function_is_its_own_scope` is what caught it.

    A comprehension IS walked into on purpose. Its body is a separate scope in Python 3, but a
    free name in it still resolves to the enclosing function's local, so the same
    UnboundLocalError applies.
    """
    for stmt in fn.body:
        if isinstance(stmt, SEPARATE_SCOPE):
            continue
        stack = [stmt]
        while stack:
            node = stack.pop()
            yield node
            for child in ast.iter_child_nodes(node):
                if isinstance(child, SEPARATE_SCOPE):
                    continue
                stack.append(child)


def _functions(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _shadowing(path, rel, tree):
    """Every (function, name) where a module-level import is also assigned locally."""
    imports = _module_level_imports(tree)
    out = []
    for fn in _functions(tree):
        bound = _bound_names(fn)
        declared_global = set()
        stores, loads = {}, {}
        for node in _own_scope(fn):
            if isinstance(node, (ast.Global, ast.Nonlocal)):
                declared_global.update(node.names)
            elif isinstance(node, ast.Name):
                where = stores if isinstance(node.ctx, ast.Store) else loads
                where.setdefault(node.id, []).append(node.lineno)
        for name, store_lines in sorted(stores.items()):
            if name not in imports or name in bound or name in declared_global:
                continue
            use_lines = [ln for ln in loads.get(name, []) if ln < min(store_lines)]
            out.append(
                {
                    "rel": rel,
                    "function": fn.name,
                    "name": name,
                    "assigned_at": sorted(store_lines),
                    "used_before_at": sorted(use_lines),
                    "live": bool(use_lines),
                }
            )
    return out


def _all_shadowing():
    found = []
    for path, rel in _python_files(MODULE_ROOT):
        with open(path, "rb") as fh:
            source = fh.read().decode("utf-8")
        tree = ast.parse(source, filename=rel)
        found.extend(_shadowing(path, rel, tree))
    return found


class TestNoUnboundLocalFromShadowedImport(unittest.TestCase):
    """Pass A: a module-level import used before being assigned locally is an UnboundLocalError."""

    def test_no_import_is_used_before_being_shadowed(self):
        live = [f for f in _all_shadowing() if f["live"]]
        self.assertEqual(
            live,
            [],
            "A function uses a module-level import before assigning the same name locally, so "
            "the name is local for the whole function body and the earlier use raises "
            "UnboundLocalError:\n"
            + "\n".join(
                "  {rel}:{function}() uses '{name}' at line(s) {used_before_at} but assigns it "
                "at {assigned_at} -- rename the assigned name (e.g. '_encoding')".format(**f)
                for f in live
            ),
        )


class TestTranslationFunctionIsNeverShadowed(unittest.TestCase):
    """Pass B: stricter, and only about `_`, because one added line makes latent become live."""

    def test_no_function_shadows_the_translation_function(self):
        shadowed = [f for f in _all_shadowing() if f["name"] == "_"]
        self.assertEqual(
            shadowed,
            [],
            "A function assigns to '_', which in a Frappe module is the translation function "
            "imported as `from frappe import _`. Any use of _() in that function -- now or "
            "after a later edit -- raises UnboundLocalError. Name the discarded value instead "
            "(e.g. '_encoding'):\n"
            + "\n".join(
                "  {rel}:{function}() assigns '_' at line(s) {assigned_at}".format(**f)
                for f in shadowed
            ),
        )


class TestTheSweepItselfWorks(unittest.TestCase):
    """The passes above are green on a clean app, so prove they can go red at all.

    A guard that has only ever been green on the code it was written for is unproven. These two
    cases are the exact shapes found on 5 Oct 2026, reduced to the smallest source that carries
    them, so a future change to the walker is caught by its own file.
    """

    def _findings(self, source):
        return _shadowing("<memory>", "<memory>", ast.parse(source))

    def test_detects_a_use_before_a_shadowing_assignment(self):
        found = self._findings(
            "from frappe import _\n"
            "import mimetypes\n"
            "def download(path=None):\n"
            "    if not path:\n"
            "        raise Exception(_('File path is required'))\n"
            "    mime, _ = mimetypes.guess_type(path)\n"
            "    return mime\n"
        )
        self.assertEqual(len(found), 1, found)
        self.assertTrue(found[0]["live"])
        self.assertEqual(found[0]["name"], "_")
        self.assertEqual(found[0]["used_before_at"], [5])
        self.assertEqual(found[0]["assigned_at"], [6])

    def test_detects_a_latent_shadowing_with_no_earlier_use(self):
        found = self._findings(
            "from frappe import _\n"
            "import mimetypes\n"
            "def info(path):\n"
            "    mime, _ = mimetypes.guess_type(path)\n"
            "    return mime\n"
        )
        self.assertEqual(len(found), 1, found)
        self.assertFalse(found[0]["live"])
        self.assertEqual(found[0]["name"], "_")

    def test_a_parameter_of_the_same_name_is_not_a_finding(self):
        # A parameter is bound on entry, so there is no unbound window and no shadowing bug.
        self.assertEqual(
            self._findings(
                "from frappe import _\n"
                "def handler(_):\n"
                "    return _('x')\n"
            ),
            [],
        )

    def test_a_local_name_that_is_not_a_module_import_is_not_a_finding(self):
        self.assertEqual(
            self._findings(
                "def handler():\n"
                "    mime, _ = (1, 2)\n"
                "    return mime\n"
            ),
            [],
        )

    def test_a_nested_function_is_its_own_scope(self):
        # The inner function's assignment must not be attributed to the outer one, which would
        # report the outer function's legitimate _() call as a use-before-assignment.
        found = self._findings(
            "from frappe import _\n"
            "def outer():\n"
            "    msg = _('hello')\n"
            "    def inner():\n"
            "        a, _ = (1, 2)\n"
            "        return a\n"
            "    return msg, inner()\n"
        )
        self.assertEqual([f["function"] for f in found], ["inner"])
        self.assertFalse(found[0]["live"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
