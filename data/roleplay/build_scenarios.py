"""Regenerates scenarios.json so the file stays readable as data. Run: python data/roleplay/build_scenarios.py"""
import json
from pathlib import Path

C = lambda i, group, text, **expect: {"id": i, "type": "capture", "group": group, "text": text, "expect": expect}
cap = [
    C("c01", "tell-me is a question, not a relay", "tell me why the nightly job failed yesterday", keep=True, kind="explore", done_kind="finding_stored"),
    C("c02", "relay to a third party", "tell the reviewer to hold the exporter until i look at the numbers", keep=True, kind="manage", done_kind="relay_delivered_and_acted"),
    C("c03", "action plus a tell-me tail", "deploy the exporter and tell me when it is live", keep=True, kind="do", done_kind="outcome_verified"),
    C("c04", "decision with a request to explain", "i cannot decide between sqlite and postgres, pick one for me and tell me why", keep=True, kind="decide", done_kind="decision_recorded"),
    C("c05", "thinking out loud gets no fake gate", "what if the queue worker ran unattended overnight, just curious what you think", keep=True, kind="explore", done_kind="open_discussion"),
    C("c06", "bare acknowledgement", "ok", keep=False),
    C("c07", "probe prompt", "reply with exactly OK", keep=False),
    C("c08", "machine relay", "[relay from reviewer] the gate is green and the change landed", keep=False),
    C("c09", "acknowledgement that carries an instruction", "ok now add a retry to the exporter and write a test for it", keep=True, kind="do"),
    C("c10", "ordinals split into three", "first add a retry to the exporter, second write a test for it, third show me the diff before anything goes out", keep=True, kind="do", parts=3),
    C("c11", "counted lead splits into two", "two things, fix the footer so it stops clipping, and also tell me which jobs are idle right now", keep=True, kind="do", parts=2),
    C("c12", "a plain and never splits", "fix the footer and add a test", keep=True, kind="do", parts=1),
    C("c13", "a concrete need without an action verb", "i need the usage report split by region for last week", keep=True, kind="do"),
    C("c14", "i need plus brainstorm stays a brainstorm", "i need to think about how this could run overnight, just brainstorming", keep=True, kind="explore", done_kind="open_discussion"),
    C("c15", "plain decision", "should we ship the fix now or wait for the review", keep=True, kind="decide"),
    C("c16", "ask a third party", "ask the maintainer to send me a short status when they get a chance", keep=True, kind="manage"),
    C("c17", "polite acknowledgement", "yes please go ahead", keep=False),
    C("c18", "modal request", "can you rename the verbose flag", keep=True, kind="do"),
    C("c19", "one word is not an ask", "why", keep=False),
]
U = lambda deliverable, executor="worker-1", requester="owner": {"id": "u", "deliverable": deliverable, "executor": executor, "requester": requester}
E = lambda verifier, result, kind=None, observed=True: {"verifier": verifier, "result": result,
    "evidence": None if kind is None else {"kind": kind, "ref": "r", "outcome_observed": observed}}
ver = [
    {"id": "v01", "type": "verify", "group": "executor grades own work", "unit": U("code"), "event": E("worker-1", "pass", "test_run"), "expect": "inconclusive"},
    {"id": "v02", "type": "verify", "group": "requester approves own request", "unit": U("code"), "event": E("owner", "pass", "test_run"), "expect": "inconclusive"},
    {"id": "v03", "type": "verify", "group": "presence is not an outcome", "unit": U("code"), "event": E("checker-1", "pass", "file_exists", False), "expect": "inconclusive"},
    {"id": "v04", "type": "verify", "group": "the honest pass", "unit": U("code"), "event": E("checker-1", "pass", "test_run"), "expect": "pass"},
    {"id": "v05", "type": "verify", "group": "evidence of the wrong type", "unit": U("code"), "event": E("checker-1", "pass", "render_capture"), "expect": "inconclusive"},
    {"id": "v06", "type": "verify", "group": "a pass with nothing behind it", "unit": U("page"), "event": E("checker-1", "pass"), "expect": "inconclusive"},
]
unit = lambda i, dv="code", pr=0: {"id": i, "status": "open", "priority": pr, "retries": 0, "done_when": "outcome observed", "deliverable": dv, "executor": "worker-1", "requester": "owner"}
ok = {"claim": "done", "seconds": 600}
good = E("checker-1", "pass", "test_run")
weak = E("checker-1", "pass", "file_exists", False)
loops = [
    {"id": "l01", "type": "loop", "group": "two units, both independently verified", "units": [unit("a", pr=2), unit("b", pr=1)],
     "executor": {"a": [ok], "b": [ok]}, "checks": {"a": good, "b": good}, "pool": 5, "config": {}, "ideas": [],
     "expect": {"stop_reason": "done", "shipped": ["a", "b"], "failure": False}},
    {"id": "l02", "type": "loop", "group": "executor edits its own done test", "units": [unit("a")],
     "executor": {"a": [{"claim": "done", "seconds": 60, "edits_done_when": "file exists"}]}, "checks": {"a": good}, "pool": 5,
     "config": {"max_retries": 1, "no_progress_limit": 9}, "ideas": [],
     "expect": {"shipped": [], "escalated": ["a"], "refused": ["a", "a"]}},
    {"id": "l03", "type": "loop", "group": "no new verified evidence for two rounds", "units": [unit("a", pr=2), unit("b", pr=1)],
     "executor": {"a": [ok], "b": [ok]}, "checks": {"a": weak, "b": weak}, "pool": 5, "config": {"no_progress_limit": 2}, "ideas": [],
     "expect": {"stop_reason": "no_progress", "shipped": [], "failure": True}},
    {"id": "l04", "type": "loop", "group": "pool runs out: pause, not failure", "units": [unit("a", pr=2), unit("b", pr=1)],
     "executor": {"a": [ok], "b": [ok]}, "checks": {"a": good, "b": good}, "pool": 1, "pool_reset_s": 1800, "config": {}, "ideas": [],
     "expect": {"stop_reason": "paused_pool_exhausted", "shipped": ["a"], "failure": False, "resume_in_s": 1800}},
    {"id": "l05", "type": "loop", "group": "idle: start the overdue idea, drop the one with no done test", "units": [],
     "executor": {"i1": [ok]}, "checks": {"i1": good}, "pool": 5, "config": {}, "today": "2025-03-10",
     "ideas": [{"id": "i1", "review_by": "2025-03-01", "done_when": "outcome observed", "deliverable": "code", "executor": "worker-1", "requester": "owner"},
               {"id": "i2", "review_by": "2025-03-02", "done_when": None, "deliverable": "code", "executor": "worker-1", "requester": "owner"}],
     "expect": {"stop_reason": "done", "shipped": ["i1"], "dropped": ["i2"]}},
]
out = {"note": "30 scenarios. Authored from the failure classes of the method; run with python -m factory_kit roleplay.",
       "scenarios": cap + ver + loops}
assert len(out["scenarios"]) == 30
Path(__file__).with_name("scenarios.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
print("wrote", len(out["scenarios"]))
