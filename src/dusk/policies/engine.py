"""Load, validate, and evaluate deterministic agent-action policies."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum
from importlib.resources import files
from pathlib import Path

import yaml

_SEVERITIES = {"low", "medium", "high", "critical"}
_STATUSES = {"enforced", "planned"}
_OPERATORS = {"equals", "in", "contains", "exists", "not_equals", "not_true"}
_MISSING = object()
_RULE_FIELDS = {
    "id",
    "version",
    "title",
    "category",
    "severity",
    "decision",
    "status",
    "owner",
    "rationale",
    "frameworks",
    "match",
    "prerequisites",
    "tests",
}


class Decision(IntEnum):
    """Policy result ordered by enforcement priority."""

    ALLOW = 0
    REQUIRE_APPROVAL = 1
    DENY = 2


@dataclass(frozen=True)
class Condition:
    """One field comparison."""

    field: str
    operator: str
    value: object = None


@dataclass(frozen=True)
class Rule:
    """One validated deterministic policy rule."""

    id: str
    version: str
    title: str
    category: str
    severity: str
    decision: Decision
    status: str
    owner: str
    rationale: str
    frameworks: tuple[str, ...]
    conditions: tuple[Condition, ...]
    prerequisites: tuple[str, ...]
    tests: tuple[str, ...]


@dataclass(frozen=True)
class PolicyResult:
    """Aggregate policy decision and matched rules."""

    decision: Decision
    policy_version: str
    matched_rules: tuple[Rule, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision.name,
            "policy_version": self.policy_version,
            "matched_rules": [
                {
                    "id": rule.id,
                    "version": rule.version,
                    "title": rule.title,
                    "owner": rule.owner,
                    "severity": rule.severity,
                    "frameworks": list(rule.frameworks),
                    "reason": rule.rationale,
                }
                for rule in self.matched_rules
            ],
        }


@dataclass(frozen=True)
class PolicyPack:
    """One immutable, validated rule pack."""

    name: str
    version: str
    default_decision: Decision
    rules: tuple[Rule, ...]

    def evaluate(self, context: Mapping[str, object]) -> PolicyResult:
        matched = tuple(
            rule
            for rule in self.rules
            if rule.status == "enforced" and _matches(rule.conditions, context)
        )
        decision = max((rule.decision for rule in matched), default=self.default_decision)
        return PolicyResult(decision=decision, policy_version=self.version, matched_rules=matched)


def load_policy_pack(path: Path) -> PolicyPack:
    """Load and strictly validate a YAML policy pack."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _load_mapping(raw)


def load_enterprise_pack() -> PolicyPack:
    """Load the bundled enterprise-v1 policy pack."""
    resource = files("dusk.policies").joinpath("enterprise-v1.yaml")
    with resource.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return _load_mapping(raw)


def _load_mapping(raw: object) -> PolicyPack:
    if not isinstance(raw, dict):
        raise ValueError("policy pack must be a mapping")
    if set(raw) != {"name", "version", "default_decision", "rules"}:
        raise ValueError("policy pack has missing or unsupported fields")
    raw_rules = raw["rules"]
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError("policy pack rules must be a non-empty list")
    rules = tuple(_load_rule(item) for item in raw_rules)
    ids = [rule.id for rule in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("policy rule IDs must be unique")
    return PolicyPack(
        name=_required_text(raw, "name"),
        version=_required_text(raw, "version"),
        default_decision=_decision(raw["default_decision"]),
        rules=rules,
    )


def _load_rule(raw: object) -> Rule:
    if not isinstance(raw, dict) or set(raw) != _RULE_FIELDS:
        raise ValueError("rule has missing or unsupported fields")
    severity = _required_text(raw, "severity")
    status = _required_text(raw, "status")
    if severity not in _SEVERITIES:
        raise ValueError(f"invalid severity: {severity}")
    if status not in _STATUSES:
        raise ValueError(f"invalid status: {status}")
    conditions = _conditions(raw["match"])
    prerequisites = _text_tuple(raw["prerequisites"], "prerequisites")
    tests = _text_tuple(raw["tests"], "tests")
    if status == "enforced" and (not conditions or not tests):
        raise ValueError("enforced rules require conditions and tests")
    if status == "planned" and not prerequisites:
        raise ValueError("planned rules require prerequisites")
    rule_id = _required_text(raw, "id")
    version = _required_text(raw, "version")
    if re.fullmatch(r"DUSK-[A-Z]+-[0-9]{3}", rule_id) is None:
        raise ValueError(f"invalid rule ID: {rule_id}")
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
        raise ValueError(f"invalid rule version: {version}")
    return Rule(
        id=rule_id,
        version=version,
        title=_required_text(raw, "title"),
        category=_required_text(raw, "category"),
        severity=severity,
        decision=_decision(raw["decision"]),
        status=status,
        owner=_required_text(raw, "owner"),
        rationale=_required_text(raw, "rationale"),
        frameworks=_text_tuple(raw["frameworks"], "frameworks"),
        conditions=conditions,
        prerequisites=prerequisites,
        tests=tests,
    )


def _conditions(raw: object) -> tuple[Condition, ...]:
    if not isinstance(raw, list):
        raise ValueError("match must be a list")
    result: list[Condition] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"field", "operator", "value"}:
            raise ValueError("condition has missing or unsupported fields")
        operator = _required_text(item, "operator")
        if operator not in _OPERATORS:
            raise ValueError(f"invalid condition operator: {operator}")
        result.append(Condition(_required_text(item, "field"), operator, item["value"]))
    return tuple(result)


def _matches(conditions: tuple[Condition, ...], context: Mapping[str, object]) -> bool:
    return bool(conditions) and all(
        _compare(_resolve(context, item.field), item, context) for item in conditions
    )


def _resolve(context: Mapping[str, object], path: str) -> object:
    value: object = context
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return _MISSING
        value = value[part]
    return value


def _compare(actual: object, condition: Condition, context: Mapping[str, object]) -> bool:
    expected = condition.value
    if isinstance(expected, str) and expected.startswith("$"):
        expected = _resolve(context, expected[1:])
    if condition.operator == "exists":
        return (actual is not _MISSING) is bool(expected)
    if condition.operator == "equals":
        return actual == expected
    if condition.operator == "not_equals":
        return actual is not _MISSING and actual != expected
    if condition.operator == "not_true":
        return actual is not True
    if condition.operator == "contains":
        return isinstance(actual, (str, list, tuple, set)) and expected in actual
    if condition.operator == "in":
        return isinstance(expected, list) and actual in expected
    return False


def _decision(raw: object) -> Decision:
    if not isinstance(raw, str) or raw not in Decision.__members__:
        raise ValueError(f"invalid decision: {raw}")
    return Decision[raw]


def _required_text(raw: Mapping[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _text_tuple(raw: object, field: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or any(not isinstance(item, str) or not item for item in raw):
        raise ValueError(f"{field} must be a list of non-empty strings")
    return tuple(raw)
