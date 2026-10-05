# -*- coding: utf-8 -*-
"""Machinery for asking whether a test file actually bites.

A test that passes tells you it passed. It does not tell you it would have
failed had the code been wrong -- and a test that cannot fail is worse than no
test, because it reports safety it does not provide. The only way to find out
is to break the code on purpose and watch the test go red.

This module is the part that does not depend on which test you are asking
about: applying an edit to real source, proving it applied, running a test
file, and putting the source back. `faults.py` holds the edits themselves.

## The three ways this goes wrong silently

Every guard below exists because the mistake it catches has actually been made
in this repo, and each one turns a false pass into a hard stop.

1. **The edit matches nothing.** erplite is CRLF throughout, so a pattern
   written with `\\n` matches zero times in every file. Six of the first twelve
   faults written for `test_xero_permission_gate.py` silently matched nothing
   for exactly this reason, and without `EXPECTED_MATCHES` they would have been
   reported as six passes. Patterns here are written with `\\n` and translated
   to the file's own ending by `read`/`nl`.

2. **The edit matches more than once**, so it lands somewhere unintended as
   well and the red you get is not the red you asked for.

3. **Restoring destroys uncommitted work.** This restores with
   `git checkout --`, which throws away whatever was in the working tree.
   `require_clean_tree` refuses to start unless the tree is clean, because the
   alternative is losing an afternoon's work to a tool that was meant to check
   it. Commit first, then inject.

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
        cwd=REPO, capture_output=True, text=True)
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    return proc.returncode != 0, (lines[-1] if lines else "(no output)")
