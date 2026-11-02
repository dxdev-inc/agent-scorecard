# Glossary

One place for every word this kit uses with a special meaning. There are four separate vocabularies. They answer different questions, and they are not interchangeable. `schema_version` for the event log is 1 (see [SCHEMA.md](SCHEMA.md)).

## 1. By-hand labels (`sample`)

You read a sampled ask and judge it against independent evidence (git, a ticket, the live system). Exactly one of six labels.

| Label | Meaning |
|---|---|
| `finished` | The asked-for thing happened, and you can point to evidence. |
| `partly_done` | Some of it happened. |
| `dropped` | Nobody did it and nobody decided not to. |
| `superseded` | A later ask or decision replaced it. |
| `cannot_tell` | You could not find evidence either way. |
| `not_a_request` | Not work: thanks, acknowledgement, chatter. |

Evidence kind for a `finished` row: `git`, `ticket`, `live` (all count as strict) or `agent_report` (counts only in the loose share). The loose share is every `finished`. The strict share is `finished` backed by `git`, `ticket` or `live`.

## 2. Event log kinds (`unit_created.kind`)

| Kind | Meaning |
|---|---|
| `do` | Change something in the real target. |
| `decide` | Pick between options. |
| `explore` | Find something out. |
| `manage` | Pass something on to someone and see it land. |

## 3. Event log states and verdicts

| Word | Meaning |
|---|---|
| `done` | The unit's last status row says done. This is "finished" in the event log. It says nothing about quality. |
| `reopened`, `reverted` | A done unit came back, inside 14 days if counted for stability. |
| `forced` | A close that skipped verification. Recorded, never counted as trusted. |
| `pass`, `fail`, `inconclusive` | Verify results. `inconclusive` is a real answer, not a failure: the evidence did not settle it. |
| trusted | Done, not forced, and at least one independent `pass` with evidence that fits the deliverable. |

## 4. Scorecard labels

| Label | Meaning |
|---|---|
| `MEASURED` | Computed from the log by a fixed rule. |
| `REPLAY` | What the capture rules would do over the same ask rows. |
| `ESTIMATED` | A stated guess. |
| `NO DATA (source: ...)` | The schema has no source for it. |

## "Finished" in the by-hand check versus "done" in the event log

These are two different bars on purpose.

- By hand, an ask is `finished` when you find evidence the asked-for thing happened. For a question, the first post counts an answer given in the next turn as handled. That is a labelling convention for the person reading; the code does not check it. Run the strict share next to it, which drops anything backed only by the agent's own report.
- In the event log, an `explore` unit is `done` only when a finding is stored with its evidence (a concrete question), or the ask is thinking out loud and has no done test at all. A written document or a ticket only advances status.

So a question answered in the next turn is `finished` in a by-hand sample and not yet `done` as an `explore` unit unless its finding was stored. Never mix the two numbers in one sentence. If you quote a share, say which vocabulary it comes from.
