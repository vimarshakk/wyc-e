from uuid import uuid4


def create_upload_reference(filename: str, content_type: str | None = None) -> dict:
    return {"object_id": str(uuid4()), "filename": filename, "content_type": content_type, "status": "PENDING_UPLOAD"}
