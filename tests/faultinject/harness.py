# -*- coding: utf-8 -*-
"""Machinery for asking whether a test file actually bites.

A test that passes tells you it passed. It does not tell you it would have
failed had the code been wrong -- and a test that cannot fail is worse than no
test, because it reports safety it does not provide. The only way to find out
is to break the code on purpose and watch the test go red.

This module is the part that does not depend on which test you are asking
about: applying an edit to real source, proving it applied, running a test
file, and putting the source back. `faults.py` holds the edits themselves.

## The four ways this goes wrong silently

Every guard below exists because the mistake it catches has actually been made
in this repo, and each one turns a false pass into a hard stop.

1. **The edit matches nothing.** A pattern written with `\\n` matches zero
   times in a CRLF file. Six of the first twelve faults written for
   `test_xero_permission_gate.py` silently matched nothing for exactly this
   reason, and without `EXPECTED_MATCHES` they would have been reported as six
   passes. Patterns here are written with `\\n` and translated to the file's own
   ending by `read`/`nl`.

   The ending is a property of the **file** -- this repo's are mixed -- and of
   the **checkout** as well: with `core.autocrlf=true` git hands Windows a CRLF
   copy of an LF file, and there is no `.gitattributes` here to stop it. Which
   is why `read` asks the file in front of it every time and nothing here
   records what the ending "should" be.

2. **The edit matches more than once**, so it lands somewhere unintended as
   well and the red you get is not the red you asked for.

3. **Restoring destroys uncommitted work.** This restores with
   `git checkout --`, which throws away whatever was in the working tree.
   `require_clean_tree` refuses to start unless the tree is clean, because the
   alternative is losing an afternoon's work to a tool that was meant to check
   it. Commit first, then inject.

4. **Python serves the previous fault's bytecode.** A cached `.pyc` is reused
   when the source's size and its mtime *in whole seconds* both match what was
   cached. Faults are small, same-shaped edits applied seconds apart, so two
   different faults on one file routinely produce the same size in the same
   second -- `frappe.get_list(` -> `frappe.get_all(` twelve times over leaves
   `erplite/scheduler/api.py` at exactly 32531 bytes every time. The second
   fault is then measured against the first one's code.

   This was not hypothetical: running one fault twice, with another between,
   gave two different answers -- a behavioural test went red, then green on the
   neighbour's bytecode. It corrupted which tests each fault was seen to break;
   it did not change any run.py verdict here, because every fault in the four
   current targets is also caught by an AST test that reads source text. That is
   luck of the target set. **A fault guarded only by a behavioural test would
   have been reported GREEN**, which is the worst thing this tool can produce: it
   reads as "the test does not notice this regression" and invites someone to go
   and fix a test that is fine.

   So `apply_fault` deletes the cached bytecode for every file it touches and
   refuses to continue if any survives, and the test subprocess runs with
   bytecode writing switched off.

A fourth, which no guard can catch for you: a "negative control" that goes red
is not a control. It must be an edit that genuinely changes the source and
genuinely changes no behaviour -- a local variable rename, not a comment.
Assert the controls as carefully as the faults.

## When a fault stops applying

These patterns are literal source text, so they rot when the code they name is
rewritten -- deliberately. A rotted fault stops with INJECTION DID NOT APPLY
rather than passing quietly, which is the right failure: the person who moved
the gate is told that the proof it was guarded no longer runs.

Runs without a bench. Not collected by pytest: it edits source files, so it is
never something a test run can trigger by accident.
"""
from __future__ import annotations

import os
import subprocess
import sys

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))

EXPECTED_MATCHES = 1


def subprocess_env():
    """The environment for a test run: no bytecode written, ever.

    Nothing may be cached from a run made under a fault, because the next fault
    can produce a source file with the same size in the same second and would
    then be handed this one's bytecode. See point 4 above.
    """
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def cached_bytecode(relpath):
    """Every cached-bytecode file Python could serve in place of this source.

    The whole cache directory is searched rather than only the path
    `importlib.util.cache_from_source` names, because that names the file for
    the interpreter running right now and the point here is to leave nothing
    behind for any of them.
    """
    if not relpath.endswith(".py"):
        return []
    directory, name = os.path.split(os.path.join(REPO, relpath))
    cache = os.path.join(directory, "__pycache__")
    if not os.path.isdir(cache):
        return []
    stem = name[:-len(".py")] + "."
    return sorted(os.path.join(cache, entry) for entry in os.listdir(cache)
                  if entry.startswith(stem) and entry.endswith(".pyc"))


def purge_bytecode(paths):
    """Delete the cached bytecode for sources that have just changed."""
    removed = []
    for relpath in paths:
        for pyc in cached_bytecode(relpath):
            os.remove(pyc)
            removed.append(pyc)
    return removed


def require_no_cached_bytecode(fault, paths):
    """Stop rather than measure a fault against the previous one's bytecode.

    Separate from `purge_bytecode` because purging and checking that purging
    worked are two different claims, and this is the one that has to hold.
    """
    stale = [pyc for path in paths for pyc in cached_bytecode(path)]
    if stale:
        restore(paths)
        raise Stop(
            "CACHED BYTECODE SURVIVED -- %s. Python could serve it instead of "
            "the edited source, so this fault would measure the previous one's "
            "code.\n  %s" % (fault.name, "\n  ".join(stale)))


class Stop(Exception):
    """A guard tripped. The run cannot produce a trustworthy answer."""


def git(*args):
    return subprocess.run(
        ["git"] + list(args), cwd=REPO, capture_output=True, text=True)


def require_clean_tree():
    """Refuse to run over uncommitted work -- restoring would destroy it."""
    dirty = git("status", "--porcelain").stdout.strip()
    if dirty:
        raise Stop(
            "the working tree is not clean, and restoring a fault discards "
            "whatever is in it. Commit your work first, then inject.\n" + dirty)


def read(relpath):
    """Read a file preserving line endings, and say which ending it uses."""
    with open(os.path.join(REPO, relpath), encoding="utf-8", newline="") as fh:
        text = fh.read()
    return text, "\r\n" if "\r\n" in text else "\n"


def nl(pattern, ending):
    """Translate a pattern written with \\n to the file's own line ending.

    Normalises the pattern first. Translating without that step turns an
    already-correct "a\\r\\nb" into "a\\r\\r\\nb", which then matches nothing --
    the very failure this function exists to prevent, reintroduced by it.
    """
    return pattern.replace("\r\n", "\n").replace("\n", ending)


def apply_fault(fault):
    """Apply every edit in a fault, proving each one landed exactly once.

    Returns the files touched, so the caller can restore precisely those.
    Raises Stop -- having restored what it already changed -- if any edit does
    not match exactly once, so a fault can never half-apply.
    """
    touched = []
    for path, old, new in fault.edits:
        text, ending = read(path)
        old_n, new_n = nl(old, ending), nl(new, ending)
        found = text.count(old_n)
        if found != EXPECTED_MATCHES:
            restore(touched)
            raise Stop(
                "INJECTION DID NOT APPLY -- %s\n"
                "  %s matched %d times, expected %d (file uses %r)\n"
                "  pattern: %r\n"
                "  Nothing was measured. Either the source moved and this "
                "fault needs rewriting, or the pattern's line endings are "
                "wrong."
                % (fault.name, path, found, EXPECTED_MATCHES, ending, old_n[:300]))
        with open(os.path.join(REPO, path), "w",
                  encoding="utf-8", newline="") as fh:
            fh.write(text.replace(old_n, new_n, EXPECTED_MATCHES))
        touched.append(path)

    # The edited source must be compiled afresh, or this fault is measured
    # against whatever was cached for the last one (point 4 above).
    purge_bytecode(touched)
    require_no_cached_bytecode(fault, touched)

    # Belief is not evidence: ask git whether the tree actually differs.
    if not git("diff", "--stat").stdout.strip():
        restore(touched)
        raise Stop(
            "INJECTION LEFT NO DIFF -- %s. The edits matched but changed "
            "nothing, so this fault would have measured the unmodified code."
            % fault.name)
    return touched


def restore(paths):
    if paths:
        git("checkout", "--", *sorted(set(paths)))
        purge_bytecode(paths)


def require_restored(fault):
    """A fault left behind would be blamed on the next one, or committed."""
    dirty = git("status", "--porcelain").stdout.strip()
    if dirty:
        raise Stop(
            "RESTORE FAILED after %s -- the tree still differs, so later "
            "results are meaningless and this must not be committed.\n%s"
            % (fault.name, dirty))


def run_test_file(path):
    """Run one test file. Returns (went_red, last line of output)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", path, "-q", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=REPO, capture_output=True, text=True, env=subprocess_env())
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    return proc.returncode != 0, (lines[-1] if lines else "(no output)")
