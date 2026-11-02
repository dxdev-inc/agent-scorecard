"""Seeded synthetic event log. Every row carries class=synthetic.

Nothing here is real. The generator is shaped like a plausible messy setup on purpose: a narrow old capture that
only files obvious "do" asks, finished work with weak verification, a few reopened units, some forced closes, and
overnight stretches where the person is away. The rates are knobs in RATES, chosen by the author, not measured
anywhere. `python -m agent_scorecard generate --seed N` is reproducible: same seed, same bytes.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .schema import CLASS_SYNTHETIC, SCHEMA_VERSION, fmt_ts

DEFAULT_SEED = 20250303
START = datetime(2025, 3, 3, 0, 0, tzinfo=timezone.utc)

RATES = {
    "kind_weights": {"do": 0.42, "explore": 0.20, "decide": 0.10, "manage": 0.10, "filler": 0.12, "probe": 0.06},
    "old_capture_files_do": 0.85,       # the old capture files most do-shaped asks...
    "old_capture_files_other": 0.10,    # ...and almost nothing else
    "old_capture_sets_done_when": 0.04,
    "finish": 0.72, "reopen": 0.09, "forced": 0.10,
    "verify_none": 0.40, "verify_presence_self": 0.25, "verify_independent_untyped": 0.12, "verify_genuine": 0.23,
}

THINGS = ["exporter", "sidebar", "nightly job", "search page", "billing report", "cache layer", "signup form",
          "queue worker", "settings panel", "import script"]
PROBLEMS = ["stops clipping on narrow screens", "stops dropping the last row", "handles empty input",
            "stops timing out under load", "shows the right count"]
EDGES = ["unicode names", "empty files", "very long lines", "duplicate keys"]
ROLES = ["reviewer", "maintainer", "analyst", "operator"]
PAIRS = [("sqlite", "postgres"), ("a queue", "a cron job"), ("a retry", "a circuit breaker"), ("json", "csv")]

T = {
    "do": ["fix the {t} so it {p}", "add a retry to the {t}", "write a test for the {t}", "update the {t} to handle {e}",
           "can you rename the {t} option in the config", "ok now deploy the {t}", "please document the {t} flags",
           "i need the {t} output split by day", "refactor the {t} and add a test"],
    "decide": ["should we use {a} or {b} for the {t}", "which is better for the {t}, {a} or {b}",
               "pick {a} or {b} for the {t} and tell me why"],
    "explore": ["why did the {t} fail last night", "what is the current size of the {t} output",
                "how does the {t} decide when to retry", "what if we cached the {t}, just curious what you think",
                "tell me why the {t} is slow on mondays", "brainstorm ways the {t} could run unattended"],
    "manage": ["tell the {r} to hold the {t} until i check the numbers", "ask the {r} to send a short status on the {t}",
               "hand off the {t} cleanup to the {r}"],
    "filler": ["ok", "thanks", "go ahead", "yes", "continue", "sounds good"],
    "probe": ["reply with exactly OK", "reply only with the word ready"],
}
DELIV = {"do": ["code", "code", "page", "config", "document", "data"], "decide": ["document"],
         "explore": ["document", "data"], "manage": ["config", "document"]}
EVID = {"code": "test_run", "page": "render_capture", "data": "stored_row_rerun_match",
        "document": "named_check", "config": "dry_run"}


def _text(r: random.Random, kind: str) -> str:
    a, b = r.choice(PAIRS)
    return r.choice(T[kind]).format(t=r.choice(THINGS), p=r.choice(PROBLEMS), e=r.choice(EDGES), r=r.choice(ROLES),
                                    a=a, b=b)


def generate(seed: int = DEFAULT_SEED, days: int = 42, asks_per_day: int = 10) -> list[dict]:
    r = random.Random(seed)
    rows: list[dict] = []

    def emit(ts: datetime, type_: str, **kw):
        rows.append({"ts": fmt_ts(ts), "type": type_, "class": CLASS_SYNTHETIC, **kw})

    kinds, weights = zip(*RATES["kind_weights"].items())
    n_ask = n_unit = 0
    for d in range(days):
        day = START + timedelta(days=d)
        # The person is away overnight, and for one stretch most days.
        s = day + timedelta(hours=22, minutes=r.randint(0, 120))
        emit(s, "owner_idle", start=fmt_ts(s), end=fmt_ts(s + timedelta(hours=r.randint(6, 9), minutes=r.randint(0, 59))))
        if r.random() < 0.6:
            m = day + timedelta(hours=11, minutes=r.randint(0, 90))
            emit(m, "owner_idle", start=fmt_ts(m), end=fmt_ts(m + timedelta(hours=r.randint(1, 3), minutes=r.randint(0, 59))))
        for _ in range(asks_per_day):
            kind = r.choices(kinds, weights)[0]
            ts = day + timedelta(hours=r.randint(8, 19), minutes=r.randint(0, 59), seconds=r.randint(0, 59))
            n_ask += 1
            ask_id = f"a{n_ask:04d}"
            emit(ts, "ask", ask_id=ask_id, text=_text(r, kind), label_kind=kind)
            if kind in ("filler", "probe"):
                continue
            filed = r.random() < (RATES["old_capture_files_do"] if kind == "do" else RATES["old_capture_files_other"])
            if not filed:
                continue
            n_unit += 1
            unit = f"u{n_unit:04d}"
            deliv = r.choice(DELIV[kind])
            executor, requester = f"worker-{r.randint(1, 3)}", "owner"
            created = ts + timedelta(minutes=r.randint(1, 30))
            emit(created, "unit_created", unit=unit, ask_id=ask_id, kind=kind, deliverable=deliv,
                 done_when="outcome observed" if r.random() < RATES["old_capture_sets_done_when"] else None,
                 executor=executor, requester=requester)
            emit(created, "status", unit=unit, status="open", forced=False)
            emit(created + timedelta(minutes=2), "usage", unit=unit, tokens=r.randint(2_000, 90_000))
            if r.random() < 0.15:
                emit(created + timedelta(minutes=r.randint(3, 40)), "intervention", unit=unit)
            if r.random() > RATES["finish"]:
                continue
            mean = 180 if r.random() < 0.7 else 720        # some work runs on overnight
            done = created + timedelta(minutes=int(r.expovariate(1 / mean)) + 5)
            forced = r.random() < RATES["forced"]
            emit(done, "status", unit=unit, status="done", forced=forced)
            v = r.random()
            c = RATES
            if v < c["verify_none"]:
                pass
            elif v < c["verify_none"] + c["verify_presence_self"]:
                emit(done + timedelta(minutes=1), "verify", unit=unit, verifier=executor, result="pass",
                     evidence={"kind": "file_exists", "ref": f"artifact-{unit}", "outcome_observed": False})
            elif v < c["verify_none"] + c["verify_presence_self"] + c["verify_independent_untyped"]:
                emit(done + timedelta(minutes=9), "verify", unit=unit, verifier="checker-1", result="pass",
                     evidence={"kind": "commit_exists", "ref": f"change-{unit}", "outcome_observed": False})
            else:
                emit(done + timedelta(minutes=15), "verify", unit=unit, verifier="checker-1", result="pass",
                     evidence={"kind": EVID[deliv], "ref": f"run-{unit}", "outcome_observed": True})
            if r.random() < RATES["reopen"]:
                emit(done + timedelta(days=r.randint(1, 12)), "status", unit=unit,
                     status=r.choice(["reopened", "reverted"]), forced=False)
    rows.sort(key=lambda e: e["ts"])
    return rows


def dumps(rows: list[dict]) -> str:
    return "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in rows)


def write(path: str | Path, seed: int = DEFAULT_SEED, **kw) -> str:
    """Write the log and return its sha256."""
    import hashlib
    text = dumps(generate(seed, **kw))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(text.encode("utf-8"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest(seed: int, sha: str, **kw) -> dict:
    return {"schema_version": SCHEMA_VERSION, "class": CLASS_SYNTHETIC, "seed": seed, "sha256": sha,
            "generator": "agent_scorecard.synth.generate", "params": kw or {"days": 42, "asks_per_day": 10}}
