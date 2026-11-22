#!/usr/bin/env python3
"""Reject undocumented, broad, mismatched, or expired scanner suppressions."""

from datetime import date
from pathlib import Path

import yaml


def parse_package(value: object) -> tuple[str, str, str]:
    """Parse the required exact package coordinate name=version:type."""
    text = str(value)
    if "=" not in text or ":" not in text:
        raise SystemExit(f"suppression package must be name=version:type: {text}")
    name, version_and_type = text.split("=", 1)
    version, package_type = version_and_type.rsplit(":", 1)
    if not name or not version or not package_type:
        raise SystemExit(f"suppression package must be name=version:type: {text}")
    return name, version, package_type


def main() -> None:
    data = yaml.safe_load(Path("ci/suppressions.yml").read_text(encoding="utf-8"))
    grype = yaml.safe_load(Path("ci/grype.yml").read_text(encoding="utf-8"))
    documented: set[tuple[str, str, str, str]] = set()
    for item in data.get("suppressions", []):
        required = ("control", "finding", "kind", "package", "reason", "owner", "expires")
        if not all(item.get(key) for key in required):
            raise SystemExit(
                "every suppression needs control, finding, kind, package, reason, owner, and expiry"
            )
        if date.fromisoformat(str(item["expires"])) < date.today():
            raise SystemExit(
                f"expired suppression: {item['control']} {item['finding']} {item['package']}"
            )
        package_name, package_version, package_type = parse_package(item["package"])
        documented.add((str(item["finding"]), package_name, package_version, package_type))

    configured: set[tuple[str, str, str, str]] = set()
    for item in grype.get("ignore", []):
        package = item.get("package") or {}
        if not all(package.get(key) for key in ("name", "version", "type")):
            raise SystemExit(f"grype ignore must pin package name, version, and type: {item}")
        configured.add(
            (
                str(item.get("vulnerability", "")),
                str(package["name"]),
                str(package["version"]),
                str(package["type"]),
            )
        )

    if configured != documented:
        missing_docs = sorted(configured - documented)
        missing_config = sorted(documented - configured)
        raise SystemExit(
            f"scanner suppression mismatch: undocumented={missing_docs}, "
            f"unconfigured={missing_config}"
        )


if __name__ == "__main__":
    main()
