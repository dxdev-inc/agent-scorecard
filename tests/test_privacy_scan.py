"""The privacy scan must be clean on this repo AND must be proven to fire. A detector nobody has seen fire is a
guess, so every class of leak is planted in a throwaway repo below and has to be caught. The planted strings are
assembled at run time so this file does not contain them."""
import os
import subprocess
import sys
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import privacy_scan as ps  # noqa: E402

ENV = {**os.environ, "GIT_AUTHOR_NAME": "DXdev", "GIT_AUTHOR_EMAIL": "noreply@dxdev.com",
       "GIT_COMMITTER_NAME": "DXdev", "GIT_COMMITTER_EMAIL": "noreply@dxdev.com"}


# Made-up, non-private stand-ins. The real list lives outside the repo.
FAKE_TERM = "zorblax" + "quux"
DENY = [re.compile(re.escape(FAKE_TERM), re.I)]


def git(cwd, *a, env=None):
    subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True, env=env or ENV)


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "ok.txt").write_text("nothing to see here\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "clean start")
    return tmp_path


def test_this_repo_is_clean_tree_and_history():
    assert ps.main([]) == 0


def test_a_clean_throwaway_repo_scans_clean(repo):
    assert ps.scan_tree(repo, DENY) == [] and ps.scan_history(repo, DENY) == []


PLANTS = {
    "deny-list term": lambda: FAKE_TERM,
    "email": lambda: "someone" + "@" + "corp-mail.io",
    "ipv4": lambda: ".".join(["10", "20", "30", "40"]),
    "drive path": lambda: "C" + ":" + chr(92) + "work",
    "secret token": lambda: "ghp" + "_" + "a" * 30,
    "credential": lambda: "pass" + "word = '" + "x" * 12 + "'",
    "ticket key": lambda: "AB" + "-" + "123",
    "key block": lambda: "-----BEGIN " + "RSA PRIVATE KEY-----",
}


@pytest.mark.parametrize("name", sorted(PLANTS))
def test_tree_scan_fires(repo, name):
    (repo / "leak.md").write_text("line one\n" + PLANTS[name]() + "\n", encoding="utf-8")
    hits = ps.scan_tree(repo, DENY)
    assert hits, f"{name} was not caught"
    assert all(PLANTS[name]() not in str(h) for h in hits), "a hit must never echo the matched text"


def test_filename_is_scanned(repo):
    (repo / (FAKE_TERM + ".txt")).write_text("harmless\n", encoding="utf-8")
    assert any("filename" in h[0] for h in ps.scan_tree(repo, DENY))


def test_binary_file_fires(repo):
    (repo / "pic.bin").write_bytes(b"\x89PNG\0\0\0binary")
    assert any(h[2] == "binary-file" for h in ps.scan_tree(repo, DENY))


def test_leak_removed_from_the_tree_is_still_caught_in_history(repo):
    (repo / "leak.md").write_text(PLANTS["deny-list term"]() + "\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "oops")
    git(repo, "rm", "-q", "leak.md")
    git(repo, "commit", "-q", "-m", "remove it")
    assert ps.scan_tree(repo, DENY) == []
    assert ps.scan_history(repo, DENY), "history scan missed a leak that only lives in an old commit"


def test_leak_on_another_branch_is_caught(repo):
    git(repo, "checkout", "-q", "-b", "side")
    (repo / "leak.md").write_text(PLANTS["email"]() + "\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "side work")
    git(repo, "checkout", "-q", "-")        # back to the first branch; the leak lives only on `side`
    assert ps.scan_history(repo, DENY)


def test_wrong_author_identity_is_caught(repo):
    (repo / "b.txt").write_text("fine\n", encoding="utf-8")
    git(repo, "add", "-A")
    env = {**ENV, "GIT_AUTHOR_NAME": "Someone Else", "GIT_AUTHOR_EMAIL": "noreply@dxdev.com"}
    git(repo, "commit", "-q", "-m", "wrong author", env=env)
    assert any(h[2] == "identity" for h in ps.scan_history(repo, DENY))


def test_a_leak_in_a_commit_message_is_caught(repo):
    (repo / "c.txt").write_text("fine\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "note about " + FAKE_TERM)
    assert ps.scan_history(repo, DENY)


def test_deny_file_is_loaded_from_argument_and_environment(tmp_path, monkeypatch):
    f = tmp_path / "deny.txt"
    f.write_text("# comment\n\n" + FAKE_TERM + "\n", encoding="utf-8")
    assert len(ps.load_deny(str(f))) == 1
    monkeypatch.setenv("PRIVACY_DENY_FILE", str(f))
    assert len(ps.load_deny()) == 1
    monkeypatch.delenv("PRIVACY_DENY_FILE")
    assert ps.load_deny() == []


def test_mode_is_stated_and_a_deny_file_changes_the_result(repo, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("PRIVACY_DENY_FILE", raising=False)
    ps.main(["--tree-only"])
    assert "GENERIC PATTERNS ONLY" in capsys.readouterr().out
    f = tmp_path / "deny.txt"
    f.write_text(FAKE_TERM + "\n", encoding="utf-8")
    ps.main(["--tree-only", "--deny-file", str(f)])
    assert "deny list (1 entries)" in capsys.readouterr().out
    # without the deny file the planted term is invisible; with it, caught
    (repo / "leak.md").write_text(FAKE_TERM + "\n", encoding="utf-8")
    assert ps.scan_tree(repo, []) == []
    assert ps.scan_tree(repo, ps.load_deny(str(f)))


TRAILER = "Co-Authored-By: Claude Sonnet 5.5 <" + "noreply" + "@" + "anthropic.com>"


def _commit_message(repo, message):
    (repo / "m.txt").write_text(message[:8] + "\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def test_assistant_coauthor_trailer_is_allowed_in_history(repo):
    _commit_message(repo, "Add a thing\n\n" + TRAILER)
    assert ps.scan_history(repo, DENY) == []


def test_the_coauthor_allowance_stays_narrow(repo, tmp_path):
    addr = "noreply" + "@" + "anthropic.com"
    # same address, but not as a trailer line
    _commit_message(repo, "mail " + addr + " about it")
    assert any(h[2] == "email" for h in ps.scan_history(repo, DENY))
    # a trailer that carries any other address
    other = tmp_path / "other"
    subprocess.run(["git", "init", "-q", str(other)], check=True, capture_output=True)
    (other / "a.txt").write_text("x\n", encoding="utf-8")
    git(other, "add", "-A")
    git(other, "commit", "-q", "-m", "x\n\nCo-Authored-By: Someone <" + "someone" + "@" + "corp-mail.io>")
    assert any(h[2] == "email" for h in ps.scan_history(other, DENY))
    # a trailer that names the vendor address AND another one
    third = tmp_path / "third"
    subprocess.run(["git", "init", "-q", str(third)], check=True, capture_output=True)
    (third / "a.txt").write_text("x\n", encoding="utf-8")
    git(third, "add", "-A")
    git(third, "commit", "-q", "-m", "x\n\nCo-Authored-By: A <" + addr + "> " + "b" + "@" + "corp-mail.io")
    assert any(h[2] == "email" for h in ps.scan_history(third, DENY))
    # in the tree it is still a hit
    (repo / "note.md").write_text(TRAILER + "\n", encoding="utf-8")
    assert any(h[2] == "email" for h in ps.scan_tree(repo, DENY))


def test_a_git_failure_is_an_error_not_a_clean_scan(tmp_path, monkeypatch, capsys):
    broken = tmp_path / "broken"
    (broken / ".git").mkdir(parents=True)   # looks like a repo, is not one
    with pytest.raises(ps.GitError):
        ps.scan_history(broken, DENY)
    with pytest.raises(ps.GitError):
        ps.scan_tree(broken, DENY)

    def failing(*a, **k):
        return subprocess.CompletedProcess(a, 128, stdout=b"", stderr=b"fatal: not a git repository")

    monkeypatch.setattr(ps.subprocess, "run", failing)
    assert ps.main([]) == 1
    out = capsys.readouterr().out
    assert "COULD NOT RUN" in out and "privacy scan clean" not in out
