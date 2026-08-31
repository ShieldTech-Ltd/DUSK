"""Committed OpenAPI artifact parity test."""

from __future__ import annotations

import json
from pathlib import Path

from dusk_control_plane.openapi import render_openapi


def test_committed_openapi_matches_application() -> None:
    contract = Path(__file__).resolve().parents[1] / "contracts" / "openapi.json"
    assert contract.read_text(encoding="utf-8") == render_openapi()


def test_v2_evaluation_contract_is_authenticated_and_has_no_tenant_input() -> None:
    schema = json.loads(render_openapi())
    operation = schema["paths"]["/v2/evaluations"]["post"]
    assert operation["security"] == [{"HTTPBearer": []}]
    request_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    request_name = request_ref.rsplit("/", 1)[1]
    request_schema = schema["components"]["schemas"][request_name]
    assert "tenant_id" not in request_schema["properties"]
    assert "principal_id" not in request_schema["properties"]
    response_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    response_name = response_ref.rsplit("/", 1)[1]
    response_fields = schema["components"]["schemas"][response_name]["properties"]
    assert {
        "policy_decision",
        "policy_pack_version",
        "matched_rules",
        "evidence_degraded",
        "reason_codes",
    } <= set(response_fields)
