from __future__ import annotations

from time import perf_counter

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "hubfiscal_http_requests_total",
    "Total de requisições HTTP processadas pelo Hub Fiscal",
    labelnames=("method", "handler", "status"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "hubfiscal_http_request_duration_seconds",
    "Duração das requisições HTTP do Hub Fiscal em segundos",
    labelnames=("method", "handler"),
)


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return "unmatched"


def install_metrics(app: FastAPI) -> None:
    @app.middleware("http")
    async def prometheus_middleware(request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        started = perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            handler = _route_template(request)
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                handler=handler,
                status=str(status),
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=request.method,
                handler=handler,
            ).observe(perf_counter() - started)

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint() -> Response:
        return Response(
            content=generate_latest(),
            headers={"Content-Type": CONTENT_TYPE_LATEST},
        )
