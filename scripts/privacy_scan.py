"""Fail loudly if anything private is in this repo: the working tree, every file name, the whole git history
(every added and removed line of every commit on every ref), commit metadata, and ref names.

    python scripts/privacy_scan.py              # tree + history, exit 1 on any hit
    python scripts/privacy_scan.py --tree-only
    python scripts/privacy_scan.py --history-only
    python scripts/privacy_scan.py --deny-file /path/to/deny.txt
    python scripts/privacy_scan.py PATH         # scan another directory (a folder you plan to publish)

The tree scan covers tracked files, untracked files AND git-ignored files (out/ is ignored and holds the sample
CSVs). Caches and environments (.git, __pycache__, .pytest_cache, .venv, node_modules and similar) are skipped.
A PATH that is not a git repository is scanned as a tree only. Conflicting or unknown flags exit 2.

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
# The one extra address allowed anywhere in HISTORY, and only as the whole of a Co-Authored-By trailer that names
# nobody else: the public vendor no-reply address that coding assistants add to commit messages. It is not
# allowed in the tree, in a normal message line, or next to any other address.
COAUTHOR_TRAILER = re.compile(r"^\s*Co-Authored-By:\s+[\w .'-]{1,60}<noreply@anthropic\.com>\s*$", re.I)

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


def scan_text(text: str, where: str, deny=None, trailers: bool = False) -> list[Hit]:
    """`trailers=True` (history only) lets a line that is exactly an assistant Co-Authored-By trailer through the
    email rule. Every other rule, and every other address, still applies."""
    deny = deny if deny is not None else load_deny()
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        trailer_ok = trailers and COAUTHOR_TRAILER.match(line) is not None
        for i, rx in enumerate(deny):
            if rx.search(line):
                hits.append(Hit(where, n, f"deny#{i}"))
        for name, rx in GENERIC:
            for m in rx.finditer(line):
                if name == "email" and (ALLOWED_EMAIL.match(m.group(0)) or trailer_ok):
                    continue
                if name == "ticket-key" and m.group(1) in TICKET_PREFIX_OK:
                    continue
                hits.append(Hit(where, n, name))
    return hits


class GitError(RuntimeError):
    """A git command failed. A scan that cannot read the repo must fail, never report it clean."""


def _git(root: Path, *args: str) -> str:
    try:
        p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    except OSError as e:
        raise GitError(f"could not run git {args[0]}: {e}") from e
    if p.returncode != 0:
        detail = p.stderr.decode("utf-8", errors="replace").strip().splitlines()
        raise GitError(f"git {args[0]} failed (exit {p.returncode}): {detail[0] if detail else 'no message'}")
    return p.stdout.decode("utf-8", errors="replace")


def _is_binary(path: Path) -> bool:
    return b"\0" in path.read_bytes()[:8192]


NOISE_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".venv", "venv",
              "node_modules", ".idea", ".vscode"}


def _noise(rel_parts: tuple[str, ...]) -> bool:
    return (any(p in NOISE_DIRS or p.endswith(".egg-info") for p in rel_parts)
            or rel_parts[-1].endswith((".pyc", ".pyo")))


def tree_files(root: Path) -> list[Path]:
    """Every file in the working tree: tracked, untracked, and git-ignored, minus cache and environment noise."""
    if (root / ".git").exists():
        out = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
        out += "\0" + _git(root, "ls-files", "-z", "--others", "--ignored", "--exclude-standard")
        names = sorted(set(out.split("\0")))
        cands = [root / n for n in names if n]
    else:
        cands = list(root.rglob("*"))
    return [f for f in cands if f.is_file() and not _noise(f.relative_to(root).parts)]


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
    hits = scan_text(body, "history", deny, trailers=True)
    for n, line in enumerate(log.splitlines(), 1):
        m = IDENT.match(line)
        if m and m.group(1).strip() not in ALLOWED_IDENTITIES:
            hits.append(Hit("history", n, "identity"))
        if line.startswith(("Binary files", "GIT binary patch")):
            hits.append(Hit("history", n, "binary-in-history"))
    refs = _git(root, "for-each-ref", "--format=%(refname)")
    hits += scan_text(refs, "refs", deny)
    return hits


def _parse(argv):
    """(deny_file, tree_only, history_only, target) or an error string."""
    deny_file, tree_only, history_only, target = None, False, False, None
    it = iter(argv)
    for a in it:
        if a == "--deny-file":
            deny_file = next(it, None)
            if not deny_file:
                return "--deny-file needs a path"
        elif a == "--tree-only":
            tree_only = True
        elif a == "--history-only":
            history_only = True
        elif a.startswith("-"):
            return f"unknown option {a}"
        elif target is None:
            target = a
        else:
            return "only one PATH may be given"
    if tree_only and history_only:
        return "--tree-only and --history-only conflict: together they would scan nothing"
    return deny_file, tree_only, history_only, target


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    parsed = _parse(argv)
    if isinstance(parsed, str):
        print(f"privacy_scan: {parsed}")
        print("usage: privacy_scan.py [--tree-only | --history-only] [--deny-file PATH] [PATH]")
        return 2
    deny_file, tree_only, history_only, target = parsed
    root = Path(target).resolve() if target else Path(__file__).resolve().parent.parent
    if not root.is_dir():
        print(f"privacy_scan: target {target} is not a directory")
        return 2
    try:
        deny = load_deny(deny_file)
    except (OSError, re.error) as e:
        print(f"privacy_scan: cannot use the deny file: {e}")
        return 2
    mode = (f"MODE: deny list ({len(deny)} entries) + generic patterns" if deny
            else "MODE: GENERIC PATTERNS ONLY (no deny list given; set PRIVACY_DENY_FILE or --deny-file)")
    print(mode)
    if target is not None and not (root / ".git").exists() and not history_only:
        tree_only = True
        print("note: target is not a git repository; scanning the tree only")
    hits: list[Hit] = []
    try:
        if not history_only:
            hits += scan_tree(root, deny)
        if not tree_only:
            hits += scan_history(root, deny)
    except GitError as e:
        print(f"PRIVACY SCAN COULD NOT RUN: {e}\nThis is a failure, not a clean result.")
        return 1
    if hits:
        bar = "!" * 72
        print(bar + "\nPRIVACY SCAN FAILED: %d hit(s). Nothing below is the matched text.\n" % len(hits) + bar)
        for h in hits[:200]:
            print("  " + str(h))
        return 1
    scope = "tree" if tree_only else "history" if history_only else "tree + history"
    print(f"privacy scan clean ({scope}): {len(deny)} deny entries, {len(GENERIC)} generic patterns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
