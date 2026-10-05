# -*- coding: utf-8 -*-
"""Break the code on purpose and check the tests notice.

    python tests/faultinject/run.py              # every target
    python tests/faultinject/run.py xero_gate    # one target
    python tests/faultinject/run.py --list       # what there is

Exit status is 0 only if every fault landed, every fault turned its test file
red, and every control stayed green. Anything else -- including a fault that
could not be applied -- is a non-zero exit, because an unmeasured claim and a
false claim are the same thing to whoever reads the result.

**Requires a clean working tree**: it edits real source files and restores them
with `git checkout --`, which discards uncommitted work. Commit first.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness  # noqa: E402
from faults import TARGETS  # noqa: E402


def run_target(key, target):
    print("== %s  (%s)" % (key, target.test))
    baseline_red, baseline = harness.run_test_file(target.test)
    if baseline_red:
        print("   BASELINE IS RED -- fix that first; nothing below would mean "
              "anything.\n   %s" % baseline)
        return [(key, "baseline", False, "baseline red")]
    print("   baseline: %s\n" % baseline)

    results = []
    for fault in target.faults:
        touched = harness.apply_fault(fault)          # raises Stop if it did not land
        try:
            red, summary = harness.run_test_file(target.test)
        finally:
            harness.restore(touched)
        harness.require_restored(fault)

        ok = red == fault.expect_red
        print("   [%s] %s\n        wanted %-5s got %-5s | %s" % (
            "ok" if ok else "!!", fault.name,
            "RED" if fault.expect_red else "GREEN",
            "RED" if red else "GREEN", summary))
        if not ok:
            print("        ^^ %s" % (
                "the test did NOT notice this regression: it passes against "
                "code that is wrong."
                if fault.expect_red else
                "the control went red: the test is pinning the code's "
                "internals, not its behaviour."))
        results.append((key, fault.name, ok, summary))
    return results


def main(argv):
    if "--list" in argv:
        for key, target in sorted(TARGETS.items()):
            print("%-14s %-52s %d faults"
                  % (key, target.test, len(target.faults)))
        return 0

    wanted = [a for a in argv if not a.startswith("-")]
    unknown = [k for k in wanted if k not in TARGETS]
    if unknown:
        print("no such target: %s (try --list)" % ", ".join(unknown))
        return 2
    chosen = {k: TARGETS[k] for k in wanted} if wanted else TARGETS

    try:
        harness.require_clean_tree()
    except harness.Stop as stop:
        print("refusing to run: %s" % stop)
        return 2

    results = []
    try:
        for key, target in sorted(chosen.items()):
            results.extend(run_target(key, target))
            print()
    except harness.Stop as stop:
        print("\nSTOPPED: %s" % stop)
        print("\nThe run is incomplete, so it proves nothing about the faults "
              "that did not run.")
        return 2

    failed = [r for r in results if not r[2]]
    print("%d injections across %d target(s): %d as expected, %d not"
          % (len(results), len(chosen), len(results) - len(failed), len(failed)))
    for key, name, _ok, _summary in failed:
        print("  NOT AS EXPECTED  %s / %s" % (key, name))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
