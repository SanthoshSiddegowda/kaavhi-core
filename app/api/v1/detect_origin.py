from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from app.models.detect_origin import DetectOriginRequest, DetectOriginResponse
from app.services.detect_origin_service import detect_origin

router = APIRouter(prefix="/detect-origin", tags=["detect-origin"])


@router.post("", response_model=DetectOriginResponse, status_code=status.HTTP_200_OK)
async def detect(req: DetectOriginRequest) -> DetectOriginResponse:
    """
    Best-effort regression-origin detection. Given a bug + the fix diff + candidate
    commits, returns the most likely introducing commit/author with a confidence score.
    """
    result = await detect_origin(req)
    try:
        return DetectOriginResponse.model_validate(result)
    except ValidationError as e:
        raise HTTPException(status_code=500, detail=f"Invalid detect-origin response: {e}") from e
