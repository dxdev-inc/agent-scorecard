# agent-scorecard

A small, stdlib-only Python kit for one question: of the work you hand to AI agents, how much actually finished, and how much of that can you trust? It logs asks, units and verification events, and computes finish rate, evidence-backed trust and stability, with every number labelled by how it was obtained. It is for engineers and AI leads who run agents on real work and suspect their task list undercounts what got done. You can run all of it in five minutes on a seeded synthetic log.

## Try it

You need Python 3.10 or newer and git. Nothing to install.

```bash
git clone https://github.com/dxdev-inc/agent-scorecard.git
cd agent-scorecard
python -m agent_scorecard quickstart
```

That builds an invented log and prints a scorecard from it in about a second. The numbers are synthetic, so they show what the tool does, not how any real team performs. Deeper reading: [method](docs/METHOD.md), [log format](docs/SCHEMA.md), [glossary](docs/GLOSSARY.md), [a first run on your own work](docs/FIRST_PILOT.md), and [Limits](#limits-read-this-before-quoting-anything).

**The hypothesis behind it (from the first post in the series, not checked here).** When you hand work to agents across many parallel sessions, the work mostly finishes and the record of it mostly does not. In one week of my own requests (one operator, one AI reviewer, a small sample, no human check of the reviewer's labels yet) the tracker confirmed little, while git and tickets said most of it was done. The data and figures are not in this repo, so you cannot check that claim here. The kit is how you test it on your own log.

**How to measure it yourself.** Two halves. (1) By hand: sample your asks with `python -m agent_scorecard sample --log YOUR_LOG.jsonl`, judge each against independent evidence (git, tickets, the live system) instead of the agent's say-so, then score the filled-in table with `python -m agent_scorecard sample --score out/sample.csv` (use the path of your filled-in table), which prints the share finished with a 95 percent interval. (2) With the event-log code: log asks, units and verification events in the schema in [docs/SCHEMA.md](docs/SCHEMA.md) and compute the measures.

**Everything in this repo runs on synthetic data. There is no real figure anywhere in it, and the tools have not been run on a real log here.** Read [Limits](#limits-read-this-before-quoting-anything) before quoting a number.

The idea is old. Winograd and Flores built request tracking with explicit conditions of satisfaction in the 1980s, and support teams already measure verified resolutions. The narrow thing I could not find published is one person's asks across parallel agent sessions, checked against git and tickets, with the gap between tracker and reality written up. That is a statement about a bounded search, not a claim that nobody has done it. See [Prior work](#prior-work).

What is in it:

| Piece | Module | What it does |
|---|---|---|
| Measure | `agent_scorecard/measure.py` | Asks against finished work, from an event log. Finish rate, time to done, trust, stability, autonomy. `--as-of` makes a run reproducible. |
| Capture | `agent_scorecard/capture.py` | Turns a message into zero or more units, each with a kind (do, decide, explore, manage) and a done test that fits the kind. Brainstorms get no fake gate. |
| Verify | `agent_scorecard/verify.py` | Evidence-backed verification: independent verifier, evidence typed by deliverable, `inconclusive` as a real answer, a completion gate, and a calibration check against a labelled set. |
| Loop | `agent_scorecard/loop.py` | A bounded execution loop: iteration and time bounds, capped retries, escalation, a no-progress stop, pause (not fail) when capacity runs out, and `done_when` read-only to the executor. |
| Scorecard | `agent_scorecard/scorecard.py` | One table where every line is labelled MEASURED, REPLAY, ESTIMATED or `NO DATA (source: ...)`. No productivity multiplier. |
| Synthetic data | `agent_scorecard/synth.py`, `data/sample/` | A seeded generator and the log it produced, with a manifest hash. Every row has `class=synthetic`. |
| Role play | `agent_scorecard/roleplay.py`, `data/roleplay/scenarios.json` | 30 scripted scenarios across capture, verification and the loop, each with an expected outcome. |
| Sample | `agent_scorecard/sample.py` | The by-hand check: a seeded draw of your asks, a table to label with six labels, and the finish share with a Wilson interval. |
| Privacy scan | `scripts/privacy_scan.py` | Fails loudly on anything private in the tree, the file names or the whole git history. Tested by planting leaks. |

The method in plain words is in [docs/METHOD.md](docs/METHOD.md). The log format is in [docs/SCHEMA.md](docs/SCHEMA.md). Every special word is defined once in [docs/GLOSSARY.md](docs/GLOSSARY.md). To try it on your own work, follow [docs/FIRST_PILOT.md](docs/FIRST_PILOT.md).

**What this repo is and is not.** It is a synthetic, illustrative implementation of the method. It does not reproduce the audit in the post: that used my private log and a separate script, and none of its data is here. What the repo does carry is the sampling and interval code (`sample.py`), so you can run the same kind of check on your own log. Evidence here comes in three separate classes: synthetic regression results (the tests and quickstart), hypotheses (the stated rules until someone tests them on a real log), and, when anyone publishes them, real-log findings, which will be labelled as such in the changelog.

**Status.** Now: the kit runs and its tests pass on synthetic data. Next: a first run on a real log, and a person to check the AI-drafted verifier labels. Not claiming: that any number here describes a real factory, or that the rules are accurate on your data. The "strict" share that `python -m agent_scorecard sample --score out/sample.csv` prints means a finish backed by something other than the agent's own report. It is not a verified outcome.

## Five-minute quickstart

You need Python 3.10 or newer and git. No packages to install to run the tools.

```bash
git clone https://github.com/dxdev-inc/agent-scorecard.git
cd agent-scorecard
python -m agent_scorecard quickstart
```

Run everything from a clone. The CLI reads `data/` next to the package, so `pip install .` alone is not supported.

That generates a synthetic log into `out/`, then runs measure, capture replay, the verification check, a simulated
loop, the scorecard and all 30 role play scenarios. It takes about a second. To run the checks:

```bash
python -m pip install pytest
python -m pytest -q
python scripts/privacy_scan.py   # generic patterns only unless PRIVACY_DENY_FILE or --deny-file points at a private deny list kept outside the repo
```

Other commands: `generate`, `measure --as-of 2025-04-01T00:00:00Z`, `scorecard`, `capture "text"`, `verify`, `loop`, `roleplay`, `sample`.
Run `python -m agent_scorecard --help`.

### What a clean run prints (abridged)

```
1. generated a synthetic log -> out/events.jsonl  (seed 20250303, sha256 5aec23670e5cd0b7...)
   1230 rows, every row class=synthetic

2. measure (MEASURED = computed from the log by a fixed rule)
  asks_without_unit                        0.517   183/354   MEASURED
  asks_with_done_test                      0.023   8/354   MEASURED
  ask_finish_rate                          0.302   107/354   MEASURED
  minutes_ask_to_done_median               233.0   107/107   MEASURED
  trust                                    0.196   21/107   MEASURED
  claimed_pass_without_evidence            0.652   45/69   MEASURED
  reopened_within_14d                      0.114   12/105   MEASURED
  autonomous_trusted_units                     5   5/21   MEASURED

3. capture replay (REPLAY = what the capture rules would do over the same ask rows)
   asks 420, kept 354 by kind {'do': 179, 'decide': 49, 'explore': 80, 'manage': 46}
   with a done test 323, open discussion 31, dropped 66 {'bare acknowledgement': 45, 'probe prompt': 21}

4. verification rules against the labelled cases in data/verifier_cases.json
   {"n": 20, "agree": 17, "agreement": 0.85, "lenient_misses": ["k18", "k19"], "strict_misses": ["k14"], ...}

5. bounded loop, simulated silent run
   stop: paused_pool_exhausted (failure=False), shipped ['d0', 'd1', 'd2'], not verified ['d2'], resume in 1800s
...
30/30 scenarios passed
```

Read blocks 2 and 3 together. `asks_with_done_test` (8/354) is MEASURED: what the synthetic log recorded. The "with a done test 323" in block 3 is REPLAY: what the capture rules would assign to the same asks. They differ on purpose, and the gap is the point. In `claimed_pass_without_evidence`, 69 is the units with some pass event and 45 of them are not backed by evidence the rules accept. In `reopened_within_14d`, 105 is the done transitions whose 14 day window has closed or that were already reopened.

These numbers describe the **generator's settings**, not any real system. The generator is deliberately a messy
setup: most asks never become a unit, most "passes" are presence-only, a tenth of closes are forced. Its rates are
knobs in `synth.RATES` that I chose.

## How to read the scorecard

| Label | Meaning |
|---|---|
| MEASURED | Computed from the log by a fixed rule. The rule is in `measure.py`. |
| REPLAY | What other code (the capture rules, the loop) would have done over the same rows. It is not what happened. |
| ESTIMATED | Typed in by a person. Never computed, never added to a MEASURED line, never given a sample size. |
| NO DATA (source: ...) | The log has no such source. The line names what it would need. Nothing is invented. |

Each MEASURED line shows `n/of`, so you can see the denominator. "Trust" is the share of **finished** units that
have an evidence-backed, independent pass; unproven units stay in the denominator. "Reopened within 14 days" is
reported beside the finish rate because a higher finish rate could be a worse factory.

## Use it on your own log

1. Write an adapter that emits the rows in [docs/SCHEMA.md](docs/SCHEMA.md) from whatever you have. Keep it out of this repo.
2. `python -m agent_scorecard measure --log your.jsonl --as-of 2025-06-01T00:00:00Z`
3. Replace `data/verifier_cases.json` with 20 cases you labelled yourself, and run `python -m agent_scorecard verify`. Report both error directions it prints.
4. Replace the capture rules wherever your messages differ from mine. They are English keyword rules, and they will be wrong on your data.

## Limits (read this before quoting anything)

- **All data is synthetic.** The generator's rates are my choices. A number from the quickstart says what the
  tools do on an invented log, not how any real factory behaves. I have not run these tools on a real log for this repo.
- **One operator's method.** The definitions (finished, trusted, autonomous) are mine. They match published ideas in
  places (below) and are untested hypotheses in others.
- **Capture is heuristic.** It is keyword and shape rules in English, no model call. The label agreement line is
  100 percent only because the synthetic asks come from my own templates; it is a regression check, not an accuracy
  claim. It already found two real defects while I built it (see METHOD.md).
- **The verification rules are checked against 20 cases drafted by an AI, and no person has checked them yet.** The labels were written before running the rules, and
  three of the 20 were kept on purpose where the rules are known to disagree with a sensible human label: two lenient misses (a test that asserts nothing; an evidence reference that points at
  a different unit's run) and one strict miss. The rules cannot see inside evidence. Real use needs your labelled set,
  and expect the first verifier to be too lenient.
- **The loop is a harness.** The executor and checker are functions you pass in; the clock is simulated; nothing here
  talks to an agent runtime. It shows the stop rules behave. It does not show that they behave under real agents.
- **Little statistics.** The only interval is the Wilson interval in `sample.py`, for the by-hand check. No significance tests, no before/after comparison. Do not write
  "the change raised X" from one log.
- **"Finished" is the last status row being `done`.** It says nothing about whether the work was good. That is what
  trust and stability are for, and both depend on your evidence being honest.
- **Autonomy** (trusted units finished while the owner was away for 2 hours or more) assumes your away episodes are
  recorded. Idle share of session time and goal progress are `NO DATA` because this schema has no source for them.
- **Tested on one machine** (Windows, Python 3.13.5, git 2.20.1). Not tested elsewhere. Nothing here needs a newer git.
- **The privacy scan is pattern matching.** It cannot tell that a paragraph describes private structure in words it
  does not know. A semantic review by a person or a different model is a separate step and has not been done for this
  draft. On 2026-11-01 gitleaks 8.30.1 (git history and working tree) and trufflehog 3.99.7 (git history and tracked files, with verification off) were run on this repo and reported nothing; that shows no known secret pattern, not that nothing private is there. They were not re-run after later commits.

## Prior work

Winograd's 1987 Coordinator and the tools that followed came first, and most pieces below have prior art. The method borrows ideas that others published. Where I match a source, I say which part. Where I go beyond, the
claim is an untested hypothesis. Sources were read for my research notes on 2026-11-01. The rows for the harness post, agent teams and the two METR posts were re-checked against the live pages on 2026-11-01; the other rows were not re-fetched, so treat their dates and claims as unverified. Most are vendor documentation or single-author write-ups, not controlled studies.

| Idea in this repo | Source |
|---|---|
| One unit per iteration, state in files rather than in the agent's memory | Anthropic, [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) (2025-11-26); Huntley, [Ralph Wiggum as a software engineer](https://ghuntley.com/ralph/) (2025-07-14) |
| The executor may change only a status field, and removing or editing tests is forbidden. In that post this is an instruction in the agent's prompt; here `done_when` is enforced read-only by the loop code, which is my addition | Same Anthropic harness post |
| A separate, sceptical evaluator, with success agreed before building; agents grade their own work too kindly | Anthropic, [Harness design for long-running apps](https://www.anthropic.com/research/harness-design-long-running-apps) (2026-03-24) |
| Grade the outcome not the path, an "Unknown" verdict, read the transcripts to check your graders, a 0 percent pass rate more often means a broken task | Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) (2026-01-09) |
| A different model decides completion; bounds written into the condition; pause on a usage limit | Claude Code docs, [Keep Claude working toward a goal](https://code.claude.com/docs/en/goal.md) |
| Stop when two rounds in a row make no progress; pause (not fail) at a usage limit that resets soon | Claude Code docs, [Dynamic workflows](https://code.claude.com/docs/en/workflows.md) |
| Teams use significantly more tokens than one session and cost scales with active teammates, so start small (3 to 5); hooks can block a task from completing | Claude Code docs, [Agent teams](https://code.claude.com/docs/en/agent-teams) |
| A clean-context reviewer that shares nothing with the author | Cognition, [Multi-Agents: What's Actually Working](https://cognition.com/blog/multi-agents-working) (2026-04-22) |
| The requester cannot approve their own request | GitHub docs, [Risks and mitigations for Copilot cloud agent](https://docs.github.com/en/copilot/concepts/security-governance-and-network-settings/risks-and-mitigations) |
| An agent session created when a person mentions or delegates to the agent, with explicit awaiting-input and stale states (state comes from the agent's activity; nothing there measures asks) | Linear, [Developing the agent interaction](https://linear.app/developers/agent-interaction) |
| Pair output with stability; more change volume without fast feedback leads to instability | Google Cloud, [Announcing the 2025 DORA Report](https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report) (2025-09-23) |
| Sessions mostly idle waiting for a human (the post says around 80 percent); human attention is the bottleneck | Anthropic, [How employment is changing at Anthropic](https://www.anthropic.com/research/employment-at-anthropic) (2026-10-16) |
| A time-saved factor from transcripts is a "soft upper bound" on real uplift, not the productivity multiplier, so no multiplier here | METR, [Analyzing coding agent transcripts to upper bound productivity gains](https://metr.org/notes/2026-02-17-exploratory-transcript-analysis-for-estimating-time-savings-from-coding-agents/) (2026-02-17) |
| Pack key context and caveats into the title and subtitle of the main figure (METR says it wished it had been clearer about caveats in its blog post); report what failed | METR, [Notes on scientific communication](https://metr.org/blog/2025-08-11-science-comms-at-metr/) (2025-08-12); Anthropic, [Building a C compiler with parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler) (2026-02-05) |

**Where this repo differs from what I found, as hypotheses only:** the unit is a single ask from one person's stream rather than a conversation or session; an ask can span many parallel sessions; each sampled ask is judged against independent evidence; and the output splits the gap between tracker and reality by cause. Nearest prior work I found: request tracking (Winograd 1987 and the ActionWorkflow follow-up), per-resolution measurement with reversal in customer support (Intercom, Decagon), and per-session goal and outcome scoring of coding sessions (SWE-chat, Stanford, 2026). I could not find a published version of the combination. That is a statement about my search, which used one search engine and was bounded, not a claim that nobody has done it. If you know of one, [tell us](https://dxdev.com/contact/).

## How this stays current

This repo is where the method lives and changes. When a definition, a schema field, a capture rule or a stated limit changes, it goes into [CHANGELOG.md](CHANGELOG.md) under a dated, tagged release, with what we learned and what it breaks for you. The blog posts in the series say which release their numbers came from.

- **See what changed.** On GitHub, choose Watch, then Custom, then Releases. You get a note per tagged release and nothing else.
- **Hear the story behind it.** Subscribe to the newsletter at [dxdev.com/newsletter](https://dxdev.com/newsletter/). Issues carry the latest learning from this repo.
- **Tell us what broke or what we missed.** Prior work, a wrong definition, an adapter you wrote: use the [contact form](https://dxdev.com/contact/). We read every note.
- **Versions.** `pyproject.toml`, `agent_scorecard.__version__` and the newest changelog heading agree (a test checks it); tags are cut separately at release. The log format is versioned at the top of [docs/SCHEMA.md](docs/SCHEMA.md), and a release that changes it says so under "What this breaks".

**Release rhythm (proposal, not a promise).** Weekly, tied to the newsletter: cut a tagged release only when the method changed or a limit was lifted. A week with nothing gets no release and no "no change" entry. DXdev has not confirmed this cadence yet.

## License

MIT, see [LICENSE](LICENSE). Published by DXdev.
