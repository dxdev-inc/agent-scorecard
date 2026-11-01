import pytest

from factory_kit import capture as c


@pytest.mark.parametrize("text,kind", [
    ("tell me why the nightly job failed", "explore"),
    ("tell the reviewer to hold the exporter", "manage"),
    ("deploy the exporter and tell me when it is live", "do"),
    ("should we use sqlite or postgres for the cache", "decide"),
    ("fix the sidebar so it stops clipping", "do"),
    ("why does the queue worker retry twice", "explore"),
    ("hand off the cleanup to the analyst", "manage"),
    ("how does the queue worker decide when to retry", "explore"),     # found by the replay label check
    ("ok now deploy the exporter", "do"),                              # found by the replay label check
])
def test_kind(text, kind):
    assert c.classify(text)["kind"] == kind


@pytest.mark.parametrize("text", ["ok", "thanks", "go ahead", "reply with exactly OK", "[relay from reviewer] done", ""])
def test_filler_is_dropped_with_a_reason(text):
    r = c.classify(text)
    assert not r["keep"] and r["reason"]


def test_every_kept_ask_has_kind_owner_and_a_done_test_or_a_stated_reason_for_none():
    for t in ["fix the footer so it stops clipping", "why did the job fail", "what if we cached it, just curious what you think",
              "should we ship now or wait", "tell the maintainer to hold the release"]:
        r = c.classify(t)
        assert r["keep"] and r["kind"] in c.KINDS and r["owner"]
        assert r["done_when"] or r["done_kind"] == "open_discussion"


def test_a_brainstorm_gets_no_done_test():
    r = c.classify("what if we let the queue run unattended overnight, just curious what you think")
    assert r["done_kind"] == "open_discussion" and r["done_when"] is None


def test_a_ticket_or_a_doc_is_never_the_done_test():
    for k in c.KINDS:
        assert "ticket" not in c.DONE_WHEN[k].lower() and "document" not in c.DONE_WHEN[k].lower()


def test_split_ordinals_and_counted_lead_but_not_plain_and():
    assert len(c.split_asks("first fix the footer, second add a test, third show me the diff")) == 3
    assert len(c.split_asks("two things, fix the footer, and also tell me which jobs are idle")) == 2
    assert len(c.split_asks("fix the footer and add a test")) == 1


def test_capture_returns_one_proposal_per_ask_and_never_accepts():
    props = c.capture("first fix the footer, second tell me why the job is slow")
    assert [p["kind"] for p in props] == ["do", "explore"]
    assert all(p["proposed"] for p in props)
    assert c.capture("ok") == []


def test_owner_words_and_default_are_explicit():
    assert c.owner_for("fix the sidebar", {"web": ["sidebar"]}) == ("web", "owner word 'sidebar'")
    owner, basis = c.owner_for("fix the thing")
    assert owner == "unassigned" and basis.startswith("default")


def test_replay_reports_without_writing_back():
    rows = [{"ts": "2025-03-03T09:00:00Z", "type": "ask", "class": "synthetic", "ask_id": "a1", "text": "fix the footer so it stops clipping"},
            {"ts": "2025-03-03T09:01:00Z", "type": "ask", "class": "synthetic", "ask_id": "a2", "text": "ok"}]
    before = [dict(r) for r in rows]
    rp = c.replay(rows)
    assert rows == before
    assert rp["kept"] == 1 and rp["dropped"] == 1 and rp["kept_but_unmapped_in_log"] == 1
