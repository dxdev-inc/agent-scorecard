"""A bounded execution loop with stop rules.

One unit per iteration. State lives in the unit list, not in the executor's memory. The executor does the
work; a DIFFERENT party checks it (`verify.judge`); the loop decides what happens next.

Bounds and stop rules (each shows up as `stop_reason` in the report):
  max_iterations         hard cap on iterations
  wall_clock             simulated or real seconds budget for the run
  no_progress            N consecutive iterations with no new independently verified evidence (default 2)
  paused_pool_exhausted  the pool of capacity ran out: PAUSE with the reset time. Not a failure.
  no_ready_units         nothing ready and no overdue idea to start
  done                   every unit is closed

Rules that hold inside the loop:
  * `done_when` is read-only to the executor. A result that edits it is refused, counts as no progress, and
    the edit is logged. Changing a done test needs a separate decision, outside this loop.
  * A unit retries up to `max_retries`, then is ESCALATED (handed to a person), never retried forever.
  * An unverified claim of done is not done. The unit closes only through `verify.can_close`.
  * With nothing ready, the oldest idea past its `review_by` date is started (if it has a done test) or
    dropped with a stated reason. Nothing sits open past its date.

The loop takes the clock and the executor as arguments, so a replay is deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import verify


@dataclass
class Config:
    max_iterations: int = 20
    wall_clock_s: int = 6 * 3600
    max_retries: int = 2
    no_progress_limit: int = 2


@dataclass
class Pool:
    """Capacity that runs out. `reset_in_s` is how long until it refills."""
    remaining: int
    reset_in_s: int = 3600

    def has_room(self) -> bool:
        return self.remaining > 0

    def consume(self) -> None:
        self.remaining -= 1


def _ready(units: list[dict], cfg: Config) -> list[dict]:
    r = [u for u in units if u["status"] == "open" and u.get("done_when") and u.get("retries", 0) <= cfg.max_retries]
    return sorted(r, key=lambda u: (-u.get("priority", 0), u["id"]))


def run(units: list[dict], executor, checker, pool: Pool, cfg: Config | None = None,
        ideas: list[dict] | None = None, today: str = "") -> dict:
    """executor(unit) -> {"seconds": int, "claim": "done"|"stuck", "edits_done_when": str|None}
    checker(unit, result) -> a verify event {verifier, result, evidence}
    ideas: [{"id", "review_by", "done_when"|None, "deliverable", "executor", "requester"}], review_by ISO date."""
    cfg = cfg or Config()
    ideas = list(ideas or [])
    elapsed, no_progress, ran, trace = 0, 0, 0, []
    shipped, escalated, refused, dropped = [], [], [], []
    stop = "max_iterations"
    for i in range(1, cfg.max_iterations + 1):
        if elapsed >= cfg.wall_clock_s:
            stop = "wall_clock"
            break
        ready = _ready(units, cfg)
        if ready and not pool.has_room():
            stop = "paused_pool_exhausted"
            trace.append({"i": i, "event": "pause", "resume_in_s": pool.reset_in_s})
            break
        if not ready:
            started = False
            for idea in sorted([x for x in ideas if x["review_by"] <= today], key=lambda x: x["review_by"]):
                ideas.remove(idea)
                if idea.get("done_when"):
                    units.append({"id": idea["id"], "status": "open", "priority": 0, "retries": 0,
                                  **{k: idea[k] for k in ("done_when", "deliverable", "executor", "requester")}})
                    trace.append({"i": i, "event": "idea_started", "unit": idea["id"]})
                    started = True
                    break
                dropped.append({"id": idea["id"], "reason": "overdue idea has no done test"})
                trace.append({"i": i, "event": "idea_dropped", "unit": idea["id"], "reason": "no done test"})
            if started:
                continue
            stop = "done" if all(u["status"] != "open" for u in units) else "no_ready_units"
            break
        u = ready[0]
        pool.consume()
        ran += 1
        res = executor(u)
        elapsed += int(res.get("seconds", 0))
        if res.get("edits_done_when") is not None:
            refused.append(u["id"])
            u["retries"] = u.get("retries", 0) + 1
            no_progress += 1
            trace.append({"i": i, "unit": u["id"], "event": "refused_done_when_edit"})
        elif res.get("claim") != "done":
            u["retries"] = u.get("retries", 0) + 1
            no_progress += 1
            trace.append({"i": i, "unit": u["id"], "event": "stuck"})
        else:
            ev = checker(u, res)
            credited, why = verify.judge(u, ev)
            ok, _ = verify.can_close(u, [ev])
            if credited == "pass" and ok:
                u["status"] = "done"
                shipped.append(u["id"])
                no_progress = 0
                trace.append({"i": i, "unit": u["id"], "event": "closed", "evidence": ev["evidence"]["kind"]})
            else:
                u["retries"] = u.get("retries", 0) + 1
                no_progress += 1
                trace.append({"i": i, "unit": u["id"], "event": "not_verified", "credited": credited, "why": why})
        if u["status"] == "open" and u.get("retries", 0) > cfg.max_retries:
            u["status"] = "escalated"
            escalated.append(u["id"])
            trace.append({"i": i, "unit": u["id"], "event": "escalated"})
        if no_progress >= cfg.no_progress_limit:
            stop = "no_progress"
            break
    else:
        stop = "max_iterations"
    if stop == "max_iterations":
        stop = "done" if all(u["status"] != "open" for u in units) else stop
    return {"stop_reason": stop, "failure": stop in ("no_progress", "wall_clock", "max_iterations"),
            "iterations": ran, "elapsed_s": elapsed, "shipped": shipped, "escalated": escalated,
            "refused_done_when_edits": refused, "dropped_ideas": dropped,
            "resume_in_s": pool.reset_in_s if stop == "paused_pool_exhausted" else None, "trace": trace}
