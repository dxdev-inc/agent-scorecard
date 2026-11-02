from agent_scorecard import verify
from agent_scorecard.cli import CASES


def u(deliv="code", executor="worker-1", requester="owner"):
    return {"deliverable": deliv, "executor": executor, "requester": requester}


def e(verifier="checker-1", result="pass", kind="test_run", observed=True):
    return {"verifier": verifier, "result": result,
            "evidence": None if kind is None else {"kind": kind, "ref": "r", "outcome_observed": observed}}


def test_each_rule_withholds_a_pass():
    assert verify.judge(u(), e())[0] == "pass"
    assert verify.judge(u(), e(verifier="worker-1"))[0] == "inconclusive"
    assert verify.judge(u(), e(verifier="owner"))[0] == "inconclusive"
    assert verify.judge(u(), e(kind=None))[0] == "inconclusive"
    assert verify.judge(u(), e(kind="file_exists"))[0] == "inconclusive"
    assert verify.judge(u(), e(kind="render_capture"))[0] == "inconclusive"
    assert verify.judge(u(), e(observed=False))[0] == "inconclusive"


def test_a_claimed_fail_stays_a_fail_and_inconclusive_is_not_fail():
    assert verify.judge(u(), e(result="fail"))[0] == "fail"
    assert verify.judge(u(), e(verifier="worker-1"))[0] != "fail"


def test_every_deliverable_type_has_a_table_row():
    from agent_scorecard.schema import DELIVERABLES
    assert set(verify.REQUIRED_EVIDENCE) == set(DELIVERABLES)


def test_completion_gate():
    assert verify.can_close(u(), [e()])[0]
    ok, why = verify.can_close(u(), [e(kind="file_exists")])
    assert not ok and "refused" in why
    ok, why = verify.can_close(u(), [], forced=True)
    assert ok and "never counted" in why


def test_calibration_on_the_shipped_cases_reports_both_error_directions():
    r = verify.calibrate(verify.load_cases(CASES))
    assert r["n"] == 20 and r["agree"] == 17
    assert r["lenient_misses"] == ["k18", "k19"] and r["strict_misses"] == ["k14"]
    assert not r["never_passes_suspect"]


def test_a_judge_that_never_passes_is_flagged():
    cases = [{"id": "x", "unit": u(), "event": e(verifier="worker-1"), "human": "pass"}]
    assert verify.calibrate(cases)["never_passes_suspect"]
