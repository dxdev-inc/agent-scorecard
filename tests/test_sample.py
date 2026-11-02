import csv

import pytest

from agent_scorecard import sample
from agent_scorecard.cli import main


def test_draw_is_reproducible_and_bounded():
    rows = list(range(100))
    assert sample.draw(rows, 10, 7) == sample.draw(rows, 10, 7)
    assert sample.draw(rows, 10, 7) != sample.draw(rows, 10, 8)
    with pytest.raises(ValueError):
        sample.draw(rows, 101, 7)


def test_wilson_known_values():
    lo, hi = sample.wilson(50, 100)
    assert (lo, hi) == (40, 60)
    lo, hi = sample.wilson(0, 10)
    assert lo == 0 and hi < 30
    with pytest.raises(ValueError):
        sample.wilson(1, 0)


def test_draw_template_fill_and_score_roundtrip(tmp_path, capsys):
    log = tmp_path / "events.jsonl"
    log.write_text("\n".join(
        '{"ts":"2025-01-01T00:00:00Z","type":"ask","class":"synthetic","ask_id":"a%d","text":"t%d"}' % (i, i)
        for i in range(20)) + "\n", encoding="utf-8")
    out = tmp_path / "s.csv"
    assert main(["sample", "--log", str(log), "--k", "10", "--out", str(out)]) == 0
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 10
    with pytest.raises(ValueError):
        sample.score(out)   # unlabelled rows are refused, not counted
    for i, r in enumerate(rows):
        r["label"] = "not_a_request" if i == 0 else "finished"
        r["evidence_kind"] = "agent_report" if i == 1 else "git"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    s = sample.score(out)
    assert s["real_requests"] == 9 and s["finished_all"] == 9 and s["finished_strict"] == 8
