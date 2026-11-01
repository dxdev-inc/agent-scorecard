from factory_kit import measure
from factory_kit.schema import validate


def ev(ts, type_, **kw):
    return {"ts": ts, "type": type_, "class": "synthetic", **kw}


def unit(ts, u, ask, deliverable="code", done_when="x"):
    return ev(ts, "unit_created", unit=u, ask_id=ask, kind="do", deliverable=deliverable, done_when=done_when,
              executor="worker-1", requester="owner")


GOOD = {"kind": "test_run", "ref": "r", "outcome_observed": True}


def log():
    return [
        ev("2025-03-03T09:00:00Z", "ask", ask_id="a1", text="fix the exporter"),
        ev("2025-03-03T09:10:00Z", "ask", ask_id="a2", text="add a test"),
        ev("2025-03-03T09:20:00Z", "ask", ask_id="a3", text="ok"),
        ev("2025-03-03T22:00:00Z", "owner_idle", start="2025-03-03T22:00:00Z", end="2025-03-04T04:00:00Z"),
        ev("2025-03-03T12:00:00Z", "owner_idle", start="2025-03-03T12:00:00Z", end="2025-03-03T13:00:00Z"),
        unit("2025-03-03T09:05:00Z", "u1", "a1"),
        ev("2025-03-03T09:05:00Z", "status", unit="u1", status="open"),
        ev("2025-03-03T23:00:00Z", "status", unit="u1", status="done"),            # inside the 6h idle episode
        ev("2025-03-03T23:10:00Z", "verify", unit="u1", verifier="checker-1", result="pass", evidence=GOOD),
        unit("2025-03-03T09:15:00Z", "u2", "a2", done_when=None),
        ev("2025-03-03T12:30:00Z", "status", unit="u2", status="done", forced=True),   # forced: never trusted
        ev("2025-03-03T12:40:00Z", "verify", unit="u2", verifier="worker-1", result="pass", evidence=GOOD),
        ev("2025-03-06T10:00:00Z", "status", unit="u2", status="reopened"),         # reopened inside 14 days
        ev("2025-03-25T10:00:00Z", "usage", unit="u1", tokens=1000),                 # moves the end of the log
    ]


def test_rows_are_well_formed():
    assert all(validate(e) == [] for e in log())


def test_known_answers():
    m = measure.compute(log())
    assert m["asks_without_unit"]["n"] == 1 and m["asks_without_unit"]["of"] == 3
    assert m["asks_with_done_test"]["n"] == 1            # u2 has no done_when
    assert m["ask_finish_rate"]["n"] == 1                # u2 was reopened, so only u1 is finished
    assert m["trust"]["value"] == 1.0 and m["trust"]["of"] == 1
    assert m["minutes_ask_to_done_median"]["value"] == 14 * 60
    assert m["autonomous_trusted_units"]["value"] == 1   # u1 finished inside the 6h episode
    assert m["reopened_within_14d"]["n"] == 1 and m["reopened_within_14d"]["of"] == 2
    assert m["tokens_per_finished_unit"]["value"] == 1000


def test_short_idle_episode_does_not_count_as_autonomy():
    rows = [e for e in log() if not (e["type"] == "owner_idle" and e["start"].startswith("2025-03-03T22"))]
    assert measure.compute(rows)["autonomous_trusted_units"]["value"] == 0


def test_same_log_same_date_same_numbers():
    assert measure.compute(log(), "2025-03-10T00:00:00Z") == measure.compute(log(), "2025-03-10T00:00:00Z")


def test_as_of_cuts_the_log():
    early = measure.compute(log(), "2025-03-03T10:00:00Z")
    assert early["ask_finish_rate"]["n"] == 0 and early["asks_without_unit"]["of"] == 3
    assert measure.compute(log(), "2025-03-03T23:30:00Z")["ask_finish_rate"]["n"] == 2


def test_open_stability_window_is_not_counted_as_stable():
    # Cut the log two days after u1 reached done: its 14-day window is still open and clean, so it is not knowable.
    m = measure.compute(log(), "2025-03-05T00:00:00Z")
    assert m["reopened_within_14d"]["of"] == 0 and m["reopened_within_14d"]["value"] is None


def test_every_number_is_labelled_measured():
    m = measure.compute(log())
    assert all(v["label"] == "MEASURED" for k, v in m.items() if k != "as_of")


def test_sample_log_loads():
    from factory_kit.cli import SAMPLE
    rows = measure.load(SAMPLE)
    assert rows and all(r["class"] == "synthetic" for r in rows)
    assert measure.compute(rows)["trust"]["value"] is not None
