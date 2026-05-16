"""LLM provider abstraction. Currently routes to Claude Sonnet 4.5 via emergentintegrations.
Designed to allow future swap to GPT/Gemini/local models without changing callers."""
import base64
import json
import logging
import uuid
import re
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
from ...core.config import settings

logger = logging.getLogger(__name__)

PRESCRIPTION_EXTRACT_SYS = """You are a medical prescription OCR specialist for WyshCare healthcare platform.
Analyze the prescription image and extract structured data. Be conservative — only extract what you can read with reasonable confidence.

Return STRICTLY valid JSON with this exact schema:
{
  "doctor_name": "string or null",
  "clinic_name": "string or null",
  "patient_name": "string or null",
  "prescription_date": "YYYY-MM-DD or null",
  "diagnosis": "string or null",
  "medications": [
    {
      "name": "string",
      "dosage": "string (e.g. 500mg)",
      "frequency": "string (e.g. twice daily, BD, TDS)",
      "duration": "string (e.g. 5 days, 2 weeks)",
      "instructions": "string or null",
      "confidence": 0.0-1.0
    }
  ],
  "notes": "string or null",
  "overall_confidence": 0.0-1.0
}

Output ONLY the JSON object. No markdown fences. No commentary."""


async def extract_prescription(image_bytes: bytes) -> dict:
    """Send image to Claude Sonnet 4.5 vision and return structured prescription JSON."""
    if not settings.EMERGENT_LLM_KEY:
        raise RuntimeError("EMERGENT_LLM_KEY missing")

    chat = LlmChat(
        api_key=settings.EMERGENT_LLM_KEY,
        session_id=f"ocr-{uuid.uuid4().hex[:12]}",
        system_message=PRESCRIPTION_EXTRACT_SYS,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    img_b64 = base64.b64encode(image_bytes).decode()
    msg = UserMessage(
        text="Extract structured prescription data from this image. Return only JSON.",
        file_contents=[ImageContent(image_base64=img_b64)],
    )
    raw = await chat.send_message(msg)
    return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    # Strip code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Find first JSON object
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        logger.error(f"Failed parsing LLM JSON: {raw[:500]}")
        return {"medications": [], "overall_confidence": 0.0, "_raw": raw[:500]}
