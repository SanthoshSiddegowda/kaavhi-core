import re

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

_KAAVHI_ORIGIN = re.compile(r"^https?://(?:[a-zA-Z0-9-]+\.)*kaavhi\.com$")


class CustomCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        origin = request.headers.get("origin")
        if origin and (
            origin == "http://localhost:8080" or _KAAVHI_ORIGIN.match(origin)
        ):
            response.headers["Access-Control-Allow-Origin"] = origin

        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"

        return response
