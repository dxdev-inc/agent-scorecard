"""Measure asks against finished work, from an event log.

Every number comes back as {"value", "n", "of", "label", "note"}: what it is, how many rows it rests on, out of
how many, and where it comes from. Label here is always MEASURED (computed from the log by a fixed rule). Numbers
produced by replaying other code over the log, or typed in by a person, are labelled in `scorecard.py`.

`as_of` cuts the log: rows after it are ignored, so the same log measured at the same date gives the same
numbers, and the same log measured at two dates shows the drift.

What "finished" means here: the unit's LAST status event at `as_of` is `done`. A unit later reopened or
reverted is not finished. What "trusted" means: a finished, non-forced unit with a verify event that
`verify.judge` credits as pass.
"""
from __future__ import annotations

import json
import math
from datetime import timedelta
from pathlib import Path

from . import verify
from .schema import parse_ts

STABILITY_WINDOW_DAYS = 14
IDLE_EPISODE_MIN_HOURS = 2


def load(path: str | Path) -> list[dict]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _m(value, n, of, note=""):
    return {"value": value, "n": n, "of": of, "label": "MEASURED", "note": note}


def _pct(sorted_vals: list[float], p: float):
    if not sorted_vals:
        return None
    k = max(0, math.ceil(p * len(sorted_vals)) - 1)
    return sorted_vals[k]


def fold(events: list[dict], as_of: str | None = None) -> dict:
    """The read model: asks, units (with status history and verify events), idle episodes, usage."""
    cut = parse_ts(as_of) if as_of else None
    rows = [e for e in events if cut is None or parse_ts(e["ts"]) <= cut]
    rows.sort(key=lambda e: parse_ts(e["ts"]))
    asks, units, idle, interventions = {}, {}, [], 0
    for e in rows:
        t = e["type"]
        if t == "ask":
            asks[e["ask_id"]] = {"ts": parse_ts(e["ts"]), "text": e["text"]}
        elif t == "unit_created":
            units[e["unit"]] = {"id": e["unit"], "ask_id": e.get("ask_id"), "kind": e["kind"],
                                "done_when": e.get("done_when"), "deliverable": e["deliverable"],
                                "executor": e["executor"], "requester": e["requester"],
                                "created": parse_ts(e["ts"]), "history": [], "verifies": [], "tokens": 0}
        elif t == "status" and e["unit"] in units:
            units[e["unit"]]["history"].append((parse_ts(e["ts"]), e["status"], bool(e.get("forced"))))
        elif t == "verify" and e["unit"] in units:
            units[e["unit"]]["verifies"].append(e)
        elif t == "usage" and e["unit"] in units:
            units[e["unit"]]["tokens"] += int(e["tokens"])
        elif t == "owner_idle":
            idle.append((parse_ts(e["start"]), parse_ts(e["end"])))
        elif t == "intervention":
            interventions += 1
    end = cut or (parse_ts(rows[-1]["ts"]) if rows else None)
    return {"asks": asks, "units": units, "idle": idle, "interventions": interventions, "as_of": cut, "end": end}


def _final(u: dict):
    return u["history"][-1] if u["history"] else None


def _done_ts(u: dict):
    """When the unit last reached done, if it is finished at the end of the log."""
    f = _final(u)
    if f and f[1] == "done":
        return f[0]
    return None


def compute(events: list[dict], as_of: str | None = None) -> dict:
    s = fold(events, as_of)
    asks, units = s["asks"], s["units"]
    by_ask = {u["ask_id"]: u for u in units.values() if u["ask_id"]}
    out = {"as_of": as_of or "end of log"}

    # Coverage: how many asks became a unit, and how many carry a done test.
    n_asks = len(asks)
    mapped = [a for a in asks if a in by_ask]
    with_done = [a for a in mapped if by_ask[a].get("done_when")]
    out["asks_without_unit"] = _m(round(1 - len(mapped) / n_asks, 3) if n_asks else None, n_asks - len(mapped), n_asks,
                                  "share of all ask rows with no unit (includes filler)")
    out["asks_with_done_test"] = _m(round(len(with_done) / n_asks, 3) if n_asks else None, len(with_done), n_asks)

    # Finish rate and time to done, over asks that became units.
    finished = [(a, by_ask[a]) for a in mapped if _done_ts(by_ask[a])]
    out["ask_finish_rate"] = _m(round(len(finished) / n_asks, 3) if n_asks else None, len(finished), n_asks,
                                "asks whose unit is done at as_of, over all ask rows")
    mins = sorted((_done_ts(u) - asks[a]["ts"]).total_seconds() / 60 for a, u in finished)
    out["minutes_ask_to_done_median"] = _m(_pct(mins, 0.5), len(mins), len(finished), "nearest rank")
    out["minutes_ask_to_done_p90"] = _m(_pct(mins, 0.9), len(mins), len(finished), "nearest rank")

    # Trust: finished, non-forced units with an evidence-backed independent pass, over all finished units.
    done_units = [u for u in units.values() if _done_ts(u)]
    forced = [u for u in done_units if _final(u)[2]]
    trusted = [u for u in done_units if not _final(u)[2] and any(verify.evidence_backed(u, v) for v in u["verifies"])]
    any_pass = [u for u in done_units if any(v["result"] == "pass" for v in u["verifies"])]
    out["trust"] = _m(round(len(trusted) / len(done_units), 3) if done_units else None, len(trusted), len(done_units),
                      "evidence-backed independent pass / all finished units; unproven units stay in the denominator")
    out["claimed_pass_without_evidence"] = _m(
        round((len(any_pass) - len(trusted)) / len(any_pass), 3) if any_pass else None,
        len(any_pass) - len(trusted), len(any_pass), "units with some pass event that the evidence rules do not credit")
    out["forced_done"] = _m(round(len(forced) / len(done_units), 3) if done_units else None, len(forced), len(done_units))

    # Stability: of the units that reached done and whose window has closed, how many were reopened or reverted.
    window = timedelta(days=STABILITY_WINDOW_DAYS)
    reached, unstable = 0, 0
    for u in units.values():
        h = u["history"]
        for i, (ts, st, _f) in enumerate(h):
            if st != "done":
                continue
            reopened = any(st2 in ("reopened", "reverted") and ts2 - ts <= window for ts2, st2, _ in h[i + 1:])
            if reopened or s["end"] - ts >= window:      # a window still open and clean is not yet knowable
                reached += 1
                unstable += 1 if reopened else 0
    out["reopened_within_14d"] = _m(round(unstable / reached, 3) if reached else None, unstable, reached,
                                    "share of done transitions followed by reopened or reverted inside 14 days")

    # Autonomy: finished, evidence-backed units whose done time falls inside a person-away episode of 2h or more.
    long_idle = [(a, b) for a, b in s["idle"] if (b - a) >= timedelta(hours=IDLE_EPISODE_MIN_HOURS)]
    auto = [u for u in trusted if any(a <= _done_ts(u) <= b for a, b in long_idle)]
    out["autonomous_trusted_units"] = _m(len(auto), len(auto), len(trusted),
                                         f"trusted units finished during an idle episode of {IDLE_EPISODE_MIN_HOURS}h or more")

    # Interventions and cost.
    out["interventions_per_finished_unit"] = _m(
        round(s["interventions"] / len(done_units), 3) if done_units else None, s["interventions"], len(done_units))
    toks = sum(u["tokens"] for u in done_units)
    out["tokens_per_finished_unit"] = _m(round(toks / len(done_units)) if done_units else None, toks, len(done_units))
    return out
