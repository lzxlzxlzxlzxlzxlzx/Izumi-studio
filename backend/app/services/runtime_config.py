"""Per-deployment LLM API config stored in data/local_config.json (not committed)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "local_config.json"

_KEYS = (
    "API_KEY",
    "API_URL",
    "DASHSCOPE_API_KEY",
    "DASHSCOPE_API_URL",
)


def _read_file() -> dict[str, str]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {k: str(v).strip() for k, v in raw.items() if k in _KEYS and v}


def get_value(key: str, env_fallback: str = "") -> str:
    stored = _read_file().get(key, "")
    if stored:
        return stored
    import os
    return os.getenv(key, env_fallback)


def get_public_status() -> dict[str, Any]:
    data = _read_file()
    import os
    deepseek_key = data.get("API_KEY") or os.getenv("API_KEY", "")
    dashscope_key = data.get("DASHSCOPE_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
    return {
        "deepseek_configured": bool(deepseek_key),
        "dashscope_configured": bool(dashscope_key),
        "llm_configured": bool(deepseek_key),
        "api_url": data.get("API_URL") or os.getenv("API_URL", "https://api.deepseek.com/v1/chat/completions"),
        "dashscope_api_url": data.get("DASHSCOPE_API_URL")
        or os.getenv("DASHSCOPE_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "source": "local_config" if data.get("API_KEY") else ("env" if deepseek_key else "none"),
    }


def save_config(payload: dict[str, str]) -> dict[str, Any]:
    current = _read_file()
    for key in _KEYS:
        if key not in payload:
            continue
        value = (payload[key] or "").strip()
        if value:
            current[key] = value
        elif key in current:
            del current[key]
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return get_public_status()
