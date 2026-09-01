"""FastAPI application factory for the isolated production service."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from dusk_control_plane.audit import DurableEvaluationService
from dusk_control_plane.dependencies import AppContainer, DependencyProbe
from dusk_control_plane.errors import error_response, install_error_handlers
from dusk_control_plane.evaluations import (
    EvaluationRequest,
    EvaluationResponse,
    EvaluationUnavailableError,
)
from dusk_control_plane.identity import Principal, require_route_policy
from dusk_control_plane.models import (
    ComponentHealth,
    ErrorEnvelope,
    LivenessResponse,
    ReadinessResponse,
)
from dusk_control_plane.request_context import new_request_id, reset_request_id, set_request_id

REQUEST_ID_HEADER = "X-Request-ID"
logger = logging.getLogger(__name__)
_evaluation_authorization = require_route_policy("POST", "/v2/evaluations")


def _install_v2_routes(
    app: FastAPI,
    container: AppContainer,
    common_errors: dict[int | str, dict[str, Any]],
) -> None:
    @app.post(
        "/v2/evaluations",
        response_model=EvaluationResponse,
        tags=["evaluations"],
        responses={
            401: {"model": ErrorEnvelope},
            403: {"model": ErrorEnvelope},
            503: {"model": ErrorEnvelope},
            **common_errors,
        },
    )
    async def evaluate_action(
        body: EvaluationRequest,
        principal: Annotated[Principal, Depends(_evaluation_authorization)],
    ) -> EvaluationResponse:
        service = container.evaluation_service
        if service is None or not isinstance(service, DurableEvaluationService):
            raise EvaluationUnavailableError
        return await service.evaluate(body, principal)


async def _probe_component(probe: DependencyProbe, timeout_seconds: float) -> ComponentHealth:
    try:
        await asyncio.wait_for(probe.check(), timeout=timeout_seconds)
    except Exception:  # noqa: BLE001 - dependency detail must not cross the health boundary
        return ComponentHealth(name=probe.name, status="unavailable", critical=probe.critical)
    return ComponentHealth(name=probe.name, status="ready", critical=probe.critical)


def create_app(
    *,
    container: AppContainer | None = None,
    readiness_probes: Sequence[DependencyProbe] = (),
) -> FastAPI:
    """Construct an isolated application with explicit dependencies."""
    resolved = (
        container
        if container is not None
        else AppContainer.build(readiness_probes=readiness_probes)
    )
    settings = resolved.settings

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.started = True
        try:
            yield
        finally:
            if resolved.database is not None:
                await resolved.database.close()
            application.state.started = False

    docs_url = "/docs" if settings.api_docs_enabled else None
    openapi_url = "/openapi.json" if settings.api_docs_enabled else None
    app = FastAPI(
        title="DUSK Control Plane API",
        summary="Production security decision control plane",
        description=(
            "A separately deployed, multi-tenant service. The legacy Flask /v1/gate "
            "boundary is not part of this application."
        ),
        version=settings.service_version,
        docs_url=docs_url,
        redoc_url=None,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    app.state.container = resolved
    app.state.started = False
    install_error_handlers(app)

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = new_request_id()
        token = set_request_id(request_id)
        try:
            try:
                content_length = request.headers.get("content-length")
                if (
                    content_length is not None
                    and content_length.isdecimal()
                    and int(content_length) > settings.max_request_body_bytes
                ):
                    response: Response = error_response(
                        status_code=413,
                        code="REQUEST_TOO_LARGE",
                        message="Request body exceeds the configured limit",
                        retryable=False,
                    )
                else:
                    response = await call_next(request)
            except Exception:  # noqa: BLE001 - map unexpected failures to a safe boundary
                logger.error("unhandled control-plane request failure request_id=%s", request_id)
                response = error_response(
                    status_code=500,
                    code="INTERNAL_ERROR",
                    message="Internal service error",
                    retryable=True,
                )
            response.headers[REQUEST_ID_HEADER] = request_id
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
        finally:
            reset_request_id(token)

    common_errors: dict[int | str, dict[str, Any]] = {500: {"model": ErrorEnvelope}}

    @app.get(
        "/livez",
        response_model=LivenessResponse,
        tags=["operations"],
        responses=common_errors,
    )
    async def liveness() -> LivenessResponse:
        return LivenessResponse(
            status="live",
            service=settings.service_name,
            version=settings.service_version,
        )

    @app.get(
        "/readyz",
        response_model=ReadinessResponse,
        tags=["operations"],
        responses={
            503: {
                "model": ReadinessResponse,
                "description": "A critical dependency is unavailable",
            },
            **common_errors,
        },
    )
    async def readiness() -> Response | ReadinessResponse:
        timeout_seconds = settings.readiness_timeout_ms / 1000
        components = await asyncio.gather(
            *(_probe_component(probe, timeout_seconds) for probe in resolved.readiness_probes)
        )
        ready = bool(app.state.started) and not any(
            component.critical and component.status != "ready" for component in components
        )
        body = ReadinessResponse(
            status="ready" if ready else "not_ready",
            service=settings.service_name,
            version=settings.service_version,
            components=list(components),
        )
        if ready:
            return body
        return JSONResponse(status_code=503, content=body.model_dump(mode="json"))

    if settings.v2_enabled:
        _install_v2_routes(app, resolved, common_errors)

    return app
