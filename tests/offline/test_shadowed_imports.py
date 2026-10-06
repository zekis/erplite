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
    the same bug is not flagged. Only assignments, loop targets, `with`/`except ... as`, walrus
    bindings and the function's own `import` statements are.
  * A name bound only on one branch of an `if`/`else` is still local for the whole body, so the
    sweep is right to flag it, but it cannot tell you whether that branch is reachable.
  * `global _` or `nonlocal _` followed by an assignment is not flagged, correctly -- the binding
    is not local -- but it does clobber the module's translation function for every later caller.
    That is a different bug and no pass here looks for it.

CORRECTIONS, 6 Oct 2026, both found while writing this file's fault-injection target and both
measured against the interpreter rather than reasoned about:

  * **A comprehension's own loop target is not a local of the enclosing function.** This file
    used to walk into a comprehension and collect its `for` target as a function-level binding,
    on the reasoning (still correct, and still why comprehensions are walked) that a *free* name
    inside one resolves to the enclosing function's local. That reasoning does not carry to the
    target, which Python 3 binds in the comprehension's own scope. The effect was a false
    positive on ordinary Python: `sum(1 for _ in rows)` in a function that calls `_()` was
    reported as a live UnboundLocalError, and running it shows there is none. A guard that fails
    on correct code gets deleted, so this mattered more than a missed case would have.
    `_comprehension_scoped` is the fix; a walrus inside a comprehension still binds in the
    enclosing scope (PEP 572) and is still a finding, which is what tells the two apart.
  * **A function's own `import` is a binding like any other, and was invisible here.** `import
    frappe` or `from frappe import _` inside a function makes that name local for the whole body,
    so a use above it raises exactly the UnboundLocalError this file is about -- but `ast` reports
    it as an `Import` node, not as a `Name` in `Store` context, so the walk never saw it. The app
    has 23 function-local imports today; none is used before its import, and the two that also
    shadow a module-level name (`datetime` and `timedelta` in `erplite/www/todo/index.py:
    get_guest_context()`) are latent, so closing this added no failure. It is one edit from a
    live one.
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
    UnboundLocalError applies. Its own loop target does not: see `_comprehension_scoped`, which
    takes those names back out again.
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


COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _names_under(node):
    return [n for n in ast.walk(node) if isinstance(n, ast.Name)]


def _comprehension_scoped(fn):
    """The Name nodes inside fn that belong to a comprehension's scope, not to fn's.

    `_own_scope` walks into comprehensions deliberately, because a free name in one resolves
    outward to the enclosing function's local. A comprehension's *own* loop target is the
    exception: Python 3 binds it in the comprehension, so `[x for _ in rows]` leaves `_` alone
    in the function around it. Collecting it as a function-level store reported correct code as
    an UnboundLocalError.

    Identified by node identity rather than by name, because the same spelling can be the
    comprehension's variable in one place and the function's in another, and only one of them is
    the comprehension's.

    Two things are deliberately NOT taken out:

      * the outermost iterable, which Python evaluates in the enclosing scope before the
        comprehension exists -- so `[x for _ in _]` really does read the function's `_`;
      * a walrus target anywhere in the comprehension, which PEP 572 binds in the enclosing
        scope on purpose. That is a real shadow and stays a finding. It is also the case that
        distinguishes this fix from simply not walking comprehensions at all.
    """
    scoped = set()
    for node in _own_scope(fn):
        if not isinstance(node, COMPREHENSIONS):
            continue
        bound = set()
        for generator in node.generators:
            bound.update(n.id for n in _names_under(generator.target))
        if not bound:
            continue
        evaluated_outside = {id(n) for n in _names_under(node.generators[0].iter)}
        for name_node in _names_under(node):
            if name_node.id in bound and id(name_node) not in evaluated_outside:
                scoped.add(id(name_node))
    return scoped


def _local_import_names(fn):
    """Names fn binds with an import of its own, and where.

    A function-level `import x` or `from m import x` makes that name local for the whole body
    exactly as an assignment does, so a use above it is the same UnboundLocalError. `ast` reports
    the binding as an Import/ImportFrom node and never as a Name in Store context, so the walk
    over Name nodes cannot see it. Spelled to match `_module_level_imports` exactly: a dotted
    `import a.b` binds `a`, and `from m import x` binds `x`.
    """
    out = {}
    for node in _own_scope(fn):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.setdefault(alias.asname or alias.name.split(".")[0], []).append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    out.setdefault(alias.asname or alias.name, []).append(node.lineno)
    return out


def _shadowing(path, rel, tree):
    """Every (function, name) where a module-level import is also assigned locally."""
    imports = _module_level_imports(tree)
    out = []
    for fn in _functions(tree):
        bound = _bound_names(fn)
        declared_global = set()
        comprehension_scoped = _comprehension_scoped(fn)
        stores, loads = {}, {}
        for node in _own_scope(fn):
            if isinstance(node, (ast.Global, ast.Nonlocal)):
                declared_global.update(node.names)
            elif isinstance(node, ast.Name) and id(node) not in comprehension_scoped:
                where = stores if isinstance(node.ctx, ast.Store) else loads
                where.setdefault(node.id, []).append(node.lineno)
        for name, lines in _local_import_names(fn).items():
            stores.setdefault(name, []).extend(lines)
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
                "  {rel}:{function}() uses '{name}' at line(s) {used_before_at} but binds it "
                "locally at {assigned_at} -- rename the bound name (e.g. '_encoding'), or move "
                "a local import above the use".format(**f)
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
            "A function binds '_' locally -- by assignment, loop target, with/except as, walrus "
            "or an import of its own -- and in a Frappe module '_' is the translation function "
            "imported as `from frappe import _`. Any use of _() in that function -- now or "
            "after a later edit -- raises UnboundLocalError. Name the discarded value instead "
            "(e.g. '_encoding'):\n"
            + "\n".join(
                "  {rel}:{function}() binds '_' at line(s) {assigned_at}".format(**f)
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

    def test_a_comprehension_target_is_not_a_finding(self):
        # Python 3 binds a comprehension's loop variable in the comprehension's own scope, so
        # this function never binds `_` and its `_()` call is fine. Running it proves it: the
        # sweep used to report this as a live UnboundLocalError, which is a guard failing on
        # correct code. `sum(1 for _ in xs)` is ordinary Python and appears everywhere.
        source = (
            "from frappe import _\n"
            "def count(rows):\n"
            "    msg = _('counting')\n"
            "    n = sum(1 for _ in rows)\n"
            "    return msg, n\n"
        )
        namespace = {"_": lambda s: s}
        exec(compile(source.replace("from frappe import _\n", ""), "<memory>", "exec"), namespace)
        self.assertEqual(namespace["count"]([1, 2, 3]), ("counting", 3))
        self.assertEqual(self._findings(source), [])

    def test_a_comprehension_that_reads_its_own_target_is_not_a_finding(self):
        # The Load of `_` inside the comprehension reads the comprehension's variable, not the
        # function's, so it is not a use of the name bound on the line below it.
        found = self._findings(
            "from frappe import _\n"
            "def pick(rows):\n"
            "    kept = [_ for _ in rows if _]\n"
            "    mime, _ = (1, 2)\n"
            "    return kept, mime\n"
        )
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["name"], "_")
        self.assertFalse(found[0]["live"], found)
        self.assertEqual(found[0]["assigned_at"], [4])

    def test_the_outermost_iterable_is_evaluated_outside_the_comprehension(self):
        """Both halves, because the difference between them is the whole of the fix.

        Python evaluates a comprehension's *outermost* iterable in the enclosing scope, before
        the comprehension's own scope exists. So the same text means two different things
        depending on whether the function binds the name anywhere else, and both readings are
        checked against the interpreter below rather than argued from the language reference.
        """
        shared = ("def pick():\n"
                  "    kept = [x for rows in rows for x in (rows,)]\n")

        # A. The comprehension's target is the only binding, so it is not a binding of the
        #    function at all and the outer `rows` reads the module-level import. No finding.
        namespace = {"rows": [1, 2]}
        exec(compile(shared + "    return kept\n", "<memory>", "exec"), namespace)
        self.assertEqual(namespace["pick"](), [1, 2])
        self.assertEqual(self._findings("import rows\n" + shared + "    return kept\n"), [])

        # B. The function binds `rows` as well, so the outer `rows` reads that local -- which is
        #    not yet assigned. Taking the comprehension's names out must not take this one.
        tail = "    rows = []\n    return kept, rows\n"
        namespace = {"rows": [1, 2]}
        exec(compile(shared + tail, "<memory>", "exec"), namespace)
        with self.assertRaises(UnboundLocalError):
            namespace["pick"]()
        found = self._findings("import rows\n" + shared + tail)
        self.assertEqual([(f["name"], f["live"]) for f in found], [("rows", True)])
        self.assertEqual(found[0]["used_before_at"], [3])   # the outer iterable
        self.assertEqual(found[0]["assigned_at"], [4])      # `rows = []`

    def test_a_walrus_inside_a_comprehension_is_still_a_finding(self):
        # PEP 572: a walrus inside a comprehension binds in the ENCLOSING scope, so unlike the
        # loop target it really does shadow. This is the case that stops the fix above from
        # being "do not walk comprehensions".
        source = (
            "from frappe import _\n"
            "def pick(rows):\n"
            "    msg = _('picking')\n"
            "    kept = [(_ := r) for r in rows]\n"
            "    return msg, kept\n"
        )
        found = self._findings(source)
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["name"], "_")
        self.assertTrue(found[0]["live"], found)
        namespace = {"_": lambda s: s}
        exec(compile(source.replace("from frappe import _\n", ""), "<memory>", "exec"), namespace)
        with self.assertRaises(UnboundLocalError):
            namespace["pick"]([1, 2])

    def test_a_function_local_import_after_a_use_is_a_finding(self):
        # A deferred import -- common in Frappe apps, to break an import cycle -- binds the name
        # for the whole body, so the module-level `frappe` is unreachable above it.
        found = self._findings(
            "import frappe\n"
            "def run():\n"
            "    frappe.msgprint('x')\n"
            "    import frappe\n"
            "    return frappe.session.user\n"
        )
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["name"], "frappe")
        self.assertTrue(found[0]["live"], found)
        self.assertEqual(found[0]["used_before_at"], [3])
        self.assertEqual(found[0]["assigned_at"], [4])

    def test_a_function_local_from_import_of_the_translation_function_is_a_finding(self):
        found = self._findings(
            "from frappe import _\n"
            "def run():\n"
            "    from frappe import _\n"
            "    return _('x')\n"
        )
        self.assertEqual([(f["name"], f["live"]) for f in found], [("_", False)])
        self.assertEqual(found[0]["assigned_at"], [3])

    def test_an_aliased_local_import_binds_the_alias_not_the_module(self):
        # `import frappe as f` binds `f`; the module-level `frappe` is untouched, so the earlier
        # frappe.msgprint() is fine and there is nothing to report.
        self.assertEqual(
            self._findings(
                "import frappe\n"
                "def run():\n"
                "    frappe.msgprint('x')\n"
                "    import frappe as f\n"
                "    return f\n"
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
