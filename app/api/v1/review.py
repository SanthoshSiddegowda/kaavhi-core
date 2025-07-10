from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from app.models.review import ReviewRequest, ReviewResponse, ReviewComment
from app.services.review_service import review_diff_with_gemini
from typing import List

router = APIRouter(prefix="/review", tags=["review"])

@router.post("/diff", response_model=ReviewResponse, status_code=status.HTTP_200_OK)
async def review_diff(
    file: UploadFile = File(...)
) -> ReviewResponse:
    """
    Accepts a diff file and returns review comments.
    """
    diff = (await file.read()).decode("utf-8")
    review_json = await review_diff_with_gemini(diff)
    try:
        comments = [ReviewComment(**c) for c in review_json.get("comments", [])]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Invalid response from Gemini: {e}")
    return ReviewResponse(comments=comments) 