import os
from google import genai
import json
import re
from app.config.app import settings

# The client is initialized here using the key from the centralized settings.
# Pydantic automatically validates that the key exists.
client = genai.Client(api_key=settings.GEMINI_API_KEY)

async def review_with_gemini(diff: str) -> str:
    """
    Uses Gemini 2.5 Pro to review the provided diff and returns the review comments as a JSON string.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    def sync_call():
        prompt = (
            "AI Code Reviewer Prompt for Kaavhi.com\n\n"
            "You're an AI code reviewer helping developers write better, safer, and cleaner code. Your job is to look at the code changes (diff) below and leave helpful review comments, just like a thoughtful human reviewer would.\n\n"
            "### What to do:\n"
            "1. **Read the Diff:** Go through the code  changes carefully. Look for potential bugs, security issues, slow code, unclear logic, bad practices, or style problems.\n\n"
            "2. **Find the File Path:** Each change will include file paths like `--- a/path/to/file` and `+++ b/path/to/file`. Use the `+++` (new file) path in your output.\n\n"
            "3. **Leave Comments in JSON Format:** Your response should be a single JSON object with a 'comments' array. Each comment should follow the structure below. The 'suggestion' field must contain only a raw code snippet.\n\n"
            "---\n\n"
            "### Comment Format (Schema)\n\n"
            "Each comment in the 'comments' array should follow this structure:\n\n"
            "* id: A unique string like '1', '2', etc.\n"
            "* type: 'issue' if it's a problem or 'suggestion' if it's an improvement.\n"
            "* severity: One of 'high', 'medium', or 'low' based on how serious the issue is.\n"
            "* line: The line number (from the + side of the diff) where the issue appears.\n"
            "* code: The exact line or block of code you're commenting on.\n"
            "* comment: A short, clear explanation of the issue or suggestion.\n"
            "* suggestion: strictly only code snippet (no explanation or wrapping)\n"
            "* confidence: A number (0–100) showing how sure you are about your comment.\n"
            "* filePath: The path of the changed file (from the +++ line in the diff).\n\n"
            "---\n\n"
            "### Example Output\n\n"
            "{\n  \"comments\": [\n    {\n      \"id\": \"1\",\n      \"type\": \"issue\",\n      \"severity\": \"high\",\n      \"line\": 428,\n      \"code\": \"$response = json_decode( $this->httpPost('salemansalesreturns/updateSaleReturnStatus'), true );\",\n      \"comment\": \"This code is forwarding a request but seems to skip access control checks. That might let unauthenticated users trigger it.\",\n      \"suggestion\": \"if (!is_authorized_user()) {\\n  return new CakeResponse(array('body' => json_encode(['Result' => false, 'Reason' => 'Unauthorized'])));\\n}\",\n      \"confidence\": 95,\n      \"filePath\": \"app/Controller/SalesreturnsController.php\"\n    },\n    {\n      \"id\": \"2\",\n      \"type\": \"suggestion\",\n      \"severity\": \"low\",\n      \"line\": 422,\n      \"code\": \"public function updateSaleReturnStatus( $responsetype = 'json' )\",\n      \"comment\": \"The 'responsetype' parameter is not used in the function. It can be removed to simplify the code.\",\n      \"suggestion\": \"public function updateSaleReturnStatus()\",\n      \"confidence\": 90,\n      \"filePath\": \"app/Controller/SalesreturnsController.php\"\n    }\n  ]\n}\n\n"
            "---\n\n"
            "Paste your code diff below to get started:\n\n"
            f"{diff}\n"
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        text = response.text.strip()
        # Remove any code block markers (```json, ```code, or ```) from the start and end
        text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
        text = re.sub(r'```$', '', text)
        print(text)
        # Try to parse the response as JSON
        try:
            return json.loads(text)
        except Exception:
            return {"comments": []}
    return await loop.run_in_executor(None, sync_call) 