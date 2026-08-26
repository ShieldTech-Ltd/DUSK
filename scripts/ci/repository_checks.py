#!/usr/bin/env python3
"""Fast, deterministic repository-integrity policy checks."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

TEXT_SUFFIXES = {".py", ".md", ".rst", ".toml", ".yml", ".yaml", ".json", ".txt", ".sh"}
MAX_BYTES = 5 * 1024 * 1024


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"])  # noqa: S607
    return [Path(item.decode()) for item in output.split(b"\0") if item]


def check() -> list[str]:  # noqa: C901
    errors: list[str] = []
    files = tracked_files()
    folded: dict[str, Path] = {}
    for path in files:
        key = str(path).casefold()
        if key in folded and folded[key] != path:
            errors.append(f"case-insensitive collision: {folded[key]} and {path}")
        folded[key] = path
        if path.is_symlink():
            target = os.readlink(path)
            resolved = (path.parent / target).resolve()
            if target.startswith("/") or not resolved.is_relative_to(Path.cwd().resolve()):
                errors.append(f"unsafe symlink: {path} -> {target}")
        if path.exists() and path.stat().st_size > MAX_BYTES:
            errors.append(f"oversized tracked file: {path}")
        if path.suffix in TEXT_SUFFIXES and path.exists():
            raw = path.read_bytes()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(f"not UTF-8: {path}")
                continue
            if b"\r\n" in raw:
                errors.append(f"CRLF line endings: {path}")
            if re.search(r"^(<<<<<<<|=======|>>>>>>>)", text, re.MULTILINE):
                errors.append(f"merge conflict marker: {path}")
    metadata = Path("pyproject.toml").read_text(encoding="utf-8")
    if 'license = "Apache-2.0"' not in metadata or not Path("LICENSE").exists():
        errors.append("Apache-2.0 package metadata and LICENSE are required")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    errors = check()
    if errors:
        raise SystemExit("\n".join(errors))


if __name__ == "__main__":
    main()
