"""The role play harness: 30 scripted scenarios that exercise capture, verification and the loop, each with an
expected outcome. A scenario that fails prints what it expected and what it got. Nothing here calls a model.

Scenarios are data (`data/roleplay/scenarios.json`), written from the failure classes the method exists to catch:
a question mistaken for a relay, a brainstorm given a fake gate, a unit graded by its own executor, an executor
that rewrites its own done test, a pool that runs out mid-run.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import capture, loop, verify

DEFAULT = Path(__file__).resolve().parent.parent / "data" / "roleplay" / "scenarios.json"


def load(path: str | Path = DEFAULT) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["scenarios"]


def _capture(sc: dict) -> tuple[bool, str]:
    c = capture.classify(sc["text"])
    exp = sc["expect"]
    got = {"keep": c["keep"]}
    if c["keep"]:
        got.update(kind=c["kind"], done_kind=c["done_kind"], parts=len(c.get("parts") or [sc["text"]]))
    for k, v in exp.items():
        if got.get(k) != v:
            return False, f"expected {exp}, got {got}"
    return True, ""


def _verify(sc: dict) -> tuple[bool, str]:
    got, why = verify.judge(sc["unit"], sc["event"])
    return got == sc["expect"], f"expected {sc['expect']}, got {got} ({why})"


def _loop(sc: dict) -> tuple[bool, str]:
    scripts = {k: list(v) for k, v in sc["executor"].items()}

    def executor(u):
        s = scripts[u["id"]]
        return dict(s.pop(0) if len(s) > 1 else s[0])

    def checker(u, res):
        return dict(sc["checks"][u["id"]])

    pool = loop.Pool(sc["pool"], sc.get("pool_reset_s", 3600))
    cfg = loop.Config(**sc["config"])
    rep = loop.run([dict(u) for u in sc["units"]], executor, checker, pool, cfg, sc["ideas"], sc.get("today", ""))
    exp = sc["expect"]
    got = {"stop_reason": rep["stop_reason"], "shipped": rep["shipped"], "failure": rep["failure"],
           "escalated": rep["escalated"], "refused": rep["refused_done_when_edits"],
           "dropped": [d["id"] for d in rep["dropped_ideas"]], "resume_in_s": rep["resume_in_s"]}
    for k, v in exp.items():
        if got[k] != v:
            return False, f"expected {exp}, got { {k2: got[k2] for k2 in exp} }"
    return True, ""


RUNNERS = {"capture": _capture, "verify": _verify, "loop": _loop}


def run_all(path: str | Path = DEFAULT) -> dict:
    results = []
    for sc in load(path):
        ok, why = RUNNERS[sc["type"]](sc)
        results.append({"id": sc["id"], "type": sc["type"], "group": sc["group"], "ok": ok, "why": "" if ok else why})
    return {"total": len(results), "passed": sum(r["ok"] for r in results), "results": results}


def render(rep: dict) -> str:
    lines = [f"{'PASS' if r['ok'] else 'FAIL'}  {r['id']}  {r['type']:<7} {r['group']}" +
             ("" if r["ok"] else f"\n      {r['why']}") for r in rep["results"]]
    return "\n".join(lines) + f"\n\n{rep['passed']}/{rep['total']} scenarios passed"
