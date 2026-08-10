"""Verify that each commit in a pull request contains a DCO sign-off."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys

SIGN_OFF_RE = re.compile(r"^Signed-off-by: .+ <[^<>\s]+@[^<>\s]+>$", re.MULTILINE)
GIT = shutil.which("git")


def _git(*args: str) -> str:
    """Run a read-only Git command and return its standard output."""
    if GIT is None:
        raise RuntimeError("git executable was not found")
    result = subprocess.run(  # noqa: S603
        [GIT, *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def main() -> int:
    """Check every non-merge commit between the supplied base and head."""
    if len(sys.argv) != 3:
        print("usage: check_dco.py <base> <head>", file=sys.stderr)
        return 2

    base, head = sys.argv[1:]
    commits = _git("rev-list", "--no-merges", f"{base}..{head}").splitlines()
    unsigned: list[str] = []
    for commit in commits:
        message = _git("show", "-s", "--format=%B", commit)
        if SIGN_OFF_RE.search(message) is None:
            unsigned.append(commit)

    if unsigned:
        print("DCO sign-off missing from these commits:", file=sys.stderr)
        for commit in unsigned:
            print(f"  {commit}", file=sys.stderr)
        print("Amend each commit with: git commit --amend --signoff", file=sys.stderr)
        return 1

    print(f"DCO check passed for {len(commits)} commit(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
