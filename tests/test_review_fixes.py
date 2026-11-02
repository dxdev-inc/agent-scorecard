"""Regression tests for the outside review of 0.2.x: each fails on the code before the fix."""
import csv
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import privacy_scan as ps  # noqa: E402

from agent_scorecard import cli, schema, verify  # noqa: E402

ENV = {**os.environ, "GIT_AUTHOR_NAME": "DXdev", "GIT_AUTHOR_EMAIL": "noreply@dxdev.com",
       "GIT_COMMITTER_NAME": "DXdev", "GIT_COMMITTER_EMAIL": "noreply@dxdev.com"}
UNIT = {"unit": "u1", "deliverable": "code", "executor": "a", "requester": "r"}
GOOD_EV = {"kind": "test_run", "ref": "run-1", "outcome_observed": True}


def _ev(**kw):
    e = {"result": "pass", "verifier": "reviewer", "evidence": dict(GOOD_EV)}
    for k, v in kw.items():
        if k.startswith("ev_"):
            e["evidence"][k[3:]] = v
        else:
            e[k] = v
    return e


def test_judge_baseline_pass():
    assert verify.judge(UNIT, _ev())[0] == "pass"


@pytest.mark.parametrize("blank", [" ", "   ", "\t\n"])
def test_whitespace_verifier_is_not_a_pass(blank):
    assert verify.judge(UNIT, _ev(verifier=blank))[0] == "inconclusive"


@pytest.mark.parametrize("blank", [" ", "   ", "\t"])
def test_whitespace_evidence_ref_is_not_a_pass(blank):
    assert verify.judge(UNIT, _ev(ev_ref=blank))[0] == "inconclusive"


def test_padded_verifier_still_cannot_be_the_executor():
    assert verify.judge(UNIT, _ev(verifier=" a "))[1] == "verifier is the executor"


# --- privacy scan: ignored files, flags, target path -------------------------------------------------------
def _repo(path):
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)
    (path / ".gitignore").write_text("out/\n__pycache__/\n", encoding="utf-8")
    (path / "ok.txt").write_text("fine\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True, capture_output=True, env=ENV)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "start"], check=True, capture_output=True, env=ENV)
    return path


TOKEN = "ghp" + "_" + "a" * 30


def test_ignored_file_with_a_token_is_caught(tmp_path):
    _repo(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "sample.csv").write_text(TOKEN + "\n", encoding="utf-8")
    hits = ps.scan_tree(tmp_path, [])
    assert any(h[0] == "out/sample.csv" and h[2] == "secret-token" for h in hits)


def test_cache_noise_is_not_scanned(tmp_path):
    _repo(tmp_path)
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"\0\0bin")
    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / ".pytest_cache" / "v").write_text("a" + "@" + "b.io\n",encoding="utf-8")
    assert ps.scan_tree(tmp_path, []) == []


def test_conflicting_flags_exit_nonzero(capsys):
    assert ps.main(["--tree-only", "--history-only"]) == 2
    out = capsys.readouterr().out
    assert "clean" not in out


def test_unknown_flag_and_extra_path_exit_nonzero(capsys):
    assert ps.main(["--bogus"]) == 2
    assert ps.main(["a", "b"]) == 2
    assert ps.main(["--deny-file"]) == 2
    assert ps.main(["/no/such/dir/here"]) == 2


def test_external_target_is_scanned(tmp_path, capsys):
    target = tmp_path / "pub"
    target.mkdir()
    (target / "a.md").write_text("clean\n", encoding="utf-8")
    assert ps.main([str(target)]) == 0
    (target / "b.md").write_text(TOKEN + "\n", encoding="utf-8")
    assert ps.main([str(target)]) == 1


def test_external_git_target_includes_ignored_and_history(tmp_path):
    _repo(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "s.csv").write_text(TOKEN + "\n", encoding="utf-8")
    assert ps.main([str(tmp_path), "--tree-only"]) == 1


# --- documented commands -----------------------------------------------------------------------------------
def test_literal_documented_score_command_works(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out").mkdir()
    with open("out/sample.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ask_id", "text", "label", "evidence_kind", "evidence_ref"])
        w.writerow(["a1", "x", "finished", "git", "abc"])
    assert cli.main(["sample", "--score", "out/sample.csv"]) == 0
    assert "finished_all" in capsys.readouterr().out


def test_docs_do_not_show_bare_score_flag():
    for name in ("README.md", "docs/FIRST_PILOT.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert not re.search(r"sample --score(?!\s+\S*\.csv)", text), name


def test_k_larger_than_asks_is_capped(tmp_path, monkeypatch, capsys):
    log = tmp_path / "log.jsonl"
    log.write_text('{"type":"ask","ask_id":"a1","text":"one"}\n{"type":"ask","ask_id":"a2","text":"two"}\n',
                   encoding="utf-8")
    out = tmp_path / "s.csv"
    assert cli.main(["sample", "--log", str(log), "--out", str(out)]) == 0
    assert "capped" in capsys.readouterr().out
    assert len(list(csv.DictReader(open(out, encoding="utf-8")))) == 2


# --- timestamps and version --------------------------------------------------------------------------------
def test_naive_timestamp_is_an_error_not_local_time():
    with pytest.raises(ValueError):
        schema.parse_ts("2025-03-20T00:00:00")
    assert schema.validate({"type": "ask", "ts": "2025-03-20T00:00:00", "class": "synthetic",
                            "ask_id": "a", "text": "t"})
    assert schema.parse_ts("2025-03-20T00:00:00Z") == schema.parse_ts("2025-03-20T02:00:00+02:00")


def test_version_matches_pyproject_and_changelog():
    import agent_scorecard
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    v = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
    assert agent_scorecard.__version__ == v
    heads = re.findall(r"^## (\d+\.\d+\.\d+)", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    assert heads[0] == v


# --- second review ------------------------------------------------------------------------------------------
def test_padded_executor_or_requester_cannot_verify_their_own_work():
    padded = {**UNIT, "executor": " worker-1 ", "requester": "\tboss "}
    assert verify.judge(padded, _ev(verifier="worker-1"))[1] == "verifier is the executor"
    assert verify.judge(padded, _ev(verifier="boss"))[1] == "verifier is the requester"


def _log(tmp_path, *rows):
    import json
    p = tmp_path / "log.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


TS = "2025-03-01T00:00:00Z"
UNIT_ROW = {"type": "unit_created", "ts": TS, "class": "synthetic", "unit": "u1", "kind": "do",
            "deliverable": "code", "executor": "a", "requester": "r"}


def test_string_booleans_are_schema_errors():
    s = {"type": "status", "ts": TS, "class": "synthetic", "unit": "u1", "status": "done", "forced": "false"}
    assert any("forced" in e for e in schema.validate(s))
    v = {"type": "verify", "ts": TS, "class": "synthetic", "unit": "u1", "verifier": "v", "result": "pass",
         "evidence": {"kind": "test_run", "ref": "r", "outcome_observed": "false"}}
    assert any("outcome_observed" in e for e in schema.validate(v))
    v["evidence"]["outcome_observed"] = False
    assert schema.validate(v) == []


def test_measure_load_rejects_a_bad_log_loudly(tmp_path):
    from agent_scorecard import measure
    bad = {"type": "status", "ts": TS, "class": "synthetic", "unit": "u1", "status": "done", "forced": "false"}
    with pytest.raises(ValueError, match="line 2"):
        measure.load(_log(tmp_path, UNIT_ROW, bad))
    with pytest.raises(ValueError):
        measure.load(_log(tmp_path, {"type": "ask", "ts": "2025-03-01T00:00:00", "class": "synthetic",
                                     "ask_id": "a", "text": "t"}))
    assert len(measure.load(_log(tmp_path, UNIT_ROW))) == 1


def test_cli_measure_on_a_bad_log_does_not_report_numbers(tmp_path):
    bad = {"type": "status", "ts": TS, "class": "synthetic", "unit": "u1", "status": "done", "forced": "false"}
    log = _log(tmp_path, UNIT_ROW, bad)
    with pytest.raises(ValueError):
        cli.main(["measure", "--log", str(log)])


def _tag_repo(tmp_path, message, tagger_name="DXdev", tagger_email="noreply@dxdev.com"):
    _repo(tmp_path)
    env = {**ENV, "GIT_COMMITTER_NAME": tagger_name, "GIT_COMMITTER_EMAIL": tagger_email}
    subprocess.run(["git", "-C", str(tmp_path), "tag", "-a", "v9", "-m", message], check=True, capture_output=True, env=env)
    return tmp_path


def test_secret_in_annotated_tag_message_is_caught(tmp_path):
    _tag_repo(tmp_path, "release " + TOKEN)
    assert any(h[0].startswith("tag ") and h[2] == "secret-token" for h in ps.scan_history(tmp_path, []))


def test_wrong_tagger_identity_is_caught(tmp_path):
    _tag_repo(tmp_path, "release", tagger_name="Someone Else")
    assert any(h[0].startswith("tag ") and h[2] == "identity" for h in ps.scan_history(tmp_path, []))


def test_clean_annotated_tag_and_lightweight_tag_pass(tmp_path):
    _tag_repo(tmp_path, "release one")
    subprocess.run(["git", "-C", str(tmp_path), "tag", "light"], check=True, capture_output=True, env=ENV)
    assert ps.scan_history(tmp_path, []) == []


@pytest.mark.parametrize("d", [".vscode", ".idea"])
def test_ide_settings_are_scanned(tmp_path, d):
    (tmp_path / d).mkdir()
    (tmp_path / d / "settings.json").write_text('{"k": "' + TOKEN + '"}\n', encoding="utf-8")
    assert ps.main([str(tmp_path)]) == 1


@pytest.mark.parametrize("name,data", [("a.pdf", b"%PDF-1.4\nplain text body\n%%EOF\n"),
                                       ("noext", b"%PDF-1.4\nplain\n"),
                                       ("pic.png", b"just text"),
                                       ("z.dat", b"PK\x03\x04textonly")])
def test_binary_without_nul_is_still_rejected(tmp_path, name, data):
    (tmp_path / name).write_bytes(data)
    assert any(h[2] == "binary-file" for h in ps.scan_tree(tmp_path, []))


def test_k_below_one_is_rejected_by_argparse(tmp_path, capsys):
    log = tmp_path / "l.jsonl"
    log.write_text('{"type":"ask","ask_id":"a1","text":"one"}\n', encoding="utf-8")
    for k in ("0", "-1"):
        with pytest.raises(SystemExit) as e:
            cli.main(["sample", "--log", str(log), "--k", k, "--out", str(tmp_path / "o.csv")])
        assert e.value.code == 2
    assert not (tmp_path / "o.csv").exists()
