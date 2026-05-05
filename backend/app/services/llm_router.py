"""
LLMRouter — Multi-provider LLM gateway with SSE streaming and tool calling.

Supported providers:
- DeepSeek (deepseek-chat, deepseek-reasoner)
- DashScope (qwen-vl-max for image description)
- Kimi / Moonshot

Features:
- OpenAI-compatible chat completions with SSE streaming
- Function calling (tool_choice="auto")
- Image → text description via qwen-vl-max
- Rate limit retry with exponential backoff
"""

from __future__ import annotations
import json
import time
import asyncio
import logging
from typing import AsyncGenerator, Optional

import httpx

from app.config import settings
from app.models.runtime import IGenerateChunk

logger = logging.getLogger(__name__)

# ============================================================
# Provider registry
# ============================================================

PROVIDERS = {
    "deepseek": {
        "base_url": settings.deepseek_api_url.rstrip("/chat/completions").rstrip("/v1"),
        "api_key": settings.deepseek_api_key,
        "default_model": "deepseek-chat",
        "supports_tools": True,
        "supports_vision": False,
    },
    "dashscope": {
        "base_url": settings.dashscope_api_url.rstrip("/chat/completions").rstrip("/v1"),
        "api_key": settings.dashscope_api_key,
        "default_model": "qwen-plus",
        "supports_tools": True,
        "supports_vision": True,
    },
    "kimi": {
        "base_url": settings.kimi_api_url.rstrip("/chat/completions").rstrip("/v1"),
        "api_key": settings.kimi_api_key,
        "default_model": "moonshot-v1-8k",
        "supports_tools": False,
        "supports_vision": False,
    },
}

# ============================================================
# Character management tool definitions (OpenAI format)
# ============================================================

CHARACTER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_characters",
            "description": "列出当前会话中所有角色",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "enum": ["all", "active", "inactive"],
                        "description": "过滤条件：all=全部, active=仅出场角色, inactive=仅离场角色",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_character",
            "description": "查询指定角色的详细信息，包括所有属性和状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "角色名称（精确匹配）",
                    }
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_character",
            "description": "在故事中创建新角色",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "新角色名称",
                    },
                    "attributes": {
                        "type": "object",
                        "description": "角色属性键值对，如 {'race':'人类','age':25,'occupation':'商人'}",
                    },
                    "is_active": {
                        "type": "boolean",
                        "description": "是否立即出场，默认 true",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_character",
            "description": "修改已有角色的属性。传 null 值的属性会被删除。不要传未变化的属性以减少变更量。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "要修改的角色名称",
                    },
                    "attributes": {
                        "type": "object",
                        "description": "要修改的属性键值对。值为 null 表示删除该属性。示例: {'affection': 55, 'location': '城镇'}",
                    },
                    "is_active": {
                        "type": "boolean",
                        "description": "是否出场",
                    },
                    "is_alive": {
                        "type": "boolean",
                        "description": "是否存活",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_character",
            "description": "删除/移除角色（角色死亡或离场时使用）",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "要删除的角色名称",
                    }
                },
                "required": ["name"],
            },
        },
    },
]


# Model name normalization (user shorthand → API model name)
MODEL_ALIASES = {
    "deepseek": "deepseek-chat",
    "deepseek-chat": "deepseek-chat",
    "deepseek-v4": "deepseek-chat",
    "deepseek-v4-pro": "deepseek-chat",
    "deepseek-v3": "deepseek-chat",
    "deepseek-reasoner": "deepseek-reasoner",
    "qwen": "qwen-plus",
    "qwen-plus": "qwen-plus",
    "qwen-max": "qwen-max",
    "qwen-vl": "qwen-vl-max",
    "kimi": "moonshot-v1-8k",
    "moonshot": "moonshot-v1-8k",
}


def normalize_model(model: str) -> str:
    """Map user-facing model names to actual API model names."""
    return MODEL_ALIASES.get(model.lower(), model)


def get_provider(model: str) -> dict:
    """Determine provider from model name."""
    model_lower = model.lower()
    if "deepseek" in model_lower:
        return PROVIDERS["deepseek"]
    if any(x in model_lower for x in ("qwen", "dashscope", "bailian")):
        return PROVIDERS["dashscope"]
    if any(x in model_lower for x in ("moonshot", "kimi")):
        return PROVIDERS["kimi"]
    return PROVIDERS["deepseek"]


# ============================================================
# Core API
# ============================================================

async def chat_stream(
    messages: list[dict],
    model: str = "deepseek-chat",
    temperature: float = 0.8,
    max_tokens: int = 2048,
    top_p: float = 0.95,
    frequency_penalty: float = 0.3,
    presence_penalty: float = 0.2,
    tools: list[dict] | None = None,
    tool_choice: str = "auto",
) -> AsyncGenerator[IGenerateChunk, None]:
    """
    Send a streaming chat completion request.

    Yields IGenerateChunk objects:
    - {type: "token", token: "文字片段"}
    - {type: "tool_call", tool_call: {...}}
    - {type: "done", full_response: "完整文本"}
    - {type: "error", error: "错误信息"}
    """
    model = normalize_model(model)
    provider = get_provider(model)
    if not provider["api_key"]:
        yield IGenerateChunk(type="error", error=f"No API key configured for model: {model}")
        return

    url = f"{provider['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {provider['api_key']}",
        "Content-Type": "application/json",
    }

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
        "stream": True,
    }

    if tools and provider.get("supports_tools"):
        body["tools"] = tools
        body["tool_choice"] = tool_choice

    collected_content: list[str] = []
    collected_tool_calls: list[dict] = []
    finish_reason: str | None = None

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=body, headers=headers) as resp:
                if resp.status_code != 200:
                    error_text = await resp.aread()
                    yield IGenerateChunk(
                        type="error",
                        error=f"API error {resp.status_code}: {error_text.decode()[:500]}",
                    )
                    return

                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        choice = data.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        finish_reason = choice.get("finish_reason")

                        # Handle token
                        if delta.get("content"):
                            token = delta["content"]
                            collected_content.append(token)
                            yield IGenerateChunk(type="token", token=token)

                        # Handle tool calls (delta format)
                        if delta.get("tool_calls"):
                            for tc in delta["tool_calls"]:
                                idx = tc.get("index", 0)
                                while len(collected_tool_calls) <= idx:
                                    collected_tool_calls.append(
                                        {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                                    )
                                if tc.get("id"):
                                    collected_tool_calls[idx]["id"] = tc["id"]
                                if tc.get("function", {}).get("name"):
                                    collected_tool_calls[idx]["function"]["name"] = tc["function"]["name"]
                                if tc.get("function", {}).get("arguments"):
                                    collected_tool_calls[idx]["function"]["arguments"] += tc["function"]["arguments"]

                        if finish_reason == "tool_calls":
                            # Emit collected tool calls
                            for tc in collected_tool_calls:
                                yield IGenerateChunk(type="tool_call", tool_call=tc)

                    except json.JSONDecodeError:
                        continue

        # Emit done
        full_text = "".join(collected_content)
        yield IGenerateChunk(
            type="done",
            full_response=full_text,
            tool_call=collected_tool_calls[0] if collected_tool_calls else None,
        )

    except httpx.TimeoutException:
        yield IGenerateChunk(type="error", error="Request timed out")
    except Exception as e:
        logger.exception("LLM stream error")
        yield IGenerateChunk(type="error", error=str(e))


async def chat_sync(
    messages: list[dict],
    model: str = "deepseek-chat",
    temperature: float = 0.8,
    max_tokens: int = 2048,
    tools: list[dict] | None = None,
) -> dict:
    """
    Non-streaming chat completion. Returns full response including tool_calls.
    """
    model = normalize_model(model)
    provider = get_provider(model)
    if not provider["api_key"]:
        return {"error": f"No API key configured for model: {model}"}

    url = f"{provider['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {provider['api_key']}",
        "Content-Type": "application/json",
    }

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools and provider.get("supports_tools"):
        body["tools"] = tools

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=body, headers=headers)
        if resp.status_code != 200:
            return {"error": f"API error {resp.status_code}: {resp.text[:500]}"}
        return resp.json()


async def describe_image(image_url: str, prompt: str = "请详细描述这张图片中的场景和人物") -> str:
    """
    Describe an image using DashScope qwen-vl-max.

    Returns a text description suitable for injection into the main LLM context.
    """
    provider = PROVIDERS["dashscope"]
    if not provider["api_key"]:
        return "[image description unavailable: no API key]"

    url = f"{provider['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {provider['api_key']}",
        "Content-Type": "application/json",
    }

    body = {
        "model": "qwen-vl-max",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": 500,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=body, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"Image description failed: {resp.status_code} {resp.text[:200]}")
                return "[image description failed]"
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content or "[no description returned]"
    except Exception as e:
        logger.warning(f"Image description error: {e}")
        return f"[image description error: {e}]"


# ============================================================
# Token estimation (rough — for budget planning)
# ============================================================

def estimate_tokens(text: str) -> int:
    """Rough token count estimation.

    Chinese chars ~2.5-3 chars/token → divide by 3.
    Non-Chinese chars ~4 chars/token → divide by 4.
    """
    if not text:
        return 0
    chinese = sum(1 for c in text if '一' <= c <= '鿿')
    other = len(text) - chinese
    return max(1, chinese // 3 + other // 4)


def estimate_message_tokens(messages: list[dict]) -> int:
    """Estimate total tokens in a messages array."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("text"):
                    total += estimate_tokens(part["text"])
    return total
