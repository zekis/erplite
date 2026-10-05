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


class TestTheLineEndingGuard(unittest.TestCase):
    """`nl` is the guard that six real faults needed and did not have.

    erplite is CRLF. A pattern written with \\n matches zero times in every
    file here, so without this translation a multi-line fault is reported as a
    pass having measured nothing.
    """

    def test_a_pattern_is_translated_for_a_crlf_file(self):
        self.assertEqual(harness.nl("a\nb", "\r\n"), "a\r\nb")

    def test_a_pattern_is_left_alone_for_an_lf_file(self):
        self.assertEqual(harness.nl("a\nb", "\n"), "a\nb")

    def test_an_already_translated_pattern_is_not_doubled(self):
        self.assertEqual(harness.nl("a\r\nb", "\r\n"), "a\r\nb")

    def test_the_app_sources_the_faults_name_are_read_as_crlf(self):
        """If this ever fails, the repo's line endings changed and the
        translation above is no longer what the patterns need."""
        seen = set()
        for target in TARGETS.values():
            for fault in target.faults:
                for path, _old, _new in fault.edits:
                    seen.add(path)
        self.assertTrue(seen)
        for path in sorted(seen):
            with self.subTest(file=path):
                self.assertEqual(
                    harness.read(path)[1], "\r\n",
                    "%s is no longer CRLF; the faults' line-ending "
                    "translation assumes it is" % path)

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
