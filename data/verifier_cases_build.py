"""Regenerates verifier_cases.json. The labels are the author's judgment, written BEFORE running the rules, and two
cases are kept on purpose where the rules are known to disagree (see `note`). Replace this set with your own."""
import json
from pathlib import Path


def case(i, deliv, verifier, result, kind, observed, human, note="", ref="run-1", executor="worker-1"):
    ev = None if kind is None else {"kind": kind, "ref": ref, "outcome_observed": observed}
    return {"id": i, "human": human, "note": note,
            "unit": {"id": "u", "deliverable": deliv, "executor": executor, "requester": "owner"},
            "event": {"verifier": verifier, "result": result, "evidence": ev}}


cases = [
    case("k01", "code", "checker-1", "pass", "test_run", True, "pass"),
    case("k02", "code", "checker-1", "pass", "replay_output", True, "pass"),
    case("k03", "page", "checker-1", "pass", "render_capture", True, "pass"),
    case("k04", "page", "checker-1", "pass", "assertion", True, "pass"),
    case("k05", "data", "checker-1", "pass", "stored_row_rerun_match", True, "pass"),
    case("k06", "document", "checker-1", "pass", "named_check", True, "pass"),
    case("k07", "config", "checker-1", "pass", "dry_run", True, "pass"),
    case("k08", "config", "checker-1", "pass", "firing_log", True, "pass"),
    case("k09", "code", "worker-1", "pass", "test_run", True, "not_pass", "executor graded its own work"),
    case("k10", "code", "owner", "pass", "test_run", True, "not_pass", "the requester approved their own request"),
    case("k11", "code", "checker-1", "pass", "file_exists", False, "not_pass", "presence only"),
    case("k12", "code", "checker-1", "pass", "commit_exists", False, "not_pass", "presence only"),
    case("k13", "page", "checker-1", "pass", None, False, "not_pass", "a pass with nothing behind it"),
    case("k14", "code", "checker-1", "pass", "render_capture", True, "pass",
         "KNOWN STRICT MISS: a captured terminal render is fine evidence for a code change; the type table withholds it"),
    case("k15", "code", "checker-1", "fail", "test_run", True, "not_pass", "verifier failed it"),
    case("k16", "code", "checker-1", "inconclusive", None, False, "not_pass", "verifier could not tell"),
    case("k17", "data", "checker-1", "pass", "stored_row_rerun_match", False, "not_pass", "evidence says the outcome was not observed"),
    case("k18", "code", "checker-1", "pass", "test_run", True, "not_pass",
         "KNOWN LENIENT MISS: the test run is typed and independent but the test asserts nothing; rules cannot see that"),
    case("k19", "document", "checker-1", "pass", "named_check", True, "not_pass",
         "KNOWN LENIENT MISS: the evidence ref points at a different unit's run; rules do not resolve refs", ref="run-of-another-unit"),
    case("k20", "code", "checker-2", "pass", "test_run", True, "pass"),
]
Path(__file__).with_name("verifier_cases.json").write_text(
    json.dumps({"note": "20 labelled cases. Labels are the author's. Use your own.", "cases": cases}, indent=1) + "\n",
    encoding="utf-8")
print("wrote", len(cases))
