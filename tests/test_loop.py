from agent_scorecard import loop

GOOD = {"verifier": "checker-1", "result": "pass", "evidence": {"kind": "test_run", "ref": "r", "outcome_observed": True}}


def unit(i, pr=0):
    return {"id": i, "status": "open", "priority": pr, "retries": 0, "done_when": "outcome observed",
            "deliverable": "code", "executor": "worker-1", "requester": "owner"}


def ok(u):
    return {"claim": "done", "seconds": 600}


def good(u, r):
    return dict(GOOD)


def test_highest_priority_first_and_all_ship():
    rep = loop.run([unit("a", 1), unit("b", 3), unit("c", 2)], ok, good, loop.Pool(9))
    assert rep["shipped"] == ["b", "c", "a"] and rep["stop_reason"] == "done" and not rep["failure"]


def test_wall_clock_stops_the_run():
    rep = loop.run([unit(str(i)) for i in range(5)], ok, good, loop.Pool(9), loop.Config(wall_clock_s=1200))
    assert rep["stop_reason"] == "wall_clock" and rep["failure"] and len(rep["shipped"]) == 2


def test_max_iterations_stops_the_run():
    rep = loop.run([unit(str(i)) for i in range(5)], ok, good, loop.Pool(9), loop.Config(max_iterations=3))
    assert rep["stop_reason"] == "max_iterations" and len(rep["shipped"]) == 3


def test_a_checker_that_is_the_executor_never_closes_a_unit():
    selfcheck = lambda u, r: {**GOOD, "verifier": "worker-1"}
    rep = loop.run([unit("a")], ok, selfcheck, loop.Pool(9), loop.Config(no_progress_limit=9))
    assert rep["shipped"] == [] and rep["escalated"] == ["a"]


def test_retry_cap_then_escalate_not_forever():
    stuck = lambda u: {"claim": "stuck", "seconds": 60}
    u = unit("a")
    loop.run([u], stuck, good, loop.Pool(99), loop.Config(max_retries=2, no_progress_limit=99))
    assert u["status"] == "escalated" and u["retries"] == 3


def test_done_when_is_read_only_to_the_executor():
    u = unit("a")
    edit = lambda x: {"claim": "done", "seconds": 5, "edits_done_when": "file exists"}
    rep = loop.run([u], edit, good, loop.Pool(9), loop.Config(max_retries=0, no_progress_limit=9))
    assert rep["shipped"] == [] and rep["refused_done_when_edits"] == ["a"] and u["done_when"] == "outcome observed"


def test_pool_exhaustion_pauses_and_is_not_a_failure():
    rep = loop.run([unit("a", 2), unit("b", 1)], ok, good, loop.Pool(1, 900))
    assert rep["stop_reason"] == "paused_pool_exhausted" and not rep["failure"] and rep["resume_in_s"] == 900


def test_a_unit_without_a_done_test_is_never_picked():
    rep = loop.run([{**unit("a"), "done_when": None}], ok, good, loop.Pool(9))
    assert rep["shipped"] == [] and rep["stop_reason"] == "no_ready_units"


def test_replay_is_deterministic():
    a = loop.run([unit("a"), unit("b")], ok, good, loop.Pool(9))
    b = loop.run([unit("a"), unit("b")], ok, good, loop.Pool(9))
    assert a == b


def test_last_unit_on_last_pool_slot_is_done_not_paused():
    # Regression (review finding 7): the pool check used to run before the readiness check.
    rep = loop.run([unit("a")], ok, good, loop.Pool(1, 900))
    assert rep["stop_reason"] == "done" and rep["shipped"] == ["a"] and rep["resume_in_s"] is None


def test_all_units_closed_with_a_future_idea_is_done_not_a_failure():
    # Regression (review finding 7): a not-yet-due idea must not turn a finished run into max_iterations / failure.
    idea = {"id": "i1", "review_by": "2999-01-01", "done_when": "x", "deliverable": "code",
            "executor": "worker-1", "requester": "owner"}
    rep = loop.run([unit("a")], ok, good, loop.Pool(9), loop.Config(max_iterations=1), ideas=[idea], today="2025-01-01")
    assert rep["stop_reason"] == "done" and not rep["failure"]
