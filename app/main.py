import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from app.api.v1 import bugzilla, review
from app.middleware import CustomCORSMiddleware

app = FastAPI()

app.add_middleware(CustomCORSMiddleware)

app.include_router(review.router)
app.include_router(bugzilla.router)

class HealthResponse(BaseModel):
    status: str


class IpResponse(BaseModel):
    ip: str


@app.get("/", response_model=HealthResponse)
def read_root() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/ip", response_model=IpResponse)
async def ip() -> IpResponse:
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.ipify.org?format=json")
        response.raise_for_status()
        return IpResponse.model_validate(response.json())
