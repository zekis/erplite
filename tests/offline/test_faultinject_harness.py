# -*- coding: utf-8 -*-
"""Keep the fault list honest, without breaking anything.

`tests/faultinject/run.py` proves the test files bite, but it edits real source
to do it, so it is not something an ordinary test run should trigger. That
leaves a gap: the faults are literal source patterns, so they rot the moment
the code they name is rewritten -- and a rotted fault is only discovered the
next time somebody remembers to run the harness by hand.

This file closes that gap. It reads; it never writes. It asserts that every
fault still matches exactly the one place it is meant to, so the ordinary suite
tells you a fault has rotted at the moment the code moves, in the same commit
that moved it, rather than months later.

It also pins the guards the harness relies on, because every one of them exists
to stop a false pass and a broken guard would restore the false pass silently.

Runs without a bench.
"""
import importlib.util
import os
import py_compile
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
FI = os.path.join(REPO, "tests", "faultinject")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load("fi_harness", os.path.join(FI, "harness.py"))
faults_mod = _load("fi_faults", os.path.join(FI, "faults.py"))
TARGETS = faults_mod.TARGETS


def _is_work_tree():
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=REPO, capture_output=True, text=True)
    except OSError:
        return False
    return done.returncode == 0 and done.stdout.strip() == "true"


WORK_TREE = _is_work_tree()
_blobs = {}


def committed(relpath):
    """Read a file as the repository stores it, line endings and all.

    Deliberately not the working tree. Git rewrites line endings on checkout
    when `core.autocrlf` is on, so the working tree's endings are a fact about
    whose machine it is; the blob is the same bytes for everybody. Anything
    asserting what *this repo* holds has to read it here.
    """
    if relpath not in _blobs:
        done = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:" + relpath.replace("\\", "/")],
            cwd=REPO, capture_output=True)
        if done.returncode != 0:
            raise AssertionError(
                "%s is not in HEAD, so what the repo stores for it cannot be "
                "read: %s" % (relpath,
                              done.stderr.decode("utf-8", "replace").strip()))
        _blobs[relpath] = done.stdout
    raw = _blobs[relpath]
    text = raw.decode("utf-8")
    return text, ("\r\n" if "\r\n" in text else "\n")


_UNITS = ("zero", "one", "two", "three", "four", "five", "six", "seven",
          "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
          "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
_TENS = {20: "twenty", 30: "thirty", 40: "forty", 50: "fifty", 60: "sixty"}


def _spelled(n):
    """`21` -> "twenty-one". The README writes its target count as a word, and a
    count nothing checks is the count that goes stale -- which is what happened.
    """
    if n < 20:
        return _UNITS[n]
    ten, unit = divmod(n, 10)
    word = _TENS.get(ten * 10)
    if word is None:
        return str(n)
    return word if unit == 0 else "%s-%s" % (word, _UNITS[unit])


class TestEveryFaultStillMatchesItsOneSpot(unittest.TestCase):
    """The assertion this file exists for: no fault has rotted.

    A fault whose pattern no longer matches measures nothing. The harness stops
    rather than passing when that happens, which is the right behaviour at the
    moment somebody runs it -- but this gets the news to whoever moved the code,
    in the ordinary test run, instead of waiting for that moment.
    """

    def test_each_edit_matches_exactly_once(self):
        for key, target in sorted(TARGETS.items()):
            for fault in target.faults:
                for path, old, _new in fault.edits:
                    with self.subTest(target=key, fault=fault.name, file=path):
                        full = os.path.join(REPO, path)
                        self.assertTrue(
                            os.path.exists(full),
                            "%s: %s no longer exists, so this fault cannot "
                            "run" % (fault.name, path))
                        text, ending = harness.read(path)
                        found = text.count(harness.nl(old, ending))
                        self.assertEqual(
                            found, harness.EXPECTED_MATCHES,
                            "%s / %s: the pattern for %r matches %d times, "
                            "expected %d. The source it names has moved, so "
                            "this fault no longer proves anything and "
                            "tests/faultinject/run.py will stop on it. Rewrite "
                            "the pattern against the code as it is now -- do "
                            "not delete the fault, the claim it checks is "
                            "still being made."
                            % (key, fault.name, path, found,
                               harness.EXPECTED_MATCHES))

    def test_each_edit_would_actually_change_the_file(self):
        """An edit whose replacement equals its pattern is a no-op dressed up."""
        for key, target in sorted(TARGETS.items()):
            for fault in target.faults:
                for path, old, new in fault.edits:
                    with self.subTest(target=key, fault=fault.name):
                        self.assertNotEqual(
                            old, new,
                            "%s / %s: replaces %r with itself, so it measures "
                            "the unmodified code" % (key, fault.name, path))


class TestEveryTargetIsWorthTrusting(unittest.TestCase):
    """Shape rules that decide whether a target's result means anything."""

    def test_each_target_names_a_test_file_that_exists(self):
        for key, target in sorted(TARGETS.items()):
            with self.subTest(target=key):
                self.assertTrue(
                    os.path.exists(os.path.join(REPO, target.test)),
                    "target %s names %s, which does not exist"
                    % (key, target.test))

    def test_each_target_has_at_least_one_negative_control(self):
        """Without a control, "every fault went red" can mean the test file is
        simply red at the slightest touch, which is not the same as bites."""
        for key, target in sorted(TARGETS.items()):
            with self.subTest(target=key):
                controls = [f for f in target.faults if not f.expect_red]
                self.assertTrue(
                    controls,
                    "target %s has no fault with expect_red=False. Add an edit "
                    "that changes the source and changes no behaviour, so a "
                    "test file that fails indiscriminately is told apart from "
                    "one that discriminates." % key)

    def test_each_target_has_faults_that_are_expected_to_bite(self):
        for key, target in sorted(TARGETS.items()):
            with self.subTest(target=key):
                self.assertTrue(
                    [f for f in target.faults if f.expect_red],
                    "target %s has no fault expected to go red" % key)

    def test_fault_names_are_distinct_within_a_target(self):
        """Results are reported by name; two faults sharing one are a confusion."""
        for key, target in sorted(TARGETS.items()):
            with self.subTest(target=key):
                names = [f.name for f in target.faults]
                self.assertEqual(
                    sorted(names), sorted(set(names)),
                    "target %s has duplicate fault names" % key)


class TestTheREADMEStillDescribesEveryTarget(unittest.TestCase):
    """A target with no section is a target whose result nobody can read.

    The README's own rule is that its two counts are "counted from `faults.py`,
    not kept by hand" -- but nothing counted them, so they went two targets
    stale, and `endpoint_wiring` sat in `faults.py` for two more targets with no
    section at all. Both were noticed by a person remembering, twice, which is
    the thing this file exists to replace everywhere else.

    These tests do not check the prose. They check the three facts a reader uses
    to find out whether a claim about a target has been written down: that it
    has a section, that the section names the file the target drives, and that
    the counts at the top are today's.
    """

    README = os.path.join(FI, "README.md")

    def _readme(self):
        with open(self.README, encoding="utf-8") as fh:
            return fh.read()

    def test_every_target_has_a_section_naming_its_test_file(self):
        text = self._readme()
        headings = {}
        for line in text.splitlines():
            match = re.match(r"^### `([a-z_]+)`(.*)$", line)
            if match:
                headings[match.group(1)] = match.group(2)
        for key, target in sorted(TARGETS.items()):
            with self.subTest(target=key):
                self.assertIn(
                    key, headings,
                    "`%s` is a target in faults.py with no `### \x60%s\x60` "
                    "section in tests/faultinject/README.md. Drive it and write "
                    "what the run said; do not write the section from the file."
                    % (key, key))
                self.assertIn(
                    target.test, headings[key],
                    "the `%s` section does not name %s, the file that target "
                    "drives" % (key, target.test))

    def test_no_section_describes_a_target_that_is_gone(self):
        text = self._readme()
        for line in text.splitlines():
            match = re.match(r"^### `([a-z_]+)`", line)
            if match:
                with self.subTest(section=match.group(1)):
                    self.assertIn(
                        match.group(1), TARGETS,
                        "the README has a section for `%s`, which faults.py no "
                        "longer defines" % match.group(1))

    def test_the_counts_at_the_top_of_targets_are_todays(self):
        """The sentence a reader believes without checking anything else."""
        text = self._readme()
        match = re.search(r"^([A-Z][a-z]+(?:-[a-z]+)?) so far, (\d+) injections",
                          text, re.M)
        self.assertIsNotNone(
            match, "the `## Targets` section no longer opens with "
                   "'<Number> so far, <n> injections', so nothing here can "
                   "check those two numbers")
        spelled, injections = match.group(1), int(match.group(2))
        self.assertEqual(
            injections, sum(len(t.faults) for t in TARGETS.values()),
            "the README says %d injections; faults.py has %d"
            % (injections, sum(len(t.faults) for t in TARGETS.values())))
        self.assertEqual(
            spelled.lower(), _spelled(len(TARGETS)),
            "the README says %s targets; faults.py has %d (%s)"
            % (spelled, len(TARGETS), _spelled(len(TARGETS))))

class TestTheLineEndingGuard(unittest.TestCase):
    """`nl` is the guard that six real faults needed and did not have.

    A pattern written with \\n matches zero times in a CRLF file, so without
    this translation a multi-line fault is reported as a pass having measured
    nothing. That is what happened to six of the first twelve faults here.

    **This repo stores both endings.** Measured 6 Oct 2026 from the committed
    blobs: 82 CRLF `.py` files and 62 LF, 31 CRLF `.json` and 22 LF -- and the
    split runs *inside* a single DocType folder, where `timesheet_entry.py` is
    CRLF and its `timesheet_entry.json` is LF.

    Two corrections are folded in here, in the order they were made, because
    each one is a narrower version of the same mistake:

    1. The ending is a property of each **file**, not of the repo. An earlier
       version of this class asserted every fault's file was CRLF. That was
       true of every file the first target happened to name, false of the repo,
       and the second target failed it immediately.
    2. The ending in front of you is a property of the **checkout**, not even
       of the file. With `core.autocrlf=true` -- git's default on Windows, and
       there is no `.gitattributes` here to override it -- the LF files are
       checked out as CRLF and the mixture above is invisible. Two tests below
       described that mixture by reading the working tree; they passed in a
       Linux sandbox and failed on a Windows checkout, which is a test
       reporting on its author's machine rather than on the repo.

    So each test reads from whichever source actually carries its claim:

    * `committed()` -- the blob -- for anything about what the repository
      holds, since that is the same for everyone.
    * `harness.read()` -- the working tree -- for anything about what the
      harness itself opens, since that is what it will really be given.

    The harness needed no change for any of this: it asks each file in front of
    it, whatever the checkout handed over. Only the descriptions of it broke.
    """

    def test_a_pattern_is_translated_for_a_crlf_file(self):
        self.assertEqual(harness.nl("a\nb", "\r\n"), "a\r\nb")

    def test_a_pattern_is_left_alone_for_an_lf_file(self):
        self.assertEqual(harness.nl("a\nb", "\n"), "a\nb")

    def test_an_already_translated_pattern_is_not_doubled(self):
        self.assertEqual(harness.nl("a\r\nb", "\r\n"), "a\r\nb")

    def _files_the_faults_name(self):
        seen = set()
        for target in TARGETS.values():
            for fault in target.faults:
                for path, _old, _new in fault.edits:
                    seen.add(path)
        self.assertTrue(seen)
        return sorted(seen)

    def _as_committed_and_checked_out(self, path):
        """Both sources, so neither can hide a problem the other would show."""
        with open(os.path.join(REPO, path), "rb") as handle:
            yield "working tree", handle.read()
        if WORK_TREE:
            yield "committed blob", committed(path)[0].encode("utf-8")

    def test_every_file_a_fault_names_has_one_consistent_ending(self):
        """What `read` actually needs: one ending per file, not one per repo.

        `read` decides by asking whether "\r\n" appears anywhere, so a file
        with both endings would be translated as CRLF and the patterns written
        for its LF half would silently match nothing. A mixed file is the one
        shape no per-file detection can rescue, so it is refused here rather
        than discovered as a fault that measures nothing.

        Checked in the working tree, which is what `read` will open, and in the
        blob as well. A converting checkout tidies a mixed file into a uniform
        CRLF one on its way out, so on Windows the working tree alone would
        wave through a file that is mixed for everybody else.
        """
        for path in self._files_the_faults_name():
            for source, raw in self._as_committed_and_checked_out(path):
                with self.subTest(file=path, source=source):
                    crlf = raw.count(b"\r\n")
                    bare_lf = raw.count(b"\n") - crlf
                    self.assertFalse(
                        crlf and bare_lf,
                        "%s mixes %d CRLF and %d LF endings (%s). harness.read "
                        "would call the whole file CRLF, so any pattern "
                        "spanning a line break in its LF part matches nothing."
                        % (path, crlf, bare_lf, source))

    def test_both_endings_really_occur_among_those_files(self):
        """The reason this is per-file, pinned against what the repo stores.

        From the blobs, not the working tree: with `core.autocrlf=true` the LF
        files arrive as CRLF and this mixture vanishes, which is precisely how
        this test came to pass in a Linux sandbox and fail on Windows.

        If it ever fails *from the blobs*, the repo really has been normalised
        to one ending. The translation stays correct either way -- but the
        claim in the docstring above would have gone stale, and a stale
        explanation is how the repo-wide version of this test got written in
        the first place.
        """
        if not WORK_TREE:
            self.skipTest("not a git work tree, so the blobs cannot be read")
        endings = {path: committed(path)[1]
                   for path in self._files_the_faults_name()}
        self.assertEqual(
            set(endings.values()), {"\r\n", "\n"},
            "expected the faults to name both a CRLF and an LF file as "
            "committed; got %r" % (sorted(set(endings.values())),))
        self.assertEqual(
            endings["erplite/projects/doctype/timesheet_entry/timesheet_entry.py"],
            "\r\n")
        self.assertEqual(
            endings["erplite/projects/doctype/timesheet_entry/timesheet_entry.json"],
            "\n",
            "the LF half of the demonstration is gone; the pair of files in one "
            "DocType folder with different endings is the whole point")

    def test_a_pattern_written_for_the_wrong_ending_matches_nothing(self):
        """Both directions of the mistake, against the two real neighbours.

        Not a unit test of `nl`: this is the actual failure, measured on real
        files that genuinely differ, in both directions -- a CRLF pattern
        against the LF file as well as the LF pattern against the CRLF file.

        From the blobs. A checkout that converts hands you two CRLF files, so
        neither direction can be demonstrated there and this test failed on
        Windows for want of an LF file to fail against. The mistake is no less
        real for that: the patterns in `faults.py` are shared by every copy of
        this repo, while the conversion is one person's.
        """
        if not WORK_TREE:
            self.skipTest("not a git work tree, so the blobs cannot be read")
        py = "erplite/projects/doctype/timesheet_entry/timesheet_entry.py"
        js = "erplite/projects/doctype/timesheet_entry/timesheet_entry.json"
        py_text, py_ending = committed(py)
        js_text, js_ending = committed(js)
        self.assertEqual((py_ending, js_ending), ("\r\n", "\n"),
                         "the two neighbours no longer differ as committed, so "
                         "neither direction below demonstrates anything")

        two_lines_of_py = "        if not self.is_new():\n            return\n"
        self.assertEqual(py_text.count(two_lines_of_py), 0,
                         "an LF pattern matched the CRLF file")
        self.assertEqual(py_text.count(harness.nl(two_lines_of_py, "\r\n")), 1)

        two_lines_of_json = ('   "fieldname": "employee",\n'
                             '   "fieldtype": "Link",\n')
        self.assertEqual(js_text.count(harness.nl(two_lines_of_json, "\r\n")), 0,
                         "a CRLF pattern matched the LF file")
        self.assertEqual(js_text.count(two_lines_of_json), 1)

    def test_a_multi_line_pattern_misses_without_translation(self):
        """The mistake itself, pinned: this is what a false pass looked like."""
        text, ending = harness.read(faults_mod.SI)
        self.assertEqual(ending, "\r\n")
        untranslated = faults_mod.SI_GATE + "\n    try:\n"
        self.assertEqual(
            text.count(untranslated), 0,
            "the untranslated pattern matched, so this test no longer "
            "demonstrates why nl() is needed")
        self.assertEqual(text.count(harness.nl(untranslated, ending)), 1)


class TestTheHarnessRefusesToDestroyWork(unittest.TestCase):
    """The guard that matters most: restore is `git checkout --`.

    Running over a dirty tree discards uncommitted work. That has happened, so
    the refusal is tested rather than assumed.
    """

    def test_a_dirty_tree_is_refused(self):
        calls = []

        def fake_git(*args):
            calls.append(args)

            class Result(object):
                stdout = " M erplite/crm/doctype/customer/customer.py\n"
            return Result()

        original = harness.git
        harness.git = fake_git
        try:
            with self.assertRaises(harness.Stop) as caught:
                harness.require_clean_tree()
        finally:
            harness.git = original
        self.assertIn("Commit your work first", str(caught.exception))
        self.assertEqual(calls, [("status", "--porcelain")])

    def test_a_clean_tree_is_allowed(self):
        original = harness.git
        harness.git = lambda *a: type("R", (), {"stdout": "\n"})()
        try:
            harness.require_clean_tree()
        finally:
            harness.git = original

    def test_a_fault_left_behind_is_reported_not_ignored(self):
        original = harness.git
        harness.git = lambda *a: type(
            "R", (), {"stdout": " M erplite/crm/doctype/customer/customer.py\n"})()
        try:
            with self.assertRaises(harness.Stop) as caught:
                harness.require_restored(
                    faults_mod.Fault("some fault", True, []))
        finally:
            harness.git = original
        self.assertIn("RESTORE FAILED", str(caught.exception))


class TestNoFaultIsMeasuredAgainstThePreviousOnesBytecode(unittest.TestCase):
    """A cached `.pyc` is reused when the source's size and whole-second mtime
    both match what was cached. Faults are small, same-shaped edits on one file
    applied seconds apart, so that happens by ordinary coincidence: every one of
    the twelve `frappe.get_list(` -> `frappe.get_all(` edits in the
    scheduler_read_gate target leaves api.py at exactly the same size.

    It was found by running one fault twice with another between and getting two
    different answers -- a behavioural test red, then green on the neighbour's
    code. No `run.py` verdict changed, because every fault in the four current
    targets is also caught by an AST test that reads source text; that is luck of
    the target set, not a property of the tool. A fault guarded only by a
    behavioural test would have been reported GREEN, and that direction is the
    dangerous one: a false GREEN reads as "the test does not notice this
    regression" and sends someone to fix a test that is fine.
    """

    SOURCE = "erplite/scheduler/api.py"

    def test_cached_bytecode_finds_what_python_would_actually_serve(self):
        """Pinned against importlib's own answer, not a hand-built path."""
        absolute = os.path.join(REPO, self.SOURCE)
        expected = importlib.util.cache_from_source(absolute)
        py_compile.compile(absolute, doraise=True)
        try:
            self.assertTrue(os.path.exists(expected), expected)
            self.assertIn(expected, harness.cached_bytecode(self.SOURCE))
        finally:
            if os.path.exists(expected):
                os.remove(expected)

    def test_purge_bytecode_removes_it(self):
        absolute = os.path.join(REPO, self.SOURCE)
        expected = importlib.util.cache_from_source(absolute)
        py_compile.compile(absolute, doraise=True)
        try:
            self.assertEqual(harness.purge_bytecode([self.SOURCE]), [expected])
            self.assertEqual(harness.cached_bytecode(self.SOURCE), [])
        finally:
            if os.path.exists(expected):
                os.remove(expected)

    def test_a_non_python_file_has_no_bytecode_to_purge(self):
        """Faults edit DocType JSONs too, and those must not confuse this."""
        self.assertEqual(
            harness.cached_bytecode(
                "erplite/projects/doctype/project/project.json"), [])

    def test_the_test_subprocess_cannot_write_bytecode(self):
        """Checked by asking an interpreter started that way, not by reading the
        dict: the point is the behaviour of the process the harness starts."""
        self.assertEqual(
            harness.subprocess_env().get("PYTHONDONTWRITEBYTECODE"), "1")
        done = subprocess.run(
            [sys.executable, "-c", "import sys; print(sys.dont_write_bytecode)"],
            cwd=REPO, capture_output=True, text=True,
            env=harness.subprocess_env())
        self.assertEqual(done.stdout.strip(), "True", done.stderr)

    def test_the_run_stops_rather_than_measure_against_stale_bytecode(self):
        """The guard, not just the purge: that purging worked is a second claim.

        A refactor that drops the purge, or a file Python recompiles into a cache
        this does not know about, must stop the run -- not quietly measure the
        wrong code.
        """
        absolute = os.path.join(REPO, self.SOURCE)
        expected = importlib.util.cache_from_source(absolute)
        py_compile.compile(absolute, doraise=True)
        original_git = harness.git
        harness.git = lambda *a: type("R", (), {"stdout": ""})()
        try:
            with self.assertRaises(harness.Stop) as caught:
                harness.require_no_cached_bytecode(
                    faults_mod.Fault("a fault", True, []), [self.SOURCE])
        finally:
            harness.git = original_git
            if os.path.exists(expected):
                os.remove(expected)
        self.assertIn("CACHED BYTECODE SURVIVED", str(caught.exception))
        self.assertIn(expected, str(caught.exception),
                      "the message has to name the file to delete")

    def test_restore_purges_the_bytecode_a_run_could_have_left(self):
        """`restore` purges as well as checking out, so a .pyc written by a run
        made under a fault cannot outlive that fault.

        Deliberately *not* written as "no bytecode is cached for api.py": that
        asserts a property of whoever's machine this is, not of the harness. It
        passed here only because an alphabetically earlier test in this class
        happened to delete the file first, and it would fail outright on the
        bench, where frappe imports erplite and the .pyc is always there.
        """
        absolute = os.path.join(REPO, self.SOURCE)
        expected = importlib.util.cache_from_source(absolute)
        py_compile.compile(absolute, doraise=True)
        checkouts = []
        original_git = harness.git
        harness.git = lambda *a: (checkouts.append(a),
                                  type("R", (), {"stdout": ""})())[1]
        try:
            self.assertTrue(os.path.exists(expected))
            harness.restore([self.SOURCE])
            self.assertFalse(os.path.exists(expected),
                             "restore left bytecode behind for the next fault")
        finally:
            harness.git = original_git
            if os.path.exists(expected):
                os.remove(expected)
        self.assertEqual(checkouts, [("checkout", "--", self.SOURCE)])


class TestTheHarnessIsNotCollectedByPytest(unittest.TestCase):
    """It edits source files. No test run may trigger it by accident."""

    def test_no_file_in_faultinject_is_named_like_a_test(self):
        for name in sorted(os.listdir(FI)):
            if name.endswith(".py"):
                with self.subTest(file=name):
                    self.assertFalse(
                        name.startswith("test_") or name.endswith("_test.py"),
                        "tests/faultinject/%s would be collected by pytest, "
                        "and running it edits real source files" % name)

    def test_no_function_in_the_harness_is_named_like_a_test(self):
        for module, label in ((harness, "harness.py"), (faults_mod, "faults.py")):
            for attr in dir(module):
                if attr.startswith("test"):
                    with self.subTest(module=label, name=attr):
                        self.fail("%s defines %s, which pytest would collect"
                                  % (label, attr))


if __name__ == "__main__":
    unittest.main(verbosity=2)
