"""Fail loudly if anything private is in this repo: the working tree, every file name, the whole git history
(every added and removed line of every commit on every ref), commit metadata, and ref names.

    python scripts/privacy_scan.py              # tree + history, exit 1 on any hit
    python scripts/privacy_scan.py --tree-only
    python scripts/privacy_scan.py --history-only
    python scripts/privacy_scan.py --deny-file /path/to/deny.txt

What it checks:
  * a deny list, one case-insensitive regex per line, read from a file that is NOT in this repo. Give its path
    with --deny-file PATH or the PRIVACY_DENY_FILE environment variable. A hit names the entry INDEX, never the
    matched text. With no file the scan runs the generic patterns only and says so on its first output line;
  * generic patterns: email addresses, IPv4 addresses, absolute drive or home paths, UNC paths, secret-shaped
    tokens and key blocks, credential assignments, ticket-key shapes;
  * binary files anywhere (images, archives, notebooks and PDFs are how metadata hides), in the tree or in history;
  * commit author and committer identity, which must be the one allowed identity below.

What it cannot do: it is pattern matching. A paragraph that describes private structure without using any denied
word passes. The semantic review is a separate, human or different-model step, listed in the README as thin.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import os

ALLOWED_IDENTITIES = {"DXdev <noreply@dxdev.com>"}
ALLOWED_EMAIL = re.compile(r"^(?:noreply@dxdev\.com|[\w.+-]+@example\.(?:com|org))$", re.I)
TICKET_PREFIX_OK = {"ISO", "SHA", "RFC", "PEP"}

GENERIC = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("abs-path", re.compile(r"\b[A-Za-z]:[\\/]|/Users/\w|/home/\w")),
    ("unc-path", re.compile(r"\\\\[\w.-]+\\")),
    ("internal-host", re.compile(r"\b[\w-]+\.(?:local|internal|lan|corp)\b", re.I)),
    ("secret-token", re.compile(r"ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("credential-assignment", re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"][^'\"]{8,}")),
    ("ticket-key", re.compile(r"\b([A-Z]{2,6})-\d{2,6}\b")),
]


class Hit(tuple):
    """(where, line, rule). `where` is a path or a history marker; never the matched text."""
    __slots__ = ()

    def __new__(cls, where, line, rule):
        return tuple.__new__(cls, (where, line, rule))

    def __str__(self):
        return f"{self[0]}:{self[1]}  rule={self[2]}"


def load_deny(path=None) -> list[re.Pattern]:
    """Compile the deny list from `path`, else $PRIVACY_DENY_FILE, else return []. Blank lines and # lines skipped."""
    path = path or os.environ.get("PRIVACY_DENY_FILE")
    if not path:
        return []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [re.compile(t.strip(), re.I) for t in lines if t.strip() and not t.lstrip().startswith("#")]


def scan_text(text: str, where: str, deny=None) -> list[Hit]:
    deny = deny if deny is not None else load_deny()
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        for i, rx in enumerate(deny):
            if rx.search(line):
                hits.append(Hit(where, n, f"deny#{i}"))
        for name, rx in GENERIC:
            for m in rx.finditer(line):
                if name == "email" and ALLOWED_EMAIL.match(m.group(0)):
                    continue
                if name == "ticket-key" and m.group(1) in TICKET_PREFIX_OK:
                    continue
                hits.append(Hit(where, n, name))
    return hits


def _git(root: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    return p.stdout.decode("utf-8", errors="replace")


def _is_binary(path: Path) -> bool:
    return b"\0" in path.read_bytes()[:8192]


def tree_files(root: Path) -> list[Path]:
    if (root / ".git").exists():
        names = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
        return [root / n for n in names if n and (root / n).is_file()]
    return [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]


def scan_tree(root: Path, deny=None) -> list[Hit]:
    deny = deny if deny is not None else load_deny()
    hits = []
    for f in tree_files(root):
        rel = f.relative_to(root).as_posix()
        hits += scan_text(rel, f"filename {rel}", deny)
        if _is_binary(f):
            hits.append(Hit(rel, 0, "binary-file"))
            continue
        hits += scan_text(f.read_text(encoding="utf-8", errors="replace"), rel, deny)
    return hits


IDENT = re.compile(r"^(?:Author|Commit):\s+(.*)$")


def scan_history(root: Path, deny=None) -> list[Hit]:
    if not (root / ".git").exists():
        return [Hit("history", 0, "no-git-directory")]
    deny = deny if deny is not None else load_deny()
    log = _git(root, "log", "--all", "-p", "--no-color", "--format=fuller", "--no-renames")
    # Drop the diff marker so "+@decorator" is not read as an email local part. Line numbers are unchanged.
    body = "\n".join(ln[1:] if ln[:1] in ("+", "-") else ln for ln in log.splitlines())
    hits = scan_text(body, "history", deny)
    for n, line in enumerate(log.splitlines(), 1):
        m = IDENT.match(line)
        if m and m.group(1).strip() not in ALLOWED_IDENTITIES:
            hits.append(Hit("history", n, "identity"))
        if line.startswith(("Binary files", "GIT binary patch")):
            hits.append(Hit("history", n, "binary-in-history"))
    refs = _git(root, "for-each-ref", "--format=%(refname)")
    hits += scan_text(refs, "refs", deny)
    return hits


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    deny_file = None
    if "--deny-file" in argv:
        i = argv.index("--deny-file")
        deny_file = argv[i + 1]
        del argv[i:i + 2]
    args = set(argv)
    deny = load_deny(deny_file)
    mode = (f"MODE: deny list ({len(deny)} entries) + generic patterns" if deny
            else "MODE: GENERIC PATTERNS ONLY (no deny list given; set PRIVACY_DENY_FILE or --deny-file)")
    print(mode)
    root = Path(__file__).resolve().parent.parent
    hits: list[Hit] = []
    if "--history-only" not in args:
        hits += scan_tree(root, deny)
    if "--tree-only" not in args:
        hits += scan_history(root, deny)
    if hits:
        bar = "!" * 72
        print(bar + "\nPRIVACY SCAN FAILED: %d hit(s). Nothing below is the matched text.\n" % len(hits) + bar)
        for h in hits[:200]:
            print("  " + str(h))
        return 1
    scope = "tree" if "--tree-only" in args else "history" if "--history-only" in args else "tree + history"
    print(f"privacy scan clean ({scope}): {len(deny)} deny entries, {len(GENERIC)} generic patterns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
