"""The event log schema, as code. The prose version is docs/SCHEMA.md.

One JSON object per line. Every row has `ts` (UTC, ISO 8601, `Z` suffix), `type`, and `class`.
`class` is the privacy classification of the row: this repo only ever ships `synthetic`.
"""
from __future__ import annotations

from datetime import datetime, timezone

SCHEMA_VERSION = 1
CLASS_SYNTHETIC = "synthetic"

EVENT_TYPES = (
    "ask",            # a person asked for something: ask_id, text
    "unit_created",   # a tracked unit of work: unit, ask_id|null, kind, done_when|null, deliverable, executor, requester
    "status",         # unit, status in STATUSES, forced (bool)
    "verify",         # unit, verifier, result in RESULTS, evidence {kind, ref, outcome_observed}|null
    "usage",          # unit, tokens
    "owner_idle",     # start, end (the person was away); ts == start
    "intervention",   # unit, the person supplied missing context
)
STATUSES = ("open", "working", "done", "reopened", "reverted")
RESULTS = ("pass", "fail", "inconclusive")
KINDS = ("do", "decide", "explore", "manage")
DELIVERABLES = ("code", "page", "data", "document", "config")

REQUIRED = {
    "ask": ("ask_id", "text"),
    "unit_created": ("unit", "kind", "deliverable", "executor", "requester"),
    "status": ("unit", "status"),
    "verify": ("unit", "verifier", "result"),
    "usage": ("unit", "tokens"),
    "owner_idle": ("start", "end"),
    "intervention": ("unit",),
}


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def fmt_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate(event: dict) -> list[str]:
    """Problems with one row; an empty list means it is well formed."""
    errs = []
    t = event.get("type")
    if t not in EVENT_TYPES:
        return [f"unknown type {t!r}"]
    for f in ("ts", "class") + REQUIRED[t]:
        if f not in event:
            errs.append(f"{t}: missing {f}")
    if "ts" in event:
        try:
            parse_ts(event["ts"])
        except (ValueError, TypeError):
            errs.append(f"{t}: bad ts {event['ts']!r}")
    if t == "status" and event.get("status") not in STATUSES:
        errs.append(f"status: bad status {event.get('status')!r}")
    if t == "verify" and event.get("result") not in RESULTS:
        errs.append(f"verify: bad result {event.get('result')!r}")
    if t == "unit_created" and event.get("kind") not in KINDS:
        errs.append(f"unit_created: bad kind {event.get('kind')!r}")
    return errs
