"""The scorecard. Every line is labelled with where it came from.

  MEASURED    computed from the event log by a fixed rule (`measure.py`)
  REPLAY      produced by running other code over the log (capture replay, loop replay). It says what the code
              WOULD have done, not what happened.
  ESTIMATED   typed in by a person (an estimates file). Never computed, never mixed into a MEASURED line.
  NO DATA     the source for this line does not exist in the log. The line says which source it needs.

There is no productivity multiplier here, on purpose: factors derived from transcripts or self-reports are upper
bounds at best, and a single headline number invites causal claims the data cannot carry.
"""
from __future__ import annotations

from . import capture, measure
from .schema import parse_ts

LIMITS = """Limits (read these next to every number above)
  - One operator and one log. Nothing here generalises to another team without its own log.
  - "Finished" means the last status event is done. It does not mean good. Trust and stability sit beside it for that reason.
  - Verification rules are written by the tool's author. Calibrate them against your own labelled set before relying on them.
  - A REPLAY line is what code would do, not what it did. An ESTIMATED line is a guess someone typed.
  - No before/after comparison is made here. Do not write "X raised Y" unless you have two logs, one definition, and a gap."""


def _row(name, value, label, n=None, of=None, note=""):
    return {"metric": name, "value": value, "label": label, "n": n, "of": of, "note": note}


def _from_measured(name, m, key):
    k = m[key]
    if k["value"] is None:
        return _row(name, f"NO DATA (source: no rows for {key} in the log)", "NO DATA")
    return _row(name, k["value"], "MEASURED", k["n"], k["of"], k["note"])


def build(events: list[dict], as_of: str | None = None, estimates: dict | None = None,
          loop_report: dict | None = None, owner_words: dict | None = None) -> list[dict]:
    m = measure.compute(events, as_of)
    cut = [e for e in events if as_of is None or parse_ts(e["ts"]) <= parse_ts(as_of)]
    rp = capture.replay(cut, owner_words)
    rows = [
        _from_measured("asks with no unit", m, "asks_without_unit"),
        _from_measured("asks with a done test", m, "asks_with_done_test"),
        _from_measured("ask finish rate", m, "ask_finish_rate"),
        _from_measured("minutes ask to done, median", m, "minutes_ask_to_done_median"),
        _from_measured("minutes ask to done, p90", m, "minutes_ask_to_done_p90"),
        _from_measured("trust (evidence-backed / finished)", m, "trust"),
        _from_measured("claimed pass the evidence rules do not credit", m, "claimed_pass_without_evidence"),
        _from_measured("forced done", m, "forced_done"),
        _from_measured("reopened within 14 days", m, "reopened_within_14d"),
        _from_measured("trusted units finished while owner away 2h+", m, "autonomous_trusted_units"),
        _from_measured("interventions per finished unit", m, "interventions_per_finished_unit"),
        _from_measured("tokens per finished unit", m, "tokens_per_finished_unit"),
        _row("asks capture would file with a done test", rp["with_done_test"], "REPLAY", rp["with_done_test"],
             rp["asks"], "capture rules replayed over the ask rows; nothing written back"),
        _row("asks capture would file as open discussion (no done test)", rp["open_discussion"], "REPLAY",
             rp["open_discussion"], rp["asks"], "brainstorms get no fake gate"),
        _row("asks capture would file that the log never made a unit for", rp["kept_but_unmapped_in_log"], "REPLAY",
             rp["kept_but_unmapped_in_log"], rp["kept"]),
    ]
    la = rp["label_agreement"]
    if la["n"]:
        rows.append(_row("capture kind agrees with the row's label", la["share"], "REPLAY", la["agree"], la["n"],
                         "labels come from the generator's templates, so this is a regression check, not accuracy"))
    if loop_report:
        rows.append(_row("units shipped with independent evidence in a simulated silent run",
                         len(loop_report["shipped"]), "REPLAY", len(loop_report["shipped"]), None,
                         f"stop reason: {loop_report['stop_reason']}"))
    for k, v in (estimates or {}).items():
        rows.append(_row(k, v, "ESTIMATED", note="typed in; not computed"))
    rows.append(_row("share of session time idle waiting for the owner",
                     "NO DATA (source: a session activity log; the event schema has none)", "NO DATA"))
    rows.append(_row("goal progress", "NO DATA (source: a goal register; the event schema has none)", "NO DATA"))
    return rows


def render(rows: list[dict]) -> str:
    w = max(len(r["metric"]) for r in rows)
    lines = [f"{'metric'.ljust(w)}  {'value':>12}  {'n/of':>9}  label"]
    for r in rows:
        v = r["value"]
        vs = f"{v}" if not isinstance(v, float) else f"{v:.3f}"
        if isinstance(v, str) and v.startswith("NO DATA"):
            lines.append(f"{r['metric'].ljust(w)}  {v}")
            continue
        nof = f"{r['n']}/{r['of']}" if r["of"] is not None else (str(r["n"]) if r["n"] is not None else "")
        lines.append(f"{r['metric'].ljust(w)}  {vs:>12}  {nof:>9}  {r['label']}")
    return "\n".join(lines) + "\n\n" + LIMITS
