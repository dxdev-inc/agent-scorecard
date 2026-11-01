# The method, in order

The question: when a person hands work to agents, how much of it finishes, how much of what finished can be
trusted, and how much happened while the person was away? Most dashboards count what was started. This one counts
what finished, and refuses to count what nobody checked.

## 1. Every real ask becomes a unit with a kind and a done test

A log of messages is not a log of work. Filler ("ok", "thanks") is dropped with a stated reason. Everything else
becomes a unit with a **kind** and a **done test that fits the kind**:

| kind | done when |
|---|---|
| do | the change is observable in the real target, and a check other than the builder recorded evidence |
| decide | a decision is recorded: the choice and who made it |
| explore | a finding is stored with its evidence (a concrete question), or NO done test (thinking out loud) |
| manage | the relay reached its recipient and the named action was observed |

Two rules run through all of it. A ticket, a next step or a written document only advances status; none of them is a
done test. And a brainstorm gets no done test: a fake gate on thinking out loud is worse than none.

## 2. Finished is not trusted

A unit is finished when someone says so. It is trusted when an independent check recorded evidence of the outcome.
The verifier must not be the executor or the requester; the evidence must be of a kind the deliverable requires
(a test run for code, a render capture for a page, a re-run match for data, and so on); presence of a file or a
commit proves nothing. `inconclusive` is a real answer, separate from `fail`. An unproven unit stays out of the
numerator of trust and stays in the denominator. A forced close is allowed, recorded, and never counted.

## 3. Stability sits beside finish rate

A higher finish rate could be a worse factory. So the share of done units reopened or reverted inside 14 days is
reported next to it, from the same events.

## 4. The loop is bounded, and the executor cannot move the goalposts

One unit per iteration, state in the unit list. Stop on max iterations, a wall clock budget, or two rounds in a row
with no new independently verified evidence. A pool of capacity that runs out PAUSES the run with a resume time; that
is not a failure. A unit retries a fixed number of times and is then handed to a person. `done_when` is read-only
to the executor: a result that edits it is refused and logged. A unit closes only through the evidence gate. With
nothing ready, the oldest idea past its review date is started, or dropped with a reason.

## 5. Every number says where it came from

`MEASURED` (computed from the log by a fixed rule), `REPLAY` (what code would have done over the same rows),
`ESTIMATED` (typed in), `NO DATA (source: ...)` (the log has no such source). No productivity multiplier is
computed. Factors derived from transcripts or self-reports are upper bounds at best.

## Mistakes made while building this

- The first synthetic log sorted rows by timestamp and then by type, which put a `status` row before the
  `unit_created` row at the same second. The measures silently ignored those statuses. Caught in code review
  before the first run; fixed by keeping emission order for ties, and covered by
  `test_units_are_created_before_their_status_rows`.
- The first capture rules dropped "brainstorm ways the sidebar could run unattended" as too short, so the replay
  reported zero open discussions. The label agreement line (88.6 percent at the time) showed something was off
  before anyone read a single row. A brainstorm cue now counts as a trigger.
- One role play scenario failed the first time it ran: a stated need with no action verb ("i need the usage report
  split by region") was dropped. Fixed in the rules, not in the scenario.
