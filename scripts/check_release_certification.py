"""Allow development packages while retaining stable provider certification."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

from validate_provider_certification import load_and_validate


def check_release(root: Path, tag: str) -> list[str]:
    """Reject mismatched tags and stable releases without provider evidence."""
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    if tag != f"v{version}":
        return ["Release tag does not match package version"]
    if re.fullmatch(r"v\d+\.\d+\.\d+(?:a|b|rc)\d+", tag):
        return []
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        return ["Unsupported release tag format"]
    return load_and_validate(root / "docs/evidence/provider-certification.json")


if __name__ == "__main__":
    errors = check_release(Path(__file__).resolve().parents[1], sys.argv[1])
    for error in errors:
        print(f"Release certification failure: {error}")
    if not errors:
        print("Scope accepted. Prerelease packages do not certify cloud enforcement.")
    raise SystemExit(bool(errors))
