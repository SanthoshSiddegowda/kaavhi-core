from pydantic import BaseModel
from typing import List, Optional

class ReviewRequest(BaseModel):
    diff: str

class ReviewComment(BaseModel):
    id: str
    type: str  # e.g., 'issue', 'suggestion'
    severity: str  # e.g., 'high', 'medium', 'low'
    line: int
    code: str
    comment: str
    suggestion: str
    confidence: int
    filePath: str

class ReviewResponse(BaseModel):
    comments: List[ReviewComment] 