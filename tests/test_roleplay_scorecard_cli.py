import subprocess
import sys
from pathlib import Path

from agent_scorecard import measure, roleplay, scorecard
from agent_scorecard.cli import SAMPLE

ROOT = Path(__file__).resolve().parent.parent


def test_thirty_scenarios_all_pass():
    scs = roleplay.load()
    assert len(scs) == 30 and len({s["id"] for s in scs}) == 30
    rep = roleplay.run_all()
    failed = [r for r in rep["results"] if not r["ok"]]
    assert not failed, failed


def test_a_broken_rule_makes_a_scenario_fail():
    # The harness must be able to fail: break an expectation and see it caught.
    sc = {"id": "x", "type": "capture", "group": "g", "text": "tell me why the job failed", "expect": {"kind": "manage"}}
    ok, why = roleplay.RUNNERS["capture"](sc)
    assert not ok and "expected" in why


def test_scorecard_labels_and_no_data_and_no_multiplier():
    rows = scorecard.build(measure.load(SAMPLE), estimates={"estimate: hours": 3})
    labels = {r["label"] for r in rows}
    assert {"MEASURED", "REPLAY", "ESTIMATED", "NO DATA"} <= labels
    assert all(str(r["value"]).startswith("NO DATA (source:") for r in rows if r["label"] == "NO DATA")
    text = scorecard.render(rows)
    assert "Limits" in text and "multiplier" not in text.split("Limits")[0].lower()
    assert [r for r in rows if r["label"] == "ESTIMATED"][0]["n"] is None      # an estimate is never given a sample size


def test_scorecard_is_reproducible_at_an_as_of_date():
    ev = measure.load(SAMPLE)
    a = scorecard.build(ev, as_of="2025-04-01T00:00:00Z")
    assert a == scorecard.build(ev, as_of="2025-04-01T00:00:00Z")
    assert a != scorecard.build(ev, as_of="2025-03-20T00:00:00Z")


def test_quickstart_runs_clean(tmp_path):
    p = subprocess.run([sys.executable, "-m", "agent_scorecard", "quickstart", "--out", str(tmp_path / "o")],
                       cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert "30/30 scenarios passed" in p.stdout and "NO DATA (source:" in p.stdout


def test_as_of_is_parsed_as_an_instant_not_compared_as_text():
    # Regression (review finding 4): the scorecard cut compared strings, measure parsed timestamps. 05:00+05:00 is
    # the same instant as 00:00Z, so an ask at 02:00Z is after the cut under both spellings.
    def row(ts, ask_id, text):
        return {"ts": ts, "type": "ask", "class": "synthetic", "ask_id": ask_id, "text": text}
    ev = [row("2025-03-19T10:00:00Z", "a1", "fix the exporter"), row("2025-03-20T02:00:00Z", "a2", "add a test")]
    z = scorecard.build(ev, as_of="2025-03-20T00:00:00Z")
    offset = scorecard.build(ev, as_of="2025-03-20T05:00:00+05:00")
    assert z == offset
    assert z != scorecard.build(ev, as_of="2025-03-20T05:00:00Z")
