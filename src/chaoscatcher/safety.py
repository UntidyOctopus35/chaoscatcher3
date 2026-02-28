from __future__ import annotations
from pathlib import Path
import sys


def _find_git_root(start: Path) -> Path | None:
    cur = start
    for _ in range(200):
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


def assert_safe_data_path(data_path: Path, allow_repo_data_path: bool) -> None:
    # refuse if data lives inside any git repo (unless overridden)
    git_root = _find_git_root(data_path.parent)
    if git_root and not allow_repo_data_path:
        print("🚫 Refusing to use a data file inside a git repo.", file=sys.stderr)
        print(f"   data_path: {data_path}", file=sys.stderr)
        print(f"   repo_root: {git_root}", file=sys.stderr)
        print(
            "   Fix: use ~/.config/chaoscatcher/*.json or pass --allow-repo-data-path",
            file=sys.stderr,
        )
        raise SystemExit(2)
