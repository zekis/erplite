# Fault injection: do the tests actually bite?

A green test tells you it passed. It does not tell you it would have gone red
had the code been wrong. A test that cannot fail is worse than no test, because
it reports safety it does not provide.

This directory breaks the code on purpose and checks the tests notice.

```sh
python tests/faultinject/run.py              # every target
python tests/faultinject/run.py xero_gate    # one target
python tests/faultinject/run.py --list       # what there is
```

Exit status is 0 only if every fault was applied, every fault turned its test
file red, and every control stayed green. A fault that *could not be applied*
is a failure too: an unmeasured claim and a false claim are the same thing to
whoever reads the result.

**Commit before you run it.** It edits real source files and restores them with
`git checkout --`, which discards uncommitted work. It refuses to start on a
dirty tree for that reason — that refusal is the most important line in here.

Nothing in this directory is named `test_*`, so pytest never collects it. The
ordinary suite cannot edit your source by accident.

## What is in here

| file | what it does |
| --- | --- |
| `run.py` | runs the targets, reports, exits non-zero on anything unexpected |
| `harness.py` | apply an edit, prove it landed, run a test file, restore |
| `faults.py` | the faults: what to break, and which test file should notice |

`tests/offline/test_faultinject_harness.py` is part of the ordinary suite. It
reads and never writes, and it asserts every fault below still matches exactly
the one place it names — so a fault that has rotted is reported in the commit
that moved the code, not months later when somebody next runs this by hand.

## The three ways this goes wrong silently

Each guard exists because the mistake has actually been made in this repo, and
each turns a false pass into a hard stop.

1. **The edit matches nothing.** A pattern written with `\n` matches zero times
   in a CRLF file. Six of the first twelve faults written for
   `test_xero_permission_gate.py` matched nothing for exactly this reason;
   without the match-count assertion they would have been reported as six
   passes. Write patterns with `\n` and let `harness.nl` translate them.

   **This repo's line endings are mixed, so the ending is a property of the
   file and never of the repo.** Measured 6 Oct 2026 from the committed blobs:
   82 CRLF `.py` files and 62 LF, 31 CRLF `.json` and 22 LF. The split runs
   *inside* one DocType folder — `timesheet_entry.py` is CRLF,
   `timesheet_entry.json` beside it is LF — which is why `harness.read`
   detects each file's own ending. The first version of this harness asserted
   every file a fault named was CRLF; that was true of everything the first
   target happened to touch, and the second target failed it immediately.

   **Nor is it a property you can read off your own working tree.** With
   `core.autocrlf=true`, git's default on Windows, the LF files are checked out
   as CRLF and that mixture is invisible locally. `harness.read` is unaffected,
   because it reads whatever is actually in front of it — but two tests that
   described the mixture by reading the working tree passed in a Linux sandbox
   and failed on Windows. They read `git cat-file` now. If you write something
   that asserts what *the repo* holds, read the blob; the working tree only
   tells you about your own checkout.
2. **The edit matches more than once**, lands somewhere unintended, and the red
   you get is not the red you asked for.
3. **Restoring destroys uncommitted work.** Hence the clean-tree refusal.

A fourth, which no guard can catch for you: **a negative control that goes red
is not a control.** It must change the source genuinely and change behaviour not
at all — a local variable rename, not a comment.

## Adding a target

For each claim the test file makes, ask: *what edit to the real source would
make that claim false?* Then write it as a `Fault` in `faults.py` and run it.

Three habits earn their keep:

* **Break the behaviour, not the spelling.** An edit that renames something the
  test matches by name proves only that the test reads that name.
* **Include a negative control.** Without one, "every fault went red" can just
  mean the test file fails at the slightest touch, which is not the same thing
  as biting.
* **Cover every instance of the rule, not a sample.** A gate on four DocTypes
  needs four faults. A test that notices two of them is guarding two — and you
  cannot find that out from a sample of two that both went red.

And one more, learned from adding the second target: **a fault on a DocType JSON
is worth as much as a fault on the code.** The rule in both targets asks frappe
for a permission rather than naming a role, so what it actually enforces is the
shipped rows. Granting the unprivileged role what the gate refuses is the only
injection that can tell you the test enforces those rows and not a role list of
its own — and it is the one most easily left out, because it does not look like
breaking the code.

## Targets

Two so far. Ten test files in this repo describe having been fault-injected;
these are the ones where that proof is reproducible.

### `xero_gate` — `tests/offline/test_xero_permission_gate.py`

Six `@frappe.whitelist()` endpoints write to the owner's real Xero ledger, and
are gated on each DocType's own permission rows (rev_c3343b2cf3). The contact
path also used to post to Xero and then save a document read before the post,
which could not succeed and duplicated the contact on the next attempt
(rev_6c9dc08cf7).

14 faults, 13 expected red and one control:

* the gate deleted, on each of the six endpoints in turn — one fault each,
  because Sales Invoice passing tells you nothing about Supplier;
* the gate present but useless: moved inside the `try`, where `except
  Exception` relabels a 403 refusal as a failed send; and `throw=False`. Both
  would pass a test that only looked for the call;
* the DocType JSON rows granting the unprivileged role `write`, and `create`
  without `write`. These are what prove the test enforces the shipped
  permission rows rather than a role list of its own — if it were hardcoded,
  granting the role access would change nothing;
* the duplicate-contact defect restored: the stale `save()` after the post, the
  already-sent guard removed, and the commit removed;
* **control:** a local variable rename in `customer.py`.

All 13 go red and the control stays green, against `main` at `9df2adc`.
### `timesheet_ownership` — `tests/offline/test_timesheet_employee_ownership.py`

Two fields answer "whose timesheet is this": frappe decides who may read and
write from `owner`, the app decides whose hours they are from `employee`, and
nothing kept them in agreement. So any Projects User could insert an entry
naming a colleague (`create` is the one right `if_owner` never restricts) and
the hours counted as that colleague's everywhere the app looks; and an entry
booked *for* you by someone else could not be corrected by you. On insert, an
`employee` other than the session user now needs write on the DocType, and
`owner` then becomes that employee (rev_84dce415b5, PR #27).

12 faults, 11 expected red and one control:

* **the gate removed or defeated** — deleted outright; `frappe.throw` softened
  to `frappe.msgprint`, so the refusal becomes a warning and the insert still
  happens; and the permission asked about *this row* (`doc=self`) instead of the
  DocType, where `if_owner` answers yes for a row the booker owns and the gate
  silently permits what it was built to refuse;
* **the authority test replaced by a hardcoded role list.** The rule names no
  role on purpose. With `"System Manager" not in frappe.get_roles()` in its
  place, a Projects Manager — who holds write in the shipped rows — stops being
  allowed, and four tests say so;
* **`owner` left as whoever entered it**, which removes the half of the change
  that lets the employee correct their own hours;
* **the wiring** — `validate()` no longer calling the rule, and the rule run
  *before* `set_employee_default`, where a blank `employee` is judged before it
  is filled in and booking your own time is refused;
* **insert-only, which is structural.** The `is_new()` guard dropped, so the
  rule reaches every save and refuses the six approval paths that exist to act
  on someone else's entry (Afterz's submit, approve, reject and un-approve, and
  erplite's own `approve_timesheet` and `reject_timesheet`); and `owner`
  re-pointed on every save as well, which would hand a row to whoever it was
  last booked for;
* **the premises, in the DocType JSON** — `if_owner` dropped from the Projects
  User row, so that role holds write outright and the gate permits a colleague's
  name; and `employee` made read-only, which would make the whole gate moot.
  This is the LF file of the CRLF/LF pair above;
* **the control**: the rule's two early returns swapped. Both return with no
  side effect, so the source changes and the behaviour does not. If it goes red,
  the test file is pinning the order the guards are written in rather than the
  rule's effect, and the test is what needs fixing.

