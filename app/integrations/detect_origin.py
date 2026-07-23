import json
from typing import Any

from google.genai import types

from app.config.app import settings
from app.integrations.gemini import client as gemini_client
from app.integrations.nvidia import _client as nvidia_client
from app.integrations.detect_origin_prompt import INSTRUCTIONS, JSON_CONTRACT, build_context
from app.models.detect_origin import DetectOriginRequest, DetectOriginResponse

_GEMINI_MODEL = "gemini-3.5-flash-lite"


async def detect_with_gemini(req: DetectOriginRequest) -> dict[str, Any]:
    prompt = f"{INSTRUCTIONS}\n\n{build_context(req)}"
    response = await gemini_client.aio.models.generate_content(
        model=_GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=DetectOriginResponse,
        ),
    )
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, DetectOriginResponse):
        return parsed.model_dump()
    if isinstance(parsed, dict):
        return DetectOriginResponse.model_validate(parsed).model_dump()
    text = (response.text or "").strip()
    return DetectOriginResponse.model_validate_json(text).model_dump()


async def detect_with_nvidia(req: DetectOriginRequest) -> dict[str, Any]:
    if not settings.NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY not configured")
    response = await nvidia_client.chat.completions.create(
        model=settings.NVIDIA_MODEL,
        messages=[
            {"role": "system", "content": f"{INSTRUCTIONS}\n\n{JSON_CONTRACT}"},
            {"role": "user", "content": build_context(req)},
        ],
        temperature=0.2,
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise ValueError("NVIDIA returned empty content")
    return DetectOriginResponse.model_validate(json.loads(content)).model_dump()
