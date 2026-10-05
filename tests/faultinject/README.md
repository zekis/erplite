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

One consequence, worth knowing before it confuses you: **do not run the whole
suite while a fault is applied.** That guard reads the source a fault names, so
any fault editing a line a pattern contains makes it red — correctly, and with
nothing wrong. `run.py` runs the target's own test file and only that, which is
the question being asked. If you want to check that a control is inert across
the app, run the suite under it with this one file ignored.

## The four ways this goes wrong silently

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
4. **Python serves the previous fault's bytecode.** A cached `.pyc` is reused
   when the source's size *and its mtime in whole seconds* both match what was
   cached. Faults are small, same-shaped edits to one file applied a fraction of
   a second apart, so that coincidence is the normal case, not a freak one: all
   twelve `frappe.get_list(` → `frappe.get_all(` edits in `scheduler_read_gate`
   leave `erplite/scheduler/api.py` at exactly 32531 bytes, and every target in
   here has at least one such pair.

   Found by running one fault twice with another between it and itself and
   getting two different answers: `test_the_refusal_is_loud` and friends went red
   the first time and green the second, because the second run was executing the
   neighbour's code.

   **What that did and did not cost, measured rather than assumed.** It corrupted
   *which tests* each fault turns red: the six/six split reported below first came
   out as two and ten, and that wrong number was written into this README before
   being caught. It did **not** change any `run.py` verdict — the pre-guard
   harness still reports 60 of 60 as expected across all four targets, three runs
   in a row — because every fault in every target here is also caught by an AST
   test that reads the source text, which no bytecode cache can affect. That is a
   fact about the current target set and not a property of this tool: **a fault
   guarded only by a behavioural test would have been reported GREEN**, and that
   is the dangerous direction, because a false GREEN reads as "the test does not
   notice this regression" and sends somebody to fix a test that is fine.

   So `apply_fault` deletes the cached bytecode for every file it touches and
   **stops** if any survives, `restore` purges too, and the test subprocess runs
   with `PYTHONDONTWRITEBYTECODE=1`. The three guards are complementary and were
   each checked by removing it and watching a test go red; the end-to-end
   misreading needs bytecode writing to be on, which is why switching it off is
   the first of the three.

Indentation is the same kind of property as the line ending, and it bit while
`whitelist_write_gate` was being written: `scheduler_log.py` is indented with
**tabs** and `scheduler/api.py` in the same module uses four spaces. A pattern
copied from one file to its neighbour matches nothing — silently, exactly like a
pass, and caught only by the match-count assertion. Never infer a file's shape
from a file beside it.

A fifth, which no guard can catch for you: **a negative control that goes red
is not a control.** It must change the source genuinely and change behaviour not
at all — a local variable rename, not a comment.

And a sixth, the same shape as all of them: **a count of red tests is not a
measurement — the set is.** "6 failed" is equally consistent with a test file
guarding the one role the defect affected and with one that refuses everybody.
Read the names. `pytest -rf` is not the place to read them from: its
short-summary lines mis-attribute both the test method and the subtest
parameters, and the same fault produced different labels on different runs.
unittest's own result object is the authority:
`{str(test) for test, _ in result.failures + result.errors}`.

A seventh, and the one this harness is best placed to find: **a test's data has
to straddle the boundary the test names, or it pins a range and not a number.**
`test_the_default_is_still_thirty_days` chose two dates 65 days apart and
asserted one of them went. That is true of a default anywhere from 1 to 64 days,
so the test passed with the default changed to 60 while claiming to pin 30. The
fix is the pair of dates immediately either side of the cutoff — and then a fault
on *each* side of 30, because a fault on one side only shows the test rejects
something.

## Adding a target

For each claim the test file makes, ask: *what edit to the real source would
make that claim false?* Then write it as a `Fault` in `faults.py` and run it.

Three habits earn their keep:

* **Break the behaviour, not the spelling.** An edit that renames something the
  test matches by name proves only that the test reads that name.
* **Include a negative control.** Without one, "every fault went red" can just
  mean the test file fails at the slightest touch, which is not the same thing
  as biting.
* **A guard that reports a list needs a second kind of control: one that
  changes behaviour and must still not be reported.** `whitelist_write_gate`
  sweeps the whole app for whitelisted endpoints reaching ungated writes, and
  five faults add such a write and must turn it red. All five would also pass
  against a sweep that reported *every* new write, so the same write is added to
  an endpoint that **is** gated and must stay green. That is not a no-op edit —
  it is a control for the classifier's discrimination rather than for the test's
  sensitivity, and the two are different claims. Say which kind each one is.
* **Cover every instance of the rule, not a sample.** A gate on four DocTypes
  needs four faults. A test that notices two of them is guarding two — and you
  cannot find that out from a sample of two that both went red. Doing this for
  all twelve call sites in `scheduler_read_gate` is what showed that half of them
  are guarded by the AST sweep *alone*, which no smaller sample would have told
  anyone.
* **Expect a fault to come back green, and treat it as a finding about the
  test, not a mistake in the fault.** One did here, and fixing the test was the
  right answer — see `scheduler_read_gate` below.

And one more, learned from adding the second target: **a fault on a DocType JSON
is worth as much as a fault on the code.** The rule in both targets asks frappe
for a permission rather than naming a role, so what it actually enforces is the
shipped rows. Granting the unprivileged role what the gate refuses is the only
injection that can tell you the test enforces those rows and not a role list of
its own — and it is the one most easily left out, because it does not look like
breaking the code.

## Targets

Five so far. Ten test files in this repo describe having been
fault-injected; these are the ones where that proof is reproducible.

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

### `timesheet_target_user` — `tests/offline/test_timesheet_target_user.py`

`save_timesheet_entries(entries, target_user)` took a `target_user` and gated it
on its own role list — `is_timesheet_admin()`, System Manager or Timesheet
Admin. That is narrower than Timesheet Entry's write rows, which also grant
Projects Manager. So a Projects Manager who sent `target_user` had it **silently
discarded**: the hours were booked against themselves and the endpoint returned
success with the entries listed, and nothing in the response carries `employee`,
so the caller could not tell whose timesheet it had written. The endpoint now
passes `target_user` through and the controller's rule above is the only rule
(PR #28).

12 faults, 11 expected red and one control:

* **the defect itself, restored** — the pre-#28 gate, verbatim. Worth reading
  the red set rather than the count: it is the Projects Manager test, the four
  refusal tests and the AST test, while **System Manager and Timesheet Admin
  stay green**. That is the shape of the real bug — it affected exactly one
  role — and a count alone would not show it;
* **`target_user` decided, used, or neither** — ignored outright, and decided
  but then not used at the line that writes the row. Two lines, so two faults: a
  test keyed on the decision would not notice the row;
* **a refusal arriving as one.** The endpoint wraps its whole body in `except
  Exception` and reports failure in a return value, so `success` flipped to True
  and the reason dropped from the message are the difference between "refused"
  and "quietly did something else";
* **the rule it defers to** — the controller's gate deleted, softened to
  `frappe.msgprint`, and `owner` left as whoever entered it. These are
  deliberately the same edits as `timesheet_ownership`'s, and that is the point:
  this test file claims the endpoint has no rule of its own, which can only be
  shown by breaking the rule it defers to and watching *this* file go red;
* **the premises, in the shipped rows** — Projects User granted write outright,
  and **Projects Manager losing write**. The second is the premise unique to
  this target: without Projects Manager holding write there was never a defect
  to fix, and it turns exactly the two tests red that name that role;
* **scope** — the role list swept out of a read endpoint as well. #28 narrowed
  one endpoint, not the module; `is_timesheet_admin()` is still the right gate
  for choosing whose data to *show*. Without this fault the AST test could be
  satisfied by deleting the role list everywhere;
* **the control**: the local variable renamed at all three occurrences. A real
  edit to the endpoint, no change in behaviour.

All 11 go red and the control stays green, against `main` at `03709ac`.


### `scheduler_read_gate` — `tests/offline/test_scheduler_read_gate.py`

Every `@frappe.whitelist()` function is callable by name over HTTP by any
logged-in user, so the Desk page is not the gate. The scheduler's read
endpoints used `frappe.get_all`, whose own docstring says it "will not check
for permissions", and never called `get_list` at all — so no scheduler read
consulted a permission row and `get_roles()` handed out every Scheduler Role
including `hourly_rate` to anyone with a login. The change is `get_all` →
`get_list` at the whitelisted read call sites (rev_d4b6b6ed62, PR #26).

This target has **two halves pulling in opposite directions**, which is what
makes it worth more than a sweep for one function name: the whitelisted reads
must apply the rows, and three internal integrity checks must keep *bypassing*
them, or a user with no read rows could delete a division that is still in use.

22 faults, 21 expected red and one control:

* **each of the twelve whitelisted read call sites reverted to `get_all`**, one
  fault apiece, across `scheduler/api.py` and three DocType controllers. The red
  sets are the result worth having, and they split the twelve exactly in half.

  **Six are covered both behaviourally and by the sweep:** `Project` in
  `get_projects_and_activities`, `Resource`, `Scheduler Role` (the charge rates,
  the headline of the whole finding — three tests), `Schedule Entry` in
  `get_schedule_entries` and in `get_unassigned_entries`, and `Schedule Row`.

  **Six are guarded by `test_every_whitelisted_scheduler_read_uses_get_list` and
  nothing else:** `Activity`; `Schedule Entry` in
  `get_resource_capacity_report`; and all four whitelisted reads in the DocType
  controllers (`division.get_active_divisions`,
  `division.get_division_projects`, `scheduler_role.get_active_roles`,
  `schedule_template.get_active_templates`). The reasons are plain once looked
  for: no test in the file calls any of those five endpoints — it loads
  `scheduler/api.py` and only that — and the `Activity` read is unreachable
  behaviourally because no shipped role can read `Project` but not `Activity`, so
  whoever is refused one is refused the other first.

  So that one AST test is carrying half of this file. Deleting it, or narrowing
  its `scheduler_sources()` walk to `api.py`, would leave six call sites with no
  guard at all — which is the kind of thing that looks like a tidy-up;
* **the three internal reads made to run as the caller** — `Division.on_trash`,
  `Scheduler Role.on_trash` (both of its reads) and
  `Schedule Entry.get_activity_progress`;
* **`Division.on_trash` whitelisted**, which turns a delete guard into an HTTP
  endpoint while leaving its `get_all` in place. The AST sweep for call sites is
  satisfied by it; only the internal-reads sweep notices. That fault is there to
  show the two sweeps are not the same sweep;
* **the premises, in the shipped rows** — an unrelated role (`Blogger`) granted
  read on `Project`; `Projects User` losing read on `Project`; `Scheduler User`
  losing read on `Scheduler Role`. These span `project.json` (**LF**) and
  `scheduler_role.json` (**CRLF**), in two different modules;
* **the recorded inconsistency made consistent, from both sides.** The shipped
  rows split the scheduler's DocTypes across two role families, so neither a
  Scheduler User nor a Projects User can load the scheduler. PR #26 pinned that
  as a position rather than widening the rows, and these two faults are how
  anyone finds out if it is ever revisited;
* **the control**: the local variable in `get_roles` renamed at all three of its
  occurrences.

**One fault came back green, and the test was what needed fixing.** Granting
`Scheduler User` read on `Project` left `test_a_scheduler_user_is_refused_project`
passing — because that user is refused `Activity` half a line later, and
`assertRaises(PermissionError)` cannot tell the two refusals apart. The test
named `Project` and was satisfied by anything at all refusing, so the class
docstring's promise that it would "go red if the rows are made consistent" was
false. `first_refusal()` now asserts *which* DocType did the refusing, and the
same assertion was added to the Projects User half, which was correct but for
no stated reason.

**One claim in this file cannot be fault-injected with the current machinery.**
`test_resource_role_really_is_undefined` checks that the DocType
`get_role_resources` is exempted for genuinely does not exist, and every fault
here is a content edit to a tracked file — a claim about a file's *absence*
would need the harness to create one, and restoring that means `rm`, not
`git checkout --`. Left out deliberately rather than faked.

All 21 go red and the control stays green, against `main` at `18c898c`.

The six/six split above is itself a measurement made *after* the bytecode guard
in point 4 was in place. Before it, the same sweep reported two and ten — and
that wrong number was written into this README before being caught. Three
independent runs of the attribution now give byte-identical results.

### `whitelist_write_gate` — `tests/offline/test_whitelist_write_gate.py`

The owner's decision on rev_18a8f8826d, and the whole-app generalisation of
rev_c3343b2cf3 that it belongs to. `clear_old_logs` is `@frappe.whitelist()` and
deletes through `frappe.db.sql`, which consults no permission row, runs no
`validate` and fires no hook — so until the gate landed, any logged-in user
could wipe the scheduler log by calling the method by name. It now asks whether
the caller may `delete` Scheduler Log, which the DocType's own rows give to
System Manager alone.

The test file has **two halves, and both are injected here**, because they fail
in different ways:

* `clear_old_logs` itself — the gate, and the argument handling around it;
* **a sweep of all 134 app modules** for whitelisted endpoints that reach a
  permission-bypassing write. `KNOWN_UNGATED` is empty, so that half passing is a
  claim about the whole app: no whitelisted endpoint anywhere reaches such a
  write ungated. A claim that strong is worth nothing unless adding one turns it
  red, and the sweep is also the part that would silently stop working.

28 faults, 26 expected red and two controls of two different kinds:

* **the gate, broken eight ways.** Deleted; asking about `read` instead of
  `delete` (which every Scheduler User holds); asking about the wrong DocType;
  `throw` dropped, so a `False` answer is ignored; a `doc=` added, which asks
  about one row and lets `if_owner` answer for the whole table; moved inside the
  `try`, where a handler could drop the refusal; moved *after* `days` is read,
  which turns the endpoint into an argument oracle for callers who may not
  delete; and nested in `if days:`, where `days=0` skips it.

  The red sets here are the interesting part, and they say something about the
  **stand-in** rather than the tests. Deleting the gate turns 9 tests red;
  asking the *wrong question* turns **14** red — every behavioural test in the
  file — because `PermissionChecks` refuses to answer anything other than
  `delete` on `Scheduler Log` and raises instead. A stand-in that had returned
  `True` for an unfamiliar question would have left all 14 green, and only the
  one test that inspects the recorded call would have noticed. That design is
  doing more work than any assertion in the file.

  Two of the nine are worth knowing about before they confuse someone: the gate
  deleted, or nested in a branch, makes `_without_the_gate()` raise instead of
  running, because it asserts the file contains exactly one `has_permission(`
  line. That is the helper correctly refusing to perform an injection it cannot
  perform — a red from an error rather than a finding, and the right answer;
* **`days`, which the caller chooses and which carries no type annotation**, so
  frappe coerces nothing and a JSON body can send a negative int. A negative
  `days` accepted (the cutoff goes into the future and every row matches);
  `days=0` refused, which is a meaning a caller can legitimately have; a
  non-numeric `days` read as 0 rather than refused, which is `cint()`'s reading
  of a typo and the worst one available; the cutoff computed forwards; and the
  default retention changed, **on both sides of 30** — see the seventh trap
  above, because that pair started as one fault that came back green;
* **what it reports, and whether the work lands.** The count read off the
  DELETE's own result — the bug the endpoint shipped with, since `frappe.db.sql`
  returns `()` when the cursor has no description, so it reported 0 however many
  rows it removed; counting after deleting, which has the same effect by a
  different route; and the commit removed;
* **the rows the gate rests on.** The endpoint invents no policy — it asks
  frappe, and frappe answers from `scheduler_log.json` — so the rows are part of
  the behaviour. System Manager losing `delete`; Scheduler User granted
  `delete`; Scheduler User granted `write`;
* **the author's own intent, in the client script.** `scheduler_log.js` offers
  the "Clear Old Logs" button only `if (frappe.user.has_role('System Manager'))`.
  The button is not the gate and never was, but it is the evidence that
  enforcing `delete` narrows the endpoint to who was meant to have it, so the
  fault widens the button to Scheduler User. First fault in this harness to edit
  a `.js` file;
* **the sweep — five faults, each of which must turn it red on its own.** An
  unchecked `db.set_value` added to an ungated whitelisted endpoint; a raw
  `DELETE`; a write **one level down**, in a helper that an ungated endpoint
  calls; a statement built as a Python string, which cannot be read and so must
  be *reported* rather than excused; and one of the six Xero endpoints losing
  its gate, seen through the sweep instead of through its own test file.

  The host matters for two of those. `get_scheduler_data` is a read endpoint
  with no gate — 73 of the app's 88 whitelisted endpoints have none, which is
  fine while they do not write, and is exactly where such a write turns up. And
  the one-level fault goes into `get_resource_utilization`, which is **not**
  whitelisted, so the only way the sweep can see it is by following the call
  from `get_resources`; checked by reading what the classifier reports under the
  fault, which names `get_resources` with no write of its own and the helper in
  `via`. Had the helper been whitelisted too, the red would have proved nothing
  about the follow;
* **control 1**, the ordinary kind: the locals in `clear_old_logs` renamed. Real
  edit, no behaviour change;
* **control 2**, the discrimination kind: the same unchecked write the five
  sweep faults add, added instead to an endpoint that **is** gated
  (`approve_timesheet`). It must not be reported. This one does change
  behaviour, deliberately — see "Adding a target" above.

All 26 go red and both controls stay green, against `main` at `ec17e3d`.

**One fault came back green, and the test was what needed fixing** — the second
time that has happened, and in the same direction as `scheduler_read_gate`'s. See
the seventh trap: `test_the_default_is_still_thirty_days` was pinning a range.
Fixed in the same commit, with a fault on each side of 30 to show the fix bites
both ways.

**What this target does not reach.** The sweep's own machinery — `classify`,
`_resolve_helper`, the module scoping — is tested against synthetic source inside
the file, and those tests cannot be fault-injected from here: there is no
real-source edit that makes "a gate is not inherited across modules on a name
match" false. The five faults above measure the sweep end to end against the real
app, which is the half that can rot without anyone noticing.
