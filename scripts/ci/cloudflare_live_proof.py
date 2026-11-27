"""Finite, owned-only post-approval proof. Never configures or deploys resources."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, OpenerDirector, Request, build_opener

SCENARIOS = (
    "allow-replay",
    "altered-action",
    "wrong-tenant",
    "destination",
    "private",
    "login",
    "redirect",
    "policy",
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None


def validate_contract(contract: dict) -> None:
    if (
        contract.get("allowed_origins") != ["https://owned.example.test"]
        or contract.get("allowed_methods") not in (["GET"], ["GET", "POST"])
        or contract.get("allowed_action_classes") != ["http.request"]
        or contract.get("tenant_id") != "owned-tenant"
        or contract.get("agent_id") != "owned-agent"
        or contract.get("environment") != "sandbox"
    ):
        raise ValueError("Only the owned fake sandbox contract is accepted")
    expiry = contract.get("expires_at_ms", 0)
    if not isinstance(expiry, int) or not 30_000 < expiry - int(time.time() * 1000) <= 3_600_000:
        raise ValueError("A fresh short-lived sandbox contract is required")
    for field in ("contract_id", "session_id"):
        uuid.UUID(contract[field])


def verified_count(status: int, value: dict) -> int:
    calls = value.get("calls")
    if status != 200 or type(calls) is not int or calls < 0:
        raise ValueError("Counter evidence unavailable")
    return calls


def verified_receipt(
    status: int,
    value: dict,
    expected: str,
    phase: str,
    identifier: str,
    seen: set[str],
    expected_code: str | None = None,
) -> dict:
    if status != (200 if expected == "ALLOW" else 403) or value.get("decision") != expected:
        raise ValueError("Unexpected enforcement decision")
    trace = value.get("audit_trace_id", "")
    uuid.UUID(trace)
    if value.get("request_id") != identifier or trace in seen:
        raise ValueError("Stale or reused receipt")
    if expected_code is not None and value.get("code") != expected_code:
        raise ValueError("Wrong denial mechanism")
    if value.get("audit_status") != "complete":
        raise ValueError("Audit completion is unproven")
    seen.add(trace)
    return {"phase": phase, "decision": expected, "audit_trace_id": trace}


def validate_scenario(contract: dict, scenario: str) -> None:
    validate_contract(contract)
    if scenario not in SCENARIOS:
        raise ValueError("Unknown scenario")
    if contract["allowed_methods"] != (["GET", "POST"] if scenario == "policy" else ["GET"]):
        raise ValueError("Contract methods must match the selected proof scenario")


def run_proof(contract: dict, scenario: str, exchange) -> dict:  # noqa: ANN001
    """Exchange is the fixed-endpoint HTTP adapter or an independent test double."""
    validate_scenario(contract, scenario)
    receipts = []
    seen: set[str] = set()
    action = {k: contract[k] for k in ("tenant_id", "agent_id", "environment", "session_id")}
    action.update(
        url="https://owned.example.test/allowed", method="GET", action_class="http.request", body=""
    )
    request_id = str(uuid.uuid4())

    def count() -> int:
        status, value = exchange("counter", "GET", "/__count", None)
        return verified_count(status, value)

    def call(
        phase: str,
        candidate: dict,
        expected: str,
        identifier: str = request_id,
        expected_delta: int = 0,
        expected_code: str | None = None,
    ) -> None:
        phase_before = count()
        status, value = exchange(
            "gateway",
            "POST",
            f"/v1/actions/{phase}",
            {"request_id": identifier, "action": candidate},
        )
        receipt = verified_receipt(status, value, expected, phase, identifier, seen, expected_code)
        delta = count() - phase_before
        if delta != expected_delta:
            raise ValueError("Per-phase downstream arrival count violates containment")
        receipts.append({**receipt, "downstream_arrivals": delta})

    before = count()
    initial = (
        {**action, "url": "https://owned.example.test/redirect"}
        if scenario == "redirect"
        else action
    )
    call("preflight", initial, "ALLOW")  # Proves the supplied session is initially usable.
    expected_calls = 0
    if scenario == "policy":
        # In scope but deliberately unsupported by native policy. This must
        # exercise policy denial rather than a method/origin scope rejection.
        denied = {**action, "method": "POST", "body": '{"fake":true}'}
        call("preflight", denied, "DENY", str(uuid.uuid4()))
        call("execute", denied, "DENY", str(uuid.uuid4()), expected_code="policy_denied")
    elif scenario in ("allow-replay", "login"):
        call("execute", action, "ALLOW", expected_delta=1)
        expected_calls = 1
        if scenario == "allow-replay":
            call("execute", action, "DENY")
        else:
            call(
                "execute",
                {**action, "method": "POST", "url": "https://owned.example.test/login"},
                "DENY",
                str(uuid.uuid4()),
            )
            call("preflight", action, "DENY", str(uuid.uuid4()))
    elif scenario == "redirect":
        call("execute", initial, "DENY", expected_delta=1)
        expected_calls = 1  # Approved fake service redirects; no outside service is contacted.
        call("preflight", action, "DENY", str(uuid.uuid4()))
    else:
        changes = {
            "altered-action": {"url": "https://owned.example.test/changed"},
            "wrong-tenant": {"tenant_id": "wrong-tenant"},
            "destination": {"url": "https://outside.example.test/allowed"},
            "private": {"url": "https://169.254.169.254/metadata"},
        }
        call("execute", {**action, **changes[scenario]}, "DENY")
        if scenario != "altered-action":
            call("preflight", action, "DENY", str(uuid.uuid4()))
    after = count()
    if after - before != expected_calls:
        raise ValueError("Downstream arrival count violates containment")
    return {
        "passed": True,
        "scenario": scenario,
        "downstream_arrivals": after - before,
        "receipts": receipts,
        "evidence": "remote-http-and-counter-only",
    }


def verify_ingress(
    opener: OpenerDirector, hosts: dict[str, str], accepted: tuple[int, ...] = (302, 403)
) -> dict[str, int]:
    statuses = {}
    for role, path in (("gateway", "/v1/actions/preflight"), ("counter", "/__count")):
        request = Request(hosts[role] + path, method="GET")  # noqa: S310 - fixed HTTPS owned endpoints
        try:
            response = opener.open(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            # No credentials, cookies or redirect following in this probe.
            if response.status not in accepted:
                raise ValueError("Unauthenticated ingress is not protected")
            statuses[role] = response.status
    return statuses


def proof_endpoints(
    account_subdomain: str | None, private_invoker_url: str | None
) -> tuple[dict[str, str], dict[str, str], tuple[int, ...]]:
    if private_invoker_url:
        if not re.fullmatch(r"http://127\.0\.0\.1:[1-9][0-9]{1,4}", private_invoker_url):
            raise ValueError("Private invoker must use an explicit loopback URL and port")
        return (
            {
                "gateway": private_invoker_url + "/gateway",
                "counter": private_invoker_url + "/target",
            },
            {"X-Dusk-Invoker-Token": os.environ["DUSK_INVOKER_TOKEN"]},
            (401,),
        )
    if not account_subdomain or not re.fullmatch(
        r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", account_subdomain
    ):
        raise ValueError("Invalid approved account subdomain")
    return (
        {
            role: f"https://{worker}.{account_subdomain}.workers.dev"
            for role, worker in (
                ("gateway", "dusk-scope-sandbox"),
                ("counter", "dusk-owned-sandbox-target"),
            )
        },
        {
            "CF-Access-Client-Id": os.environ["CF_ACCESS_CLIENT_ID"],
            "CF-Access-Client-Secret": os.environ["CF_ACCESS_CLIENT_SECRET"],
        },
        (302, 403),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    endpoints = parser.add_mutually_exclusive_group(required=True)
    endpoints.add_argument("--account-subdomain")
    endpoints.add_argument("--private-invoker-url")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--scenario", choices=SCENARIOS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new evidence path for every run")
    hosts, access, accepted_ingress = proof_endpoints(
        args.account_subdomain, args.private_invoker_url
    )
    token = os.environ["DUSK_GATEWAY_TOKEN"]
    if not token or not all(access.values()):
        raise ValueError("Nonempty sandbox authentication is required")
    opener = build_opener(NoRedirect())
    ingress_status = verify_ingress(opener, hosts, accepted_ingress)
    timings = []

    def exchange(role: str, method: str, path: str, value: dict | None) -> tuple[int, dict]:
        headers = {**access, "Content-Type": "application/json"}
        if role == "gateway":
            headers["Authorization"] = f"Bearer {token}"
        request = Request(  # noqa: S310 - hosts and paths are fixed HTTPS owned Worker endpoints
            hosts[role] + path,
            method=method,
            headers=headers,
            data=None if value is None else json.dumps(value).encode(),
        )
        start = time.monotonic()
        try:
            response = opener.open(request, timeout=10)  # noqa: S310 - fixed HTTPS owned Worker origins
        except HTTPError as error:
            response = error
        with response:
            payload = response.read(65_537)
            if len(payload) > 65_536:
                raise ValueError("Response exceeds evidence limit")
            body = json.loads(payload)
            if not isinstance(body, dict):
                raise ValueError("Invalid evidence response")
            timings.append(round((time.monotonic() - start) * 1000, 2))
            return response.status, body

    report = run_proof(json.loads(args.contract.read_text()), args.scenario, exchange)
    report["request_latency_ms"] = timings
    report["unauthenticated_ingress_status"] = ingress_status
    with args.output.open("x", encoding="utf-8") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    print("Owned scenario completed; redacted report written")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Do not echo HTTP bodies, request envelopes, credential values or URLs.
        raise SystemExit("Proof failed; do not promote this candidate") from None
