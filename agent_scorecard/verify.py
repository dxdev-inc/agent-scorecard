"""Evidence-backed verification.

A unit is "done" when someone SAYS it is. It is TRUSTED when an independent check recorded evidence of the
outcome. This module is the second half.

Rules, in the order they are applied to a claimed pass:
  1. A claimed fail or inconclusive stays what it is.
  2. A verifier must be named, and must not be the executor or the person who asked. Otherwise: inconclusive.
  3. No evidence, or evidence with no `ref` to check it by: inconclusive.
  4. Presence-only evidence (the file exists, the commit exists) proves nothing about the outcome: inconclusive.
  5. The evidence kind must be one the deliverable type requires (table below). Otherwise: inconclusive.
  6. The evidence must record that the outcome was observed. Otherwise: inconclusive.
  7. Only then: pass.

`inconclusive` is a real answer and a different one from `fail`. An unproven unit stays out of the numerator
of trust and stays in the denominator.
"""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_EVIDENCE = {
    "code": {"test_run", "replay_output"},
    "page": {"render_capture", "assertion"},
    "data": {"stored_row_rerun_match"},
    "document": {"named_check"},
    "config": {"dry_run", "firing_log"},
}
PRESENCE_ONLY = {"file_exists", "presence", "commit_exists"}


def judge(unit: dict, event: dict) -> tuple[str, str]:
    """(credited result, reason) for one verify event against the unit it is about."""
    claimed = event.get("result")
    if claimed != "pass":
        return claimed, "verifier did not claim a pass"
    verifier = event.get("verifier")
    verifier = verifier.strip() if isinstance(verifier, str) else verifier
    if not verifier:
        return "inconclusive", "no verifier recorded"
    if verifier == unit.get("executor"):
        return "inconclusive", "verifier is the executor"
    if verifier == unit.get("requester"):
        return "inconclusive", "verifier is the requester"
    ev = event.get("evidence")
    if not ev:
        return "inconclusive", "no evidence recorded"
    ref = ev.get("ref")
    if not (ref.strip() if isinstance(ref, str) else ref):
        return "inconclusive", "evidence has no ref to check it by"
    kind = ev.get("kind")
    if kind in PRESENCE_ONLY:
        return "inconclusive", "presence-only evidence"
    if kind not in REQUIRED_EVIDENCE.get(unit.get("deliverable"), set()):
        return "inconclusive", f"evidence kind {kind!r} does not fit a {unit.get('deliverable')} deliverable"
    if not ev.get("outcome_observed"):
        return "inconclusive", "evidence does not record the outcome being observed"
    return "pass", "independent, typed, outcome observed"


def evidence_backed(unit: dict, event: dict) -> bool:
    return judge(unit, event)[0] == "pass"


def can_close(unit: dict, verify_events: list[dict], forced: bool = False) -> tuple[bool, str]:
    """The completion gate: a unit cannot be marked done at the moment of the claim without an evidence-backed
    pass. A forced close is allowed to happen but never counts toward trust, and says so."""
    if any(evidence_backed(unit, e) for e in verify_events):
        return True, "evidence-backed pass present"
    if forced:
        return True, "forced close: allowed, recorded, never counted toward trust"
    return False, "refused: no evidence-backed pass"


def load_cases(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["cases"]


def calibrate(cases: list[dict]) -> dict:
    """Agreement between `judge` and a labelled set. Each case: {id, unit, event, human: "pass"|"not_pass"}.

    Reports both error directions, because they cost different things: a LENIENT miss (judge passes, human
    does not) lets bad work count as trusted; a STRICT miss (judge withholds, human passes) only costs a re-check.
    Also flags a judge that never passes anything, which is more likely broken than strict."""
    agree, lenient, strict, passes = 0, [], [], 0
    for c in cases:
        got = judge(c["unit"], c["event"])[0]
        got_pass = got == "pass"
        passes += got_pass
        want_pass = c["human"] == "pass"
        if got_pass == want_pass:
            agree += 1
        elif got_pass:
            lenient.append(c["id"])
        else:
            strict.append(c["id"])
    n = len(cases)
    return {"n": n, "agree": agree, "agreement": round(agree / n, 3) if n else None,
            "lenient_misses": lenient, "strict_misses": strict, "judge_passes": passes,
            "never_passes_suspect": n > 0 and passes == 0}
