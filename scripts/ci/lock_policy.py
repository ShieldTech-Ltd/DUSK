#!/usr/bin/env python3
"""Require every direct dependency to be represented in a hash-locked input."""

from pathlib import Path


def main() -> None:
    for lock in (Path("ci/requirements.lock"), Path("ci/example-requirements.lock")):
        text = lock.read_text(encoding="utf-8")
        entries = [line for line in text.splitlines() if line and not line.startswith(("#", " "))]
        if not entries or any("==" not in line or "--hash=sha256:" not in line for line in entries):
            raise SystemExit(f"{lock} must contain pinned, hashed requirements")


if __name__ == "__main__":
    main()
