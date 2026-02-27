"""
Model Routes
Fetch OpenRouter models and return GPT/Gemini only.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
import httpx

from src.core.settings import OPENROUTER_API_KEY, OPENROUTER_BASE_URL

router = APIRouter()


@router.get("/openrouter", summary="List OpenRouter GPT/Gemini models")
async def list_openrouter_models():
    base_url = (OPENROUTER_BASE_URL or "https://openrouter.ai/api/v1").rstrip("/")
    url = f"{base_url}/models"

    headers = {}
    if OPENROUTER_API_KEY:
        headers["Authorization"] = f"Bearer {OPENROUTER_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers=headers)
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="OpenRouter request failed")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="OpenRouter unreachable")

    payload = resp.json() if resp.content else {}
    items = payload.get("data", []) if isinstance(payload, dict) else []

    filtered = []
    for item in items:
        model_id = str(item.get("id", ""))
        name = str(item.get("name", model_id))
        model_id_lower = model_id.lower()
        if model_id_lower.startswith("openai/") and "gpt" in model_id_lower:
            filtered.append({"id": model_id, "name": name})
        elif model_id_lower.startswith("google/") and "gemini" in model_id_lower:
            filtered.append({"id": model_id, "name": name})

    filtered.sort(key=lambda m: m["name"].lower())
    return {"data": filtered}
