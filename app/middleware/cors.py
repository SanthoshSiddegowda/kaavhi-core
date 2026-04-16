import re

from fastapi import Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

_KAAVHI_ORIGIN = re.compile(r"^https?://(?:[a-zA-Z0-9-]+\.)*kaavhi\.com$")


class CustomCORSMiddleware(BaseHTTPMiddleware):
    @staticmethod
    def _is_allowed_origin(origin: str | None) -> bool:
        return bool(
            origin
            and (
                origin == "http://localhost:8080" or _KAAVHI_ORIGIN.match(origin)
            )
        )

    @staticmethod
    def _apply_cors_headers(request: Request, response: Response) -> Response:
        origin = request.headers.get("origin")
        if CustomCORSMiddleware._is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"

        request_headers = request.headers.get("access-control-request-headers")
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = (
            request_headers or "Authorization, Content-Type"
        )
        return response

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return self._apply_cors_headers(request, Response(status_code=204))

        response = await call_next(request)
        return self._apply_cors_headers(request, response)
