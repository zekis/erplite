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

An eighth, which is where that one leads: **a chain of branches partitioning a
continuous range makes one claim per branch and one more per instant where two of
them meet, and the instants are the only data that pins the comparisons.**
`trip.py` derives a status from `now < departure`, `departure <= now <= arrival`,
`now > arrival`. Every date in `test_trip_status.py` sat in the middle of a
window, so all three arms were pinned and neither edge was: `<` could become
`<=` on one side and `<=` could become `<` on the other with the whole file
green. A window a fortnight wide tells you nothing about its own edges. Four
positions fix it — each instant, and the tick either side — and they are cheap,
because a test that freezes the clock can place a document exactly on one.

And a ninth, which took eight targets to meet: **a fault that comes back green
because it changes nothing is a finding about your model of the code, not about
the test — keep it, as a control.** Every green fault before this one was a gap
in a test. This one was a gap in me: I swapped two guards in `before_save`
believing their order was load-bearing, because the test file's own docstring
said so. Both guards do nothing but `return`, so the order cannot matter, and
the docstring was wrong. The two outcomes look identical in `run.py` — `wanted
RED got GREEN` — so when one happens, the question is which, and the way to tell
is to work out what the edit changes for a caller before deciding the test is at
fault. A wrong fault is worth keeping once you know why it is wrong: it is the
only place an equivalence gets written down.

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
* **If you fix the test in the same pass, go back and watch the fault go
  green.** Writing the fault and the missing test together means you never see
  the before-state, so "this fault would not have bitten" is a guess about your
  own work. It is cheap to measure: put the old test file back on a throwaway
  commit and run the new faults against it. Doing that for `xero_invoice_send`
  turned up exactly the five that were predicted — which is the only reason
  that number is in this README rather than an estimate.
* **A rule written out once per DocType is guarded once per DocType, and
  rarely evenly.** See `xero_invoice_send`: deleting the duplicate-send lookup
  from the sales path turns seven tests red, and deleting the identical call
  from the purchase path turns exactly one. The code is symmetric and the test
  file looks symmetric; the guarding is not, and only one fault per copy shows
  it.

* **When the thing under test is a *detector*, the faults are the bug it was
  written to find — and the question changes shape.** Eight of the nine targets
  here ask of a behavioural rule: would this test notice if the rule broke? The
  ninth (`post_save_writes`) asks it of a whole-app sweep, and there the useful
  question is not "is the rule pinned" but **"what can real code do that this
  detector cannot see?"** You cannot answer it from the detector's own unit
  tests, because those are synthetic fixtures the author wrote: they pin the
  shapes the author thought of, and are silent by construction about the ones
  they did not. The answer only comes from planting real ones in real source.
  Eight of eleven exceptions in that target's first run were shapes nobody had
  thought of — including `self.set("status", x)`, frappe's own setter.
* **A detector needs a third verdict, and conflating it with a control is a
  reporting bug.** `run.py` has two: red-expected and green-expected, and
  green-expected reads as "equivalent edit, no bug here". For a detector some
  faults are green because the regression is **real and deliberately invisible**
  — closing it would need control flow or data flow, and a wrong finding costs
  more than a missed one. Those are the opposite claim wearing the same colour.
  `post_save_writes` names them `KNOWN BLIND SPOT: ... (green: <why>)` against
  `CONTROL: ... (must stay green)`, and the test file lists them in a
  "What this cannot see" section, so a green run is read for what it is.

And one more, learned from adding the second target: **a fault on a DocType JSON
is worth as much as a fault on the code.** The rule in both targets asks frappe
for a permission rather than naming a role, so what it actually enforces is the
shipped rows. Granting the unprivileged role what the gate refuses is the only
injection that can tell you the test enforces those rows and not a role list of
its own — and it is the one most easily left out, because it does not look like
breaking the code.

## Targets

Fifteen so far, 460 injections: edits applied to the app's real source, with
`run.py` watching one test file go red.

Two other test files do fault injection of their own, inside the file —
`test_mandatory_fields_on_insert.py` and `test_projects_api.py`. Those plant
shapes in their own fixtures rather than editing the app, so `run.py` does not
drive them, and what they prove is narrower: that the sweep reads what its
author planted. `string_refs` below is what that distinction costs.

`test_afterz_timesheet_workflow.py` was in that list until the thirteenth
target. It had a test named "the fault-injection half, so a green run above
means something" — one fault, planted in its own fixture. Driving the same file
from here found **twelve regressions it did not notice**, which is the
difference between a file that injects a fault and a file that has been
injected into. If a file below says it tests itself, that is a reason to point
`run.py` at it, not a reason to skip it.

`test_query_fields.py` was in that list until the fourteenth target, and it
makes the point twice over, because it is a *sweep*: its self-tests run the
detector over synthetic snippets, which proves the detector understands a
shape, never that the sweep reaches that shape where it really occurs. Three
of those two claims came apart — see `query_fields` below.

`test_undeclared_attributes.py`, the fifteenth target, is the opposite case and
worth naming beside it: it had **no self-tests at all**. Three whole-app sweeps,
three `assertEqual([], findings)` calls, and nothing anywhere that asked whether
a violation put in front of them would be reported. Seven of twenty-two faults
were green. A sweep that tests itself over-claims about its reach;
a sweep that does not test itself has made no claim anyone can check.

### `undeclared_attrs` — `tests/offline/test_undeclared_attributes.py`

Three whole-app sweeps in one file, after the regression that stopped the
scheduler creating entries: `Schedule Row.task` was written by code and declared
by no DocType, so every row saved with no work attached and nothing raised. The
sweeps are a controller one (`self.<x>` against its own DocType's fields, split
hot/cold by whether a new-document hook reaches it), a read one (anywhere in the
app, on documents built in memory) and a write one (anywhere, however the
document arrived). **22 faults, seven green.** Two more were added for a shape
the fix introduced, so 24 now.

Every one of the seven was on the same side of the sweep. Not one was a shape it
misunderstood; all seven were shapes it never asked about — and the useful
generalisation is why they were invisible:

**A sweep's documented scope limits and its undocumented blind spots look
identical from the outside.** Both are green. This file documents, at length and
correctly, that a document loaded by `get_doc("X", name)` is out of scope for
the *read* sweep: it is populated by `SELECT *`, so an orphan column is really
there and reading it returns something stale rather than raising. The
implementation of that limit resolved a loaded binding to **nothing** — which
marked the variable *unresolved*, and the conservative rule then dropped the
variable altogether. So `save_timesheet_entries`, which binds `timesheet_doc`
from `get_doc("Timesheet Entry", id)` in its update branch and from `new_doc` in
its insert branch, was read-checked in **neither** branch, although the new-doc
branch still raises. "Out of scope" and "we cannot tell what this is" are
different facts, and conflating them turned a deliberate limit into a hole of
unknown size — *behind the limit's own documentation*, which is what made the
green look earned. The rule is now applied per binding: a loaded binding agrees
about the DocType and only declines to be reportable, so a purely-loaded name is
still dropped (the limit, intact and still measured by its own fault) while a
name some other binding builds in memory is checked.

**A write does not have to look like `doc.x = v`.** The write sweep read
attribute assignment and nothing else, so `self.db_set("x", v)`,
`doc.update({...})`, `setattr(doc, "x", v)` and `doc.set("x", v)` were all
invisible. The cheapest way to find that, and the same move that worked in
`query_fields`: **ask which shapes the app actually writes, not which shapes the
sweep already lists.** `db_set` is the answer here — **five of the six `db_set`
sites in this tree** are the `self.db_set("x", v)` form, in DocType controllers,
and it is the worst shape to miss because it is the one that does not merely get
dropped: `db_set` builds its `UPDATE` from the name it was handed rather than
from `get_valid_dict()`, so an undeclared name is a failed statement, not a
discarded value. There are no `setattr` sites and no `.update({...})` on a
document, so those two cost nothing in noise — but `self.set(...)` and
`doc.set(...)` were implemented at the same time and *nothing measured them*,
which is this target's own subject, so two faults were added rather than
shipping a fourth shape on the strength of reading the code.

**The one that needed a new rule rather than a wider walker.** A controller
writing `self.<undeclared> = v` loses the value on save: computed, dropped by
`get_valid_dict()`, and the document still saves. But this file's stated
position — correctly — is that a controller may invent attributes of its own,
which is precisely why `scan.assigned` is in the *read* sweep's known set. So
"it is assigned here" cannot also be what excuses the write; that reasoning is
circular and would make the rule report nothing. What actually separates a
working transient from a lost field is that **a transient is read back somewhere
in the class**. An undeclared attribute that is only ever written is not a
transient, it is a dropped field. The app has zero such writes today — measured,
not assumed — so the rule costs nothing, and the control that holds the file to
its position (assign `self._open_entry`, then read it back) stays green.

**The coverage-collapse pair, and the schema half is the worse one.**
`query_fields` found that a file the sweep cannot parse contributes no findings
and says nothing, so coverage can shrink with every assertion green. The same
hole was here, in all three sweeps. But the DocType JSONs are the half worth
transferring: `_app_doctypes` dropped an unparseable JSON with a bare
`continue`, which dropped the DocType from the map — and **the map is what
"undeclared" is measured against**, so the `doctype in doctypes` guard
downstream then made every violation on that DocType unreportable, in every file
in the app, not just in the one that would not read. A detector losing its
*standard of comparison* is quieter than a detector losing its input: the second
shows up in a parsed-file count, the first shows up nowhere. Both are now
collected and asserted empty.

**Two faults I got wrong, and both failures were in the measuring, not the
code.** The first: the two "the sweep cannot parse this" faults originally
planted `'this is not python'`, which **is valid Python** — `is not` comparing
two names. Those files were never unparseable; they went red for the ordinary
reason, and "the sweep notices its coverage collapsing" was about to be recorded
as measured. The tell was reading the code instead of the colour: one case was
red where the source plainly said `continue`. **`ast.parse` a planted syntax
error before trusting it**; `(((` is a real one. The second: a pre-flight script
written to check every pattern matched exactly once reported **24 of 24
patterns broken**, because it read the files with `newline=""` and the sources
are a mix of CRLF and LF, which the harness normalises and it did not. A
measuring tool failing looks exactly like the thing it measures failing — and
the tell was the count, for the third time in three targets: 24 of 24 is not a
plausible number of broken patterns. **Read the count before you believe the
verdict**, now including the verdicts of your own instruments.

**How each red was attributed.** A green run of the fixed file proves the faults
land, not that this change is what lands them. So the 24 faults were run again
against the **old** test file: exactly nine flipped to green, and they were
exactly the seven holes plus the two new `set` faults. Everything else —
including all three controls and scope limits, and the one parse fault that was
already red for the wrong reason — behaved identically against both versions.

**What a target cannot tell you: the blast radius.** `_app_doctypes` is shared.
Changing its signature broke **ten tests in two other files** that import it,
and `run.py` on this target was green throughout, because `run.py` runs one test
file. The full offline suite found it. Those two call sites now take the tuple
and discard the unreadable list deliberately: an unreadable JSON shrinks their
coverage too, but it is one fact that only needs to be loud once, and no DocType
JSON can stop parsing without this file going red in the same run. That is
written at the helper rather than left for someone to infer from two call sites
that look unguarded.

**What this target does not reach**, now pinned in `TestWhatTheseSweepsCannotSee`
rather than left in prose: a document arriving as a function parameter (so every
module-level helper taking a doc), a fieldname assembled at runtime, child rows
added by `doc.append("rows", {...})` whose keys belong to a DocType these sweeps
never resolve, and a name bound from two different DocTypes in one function,
which is dropped by the conservative rule — a violation hidden behind a
disagreement is the price of never reporting one. That class also holds the one
rule `run.py` **cannot** measure: the hot/cold split asserts empty in both
buckets, so a change collapsing one into the other would fail nothing. It is
tested directly, on a class whose `validate()` reaches a helper two self-calls
deep and whose `on_trash()` reaches one that must stay cold.

### `query_fields` — `tests/offline/test_query_fields.py`

A whole-app sweep: every `.py` under `erplite/`, every query, reported if it
names a field its DocType does not declare. The app has made that mistake twice
(`Activity.subject`/`assigned_to`, then `Timesheet Entry.date`) and `bench
migrate` never drops a column, so the orphan is still there to be read.

The 29 faults put a real undeclared field into a real query in a real file —
one per call shape the sweep claims, and one per area of the app (DocType
controller, `api` module, `www/` page, patch, dashboard widget), because
"whole-app" is the claim being measured. Most use `subject` or `date`: a fault
that puts back the app's own historical mistake is the regression the sweep
exists to stop, not an invented string.

**Three of the 29 were green, and all three were holes in the sweep, not in the
faults.**

* **The fieldname given by keyword.** `get_value`/`set_value`/`get_single_value`
  were read only in their positional forms, so
  `frappe.db.get_value(dt, filters=..., fieldname="x")` was unswept — and that
  is the form `erplite/xero/api.py:50` already uses. The uncovered shape was not
  hypothetical; it was in the tree, and it happened to name a standard column.
* **The DocType given by keyword.** `scan_tree` began `if not node.args:
  continue`, so a call written entirely in keywords had no positional arguments
  and every field in it was invisible.
* **A file the sweep cannot parse.** `except (SyntaxError, OSError): continue`
  meant an unreadable file contributed no findings and said nothing, so the
  sweep's coverage could shrink without a single test going red. It is now a
  finding in its own right.

All three are fixed and pinned by self-tests. The sweep found nothing new in
the app once fixed, which is the result to want and not the result to assume:
the point of the run is that the next bad query will be reported, whichever of
these shapes it is written in.

**Two faults I had to rewrite, and the reason is the more useful half.** Both
went green, and neither was the sweep's fault:

* `get_all("DT", ["name", "date"], ..., fields=[...])` added a positional
  *beside* the keyword. That is a `TypeError` at runtime and `fields=` wins; the
  sweep was right to ignore it. The shape that occurs is positional-only.
* `filters=[[...]] + extra` is a `BinOp`, not a list literal, so it falls under
  the same rule that makes a non-literal DocType unjudged. Recorded as a
  documented limit with a test, rather than quietly fixed into scope.
* And a third, which is the same mistake as the bad control in `afterz_workflow`:
  the keyword-DocType fault at first only changed `get_all("Schedule Row", ...)`
  to `get_all(doctype="Schedule Row", ...)` and left every field declared. **A
  fault that changes the shape but not the violation proves only that the shape
  parses.** Read what the edit actually does before believing the verdict.

Found while writing this and left alone deliberately, because it is an app
decision and not a test's to make: `Scheduler Role.on_trash()` queried
`"Resource Role"`, a DocType that exists nowhere in this repo — no JSON, no
Table field pointing at it. The sweep is silent on it by design (it judges only
DocTypes the app defines), which is exactly the blind spot an unknown DocType
leaves.

**Settled since.** The owner's answer was that there was never meant to be a
`Resource Role` table, so that read was dead code and it made every
`Scheduler Role` undeletable — `get_all` raises `TableMissingError` before it
runs any SQL. It is gone, with
`tests/offline/test_scheduler_role_delete.py` on it. `get_role_resources` and
`get_role_statistics` still read the missing DocType and are still an app
decision, so the blind spot described above is still worth having in mind.

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
  `Scheduler Role.on_trash` and
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

### `xero_invoice_send` — `tests/offline/test_xero_invoice_send.py`

The owner's two decisions on the Xero invoice send (rev_7b11901cfb,
rev_5c3dfe6ff3). Every invoice goes to Xero as a `DRAFT`, because invoices are
reviewed and approved in Xero and not in this app; and a send whose reply is
lost must not become a second invoice in the real ledger, which
`find_invoice_in_xero` prevents by asking Xero before posting.

Both decisions land in near-copies: `create_sales_invoice` and
`create_purchase_invoice` in `erplite/xero/accounts.py`, and a `send_to_xero`
written out once per DocType. So every fault that can be made on one side is
made on both.

30 faults, 28 expected red and two controls:

* **the status**, four ways. The removed `"AUTHORISED" if status == "Submitted"`
  branch restored verbatim on each call site — and then the same mistake made
  *without the word*, `cstr(doc.status).upper()`, because
  `test_the_module_no_longer_mentions_authorised` reads the source and would
  catch the first pair on their spelling alone. The second pair is what shows
  the behavioural tests carry it: each turns exactly one test red, the one whose
  document arrives with `status == "Submitted"`;
* **what is recorded locally** taken from our own document instead of Xero's
  answer — the two agree today and differ precisely when Xero disagrees;
* **the lookup deleted**, once per call site: the exact state before the fix;
* **the lookup still called, but from inside the `try`**, where
  `except Exception` hands the stop back as "Error creating invoice in Xero:
  ...". Its position outside that `try` is the whole of what makes a stop read
  as a stop, and it is one line of indentation away from being lost;
* **the re-wrap in `send_to_xero`** restored ("Failed to send invoice to Xero:
  Xero already has this invoice"), once per DocType, plus the already-sent guard
  deleted once per DocType, plus the Error Log entry for a stop dropped — the
  only trace a send with an unknown outcome leaves;
* **`find_invoice_in_xero` answering "not there" on doubt**, in each of the four
  ways it can be in doubt: unreachable, non-200, an answer it cannot read, and a
  filter Xero ignored. All four are injected in the dangerous direction, since
  `None` means "go ahead and post";
* **what counts as a match**: `VOIDED`/`DELETED` no longer skipped, narrowed to
  `VOIDED` alone, `Type` dropped, the contact's name dropped, and the lookup no
  longer asking Xero for the one number;
* **the timeout**, one fault per module (`accounts.py`, `auth.py`, `client.py`)
  because the claim is that no call site in the package is left out and the sweep
  walks every file in it; `auth.py` using `XERO_HTTP_TIMEOUT` without importing
  it; and the value itself as a bare number and as a pair with the read shorter
  than the connect;
* **two controls**, both ordinary: a local renamed in `find_invoice_in_xero`,
  and a local renamed in Sales Invoice's `send_to_xero`. Two files, because the
  tests read both.

All 28 go red and both controls stay green, against `main` at `7fe563a`.

**Five faults came back green against the test file as it stood, and the test
file was what needed fixing** — measured, not inferred: the old file was put
back on a throwaway commit and the new faults run against it, and exactly the
five predicted passed. Three were untested claims the file's own docstring
makes (an unreadable answer stops the send; `DELETED` frees the number as
`VOIDED` does; the purchase-side already-sent guard), fixed by adding the three
tests. The other two needed an existing test strengthened: both stop messages
were asserted with `assertIn`, which cannot tell a stop from a stop wearing a
failure's prefix, so the lookup could move inside the `try` and the purchase
`send_to_xero` could re-wrap its stop with every assertion still passing. They
now assert the message arrives with no prefix at all.

**The red sets are very uneven between the two copies.** Deleting the lookup
from the sales path turns seven tests red; deleting the identical call from the
purchase path turns exactly **one**,
`test_the_same_number_from_the_same_supplier_does_block_a_bill`. Everything
protecting the owner's real ledger from a duplicated *bill* rests on that single
test. Worth knowing before anyone tidies it, and the reason the fault is split
per call site rather than written once.

**One fault is caught twice over, and it is worth knowing which half you are
reading.** Dropping the timeout from the lookup `GET` turns 17 of the 23 tests
red, not because 17 assertions are about timeouts but because `FakeXero.get`
asserts `timeout is not None` on every call, so every behavioural test fails as
well as the AST sweep. The sweep is the half that generalises to the package;
the stand-in's assertion only covers the two calls it serves.

**What this target does not reach.** Whether Xero itself rejects a duplicate
`InvoiceNumber` — that needs a real write to the owner's accounts, and the point
of the change is that the app no longer sends the second one. And the four
`except Exception: frappe.throw(...)` handlers wrapping the POST itself are only
exercised through the lost-reply path; a fault on the POST's own error handling
would need Xero stand-ins this file does not have.

### `todo_assignment` — `tests/offline/test_todo_assignment.py`

The todo kanban page (`erplite/www/todo/index.py`): anyone may assign a todo to
anyone, and whoever created or handed one on keeps track of it afterwards. That
is frappe's own ToDo rule — `allocated_to == user or assigned_by == user or
owner == user` — and the page writes it out **three times**: as
`_can_manage_todo` for the writes, as the board's `or_filters` for the lists,
and again in JavaScript as `canEditTodo`.

41 faults, 38 expected red and 3 controls:

* the pre-fix rule restored (allocated_to only), then **one fault per clause**
  of the three-way OR, in both the server's copy and the board's — plus the
  rule widened to everybody, which is the other direction;
* who counts as a manager: `Has Role` asked for the row's `name` instead of the
  user's `parent`, `Administrator` dropped from `MANAGER_ROLES`, and the role
  filter dropped so that any role at all counts;
* `create_todo`: the chosen assignee overwritten with the caller (the exact
  pre-fix bug), the default assignee dropped, `assigned_by` recorded as the
  assignee, a new todo starting in `Open`;
* `update_todo`: the hand-over not recorded, every edit treated as a hand-over,
  `allocated_to` written when the caller sent none, and the todo re-created
  instead of saved (Afterz's `Planner Entry` points at it by name, and
  `ignore_links_on_delete` covers it, so frappe will not catch that);
* the rule's two call sites broken one endpoint at a time, and `delete_todo` —
  deliberately narrower than updating — broken in both directions;
* the board: each clause of `or_filters`, both status filters (one per branch of
  `if is_manager`), and every non-manager handed the manager's query;
* the three fields the page decides its own permissions from, one fault each,
  and `owner` dropped from the fields the query asks for;
* the client's copy: `canEditTodo` losing a clause, and `canDeleteTodo` widened
  to the editor's rule so the button would fail on the click;
* three controls — a local renamed in `get_context`, one in `delete_todo`, and
  one in `TodoDataManager.makeRequest`. The last matters because two tests here
  read source text rather than run it, and would otherwise be satisfied by any
  edit at all to that file.

**Six faults came back green against the test file as it stood, and in every
case the test file was what needed fixing.** They were measured before the
repairs, not reasoned about afterwards: the faults were written and run first,
on a commit with main's test file. Five new tests close them.

**The finding: one rule, written twice, pinned as a whole in one copy and
clause by clause in the other.** Deleting any single clause from
`_can_manage_todo` went red; deleting the same clause from the board's
`or_filters` went **green, all three times**. The code is symmetric. The
difference is in the fixtures: the update tests hand a todo on, which leaves
documents matching exactly one clause each (handed on by you, created by you,
with you), so they reach the clauses separately as a side effect of what they
were testing. The board's two fixtures were the creator's by all three fields
at once, and a three-way OR is satisfied by any one of them. Three fixtures
reachable through exactly one field each fix it. `frappe.get_all` passes
`ignore_permissions=True`, so these filters are the whole of what a non-manager
sees — there is nothing behind them to catch a clause that goes missing.

**A table that only holds the positive case cannot falsify the predicate that
reads it.** `Has Role` was built for the managers only, so every non-manager
held no role at all — and in that world "System Manager or Administrator" and
"any role whatsoever" give the same answer for every user. Dropping the role
filter entirely was green. Now everybody holds a role and only the managers
hold a managing one: the same fault turns 5 tests red. The same gap left
`Administrator` — half of `MANAGER_ROLES` — pinned by nothing; it now has one
test, and that one test is all that guards it.

**An actor who is also the value being overwritten hides the overwrite.**
`if allocated_to is not None and ...` became `if allocated_to != ...`, so a
description-only edit unallocated the todo. Green: the only assertion after a
plain edit was on `assigned_by`, the edit was made by the creator, and the
creator is also what `assigned_by` would have been overwritten with. The wrong
code and the right code agreed on the one field being read. Generally: when
asserting that a field is left alone, make the actor differ from what the bug
would write there.

**One fault is caught ten times over, and not for the reason the number
suggests.** Dropping `owner` from `todo_fields` turns 10 of 34 red — not ten
assertions about `owner`, but `fake_frappe._dict` raising `AttributeError` on a
key the query never asked for, in every test that builds a board. The
stand-in's strictness is carrying that one, not the file's assertions.

**What this target does not reach.** `canEditTodo` and `canDeleteTodo` are
checked by reading the JavaScript as text, so those two tests pin the spelling
of both method names as well as their contents — renaming either would go red
without any behaviour changing. That is deliberate (there is no JS runtime
here) but it means the client half is guarded by a name match, not by running
anything. The eight call sites that gate a card's controls on `canEditTodo` are
not covered at all.

### `trip_status` — `tests/offline/test_trip_status.py`

A derived field a user is also allowed to set by hand. `Trip.before_save`
derives `status` from the trip's dates; `trip.js` offers "Start Trip" and
"Complete Trip" buttons that `set_value('status', ...)` and save, and the Select
is editable. Commit e585a5b moved the derivation into `before_save` to fix a
lost write and thereby broke both buttons: they saved successfully and the field
simply was not what was asked for. The repair consults `get_doc_before_save()`,
and the owner's answer to rev_f9dce41f7f ("a Completed trip stays Completed")
added `TERMINAL_STATUSES`. The test file pins three different things — the
controller's behaviour, the premises it rests on (`trip.js`'s buttons,
`trip.json`'s Select) and a whole-app rule — so the faults are grouped by which
of the three should notice.

**40 faults, 35 red, 5 controls green. 29 tests, 10 subtests.** Six came back
green against the file as it stood, and all six were measured before anything
was repaired — the faults were written and run first, against the file on `main`.

**Two of the three copies of a rule were unguarded, and the file's own docstring
said all three carried it.** Cancelled is honoured on insert — where there is no
previous document — by a `!= "Cancelled"` check inside each of the three
derivation arms. Only the past arm was tested. Dropping the exclusion from the
future arm or from the running arm left the whole file green. Same family as the
7-red-versus-1-red in `xero_invoice_send`, with one difference worth noting: the
three copies here sit in three consecutive branches of one `if`/`elif` chain, ten
lines apart, which is about as symmetric as code gets and made the single test
look like it covered them.

**Neither instant where the arms meet was tested** — see the eighth lesson
above. `now < departure` → `<=` and `departure <= now <= arrival` →
`< arrival` were both green, and the second of those leaves a trip arriving at
this instant derived by no arm at all.

**`arrival <= departure` was pinned only as `<`.** The refusal test used two
dates days apart the wrong way round, which is true of `<` as well, so a trip
arriving at the instant it departs would have been accepted. The equal case is
the only one that pins the `=`.

**The two halves of the owner's rule are not guarded alike, and cannot be.**
Dropping `"Completed"` from `TERMINAL_STATUSES` turns three tests red. Dropping
`"Cancelled"` turns exactly one — and it is
`test_terminal_statuses_are_real_options_on_the_doctype`, which reads the tuple
rather than exercising it. No behavioural test notices, because the three
derivation arms already skip a Cancelled trip on their own, so the Cancelled
half makes no behavioural difference while those arms stand. That asymmetry is
recorded in the test class's docstring, because the alternative is somebody
reading "1 red" as a gap and going looking for a test that cannot be written.
Keeping the redundant half is still right: it states the rule where the rule is
read, and the arms are what the next change might remove.

**One fault was wrong, and that was the useful part** — see the ninth lesson
above. It is now a control.

**The whole-app rule has two instances in the app and accepts two remedies, so
it takes three faults.** `TestNoButtonSetSelectIsSilentlyOverwritten` holds that
a button setting a Select must not be overwritten by a pre-save hook, and
accepts either consulting the previous document (`trip`) or excluding the
button's values by name (`supplier_quote`, whose guard is
`status not in ["Accepted", "Rejected"]`). One fault empties that list, one
narrows it to `["Accepted"]` so only Reject breaks, and a third switches `trip`
from the first remedy to the second. That third is worth reading carefully: the
whole-app test stays **green** under it, correctly, because excluding the
button's values *is* one of the two remedies — and three behavioural tests go
red, because for `trip` the button values are also what derivation produces, so
excluding them disables most of it. The rule is deliberately permissive about
how you fix it and says nothing about whether your fix works.

**A discrimination control for the walker, not just a sensitivity one.**
`_button_set_values` brace-matches the callback of each `add_custom_button`,
because a field-change handler recomputing a dependent value is the server being
authoritative and is correct. So one control adds `set_value('status', 'Draft')`
to `supplier_quote.js`'s `quote_date` handler — outside any button, and a value
the guard does not protect. A line-based walker would flag it. It must stay
green.

**What this target does not reach.** The walker's own machinery
(`_button_set_values`, `_pre_save_assignments_and_guards`) is exercised against
synthetic source inside the test file, so no edit to real source can falsify its
units — the same honest limit as `whitelist_write_gate`. And the buttons
themselves are pinned by reading `trip.js` as text: nothing here runs any
JavaScript, so "the button does what the test says it does" rests on a string
match.

### `post_save_writes` — `tests/offline/test_post_save_field_writes.py`

44 faults, 33 red, 7 controls green, 4 known blind spots green. The first
target whose subject is a **detector** rather than a behavioural rule: a
whole-app sweep for a field assigned in a hook frappe runs *after* the row has
been written, where the value is silently discarded. So every fault plants (or
removes) something in real app source and asks whether the sweep notices.

**The finding: a detector's unit tests pin the shapes its author thought of,
and are silent by construction about the ones they did not.** This file had
fifteen self-tests covering every post-save hook name, nesting, augmented
assignment, the scope boundary, three kinds of non-finding — a thorough set, and
all of it against synthetic source the file writes itself. Eight of the eleven
exceptions in the first run were ways of binding a field that none of those
tests names:

| planted in real source | seen |
| --- | --- |
| `self.status = "Open"` | yes |
| `self.set("status", "Open")` | **no** |
| `self.update({"status": "Open"})` | **no** |
| `self.update_if_missing({...})` | **no** |
| `setattr(self, "status", "Open")` | **no** |
| `self.status, self.project_name = ...` | **no** |
| `self.status: str = "Open"` | **no** |
| `for self.status in [...]` | **no** |
| `with ... as self.project_name` | **no** |

The first three are not exotica. `BaseDocument.set` is frappe's own setter
(`base_document.py:228`, ending in `self.__dict__[key] = value`) and `update()`
is a documented loop into it (`:169-186`) with an example in its own docstring —
so a sweep that reads `ast.Assign` alone covers one of four documented ways to
set a field, and the one that loses *several* fields on one line was invisible.
Tuple unpacking is the shape most likely to be written by accident: it puts a
single `ast.Tuple` in `targets`, and `isinstance(tgt, ast.Attribute)` on that
Tuple is simply false. All eight now report, through one generic
`_attr_targets` + `_setter_fields` pass rather than an enumeration of node
types, which is why `for`/`with` targets come free.

The general form, and it is not about AST: **a detector tested only against
fixtures it writes itself has been asked "do you find what I thought of?" and
answered yes.** The question it has not been asked is what real code can do.
That one needs the real tree.

**Second: a control that goes red can mean the detector is wrong, not the
test.** `run.py` prints "the control went red: the test is pinning the code's
internals" — the right reading for eight targets, and the wrong one here. A
plain `class _ProjectTotals:` added beside the controller, with an `on_update`
that frappe never calls, was reported as a lost write. That is a *false
positive*, in a file whose own rule is that coarse-and-silent beats
confidently-wrong, and the author had already reasoned about the same mistake
one level in (`test_a_method_of_a_nested_class_is_not_a_hook`). The fix is
narrow on purpose: a class with **no base at all** is not a controller. It does
not try to decide whether a base *is* `Document`, because that cannot be
resolved offline and guessing wrong would silently stop reading a real
controller — under-detection a sweep cannot report. A helper class that does
declare a base is still swept, and
`test_a_helper_class_with_a_base_is_still_reported` pins that as the remaining
surface rather than leaving it implied.

**Third: a baseline keyed by a tuple counts keys, not lines.**
`PENDING_DECISION` lists four known lost writes awaiting the owner's answer on
`rev_7b11901cfb`, keyed `(file, class, hook, field)`. But
`SalesInvoice.on_submit` assigns `status` on two lines — once plainly, once
under `if self.is_paid` — so **four entries stand for six lines**, and deleting
either line of either pair left both baseline tests green: the key survived, so
nothing went stale, and the pending set had quietly changed. The file's own
BASELINE note says "six". Asserting the number the docstring already claims is
the whole fix, and it is the cheap half of a general point: *when a baseline
collapses several instances into one key, the count is the only thing that
notices a partial change.*

**What this target does not reach**, and the test file now lists it under "What
this cannot see" rather than leaving a green run to be over-read: four faults
are real regressions that stay green on purpose. `self.db_update()` moved
*above* the assignment it persists, or put under `if False:`, still loses the
write — the persisting check is per hook with no ordering and no reachability.
The write moved into a closure the hook calls immediately is skipped, because
`walk_scope` skips nested scopes on the grounds that a nested def may be a
callback run elsewhere (right for a callback, wrong here, and telling them apart
needs a call graph). `doc = self; doc.status = x` needs data flow. Each would
cost control-flow reasoning to close, which is how a guard like this starts
producing confidently wrong findings.

One more limit, found by reading rather than injecting: a post-save hook
attached through `doc_events` in `hooks.py` is a **module-level function** taking
`doc`, not a method taking `self` — so `test_a_module_level_function_is_not_a_hook`
is pinning the right thing only while `doc_events` is unused. It is commented
out in `erplite/hooks.py` today. If it is ever filled in, this sweep stops
covering the app and that test's name becomes wrong.

### `string_refs` — `tests/offline/test_string_references.py`

39 faults, 23 red, 11 controls green, 5 known blind spots green. The second
**detector** target, and a detector with no self-tests at all: five whole-app
assertions and nothing synthetic. That turned out to be the more interesting
starting point than `post_save_writes`' fifteen self-tests, because the question
is the same either way — *what can real code do that this cannot see?* — and
with no fixtures to read, the only way to ask it is to plant the real thing in
real source. **Ten of the thirty-nine faults were invisible to the file as it
stood**, measured before anything was repaired.

**The finding: one of the four surfaces was swept by nothing.** The file checked
asset URLs, dotted method paths and whitelisting across `.py`, `.js`, `.vue` and
`.html`. `erplite/patches.txt` is none of those, so the one patch this app ships
— `erplite.patches.declare_todo_status_options`, which writes a Property Setter
the live database depends on — was resolved by no test anywhere. Five faults in
it were all green:

| planted in `patches.txt` | noticed |
| --- | --- |
| a misspelt module (`..._optoins`) | **no** |
| a module that exists but has no `execute()` | **no** |
| the patch module's `execute` renamed | **no** |
| a path one element short | **no** |
| a misspelt module with frappe's usual trailing date | **no** |

None of those is exotic; every one is a typo in a text file with no import to
check it. And this is the surface with the **worst** symptom of the four:
`execute_patch` (`frappe/modules/patch_handler.py:157`) does
`get_attr(f"{entry.split()[0]}.execute")` *before it runs anything* and
`migrate` lets the exception out, so **`bench migrate` stops** — part-way
through the patch run, with the entries before it already committed. The other
three surfaces are a dead button or a modal dialog. This one is a failed deploy.

The general form: **a sweep's reach is its file-extension list, and a text
file that is not source is where the extension list ends.** `patches.txt`,
`hooks.py`-adjacent config, `.cfg`, a CSV of fixtures — each is a place a name
is resolved at runtime and no import or editor will follow it. It is worth
asking of any whole-app guard which files it opens, as a list, out loud.

**Second: the two halves of one file disagreed about where the app's source
lives.** Pass B and pass C both swept `erplite/` *and* `frontend/src` (the
un-built Vue source). Pass A swept `erplite/` only. So a missing asset
referenced from the Vue source was invisible, in a file whose passes look
symmetric and sit forty lines apart — the same proximity-and-symmetry trap as
`trip_status`' three consecutive `if/elif` arms, one level up: not three copies
of a rule, but three copies of *where to look*. There is one `source_roots()`
now, used by all of them, so the next root is added once.

**Third: a positional-only parameter is not a style question, and skipping it
was wrong in both directions.** The file said, reasonably: positional-only
parameters and `*args` can never be filled by `frappe.call`, the app has none
(measured, 0 of 114), so neither is handled rather than guessed at. The
measurement was true and nothing asserted it. Underneath, `node.args.defaults`
is right-aligned over `posonlyargs + args` *together*, while the code sliced it
against `args` alone — so the moment a `/` appeared the arithmetic was computed
off the wrong list:

* `def f(project, /, entries_data)` — reported as callable, requiring
  `entries_data`. In fact uncallable by `frappe.call` at all: Python answers a
  keyword given for a positional-only parameter with `TypeError: f() got some
  positional-only arguments passed as keyword arguments`. **Invisible.**
* `def f(a="1", /, b="2", c="3")` — reported as requiring `b`, which has a
  default. A **false positive** on correct code.
* `def f(entries_data, /)` — went red, and for the wrong reason: making the only
  parameter positional-only emptied `args`, so the name the caller sends looked
  *unknown*. The right colour with a message that misdescribes the bug.

Both faults are in the target, because the difference between them is the
finding. The signature is now read in full and
`test_no_called_function_has_a_positional_only_parameter` reports the real
thing, so the blind spot and the false positive close with one change — and the
measurement is a test rather than a sentence. A `*args` stays unreported: it is
unfillable too, but harmlessly, because it is never required.

**Fourth: order is not meaning.** Pass C matched `method: "..."` followed by
`args: {...}`, in that order, with a body of `[^{}]*`. Two consequences, both
measured: the identical wrong argument written `args` first was invisible, and
so was a wrong argument in any call whose `args` holds a nested object — which
is `filters: {...}`, the ordinary shape of a frappe.call. A regex that spells
out the order of two keys is pinning the keystrokes, not the call. It now parses
the object literal: string-aware, brace-balanced, reading only the object's own
keys. Same net, cast at the object instead of at a character sequence — the
seventeen call sites it reads and the keys it reads from them are unchanged.

**Two corrections to the file's own prose, both of which read as evidence.**
This is the `trip_status` lesson a second time, and it is the one I keep having
to relearn:

* The pass C docstring named `get_supplier_quotes_for_comparison(item_name,
  project)` as its worked example of a missing required argument, in a paragraph
  that says it was "confirmed by lifting that function out of the v15.52.0
  source and running it". **That signature has never existed in this
  repository** — it has been `(item_name=None, project=None)` since the file was
  created in 98e9b04 — so against the real one, `{item_name: ...}` runs to
  completion with `project` as `None`. Checked by running frappe's own
  `get_newargs` against both. The general claim was right; the example was
  invented.
* The blind-spots list said pass B "does cover the bundles, because the bundle
  is what is deployed — that is how the transposed name above was found".
  `erplite/public/frontend/` is **gitignored** (b95a358, "Ignore generated
  frontend build output"), so `BUNDLE_DIRS` matches nothing in any checkout and
  `_is_bundle` never fires. The handling is kept, because it is correct on a
  built bench, but offline the strength *and* the weakness that paragraph
  describes are both empty. A sentence about coverage the tree cannot provide is
  worse than no sentence: it reads as a reason to stop looking.

**What this target does not reach**, listed in the test file rather than left
for a green run to be over-read. A method path assembled at runtime has no
string to read. An `args` object holding a spread, an ES2015 shorthand property
or a computed key is skipped **whole** — reading it partly would report the
entries it could not see as arguments the caller never sends, a false
missing-required-argument finding against correct code, and a sweep that argues
with correct code gets switched off. A dotted path inside a `.json` is not
swept: frappe resolves one out of some DocType *records* (a Dashboard Chart's
`method`, a Notification, a Server Script) and this app ships none of them,
measured — and which JSON field in which doctype is a method path is knowledge
that lives in frappe, not here.

One shape worth naming because it is the cheap kind of wrong: pass A used
`os.path.exists`, which is true for a **directory**. `/assets/erplite/images`
passes that check and 404s on the live site exactly like a missing file. It is
`os.path.isfile` now, and the finding says which of the two it is.

### `select_values` — `tests/offline/test_select_values.py`

33 faults, 21 red, 3 false positives green, 5 controls green, 4 known blind
spots green. The third **detector** target, and the one that makes the point
cheapest: its subject is a narrow, decidable question — *is this one of the
values the field is allowed to take?* — and the sweep asking it read **two** of
the ways frappe writes or filters a Select value. Fourteen of the thirty-three
faults were invisible to the file as it stood, and **three of those are in
frappe's own docstrings**: `get_all`'s documents `filters` as a list of lists
right beside the dict form, `db.set_value`'s says `field` may be "a dictionary
of values to be updated", and its `dn` is "a document name **or filters** for
updating many records". The app already uses the dict form of `set_value` in
four live Xero writes.

**Two minutes of probe predicted every one of them.** Before writing a fault,
a throwaway script imported `violations()` and asked it about twenty candidate
shapes planted one at a time. It named 18 blind spots and 3 false positives;
checking each against frappe 15.52.0's source cut the 18 to 14 real ones — a
flat three-element list is rejected by frappe itself (`get_filter`,
`utils/data.py:1958`), `db.get_all_names` does not exist in v15, and
`get_cached_value`'s second argument is a name, not filters. That is the
procedure worth copying from this target: **ask the detector what it sees
before you spend an hour proving what it doesn't, and check each answer against
the framework's source before claiming it.** Three of the twenty candidates
were my mistake, not the sweep's.

**The general form, for any detector of a bug class: its reach is the set of
syntaxes it reads, and a framework usually offers four or five ways to do the
thing it is looking for.** `post_save_writes` read one of frappe's four ways to
set a field; this read two of frappe's eleven query entry points and one of its
four filter shapes. In both cases the detector's own tests were about the shape
the author had in mind. The fix in both cases was one generic pass — here,
following `get_filter` (`utils/data.py:1940-1975`), the single funnel every
filter frappe accepts goes through — rather than an enumeration of call sites,
which is why `or_filters`, `db.get_values` and the four-element filter came
free.

**A four-element filter names its own DocType** (`[doctype, fieldname,
operator, value]`, `data.py:1963`), which need not be the one queried. A sweep
that assumed the query's DocType would compare a value against the wrong
field's options and be confidently wrong in both directions. There is a test
for the precedence rather than a comment about it.

**Three faults were FALSE POSITIVES — real frappe accepts the edit and the
sweep reported it.** This is the `post_save_writes` lesson a second time: a
green-expected fault going red can mean the detector is wrong, not the test.
`_validate_selects` (`base_document.py:892-920`) is the authority on a write
and it is narrower than "the value is in options" in three ways: it exempts
`naming_series` by name, skips a falsy value, and **strips** the value before
comparing. So `"status": ""` and `"status": "Draft "` are correct code, and this
sweep flagged both. In a file whose own standing comment is *widen the mirror,
do not narrow the app*, a guard that argues with correct code is the specific
failure that teaches people to ignore it.

And the asymmetry underneath, which is why the fix is two code paths and not
one: **a write is stripped, a filter is not.** `_validate_selects` rewrites the
field before comparing; nothing touches a filter value, which reaches the WHERE
clause with its space and matches nothing. The same string is correct code on
one side and a real finding on the other.

**What this target does not reach**, named in the test file and asserted there
by `test_what_this_cannot_see_is_still_invisible`, so the list is a measurement
rather than a claim: attribute assignment on a local, a value held in a
variable or built by an f-string, a filters dict built by a helper, and a
DocType that is not a literal. Each needs the type of a local or a value that
does not exist until runtime, and guessing either is what produced this file's
original false positives. `.update()` is read only where the DocType is in the
same expression (`new_doc("X").update({...})`) — the same boundary, drawn in
the same place, rather than a special case.

One tripwire for a case skipped on purpose, the habit from `string_refs`:
`from frappe import get_all` then a bare `get_all(...)` is ordinary Python that
`_dotted` reads as `get_all`, which is in no table. No call site in this app is
written that way — and that measurement is now a test naming the file, because
a measurement that is not a test is just a sentence.

### `todo_status_patch` — `tests/offline/test_todo_status_property_setter.py`

42 faults, 36 red, 2 false positives green, 4 controls green, 2 blind spots left
green on purpose. Behavioural again after three detectors, and much smaller
ground than any of them: one 30-line patch module, one text file that wires it
up, and a test file that stubs `frappe` by hand rather than using
`fake_frappe`. That last choice is what makes this target worth having,
because it changes the governing question. For a detector the question is *what
syntax can it read?* For a test that runs the real code against stand-ins it is
**what is the stand-in more permissive about than frappe is?** — and a stand-in
written to make a test pass is permissive in exactly the places nobody thought
about.

**The sharpest instance: `frappe.get_meta` was `lambda doctype: _Meta(...)`.**
It ignores its argument, so it answers for every DocType alike. `execute()`
reads exactly one thing from the site — ToDo's `status` field — and
`frappe.get_meta("ToDo")` → `frappe.get_meta("Task")` was invisible: a patch
pinning one DocType's options onto another DocType's field, with every test
green. The neighbouring stub is the contrast that makes the point:
`_Meta.get_field` returns the field for `"status"` and `None` for anything else,
so the *field* could not be got wrong, because that stub discriminates and the
other does not. The general form: **a stand-in that ignores an argument has
deleted a claim, and the test file reads as though it still makes it.** The
stub now records what it was asked for.

**Second, and the one with the most behind it: the patch pins two properties
and the file asserted the recovery of one.** `options` and `default` are both
written, and there is a test that a site frappe has reset gets all five options
back. Nothing asserted the default. So
`_declare("default", DEFAULT_STATUS)` → `_declare("default", status.default or
DEFAULT_STATUS)` — preserving the site's own default instead of forcing
Backlog — stayed green across all twenty tests, while on a reset site the
default would be frappe's `Open` and **the board's first column would stop
being where a new ToDo lands**. Half of what the patch exists to do, lost in
one `or`. The file's own docstring says the patch "pins the options the site
already has" *and* forces the default; the tests covered the first clause.
Worth asking of anything that writes more than one row: is each one's story
asserted, or does one of them get its colour from the other's test?

**Third: two parsers of one text file, and the newer one was right.** This
file hand-rolled its own reading of `patches.txt` — strip the line, skip `#`
and `[`, split on `"."`, ask for a file — in a repo where
`test_string_references.py` had, since the tenth target, a parser that does it
the way frappe does. The hand-rolled one was wrong **in both directions**, and
both were measured:

| entry | frappe | this file |
| --- | --- | --- |
| `erplite.patches.x #2026-10-05` | runs it (`split(maxsplit=1)[0]`) | **reported it** |
| `execute:frappe.db.set_single_value(...)` | `exec()`s it, no path at all | **reported it** |
| a module that exists with no `execute` | **migrate stops** | passed it |

The trailing date is not exotica: it is the form frappe's own `patches.txt`
writes. So the guard argued with two entries frappe runs happily and waved
through the one that fails a deploy — the `isfile` question is not the
`get_attr` question. The whole-file sweep is not duplicated here any more; this
file asserts only its own patch, through that same parser, so there is one
answer to the question instead of two. **Two hand-kept records of one thing is
how one of them goes stale** — which is the argument this file already made, in
its own `TestItAgreesWithTheSelectGuard`, about the five statuses. It had made
the argument and then kept a second parser.

**Fourth, and it is the half of that fix worth reading: closing a blind spot by
deferring to someone else's parser opened a new one.** `patch_module_paths`
strips a `finally:` prefix, on the sound grounds that deferring the run to the
end of the patch list is all the prefix means. v15.52.0 does not agree:
`execute_patch` resolves `patchmodule.split(maxsplit=1)[0] + ".execute"` at
`patch_handler.py:166-167`, **before** the prefix check at `:182`, and
`get_attr` reads the app name as `method_string.split(".", 1)[0]` — which is
`"finally:erplite"`, not an installed app, so it throws `AppNotInstalledError`
and the migrate stops. A `finally:` entry is a failed deploy that the parser
calls resolvable. The answer was not to make the parser argue with what the
entry means, but to assert the measurement that makes its stripping safe — *we
do not write one* — and to put that tripwire with the parser rather than in a
second copy here. The fault for it is in the `string_refs` target, not this
one, which is why it is green above. **When you delete a duplicate check, the
question is not only "is the survivor better" but "does the survivor make the
same promises".**

**A control that went red, and it is the cleanest one of these yet.** The two
Property Setters are independent upserts: separately-named documents
(`{doc_type}-{field_name}-{property}`, `property_setter.py:34-37`), each
deleting only its own property's row (`delete_property_setter`, `:90-98`), both
applied by one pass over the table (`meta.py:379-387`), with nothing re-reading
the meta in between. So declaring them the other way round changes nothing —
and four tests went red, because the file did `options, default = calls` and
compared `[s.property for s in calls]` to `["options", "default"]`. It was
pinning the order the two lines were typed in. They are read by property now.
The order of two independent writes is the kind of thing a test picks up for
free and then nobody notices it is being asserted.

**Two corrections to prose, in the patch and in the test's copy of the same
sentence.** Both said `reset_customization` "exempts `property != "options"`
but nothing else". It has two exemptions — `property != "options"` **and**
`field_name != "naming_series"` (`customize_form.py:675-685`) — the second
being the same special case for the same field that `_validate_selects` turned
out to have in the eleventh target. The conclusion was unaffected (`status` is
not `naming_series`, so the `default` row is spared by neither and must be
marked), which is the kind of slip that survives review precisely because the
sentence it sits in is going somewhere true.

**The probe again, and this time it was the whole of it.** Twelve candidate
edits planted one at a time in the real patch source, two minutes, and all
twelve came back as predicted — including the three I expected to be false
positives and the control I expected to go red. Then the same correction as
the eleventh target, in the same direction: reading `patch_handler.py` and
`frappe/__init__.py` at v15.52.0 **cut three false positives to two**, because
frappe rejects a `finally:` entry too. The probe is good at *what does this
test see*; only the framework's source answers *and is that the right answer*.

**Every claim in the patch's docstring was re-read at the tag it names**, which
the test for it now pins by name rather than by the shape `v15.<n>.<n>` — a
test whose entire point is that the tag is what to re-check against could not
see the tag being changed. All of it held: `apply_property_setters` on every
meta load (`meta.py:138`, body 360-387, `cast(ps.property_type, ps.value)` at
386); the DocType skip gate being `migration_hash` alone, with the timestamp
gate beside it explicitly `and doc["doctype"] != "DocType"`
(`import_file.py:130-144`); `delete_old_doc` (`:258-276`) sparing no child
table because `ignore_doctypes = [""]` (`:40`); `sync_all()` called with no
arguments (`migrate.py:120`); the delete-then-insert upsert
(`property_setter.py:39-44`); `is_system_generated` not being a parameter of
`make_property_setter` (`:63-71`); and both `DocField.options` and
`DocField.default` being `Small Text`, which is what `cast` reads the value
back with.

**What this target does not reach.** `erplite/patches/__init__.py` is empty, and
the harness only does find-and-replace, so the claim that a patches package
without it is not importable is asserted and **not** fault-injected — the one
claim here measured by reading rather than by breaking. `MEASURED_OPTIONS` is
documentation, not code, and two faults in it are caught only by comparing it
to this file's own `LIVE_OPTIONS`: two records of one measurement, which is the
staleness this file was already built to catch, now closed in the one place it
was still open. And the stand-ins remain stand-ins: that frappe applies these
rows the way the docstring says needs a bench, and the file says so rather than
implying otherwise.

### `afterz_workflow` — `tests/offline/test_afterz_timesheet_workflow.py`

49 faults, 46 red, 3 controls green. Afterz
(crew.tierneymorris.com.au/afterz) is the owner's daily timesheet UI; it never
calls erplite code, but it creates and saves `Timesheet Entry` rows directly, so
this controller's hooks and guards are the only ones its rows ever meet. The
file existed because e585a5b put a check-out auto-submit in `before_save`, which
runs on **every** save — so creation locked the entry, submit-week found
nothing, and reject and un-approve landed back on `Submitted`: a rejection that
silently re-queues the entry it just rejected.

**The headline: twelve of the 49 were green, and five of the twelve belonged to
one function.** `reject_timesheet` and `approve_timesheet` implement one rule
from two copies of the same two lines — byte-identical except for the word
"approve"/"reject" in the refusal, which is why every pattern in this target has
to carry the message to match once. Approve had four tests. Reject had one, the
happy path. So deleting reject's gate, inverting it, making it `msgprint`
instead of `throw`, removing its write-permission hatch, and dropping its
`!= "Submitted"` requirement were **all five green**: anyone at all could reject
anyone's timesheet and the suite was satisfied.

This is the `select_values` lesson — cover every instance, not a sample — in its
sharpest form yet, because here the two instances are not in different files or
different DocTypes. They are forty lines apart, in the same file, written by the
same hand, and the test file had read one of them. **The second copy of a rule is
free to be wrong for exactly as long as nobody asks it the questions the first
one was asked.** The fix is six mirror tests, and the general habit: if you find
yourself writing a pattern that needs the error message to match once, that is
the code telling you there are two copies and you have tested one.

**Second, and it is the worst defect of the twelve: an approval could have moved
the hours.** `set_employee_default` only fills a blank `employee`. Change it to
assign — one plausible tidy-up, `self.employee = frappe.session.user` instead of
`if not self.employee:` — and every one of Afterz's four approval-side calls
re-books the row against whoever clicked, because all four save an entry whose
`employee` is somebody else. The approver's click silently transfers the time to
themselves and the entry still reads `Approved`. All 22 tests passed. The reason
they did is worth more than the fault: the file's `EMPLOYEE` and `APPROVER`
constants are **the same string**, so no test above `TestTheApprovalGate` ever
had two different people in it. A fixture where two roles are one value cannot
fail a test that distinguishes them. `TestWhoseHoursTheseAre` now drives the
approval and the week-submit as a different session user and asserts `employee`
is untouched.

**Third: four guards nothing had ever asked a question of.** `check_out`'s
ownership check, `check_out`'s `is_active` check, the `validate_times()` call
and the `check_overlapping_entries()` call could each be deleted outright with
all 22 green. Every entry the file built was well-formed, owned by the session
user and alone on the clock, so the guards against every other case were never
reached. Two of the new tests are shaped by *which* guard they mean:

* a second check-out must not rewrite `check_out_time` — a guard whose absence
  does not throw, it silently inflates the hours on an already-submitted entry,
  so the assertion has to be on the stored time and not on the refusal;
* the overlap test inserts directly rather than calling `check_in()` twice,
  because `check_in()` has an active-entry guard **of its own**. Going through
  it measures that guard and leaves the controller's untested — and Afterz never
  calls `check_in()`, so the controller's is the only one its rows meet. A test
  that reaches a rule through the nearest convenient door may be testing the
  door.

**The two halves of this file cover each other, which is why both are faults
here.** `TestNoSaveHookOwnsStatus` reads the source with `ast` and fails if any
save hook assigns `self.status`; the behavioural tests drive frappe's real
save ordering. Seven faults put the same submit in seven different hooks —
`validate`, `before_validate`, `before_insert`, `on_update`, `on_change`,
`after_insert`, `on_update_after_submit` — and the two halves catch different
subsets: the driver only runs the hooks frappe's `_save()` runs, so
`before_insert` and `after_insert` are caught by the AST test alone, while
`on_update` is caught *only* by it (an assignment there is discarded, so the
behaviour is correct by accident). Conversely two faults spell the assignment so
the AST test cannot see it — `setattr(self, "status", ...)`, which it does not
recognise, and `self.status += "ted"`, which it does — and the behavioural tests
catch the first. Neither half is redundant; each is the other's blind spot.

**A control that went red, and it was the control that was wrong.** The first
version of "the overlap query's local renamed" renamed the two reads of
`active_entries` and not the assignment, so the local was undefined and 18 tests
raised `NameError`. That is not a control, it is a fault wearing a control's
label, and this README already says why it matters: *a negative control that
goes red is not a control.* The signal was the shape of the failure — a control
that pins an internal goes red in one or two tests, not eighteen. **Read the
count before you believe the verdict.** The pattern is now the whole span,
assignment included, generated from the source rather than typed.

**One claim corrected in the test file, not in the code.** Its docstring said
Afterz "was last pushed 15 Aug 2025 (dd78fe0), so the deployed copy may differ"
— a date read off GitHub when the file was written, and the stated reason for
pinning behaviour rather than line numbers. Afterz is now an office repository
that moves daily: `develop` is its default branch and its tip was `caa000d` on
6 Oct 2026. Every line number in that docstring's table had moved (five of five,
by as much as 83 lines). **Not one of the five behaviours had**, read from
`origin/develop` at `caa000d`. So the choice the stale claim was used to justify
was right for a better reason than the one given, and the reasoning is what gets
corrected: the line numbers are a sketch of where to look and the part of the
file to distrust; the five states are the claim.

**What this target does not reach.** That frappe really runs these hooks in this
order needs a bench; `WorkflowTestCase` is a port of `Document._save()` and
`insert()` and says which lines it stands for, which is a claim about the port
and not about frappe. `validate_employee_ownership` has its own target
(`timesheet_ownership`) and this file deliberately does not duplicate it — one
fault here measures only that Afterz's own paths still survive it. And the
approval gate's `or not frappe.has_permission(...)` hatch is pinned as it
stands, in both copies now, so changing it is a decision rather than an
accident.
