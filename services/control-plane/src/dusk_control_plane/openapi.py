"""Deterministic OpenAPI rendering."""

from __future__ import annotations

import json

from dusk_control_plane.app import create_app
from dusk_control_plane.config import Environment, Settings
from dusk_control_plane.dependencies import AppContainer


def render_openapi() -> str:
    """Return stable, human-reviewable OpenAPI JSON."""
    settings = Settings(environment=Environment.TEST, api_docs_enabled=False)
    app = create_app(container=AppContainer.build(settings=settings))
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
