from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from app.models.review import ReviewRequest, ReviewResponse, ReviewComment
from app.services.review_service import review_diff_with_gemini
from typing import List

router = APIRouter(prefix="/review", tags=["review"])

@router.post("/diff", response_model=ReviewResponse, status_code=status.HTTP_200_OK)
async def review_diff(
    request: ReviewRequest
) -> ReviewResponse:
    """
    Accepts a diff as a string and returns review comments.
    """
    review_json = await review_diff_with_gemini(request.diff)
    try:
        comments = [ReviewComment(**c) for c in review_json.get("comments", [])]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Invalid response from Gemini: {e}")
    return ReviewResponse(comments=comments) 