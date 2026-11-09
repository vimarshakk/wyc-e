from typing import Any


async def extract_medical_document(text: str) -> dict[str, Any]:
    """Return a reviewable extraction envelope; never writes directly to an EMR."""
    return {"status": "REVIEW_REQUIRED", "source_text_length": len(text), "fields": {}, "warnings": ["Human review required before clinical use"]}
