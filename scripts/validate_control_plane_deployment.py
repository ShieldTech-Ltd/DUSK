#!/usr/bin/env python3
"""Fail closed on unsafe control-plane Helm values and promotion records."""

from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path
from typing import Any

import yaml

PLACEHOLDER_HOSTS = {"control-plane.example.invalid", "identity.example.invalid"}
DOCUMENTATION_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
)


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _validate_production_endpoints(config: dict[str, Any], ingress: dict[str, Any]) -> None:
    for field in ("oidcIssuer", "oidcJwksUri"):
        value = str(config.get(field, ""))
        if any(host in value for host in PLACEHOLDER_HOSTS) or not value.startswith("https://"):
            raise ValueError(f"production {field} must be a real HTTPS endpoint")
    if not ingress.get("enabled") or not ingress.get("tlsSecretName"):
        raise ValueError("production ingress must enable TLS with an existing secret")


def validate_values(path: Path, *, production: bool) -> None:
    values = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "values")
    image = _mapping(values.get("image"), "image")
    digest = image.get("digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:") or len(digest) != 71:
        raise ValueError("image.digest must be an exact SHA-256 digest")
    if production and digest == "sha256:" + ("0" * 64):
        raise ValueError("production cannot use the placeholder image digest")

    config = _mapping(values.get("config"), "config")
    ingress = _mapping(values.get("ingress"), "ingress")
    if production:
        _validate_production_endpoints(config, ingress)

    policy = _mapping(values.get("networkPolicy"), "networkPolicy")
    if not policy.get("enabled"):
        raise ValueError("NetworkPolicy cannot be disabled")
    egress = policy.get("approvedEgress")
    if not isinstance(egress, list) or not egress:
        raise ValueError("at least one approved egress destination is required")
    for item in egress:
        destination = _mapping(item, "approvedEgress item")
        network = ipaddress.ip_network(str(destination.get("cidr")), strict=False)
        if production and any(network.subnet_of(block) for block in DOCUMENTATION_NETWORKS):
            raise ValueError("production egress cannot use documentation-only networks")


def validate_promotion(path: Path) -> None:
    record = _mapping(json.loads(path.read_text(encoding="utf-8")), "promotion record")
    digest = record.get("image_digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:") or len(digest) != 71:
        raise ValueError("promotion image_digest must be an exact SHA-256 digest")
    environments = record.get("environments")
    if not isinstance(environments, list) or [item.get("name") for item in environments] != [
        "development",
        "staging",
        "production",
    ]:
        raise ValueError("promotion must proceed development, staging, then production")
    for item in environments:
        environment = _mapping(item, "environment evidence")
        if environment.get("image_digest") != digest:
            raise ValueError("every environment must use the same image digest")
        checks = ("signature_verified", "sbom_verified", "provenance_verified")
        if not all(environment.get(key) is True for key in checks):
            raise ValueError("signature, SBOM, and provenance verification are mandatory")
        if not environment.get("evidence_uri") or not environment.get("approved_at"):
            raise ValueError("immutable evidence and approval timestamps are mandatory")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    values_parser = subparsers.add_parser("values")
    values_parser.add_argument("path", type=Path)
    values_parser.add_argument("--production", action="store_true")
    promotion_parser = subparsers.add_parser("promotion")
    promotion_parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "values":
        validate_values(args.path, production=args.production)
    else:
        validate_promotion(args.path)


if __name__ == "__main__":
    main()
