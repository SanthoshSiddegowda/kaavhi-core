from fastapi import FastAPI
from pydantic import BaseModel
from mangum import Mangum
from app.api.v1 import review
from app.middleware import CustomCORSMiddleware

app = FastAPI()

# Add custom CORS middleware
app.add_middleware(CustomCORSMiddleware)

app.include_router(review.router)

class HealthResponse(BaseModel):
    status: str

@app.get("/", response_model=HealthResponse)
def read_root() -> HealthResponse:
    return HealthResponse(status="ok")

handler = Mangum(app)
