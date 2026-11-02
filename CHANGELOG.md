# Changelog

Dated, newest first. Each release says what we learned, what changed in the method, what it breaks for you, and what is still open. Releases are tagged `vX.Y.Z`. On GitHub, choose Watch, then Custom, then Releases to be told about each one. Newsletter: https://dxdev.com/newsletter/ . Questions or corrections: https://dxdev.com/contact/ .

All figures in this repo are synthetic. A learning below is about the tools, not about any real factory.

## 0.3.0 (2026-11-01)

**What we learned**
- An outside review found that several of our own safeguards could be defeated or were false-clean: a verifier or evidence ref of only spaces counted as a trusted pass, the privacy scan skipped git-ignored files (where `out/` sample tables live), and passing both `--tree-only` and `--history-only` scanned nothing and reported clean.
- The documented commands had never been run literally. `sample --score` without a path failed, and the default sample size failed on a log with fewer than 80 asks.

**What changed in the method**
- Verification: a verifier name or evidence `ref` that is empty after trimming whitespace is treated as missing (inconclusive).
- Timestamps: a timestamp with no zone is now an error instead of being read in the machine's local time. Explicit offsets are converted to UTC.
- `sample`: `--k` larger than the number of asks is capped, with a printed note.
- Privacy scan: the tree scan now includes git-ignored files (not caches or environments), takes an optional PATH to scan another folder, and exits 2 on unknown or conflicting flags.
- Verification: executor, requester and verifier are compared after trimming whitespace on all three.
- Event logs: `forced` and `outcome_observed` must be real JSON booleans (the string "false" is an error), and `measure.load` now validates every row and raises a ValueError naming the line, so `measure` and `scorecard` refuse a bad log instead of computing from it.
- `sample --k` below 1 is rejected.
- `sample --log` refuses (exit 2) to overwrite an existing output table, which may hold hand labels, unless `--force` is given. Scoring an unlabelled table prints a clean message and exits 2 instead of a traceback.
- Privacy scan: annotated tag messages and tagger lines are scanned, `.idea` and `.vscode` are no longer skipped, and PDFs, archives, images and other known binary types are rejected by extension or file signature even when they contain no NUL byte.
- Docs: added docs/GLOSSARY.md and docs/FIRST_PILOT.md; fixed the commands in the README and pilot guide to the full literal form; said plainly that the loose finished share does not check evidence.

**What this breaks**
- The Python package was renamed from `factory_kit` to `agent_scorecard` (`python -m agent_scorecard ...`, `import agent_scorecard`). Anything importing the old name must change. The `v0.2.0` tag points at the old layout, so use this release or later.
- Event logs with naive timestamps (no `Z` or offset), string booleans, or any other schema error now raise an error when loaded. Fix the rows. The log schema version is unchanged (1).

**Still open**
- The glossary reconciles the two bars by naming them, it does not make them the same bar. Still no real-log run.
- Capture replay counts only the first ask of a message that holds several.

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
