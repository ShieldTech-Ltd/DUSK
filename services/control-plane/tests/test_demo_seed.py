"""Public demo reset safety tests."""

from __future__ import annotations

import pytest

from dusk_control_plane.demo_seed import DEMO_TENANT_ID, validate_target


def test_demo_reset_accepts_only_the_dedicated_database() -> None:
    approved = "postgresql+asyncpg://dusk:secret@postgresql/dusk_public_demo"
    assert validate_target(approved, str(DEMO_TENANT_ID), "true") == approved

    with pytest.raises(ValueError, match="PUBLIC_DEMO_MODE"):
        validate_target(approved, str(DEMO_TENANT_ID), "false")
    with pytest.raises(ValueError, match="fixed demo tenant"):
        validate_target(approved, "wrong-tenant", "true")

    for unsafe in (
        "postgresql+asyncpg://dusk:secret@production/dusk_public_demo",
        "postgresql+asyncpg://dusk:secret@postgresql/customer_data",
        "sqlite+aiosqlite:///dusk_public_demo",
    ):
        with pytest.raises(ValueError, match="dedicated container database"):
            validate_target(unsafe, str(DEMO_TENANT_ID), "true")
