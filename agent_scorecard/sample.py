"""The by-hand check from the post, as code: draw a reproducible sample of asks and score the labels you give them.

You read each sampled ask against independent evidence (git, tickets, the live system) and write one label per row.
This module draws the rows, writes the table to fill in, and reports the share with a Wilson interval.
"""
import csv
import json
import math
import random
from pathlib import Path

# The six labels used in the post. Keep them as-is so your numbers can be compared with anyone else's.
LABELS = ("finished", "partly_done", "dropped", "superseded", "cannot_tell", "not_a_request")
FINISHED = "finished"
STRICT_EVIDENCE = ("git", "ticket", "live")   # an evidence kind that is not the agent's own report
# A strict finish also needs a non-empty evidence_ref: a kind with nothing to point at cannot be checked.


def draw(rows, k, seed):
    """Same seed, same rows, so a second reader can check the draw."""
    rows = list(rows)
    if k > len(rows):
        raise ValueError(f"asked for {k} rows but only {len(rows)} exist")
    return random.Random(seed).sample(rows, k)


def wilson(successes, n, z=1.96):
    """95 percent interval for a share, as (low, high) percentages. The plain interval is worse on small n."""
    if n <= 0:
        raise ValueError("n must be positive")
    p = successes / n
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round((centre - spread) / d * 100), round((centre + spread) / d * 100)


def ask_rows(log_path):
    out = []
    for line in Path(log_path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get("type") == "ask":
                out.append({"ask_id": r["ask_id"], "text": r["text"]})
    return out


def write_template(rows, path):
    """CSV for you to fill in: label, evidence_kind (git|ticket|live|agent_report), evidence_ref."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ask_id", "text", "label", "evidence_kind", "evidence_ref"])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "label": "", "evidence_kind": "", "evidence_ref": ""})


def score(csv_path):
    """Two numbers over real requests: every finish, and the strict one that drops a finish backed only by the agent."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    bad = [r["ask_id"] for r in rows if r["label"] not in LABELS]
    if bad:
        raise ValueError(f"unlabelled or unknown label on: {bad[:5]}")
    real = [r for r in rows if r["label"] != "not_a_request"]
    n = len(real)
    if n == 0:
        raise ValueError("no real requests in the table")
    all_f = sum(r["label"] == FINISHED for r in real)
    strict = sum(r["label"] == FINISHED and r["evidence_kind"] in STRICT_EVIDENCE
                 and (r.get("evidence_ref") or "").strip() != "" for r in real)
    return {"real_requests": n, "not_a_request": len(rows) - n,
            "finished_all": all_f, "finished_all_pct": round(100 * all_f / n), "finished_all_ci95": wilson(all_f, n),
            "finished_strict": strict, "finished_strict_pct": round(100 * strict / n),
            "finished_strict_ci95": wilson(strict, n)}
