"""python -m factory_kit <command>. Commands: quickstart, generate, measure, capture, verify, loop, scorecard, roleplay."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import capture, loop, measure, roleplay, sample, scorecard, synth, verify

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "sample" / "events.jsonl"
CASES = ROOT / "data" / "verifier_cases.json"


def _events(path):
    return measure.load(path or SAMPLE)


def _print_measure(m: dict) -> None:
    for k, v in m.items():
        if k == "as_of":
            print(f"as of: {v}")
            continue
        val = "NO DATA" if v["value"] is None else v["value"]
        print(f"  {k:<36} {str(val):>9}   {v['n']}/{v['of']}   {v['label']}")


def demo_loop() -> dict:
    """A simulated silent run: six units, a pool that holds four runs, one unit whose first check has only presence evidence."""
    units = [{"id": f"d{i}", "status": "open", "priority": 6 - i, "retries": 0, "done_when": "outcome observed",
              "deliverable": "code", "executor": "worker-1", "requester": "owner"} for i in range(6)]
    good = {"verifier": "checker-1", "result": "pass",
            "evidence": {"kind": "test_run", "ref": "r", "outcome_observed": True}}
    weak = {"verifier": "checker-1", "result": "pass",
            "evidence": {"kind": "file_exists", "ref": "r", "outcome_observed": False}}

    def executor(u):
        return {"claim": "done", "seconds": 900}

    seen = {}

    def checker(u, res):
        seen[u["id"]] = seen.get(u["id"], 0) + 1
        return dict(weak if (u["id"] == "d2" and seen["d2"] == 1) else good)     # d2 passes on its retry

    return loop.run(units, executor, checker, loop.Pool(4, 1800), loop.Config(wall_clock_s=6 * 3600))


def cmd_quickstart(a) -> int:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "events.jsonl"
    sha = synth.write(log, a.seed)
    print(f"1. generated a synthetic log -> {log}  (seed {a.seed}, sha256 {sha[:16]}...)")
    ev = measure.load(log)
    print(f"   {len(ev)} rows, every row class=synthetic\n")
    print("2. measure (MEASURED = computed from the log by a fixed rule)")
    _print_measure(measure.compute(ev))
    print("\n3. capture replay (REPLAY = what the capture rules would do over the same ask rows)")
    rp = capture.replay(ev)
    print(f"   asks {rp['asks']}, kept {rp['kept']} by kind {rp['by_kind']}")
    print(f"   with a done test {rp['with_done_test']}, open discussion {rp['open_discussion']}, "
          f"dropped {rp['dropped']} {rp['dropped_reasons']}")
    ex = "first add a retry to the exporter, second tell me which jobs are idle"
    print(f"   one message, two asks: {[(p['kind'], p['done_kind']) for p in capture.capture(ex)]}")
    print("\n4. verification rules against the labelled cases in data/verifier_cases.json")
    print("   " + json.dumps(verify.calibrate(verify.load_cases(CASES))))
    print("\n5. bounded loop, simulated silent run")
    rep = demo_loop()
    nv = [t["unit"] for t in rep["trace"] if t.get("event") == "not_verified"]
    print(f"   stop: {rep['stop_reason']} (failure={rep['failure']}), shipped {rep['shipped']}, "
          f"not verified {nv}, resume in {rep['resume_in_s']}s")
    print("\n6. scorecard\n")
    est = {"estimate: hours to wire this into a real setup": 6}
    print(scorecard.render(scorecard.build(ev, estimates=est, loop_report=rep)))
    print("\n7. role play\n")
    rr = roleplay.run_all()
    print(roleplay.render(rr))
    return 0 if rr["passed"] == rr["total"] else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="factory_kit")
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("quickstart", help="run everything end to end on a fresh synthetic log")
    q.add_argument("--out", default="out")
    q.add_argument("--seed", type=int, default=synth.DEFAULT_SEED)
    g = sub.add_parser("generate", help="write a synthetic event log")
    g.add_argument("--out", default="out/events.jsonl")
    g.add_argument("--seed", type=int, default=synth.DEFAULT_SEED)
    for name in ("measure", "scorecard"):
        s = sub.add_parser(name)
        s.add_argument("--log")
        s.add_argument("--as-of", help="UTC, e.g. 2025-03-20T00:00:00Z")
        s.add_argument("--json", action="store_true")
    c = sub.add_parser("capture", help="classify one message")
    c.add_argument("text")
    sub.add_parser("verify", help="check the verification rules against data/verifier_cases.json")
    sub.add_parser("loop", help="run the simulated loop demo")
    sub.add_parser("roleplay", help="run the 30 scenarios")
    sm = sub.add_parser("sample", help="draw a seeded sample of asks to label by hand, or score a filled-in table")
    sm.add_argument("--log", help="event log to draw ask rows from")
    sm.add_argument("--k", type=int, default=80)
    sm.add_argument("--seed", type=int, default=7)
    sm.add_argument("--out", default="out/sample.csv")
    sm.add_argument("--score", help="a filled-in table from an earlier draw; prints both finish shares with 95 percent intervals")
    a = p.parse_args(argv)
    if a.cmd == "quickstart":
        return cmd_quickstart(a)
    if a.cmd == "generate":
        sha = synth.write(a.out, a.seed)
        (Path(a.out).parent / "MANIFEST.json").write_text(
            json.dumps(synth.manifest(a.seed, sha), indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(sha)
        return 0
    if a.cmd == "measure":
        m = measure.compute(_events(a.log), a.as_of)
        if a.json:
            print(json.dumps(m, indent=1))
        else:
            _print_measure(m)
        return 0
    if a.cmd == "scorecard":
        rows = scorecard.build(_events(a.log), a.as_of)
        print(json.dumps(rows, indent=1) if a.json else scorecard.render(rows))
        return 0
    if a.cmd == "capture":
        print(json.dumps(capture.classify(a.text), indent=1))
        return 0
    if a.cmd == "verify":
        print(json.dumps(verify.calibrate(verify.load_cases(CASES)), indent=1))
        return 0
    if a.cmd == "loop":
        print(json.dumps(demo_loop(), indent=1))
        return 0
    if a.cmd == "sample":
        if a.score:
            print(json.dumps(sample.score(a.score), indent=1))
            return 0
        if not a.log:
            print("give --log to draw a sample, or --score to score a filled-in table")
            return 2
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        drawn = sample.draw(sample.ask_rows(a.log), a.k, a.seed)
        sample.write_template(drawn, a.out)
        print(f"wrote {len(drawn)} rows to {a.out}; fill label, evidence_kind, evidence_ref, then run with --score")
        return 0
    rep = roleplay.run_all()
    print(roleplay.render(rep))
    return 0 if rep["passed"] == rep["total"] else 1
