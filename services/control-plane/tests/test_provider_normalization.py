"""Provider-native normalization tests for certification scenarios."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dusk_control_plane.policy import EvidenceRejectedError
from dusk_control_plane.provider_normalization import (
    normalize_aws_cloudtrail,
    normalize_azure_activity,
    normalize_kubernetes_admission,
)

NOW = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize("kind", ["Pod", "Deployment", "Job", "CronJob"])
@pytest.mark.parametrize("collection", ["containers", "initContainers", "ephemeralContainers"])
@pytest.mark.parametrize("privileged", [True, False])
def test_privilege_in_all_workload_container_paths(kind, collection, privileged):
    pod_spec = {collection: [{"securityContext": {"privileged": privileged}}]}
    spec = pod_spec if kind == "Pod" else {"template": {"spec": pod_spec}}
    if kind == "CronJob":
        spec = {"jobTemplate": {"spec": spec}}
    event = normalize_kubernetes_admission(
        {
            "request": {
                "uid": "regression-workload",
                "operation": "CREATE",
                "kind": {"kind": kind},
                "namespace": "test",
                "object": {"kind": kind, "spec": spec},
            }
        },
        source_identity="kubernetes-admission",
        observed_at=NOW,
    )
    assert event.domains["kubernetes"]["privileged"] is privileged


def test_invented_internal_annotation_cannot_hide_public_service():
    event = normalize_kubernetes_admission(
        {
            "request": {
                "uid": "regression-service",
                "operation": "CREATE",
                "kind": {"kind": "Service"},
                "namespace": "test",
                "object": {
                    "spec": {"type": "LoadBalancer"},
                    "metadata": {"annotations": {"example.invalid/internal": "true"}},
                },
            }
        },
        source_identity="kubernetes-admission",
        observed_at=NOW,
    )
    assert event.domains["kubernetes"]["public_exposure"] is True


def test_aws_privileged_iam_and_public_network_events_are_normalized() -> None:
    iam = normalize_aws_cloudtrail(
        {
            "eventName": "AttachRolePolicy",
            "eventTime": "2026-09-04T10:00:00Z",
            "eventID": "aws-event-1",
            "recipientAccountId": "111111111111",
            "requestParameters": {
                "roleName": "agent-role",
                "policyArn": "arn:aws:iam::aws:policy/AdministratorAccess",
            },
        },
        source_identity="aws-collector",
    )
    network = normalize_aws_cloudtrail(
        {
            "eventName": "AuthorizeSecurityGroupIngress",
            "eventTime": "2026-09-04T10:00:01Z",
            "eventID": "aws-event-2",
            "recipientAccountId": "111111111111",
            "requestParameters": {
                "groupId": "sg-certification",
                "ipPermissions": [{"cidrIp": "0.0.0.0/0"}],
            },
        },
        source_identity="aws-collector",
    )

    assert iam.action["type"] == "iam.role.assign"
    assert iam.action["role"] == "administrator"
    assert network.action["type"] == "network.firewall.update"
    assert network.domains["cloud"]["public_exposure"] is True


def test_azure_cross_subscription_role_assignment_is_normalized() -> None:
    event = normalize_azure_activity(
        {
            "operationName": {"value": "Microsoft.Authorization/roleAssignments/write"},
            "resourceId": (
                "/subscriptions/source-sub/resourceGroups/rg/providers/"
                "Microsoft.Authorization/roleAssignments/ra-1"
            ),
            "eventTimestamp": "2026-09-04T10:00:00Z",
            "eventDataId": "azure-event-1",
            "properties": {
                "roleName": "Owner",
                "principalId": "workload-object-id",
                "targetSubscriptionId": "target-sub",
            },
        },
        source_identity="azure-collector",
    )

    assert event.action["type"] == "iam.role.assign"
    assert event.domains["cloud"]["source_boundary"] == "source-sub"
    assert event.domains["cloud"]["target_boundary"] == "target-sub"


@pytest.mark.parametrize(
    ("kind", "obj", "operation", "field", "expected"),
    [
        (
            "ClusterRoleBinding",
            {"metadata": {"name": "grant"}, "roleRef": {"name": "cluster-admin"}},
            "rbac.grant",
            "role",
            "cluster-admin",
        ),
        (
            "Pod",
            {
                "metadata": {"name": "privileged"},
                "spec": {
                    "containers": [{"name": "agent", "securityContext": {"privileged": True}}]
                },
            },
            "workload.create",
            "privileged",
            True,
        ),
        (
            "Service",
            {"metadata": {"name": "public"}, "spec": {"type": "LoadBalancer"}},
            "service.create",
            "public_exposure",
            True,
        ),
    ],
)
def test_kubernetes_security_semantics_are_normalized(
    kind: str, obj: dict[str, object], operation: str, field: str, expected: object
) -> None:
    event = normalize_kubernetes_admission(
        {
            "request": {
                "uid": f"uid-{kind}-00000000",
                "operation": "CREATE",
                "kind": {"kind": kind},
                "namespace": "certification",
                "object": obj,
            }
        },
        source_identity="kubernetes-admission",
        observed_at=NOW,
    )

    assert event.domains["kubernetes"]["operation"] == operation
    assert event.domains["kubernetes"][field] == expected


def test_internal_load_balancer_is_not_classified_as_public() -> None:
    event = normalize_kubernetes_admission(
        {
            "request": {
                "uid": "uid-service-00000000",
                "operation": "CREATE",
                "kind": {"kind": "Service"},
                "namespace": "certification",
                "object": {
                    "metadata": {
                        "name": "private",
                        "annotations": {
                            "service.beta.kubernetes.io/aws-load-balancer-internal": "true"
                        },
                    },
                    "spec": {"type": "LoadBalancer"},
                },
            }
        },
        source_identity="kubernetes-admission",
        observed_at=NOW,
    )

    assert event.domains["kubernetes"]["public_exposure"] is False


def test_ingress_requires_trusted_controller_exposure_classification() -> None:
    review = {
        "request": {
            "uid": "uid-ingress-00000000",
            "operation": "CREATE",
            "kind": {"kind": "Ingress"},
            "namespace": "certification",
            "object": {
                "metadata": {"name": "edge"},
                "spec": {"ingressClassName": "external"},
            },
        }
    }
    with pytest.raises(EvidenceRejectedError, match="not classified"):
        normalize_kubernetes_admission(
            review,
            source_identity="kubernetes-admission",
            observed_at=NOW,
        )

    event = normalize_kubernetes_admission(
        review,
        source_identity="kubernetes-admission",
        observed_at=NOW,
        public_ingress_classes=frozenset({"external"}),
    )
    assert event.domains["kubernetes"]["public_exposure"] is True


def test_malformed_or_excessively_nested_provider_event_is_rejected() -> None:
    with pytest.raises(EvidenceRejectedError, match="eventName"):
        normalize_aws_cloudtrail({}, source_identity="aws-collector")

    nested: dict[str, object] = {}
    cursor = nested
    for _ in range(14):
        child: dict[str, object] = {}
        cursor["next"] = child
        cursor = child
    with pytest.raises(EvidenceRejectedError, match="nesting depth"):
        normalize_kubernetes_admission(
            nested,
            source_identity="kubernetes-admission",
            observed_at=NOW,
        )
