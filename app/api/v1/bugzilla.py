from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.integrations.bugzilla import fetch_regression_bugs

router = APIRouter(prefix="/bugzilla", tags=["bugzilla"])


class RegressionBugsRequest(BaseModel):
    version: str = Field(min_length=1, max_length=32)
    chfieldfrom: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    chfieldto: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


@router.post("/regression-bugs")
async def regression_bugs(body: RegressionBugsRequest) -> dict:
    try:
        return await fetch_regression_bugs(
            version=body.version,
            chfieldfrom=body.chfieldfrom,
            chfieldto=body.chfieldto,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Bugzilla regression query failed: {exc}",
        ) from exc
