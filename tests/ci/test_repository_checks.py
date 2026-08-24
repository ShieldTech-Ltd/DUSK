from scripts.ci.repository_checks import check


def test_repository_integrity_policy() -> None:
    assert check() == []
