"""Ask capture: turn a person's message into zero or more tracked units, each with a kind and a done test.

Deterministic, no model call. The point is the method, not the regexes:

* A message is either filler (dropped, with a reason) or one or more asks.
* Every kept ask gets a KIND (do, decide, explore, manage) and a DONE TEST that fits the kind:
    do       the change is observable in the real target and an independent check recorded evidence of it
    decide   a decision is recorded: who chose what
    explore  with a concrete question: a finding is stored with its evidence.
             Thinking out loud gets NO done test (`open_discussion`). A fake gate on a brainstorm is worse than none.
    manage   the relay reached its recipient and the named action was observed
* A ticket, a next step or a written doc only advances status. None of them is a done test.
"""
from __future__ import annotations

import re

KINDS = ("do", "decide", "explore", "manage")

DONE_WHEN = {
    "do": "The requested change is observable in the real target, and a check other than the builder recorded "
          "evidence of that outcome.",
    "decide": "A decision is recorded that names the choice and who made it.",
    "explore": "A finding is stored that answers the question, with its evidence.",
    "manage": "The relay reached its recipient, and the action it named was observed.",
}
DONE_KIND = {"do": "outcome_verified", "decide": "decision_recorded", "explore": "finding_stored",
             "manage": "relay_delivered_and_acted"}
NEXT_STEP = {
    "do": "Owner names the concrete deliverable and starts.",
    "decide": "Put the question and the options in front of the decider with a recommendation.",
    "explore": "Owner answers it from the record and stores the finding.",
    "manage": "Deliver the relay to the named recipient and confirm it was acted on.",
}

_STOP = set("a an the and or but of to in on at for with is are was were be been it this that these those i we you "
            "my our your me us do does did so if as by from up out not no yes ok okay then than also just can "
            "could would should will".split())

_ACK_WORDS = (r"ok|okay|yes|yep|yeah|y|sure|thanks|thank you|thx|go|go ahead|go on|continue|proceed|next|done|"
              r"sounds good|lgtm|good|great|fine|please|now|and|resume|carry on|keep going|do it|as is")
_ACK_ONLY = re.compile(rf"^\W*(?:(?:{_ACK_WORDS})\b[\s,.!;:-]*)+$", re.I)
_LEAD_ACK = re.compile(r"^\W*(?:(?:ok|okay|yes|yep|sure|thanks|so|now|and|also|then|alright)\b[\s,.!;:-]*)+", re.I)
_PROBE = re.compile(r"^\s*(?:reply with exactly|reply only with|respond with only)\b", re.I)
_MACHINE = re.compile(r"^\s*\[(?:relay|auto|system)\b", re.I)

# Addressed to a third party: "tell the reviewer ...", never "tell me ...".
_MANAGE = re.compile(
    r"\b(?:tell|ask|message|notify|ping)\s+(?!me\b|us\b|you\b|whether\b|if\b)(?:the\s+)?\w+|"
    r"\b(?:hand ?off|delegate|dispatch|assign|reassign|follow up with|check with|loop in|stand down|unblock)\b",
    re.I)
_OUTLOUD = re.compile(r"\b(?:brainstorm\w*|thinking out loud|just curious|what if|wondering|imagine)\b", re.I)
_TELL_Q = re.compile(r"^\W*(?:and\s+)?(?:also,?\s+)?(?:tell|show)\s+(?:me|us)\s+"
                     r"(?:why|what|how|which|where|when|who|whether)\b", re.I)
_VERBS = (r"fix|build|add|make|create|implement|write|update|change|remove|delete|deploy|ship|run|check|set up|"
          r"wire|move|rename|refactor|test|verify|debug|draft|review|close|open|show|restore|migrate|enable|disable|"
          r"stop|start|restart|install|configure|merge|revert|push|sync|audit|clean up|replace|rewrite|document|"
          r"schedule|automate|generate|render|design|plan|import|export|upload|resolve|handle|prevent|block|put|"
          r"send|apply|finish|complete|post|deploy")
_IMPERATIVE = re.compile(rf"^\W*(?:please\s+)?(?:{_VERBS})\b", re.I)
_REQUEST = re.compile(rf"\b(?:can you|could you|please|let'?s|make sure|we need to|i need to|i want to|needs? to)\s+"
                      rf"(?:\w+\s+)?(?:{_VERBS})\b", re.I)
_WH_QUESTION = re.compile(r"^\W*(?:how|why|when|where)\b", re.I)
_NEED = re.compile(r"\b(?:i need|i want|we need|i'd like)\b", re.I)
_DECIDE = re.compile(r"\b(?:should we|should i|which (?:one|option|is|do)|pick|choose|decide|your call|"
                     r"what do you recommend|or should|versus)\b", re.I)
_RESEARCH = re.compile(r"\b(?:why|how|what (?:is|are|happened)|status|investigate|find out|compare|explain|"
                       r"look into|which|when did|where is|is there|are there)\b", re.I)

_ORD = re.compile(r"\b(first|second|third|fourth|fifth)\b[,:]?\s+", re.I)
_LEAD_COUNT = re.compile(r"^\W*(?:two|three|four|2|3|4)\s+(?:things|asks|items|tasks)\b[\s,:;-]*", re.I)
_PART_SPLIT = re.compile(r",?\s+(?:and\s+)?also,?\s+|;\s+|\s+and then\s+", re.I)
_TAIL = re.compile(r"[\s,;]+(?:and|then)?[\s,;]*$", re.I)


def meaningful(text: str) -> int:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'_-]*", text)
    return len([w for w in words if w.lower() not in _STOP and len(w) > 1])


def split_asks(text: str) -> list[str]:
    """Several asks in one message come back as one string each; anything else comes back as [text].
    Only two explicit shapes split (ordinals; a counted lead). A plain "and" never splits a sentence."""
    t = " ".join((text or "").split())
    parts: list[str] = []
    marks = list(_ORD.finditer(t))
    if len(marks) >= 2 and marks[0].start() <= 3:
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(t)
            parts.append(t[m.end():end])
    elif _LEAD_COUNT.match(t):
        parts = _PART_SPLIT.split(_LEAD_COUNT.sub("", t, count=1))
    parts = [p for p in (_TAIL.sub("", p).strip() for p in parts) if p]
    if len(parts) >= 2 and all(meaningful(p) >= 2 for p in parts):
        return parts
    return [t]


def kind_of(text: str) -> str:
    """First match wins, in this order: manage, thinking out loud, "tell me <question>", do, a concrete need,
    decide, explore."""
    t = _LEAD_ACK.sub("", " ".join((text or "").split()))
    if _MANAGE.search(t) and not _TELL_Q.search(t):
        return "manage"
    if _OUTLOUD.search(t) and not _IMPERATIVE.search(t):
        return "explore"
    if _TELL_Q.search(t):
        return "explore"
    if _IMPERATIVE.search(t) or _REQUEST.search(t):
        return "do"
    if _NEED.search(t) and not t.rstrip().endswith("?") and not _DECIDE.search(t) and meaningful(t) >= 4:
        return "do"
    if _WH_QUESTION.match(t):          # "how does it decide ..." asks how, it does not ask for a decision
        return "explore"
    if _DECIDE.search(t):
        return "decide"
    return "explore"


def owner_for(text: str, owner_words: dict[str, list[str]] | None = None) -> tuple[str, str]:
    """(owner, basis). First owner whose word appears wins; otherwise a stated default, never a silent guess."""
    low = (text or "").lower()
    for owner, words in (owner_words or {}).items():
        for w in words:
            if re.search(rf"\b{re.escape(w.lower())}\b", low):
                return owner, f"owner word {w!r}"
    return "unassigned", "default: no owner word in the ask"


def classify(text: str, owner_words: dict | None = None, _part: bool = False) -> dict:
    """{keep, reason, kind, done_kind, done_when, next_step, owner, owner_basis, parts?}. Pure."""
    t = " ".join((text or "").split())
    if not t:
        return {"keep": False, "reason": "empty", "kind": None}
    if _MACHINE.search(t):
        return {"keep": False, "reason": "machine relay, not a person's words", "kind": None}
    if _PROBE.search(t):
        return {"keep": False, "reason": "probe prompt", "kind": None}
    parts = split_asks(t)
    if len(parts) > 1:
        c = classify(parts[0], owner_words, _part=True)
        if c.get("keep"):
            c["parts"] = parts
        return c
    if _ACK_ONLY.match(t):
        return {"keep": False, "reason": "bare acknowledgement", "kind": None}
    body = _LEAD_ACK.sub("", t)
    n = meaningful(body)
    kind = kind_of(body)
    triggered = bool(_MANAGE.search(body) or _DECIDE.search(body) or _RESEARCH.search(body)
                     or _IMPERATIVE.search(body) or _REQUEST.search(body) or _NEED.search(body) or _OUTLOUD.search(body))
    floor = 2 if (_part or _IMPERATIVE.search(body)) else 3      # "deploy the exporter" is a complete ask
    if n < floor or (n < 8 and not triggered):
        return {"keep": False, "reason": "too short to carry an ask", "kind": None}
    owner, basis = owner_for(body, owner_words)
    # A concrete question or a research verb earns "finding stored". A statement or a brainstorm earns no done test.
    concrete = "?" in body or bool(_RESEARCH.search(body))
    brainstorm = kind == "explore" and (bool(_OUTLOUD.search(body)) or not concrete)
    out = {"keep": True, "reason": "", "kind": kind, "owner": owner, "owner_basis": basis,
           "next_step": NEXT_STEP[kind]}
    if brainstorm:
        out.update(done_kind="open_discussion", done_when=None)
    else:
        out.update(done_kind=DONE_KIND[kind], done_when=DONE_WHEN[kind])
    return out


def capture(text: str, owner_words: dict | None = None) -> list[dict]:
    """One proposal per ask in the message. A proposal is not accepted work: `proposed` stays True until
    someone (or a rule) accepts it."""
    c = classify(text, owner_words)
    if not c["keep"]:
        return []
    texts = c.get("parts") or [text]
    out = []
    for part in texts:
        pc = classify(part, owner_words, _part=len(texts) > 1)
        if pc["keep"]:
            out.append({"text": " ".join(part.split())[:160], "proposed": True, **{k: v for k, v in pc.items()
                        if k not in ("keep", "parts", "reason")}})
    return out


def replay(events: list[dict], owner_words: dict | None = None) -> dict:
    """Run capture over the ask rows of an event log, on the rows only (nothing is written back).
    Reports what a stricter capture would have kept, by kind, with how many carry a done test."""
    asks = [e for e in events if e["type"] == "ask"]
    mapped = {e.get("ask_id") for e in events if e["type"] == "unit_created" and e.get("ask_id")}
    kept = dropped = with_done = 0
    by_kind = {k: 0 for k in KINDS}
    reasons: dict[str, int] = {}
    kept_ids = []
    for a in asks:
        props = capture(a["text"], owner_words)
        if not props:
            dropped += 1
            why = classify(a["text"], owner_words)["reason"]
            reasons[why] = reasons.get(why, 0) + 1
            continue
        kept += 1
        kept_ids.append(a["ask_id"])
        by_kind[props[0]["kind"]] += 1
        with_done += 1 if props[0].get("done_when") else 0
    unmapped_now = len([i for i in kept_ids if i not in mapped])
    # Agreement with the row's own label, when the log carries one (the synthetic log does; real logs do not).
    labelled = [a for a in asks if a.get("label_kind")]
    agree = 0
    for a in labelled:
        props = capture(a["text"], owner_words)
        want = a["label_kind"]
        agree += (not props) if want in ("filler", "probe") else bool(props and props[0]["kind"] == want)
    return {"label_agreement": {"n": len(labelled), "agree": agree,
                                "share": round(agree / len(labelled), 3) if labelled else None},
            "asks": len(asks), "kept": kept, "dropped": dropped, "dropped_reasons": reasons, "by_kind": by_kind,
            "with_done_test": with_done, "open_discussion": kept - with_done,
            "kept_but_unmapped_in_log": unmapped_now,
            "kept_but_unmapped_share": round(unmapped_now / kept, 3) if kept else None}
