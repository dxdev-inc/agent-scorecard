import hashlib
import json

from agent_scorecard import synth
from agent_scorecard.cli import SAMPLE
from agent_scorecard.schema import validate


def test_same_seed_same_bytes():
    assert synth.dumps(synth.generate(7, days=5)) == synth.dumps(synth.generate(7, days=5))


def test_different_seed_differs():
    assert synth.dumps(synth.generate(7, days=5)) != synth.dumps(synth.generate(8, days=5))


def test_every_row_is_synthetic_and_valid():
    for r in synth.generate(3, days=10):
        assert r["class"] == "synthetic" and validate(r) == [], r


def test_units_are_created_before_their_status_rows():
    seen = set()
    for r in synth.generate(11, days=20):
        if r["type"] == "unit_created":
            seen.add(r["unit"])
        elif r["type"] in ("status", "verify", "usage"):
            assert r["unit"] in seen


def test_committed_sample_reproduces_from_the_seed():
    regenerated = synth.dumps(synth.generate(synth.DEFAULT_SEED))
    assert SAMPLE.read_bytes() == regenerated.encode("utf-8")
    manifest = json.loads((SAMPLE.parent / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["sha256"] == hashlib.sha256(regenerated.encode("utf-8")).hexdigest()
    assert manifest["class"] == "synthetic" and manifest["seed"] == synth.DEFAULT_SEED
