# Event log schema (version 1)

One JSON object per line, UTF-8. Every row has `ts` (UTC, ISO 8601, `Z` suffix; a timestamp with no zone is rejected as an error, an explicit offset is converted to UTC), `type`, and `class`.
`class` is the privacy classification of the row. Every row this repo ships is `synthetic`. If you point the
tools at your own log, set `class` to whatever your own policy says, and decide what may leave your machine
before you publish anything built from it.

| type | required fields | meaning |
|---|---|---|
| `ask` | `ask_id`, `text` | A person asked for something. Optional `label_kind` (a hand label, used only for the capture replay check). |
| `unit_created` | `unit`, `kind`, `deliverable`, `executor`, `requester`; optional `ask_id`, `done_when` | A tracked unit of work. `kind` is `do`, `decide`, `explore` or `manage`. `deliverable` is `code`, `page`, `data`, `document` or `config`. `done_when` is the outcome test, or null. |
| `status` | `unit`, `status`; optional `forced` | `open`, `working`, `done`, `reopened`, `reverted`. A unit's current state is its LAST status row. `forced` marks a close that skipped verification. |
| `verify` | `unit`, `verifier`, `result`; optional `evidence` | `result` is `pass`, `fail` or `inconclusive`. `evidence` is `{kind, ref, outcome_observed}` or null. |
| `usage` | `unit`, `tokens` | Cost attributed to a unit. Sums per unit. |
| `owner_idle` | `start`, `end` | The person was away. `ts` equals `start`. Used for the autonomy line. |
| `intervention` | `unit` | The person supplied missing context mid-run. |

Words used here are defined once in [GLOSSARY.md](GLOSSARY.md).

## Definitions the measures use

- **Finished**: the unit's last status row at the measurement date is `done`.
- **Trusted**: finished, not forced, and at least one `verify` row that `agent_scorecard.verify.judge` credits as a
  pass (independent of the executor and the requester, typed evidence that fits the deliverable, outcome observed).
- **Reopened within 14 days**: a `done` row followed by `reopened` or `reverted` inside 14 days. Only done rows whose
  14 day window has closed, or that were already reopened, count in the denominator.
- **Autonomous trusted unit**: trusted, and its done time falls inside an `owner_idle` episode of 2 hours or more.
- **`--as-of`**: rows after that timestamp are ignored. Same log and same date give identical output.

`agent_scorecard/schema.py` holds the same schema as code, with `validate(row)`.

## Mapping your own log

Write one adapter that emits these rows from whatever you have (a ticket export, a chat log, a run ledger). Keep it
out of this repo. The only hard part is `ask`: deciding which messages count. `agent_scorecard.capture` is one answer
and a replaceable one.
