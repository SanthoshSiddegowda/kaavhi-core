import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app

client = TestClient(app)

@pytest.mark.asyncio
@patch("app.api.v1.review.review_diff_with_gemini", new_callable=AsyncMock)
async def test_review_diff_success(mock_review_diff_with_gemini):
    """
    Tests the /review/diff endpoint for a successful response.
    Mocks the Gemini API call to ensure the test is fast and independent of external services.
    """
    # Arrange: Configure the mock to return a sample JSON response
    mock_review_diff_with_gemini.return_value = {
        "comments": [
            {
                "id": "1",
                "type": "suggestion",
                "severity": "low",
                "line": 1,
                "code": "const a = 1;",
                "comment": "This is a test comment.",
                "suggestion": "const a = 2;",
                "confidence": 95,
                "filePath": "test.js",
            }
        ],
        "summary": {
            "overview": (
                "This change updates a number in test.js—probably to match new expected output."
            ),
            "keyChanges": [
                "Updates literal in `test.js` from `1` to `2`",
            ],
            "focus": [
                "Confirm the new value matches intended behavior and any related assertions.",
            ],
        },
    }

    # Act: Call the API endpoint (multipart file, matching production usage)
    diff_text = "--- a/test.js\n+++ b/test.js\n-const a = 1;\n+const a = 2;"
    response = client.post(
        "/review/diff",
        files={"file": ("changes.diff", diff_text.encode("utf-8"), "text/plain")},
    )

    # Assert: Check the response
    assert response.status_code == 200
    response_data = response.json()
    assert "comments" in response_data
    assert len(response_data["comments"]) == 1
    assert response_data["comments"][0]["id"] == "1"
    assert response_data["comments"][0]["comment"] == "This is a test comment."
    assert "summary" in response_data
    assert response_data["summary"]["overview"].startswith("This change updates")
    assert response_data["summary"]["keyChanges"] == [
        "Updates literal in `test.js` from `1` to `2`",
    ]
    assert response_data["summary"]["focus"] == [
        "Confirm the new value matches intended behavior and any related assertions.",
    ]
