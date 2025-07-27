from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from mangum import Mangum
from app.api.v1 import review
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import re

app = FastAPI()

class CustomCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        origin = request.headers.get("origin")
        if origin:
            # Allow localhost for development
            if origin == "http://localhost:8080":
                response.headers["Access-Control-Allow-Origin"] = origin
            # Allow kaavhi.com and all its subdomains
            elif re.match(r"https?://(?:[a-zA-Z0-9-]+\.)*kaavhi\.com$", origin):
                response.headers["Access-Control-Allow-Origin"] = origin
            # Allow the main kaavhi.com domain
            elif origin == "https://kaavhi.com":
                response.headers["Access-Control-Allow-Origin"] = origin
        
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        
        return response

# Add custom CORS middleware
app.add_middleware(CustomCORSMiddleware)

app.include_router(review.router)

class HealthResponse(BaseModel):
    status: str

@app.get("/", response_model=HealthResponse)
def read_root() -> HealthResponse:
    return HealthResponse(status="ok")

handler = Mangum(app) 