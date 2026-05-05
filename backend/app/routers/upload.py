"""
Image upload endpoint.

POST /api/upload/image  — upload an image, get Qwen-Plus description

Flow:
1. Save uploaded image to uploads_dir
2. Call Qwen-VL-Max to analyze the image → text description
3. Return the description (to be injected into user message) + image URL
"""

import base64
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.config import settings
from app.services.llm_router import describe_image

router = APIRouter()

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/image")
async def upload_image(file: UploadFile = File(...)):
    if file.content_type and file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported image type: {file.content_type}")

    raw = await file.read()
    if len(raw) > MAX_SIZE:
        raise HTTPException(400, "Image too large (max 10 MB)")

    # Save to disk
    ext = Path(file.filename or "image.png").suffix or ".png"
    filename = f"{uuid.uuid4().hex}{ext}"
    out_path = Path(settings.uploads_dir) / filename
    out_path.write_bytes(raw)

    # Build data URL for Qwen-VL
    mime = file.content_type or "image/png"
    data_url = f"data:{mime};base64,{base64.b64encode(raw).decode()}"

    # Analyze with Qwen-VL
    description = await describe_image(data_url)

    # Return description + image reference
    return {
        "ok": True,
        "filename": filename,
        "image_path": f"/uploads/{filename}",
        "description": description,
    }
