#!/usr/bin/env python3
"""Pre-push guard: refuse to push credentials / personal info in tracked files.

Usage:
    python3 scripts/check_no_secrets.py          # scan working tree (tracked files)
    python3 scripts/check_no_secrets.py --staged # scan only what is staged for commit

Exit code 0 = clean, 1 = findings (blocks the push/commit).

Design notes:
- Scans git-tracked files only (what would actually leave the machine).
- Patterns flag VALUES, not placeholders: 'your-key', 'mock', '<...>', 'example'
  are intentionally ignored so vendored OSS test fixtures do not trip it.
- Personal-path patterns are configurable at the bottom; they are the ones the
  user asked never to be pushed (local usernames / home dirs).
- Run this before `git push`. Optionally wire it into a git pre-push hook.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (label, compiled regex) — flag patterns that carry an actual value.
SECRET_PATTERNS = [
    ("OpenAI/DeepSeek-style sk- key", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("OpenRouter key", re.compile(r"sk-or-[A-Za-z0-9_-]{20,}")),
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("WSL sudo password (known literal)", re.compile(r"tianleiyu")),
]

# Lines containing any of these are treated as harmless placeholders/docs.
PLACEHOLDER = re.compile(
    r"your[-_ ]?key|your[-_ ]?api|mock|example|placeholder|dummy|xxx+|"
    r"test[-_ ]?key|<[^>]+>|sk-or-\.\.\.|sample|change[-_ ]?me",
    re.I,
)

# Personal environment paths the user does not want published.
# Keep this list short and explicit; add entries as needed.
PERSONAL_PATH = re.compile(
    r"tlyth|atdoc|C:/Users/[A-Za-z0-9._-]+|C:\\Users\\[A-Za-z0-9._-]+|"
    r"/home/[A-Za-z0-9._-]+/projects",
)

# Directories/blobs we never scan (binary or vendored noise handled separately).
SKIP_SUFFIX = {".jpg", ".jpeg", ".png", ".gif", ".ico", ".pyc", ".pth", ".pkl", ".so", ".dll"}
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv"}


def git_tracked() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True
    )
    if out.returncode != 0:
        print(f"ERROR: git ls-files failed: {out.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    return [f for f in out.stdout.splitlines() if f.strip()]


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if out.returncode != 0:
        print(f"ERROR: git diff --cached failed: {out.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    return [f for f in out.stdout.splitlines() if f.strip()]


def read_blob(path: str, staged: bool) -> str | None:
    if staged:
        r = subprocess.run(
            ["git", "show", f":{path}"], cwd=ROOT, capture_output=True
        )
        if r.returncode != 0:
            return None
        return r.stdout.decode("utf-8", errors="replace")
    p = ROOT / path
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true", help="scan staged files instead of working tree")
    args = ap.parse_args()

    files = staged_files() if args.staged else git_tracked()
    findings: list[tuple[str, str, int, str]] = []

    for rel in files:
        # This guard literally contains the patterns it scans for, so it would
        # always flag itself once tracked. Skip its own path.
        if rel.replace("\\", "/") == "scripts/check_no_secrets.py":
            continue
        if Path(rel).suffix.lower() in SKIP_SUFFIX:
            continue
        if any(part in SKIP_DIRS for part in Path(rel).parts):
            continue
        txt = read_blob(rel, args.staged)
        if not txt:
            continue
        for lineno, line in enumerate(txt.splitlines(), 1):
            for label, pat in SECRET_PATTERNS:
                if pat.search(line) and not PLACEHOLDER.search(line):
                    findings.append(("SECRET", label, rel, lineno, line.strip()[:140]))
            # Personal paths are always flagged (placeholders already replaced).
            if PERSONAL_PATH.search(line) and not PLACEHOLDER.search(line):
                findings.append(("PERSONAL_PATH", "local username/home path", rel, lineno, line.strip()[:140]))

    mode = "staged files" if args.staged else "tracked files"
    if not findings:
        print(f"OK: no secrets or personal info in {len(files)} {mode}.")
        return 0

    print(f"BLOCKED: {len(findings)} finding(s) in {mode}:")
    for kind, label, rel, lineno, line in findings:
        print(f"  [{kind}] {label} — {rel}:{lineno}")
        print(f"      {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
