"""Fail CI if CLAUDE.md or README.md quote a Config default that has drifted.

Narrowly targeted at the exact bug in #62: CLAUDE.md's example dusk.yaml
block claimed gate_block_threshold: 0.7 while config.py's real default was
0.6, and README.md's own config table happened to already be correct --
so the two docs disagreed with each other and one of them was wrong,
silently, until a manual review caught it.

This does not parse prose or catch every kind of doc drift -- only numeric
Config defaults that appear in a `name: value` or `` `name` `` ... `value`
shape in the two files below, checked against dataclasses.fields(Config()).
"""

from __future__ import annotations

import dataclasses
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dusk.config import Config  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_FILES = [REPO_ROOT / "CLAUDE.md", REPO_ROOT / "README.md"]


def _real_defaults() -> dict[str, object]:
    config = Config()
    return {f.name: getattr(config, f.name) for f in dataclasses.fields(config)}


def _check_file(path: Path, defaults: dict[str, object]) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for name, real_value in defaults.items():
        if not isinstance(real_value, (int, float)) or isinstance(real_value, bool):
            continue
        # Matches "name: 0.6" (a YAML-block example) or "`name`" followed
        # later on the same line by a bare number (a markdown table cell).
        for match in re.finditer(rf"\b{re.escape(name)}\b[^\n]{{0,40}}", text):
            line = match.group(0)
            numbers = re.findall(r"-?\d+\.?\d*", line)
            if not numbers:
                continue
            documented = float(numbers[0])
            if documented != float(real_value):
                line_no = text[: match.start()].count("\n") + 1
                errors.append(
                    f"{path.name}:{line_no}: '{name}' documented as {numbers[0]}, "
                    f"but Config's real default is {real_value}"
                )
    return errors


def main() -> int:
    defaults = _real_defaults()
    all_errors: list[str] = []
    for path in DOC_FILES:
        all_errors.extend(_check_file(path, defaults))

    if all_errors:
        print("Config default(s) documented incorrectly:", file=sys.stderr)
        for error in all_errors:
            print(f"  {error}", file=sys.stderr)
        return 1

    print(
        f"Checked {len(defaults)} Config default(s) against "
        f"{len(DOC_FILES)} doc file(s), all match."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
