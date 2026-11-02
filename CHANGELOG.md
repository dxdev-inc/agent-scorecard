# Changelog

Dated, newest first. Each release says what we learned, what changed in the method, what it breaks for you, and what is still open. Releases are tagged `vX.Y.Z`. On GitHub, choose Watch, then Custom, then Releases to be told about each one. Newsletter: https://dxdev.com/newsletter/ . Questions or corrections: https://dxdev.com/contact/ .

All figures in this repo are synthetic. A learning below is about the tools, not about any real factory.

## Unreleased

- Added docs/GLOSSARY.md (one glossary for the four vocabularies, and how by-hand `finished` differs from the event-log `done` for explore) and docs/FIRST_PILOT.md (checklist for a first real run). No code or results changed.
- Still open: the glossary reconciles the two bars by naming them, it does not make them the same bar. Still no real-log run.

## 0.2.0 (2026-11-01)

**What we learned**
- The by-hand check in the first post had no code behind it here. A reader coming from the post would find an event-log kit and no sampler. The sampler and the interval are now in the repo.
- Our own README said "no confidence intervals" while the post's method depends on one. The two disagreed until a reviewer pointed it out.
- A README that opens by saying its main claim cannot be checked loses the reader on the first screen. It now opens on what the kit does and who it is for.

**What changed in the method**
- New `sample` command: a seeded draw of asks, a table with six labels (finished, partly_done, dropped, superseded, cannot_tell, not_a_request), and a score with a strict reading that drops a finish backed only by the agent's own report. Intervals are Wilson 95 percent.
- The README now explains MEASURED against REPLAY in the sample output, and what the 69 and 105 denominators are.

**What this breaks**
- Nothing. The event log schema is unchanged (version 1).

**Still open**
- The tools have not been run on a real log for this repo.
- The six labels in `sample` and the kinds and verdicts in the event log are two vocabularies. A single glossary is not written yet.
- The post says a question counts as handled when it is answered in the next turn. That is looser than the explore done test in docs/METHOD.md. Not reconciled.

## 0.1.0 (2026-11-01)

First drop, synthetic data only.

**What we learned** (from "Mistakes made while building this" in docs/METHOD.md)
- Sorting synthetic rows by timestamp then type put a status row before its unit row at the same second, and the measures silently ignored those statuses. Emission order is now kept for ties.
- A label agreement line of 88.6 percent flagged a capture defect before anyone read a row: brainstorm asks were dropped as too short. A brainstorm cue now counts as a trigger.
- A stated need with no action verb was dropped by the capture rules. The rule was fixed, not the scenario.
- Filler and probe rows were counted in the ask denominators. They are excluded now, with a regression test for each fix.

**What changed in the method**
- Initial measure, capture, verify, loop, scorecard, role play and privacy scan modules.

**What this breaks**
- Nothing, first release.

**Still open**
- Same as under 0.2.0.
