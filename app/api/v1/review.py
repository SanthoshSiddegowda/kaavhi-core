from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import ValidationError

from app.models.review import ReviewResponse
from app.services.review_service import review_diff_with_gemini

router = APIRouter(prefix="/review", tags=["review"])


@router.post("/diff", response_model=ReviewResponse, status_code=status.HTTP_200_OK)
async def review_diff(file: UploadFile = File(...)) -> ReviewResponse:
    """
    Accepts a diff file and returns ``summary`` (overview + keyChanges) and line-level ``comments``.
    """
    diff = (await file.read()).decode("utf-8")
    review_json = await review_diff_with_gemini(diff)
    try:
        return ReviewResponse.model_validate(review_json)
    except ValidationError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid response from Gemini: {e}",
        ) from e
