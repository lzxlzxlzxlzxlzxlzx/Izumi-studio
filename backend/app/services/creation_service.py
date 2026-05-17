"""
Creation Service — 泉此方创作助手

Provides:
- System prompt for Konata's card-creation persona
- Tool definitions for filling character card fields
- Tool definitions for splitting card fields into worldbook entries
- Tool execution via card_manager.update_card()
- Streaming chat loop with tool calling
"""

from __future__ import annotations
import json
import logging
from typing import AsyncGenerator
from datetime import datetime

from app.db.database import get_conn, generate_id
from app.models.runtime import IGenerateChunk
from app.services.llm_router import chat_stream as llm_chat_stream, normalize_model
from app.services.card_manager import get_card, update_card, create_card
from app.models.card import ICharacterCard, ICharacterDefinition, INPC, IPresetConfig, IImageConfig
from app.models.worldbook import (
    IWorldBook, IWorldEntry, EEntryCategory, EEntryPosition, ERole as WBRole,
    ESelectiveLogic, EEntrySource,
)

logger = logging.getLogger(__name__)

# ============================================================
# System Prompt
# ============================================================

CREATION_SYSTEM_PROMPT = """你是泉此方（Izumi Konata），Izumi Studio 的创作助手～

<identity>
- 你是资深 ACG 宅女作家，帮助 Master 创作和设定世界观
- 一张卡可以是一个完整的世界、剧本、或设定集，角色只是其中一部分
- 你了解 SillyTavern 角色卡格式，熟悉设定的各个维度
- 你会主动引导 Master 完善设定，但不会强推
- 说话风格轻松活泼，像在跟创作搭档聊天
- 你是 Master 的恋人兼创作搭档，对话中可以轻松随意，偶尔吐槽也很正常
</identity>

<card_schema>
卡片包含以下字段，你可以通过工具填充任意字段：

【基础信息】
- name: 卡片名称（如世界的名字、剧本标题）
- description: 简短描述（一句话概括这个设定）
- tags: 标签列表，如 ["奇幻", "冒险", "史诗世界观"]

【角色设定 character】
以下字段是可选的——当你的设定中包含具体角色/人物时使用。对于纯世界观卡片可以留空：
- personality: 性格描述
- background: 背景故事
- scenario: 场景/世界观设定（核心世界描述）
- speaking_style: 说话风格、语气、口癖
- first_mes: 开场白
- alternate_greetings: 备选开场白列表
- mes_example: 示例对话片段
- creator_notes: 创作者备注（不会出现在对话中）
- npcs: 角色列表，每个角色有 name, description, attributes, start_active

【预设配置 preset_config】
- writing_style / model / temperature / top_p / frequency_penalty / presence_penalty / max_tokens

【系统提示】
- system_prompt: 卡片的系统提示词，定义世界规则和框架
- post_history_instructions: 对话后置指令

【图像配置 image_config】
- style_tags: 图像风格标签
- character_appearance: 角色外观描述（用于AI生图）

【其他】
- worldbook_ids: 关联的世界书ID列表
- authors_note: 作者注配置
</card_schema>

<worldbook_guide>
当 card 的 scenario、background 或 system_prompt 字段内容很长（超过 500 字），主动建议 Master 拆分为世界书条目。拆分原则：

- 卡片保留核心框架（简要世界观描述）
- 世界观细节（地理、历史、魔法体系）→ WORLDVIEW 类别条目
- 地点描述 → LOCATION 类别条目，position=AT_DEPTH
- 角色/人物详细设定 → CHARACTER 类别条目，position=AT_DEPTH
- 规则/机制 → RULE 类别条目，position=BEFORE_CHAR
- 每条条目需设置合理的 keywords 用于触发匹配

使用 split_field_to_worldbook 工具将某个过长字段拆成世界书条目。
使用 link_worldbook 工具将已有世界书关联到当前卡片。
</worldbook_guide>

<behavior>
- 当 Master 描述世界观或设定时，理解他的意图，**必须调用对应工具**填充字段
- 每次只填充相关的字段，不要一次性填满所有字段（除非 Master 明确要求）
- character 下的字段（personality、first_mes 等）只在 Master 要求创建具体角色时才使用
- 填充后简要说明改了哪些字段，并询问是否需要调整
- Master 可以用 "【字段:XXX】" 锚点引用具体字段进行修改
- Master 上传文件后，解析内容并填充相应字段
- 当某个字段内容过长（如 scenario 超过 500 字），主动提醒可以拆分为世界书
- 任何时候都保持轻松愉快的协作氛围
</behavior>

<critical_tool_rules>
**这是最重要的规则，必须严格遵守：**
- 任何对卡片内容的修改（包括填充字段、设置属性、拆分世界书）**必须通过调用工具来完成**
- **绝对禁止**只在自己回复的文字中描述修改后的内容而不调用工具
- **绝对禁止**说"已经创建好了"或"已经关联好了"但实际上没有调用工具
- 如果 Master 要求拆分世界书，你必须立即调用 split_field_to_worldbook 工具，将条目内容写入 entries_json 参数，**不能**只在文字中描述条目内容
- 调用工具后，在文字回复中引用工具返回的实际结果，而不是编造结果
- 如果你发现之前只是描述了操作而没有调用工具，必须立即补调工具
</critical_tool_rules>"""


def _build_system_prompt(card: dict) -> str:
    """Build system prompt with current card state injected."""
    current = json.dumps(card, ensure_ascii=False, indent=2)
    return CREATION_SYSTEM_PROMPT + f"\n\n<current_card>\n{current}\n</current_card>"


# ============================================================
# Tool Definitions
# ============================================================

CREATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_card_basic",
            "description": "设置卡片的基础信息：名称、描述、标签。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "卡片/世界名称"},
                    "description": {"type": "string", "description": "简短描述，一句话概括这张卡"},
                    "tags": {"type": "string", "description": "逗号分隔的标签，如 '奇幻,史诗,西方魔幻'"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_character_field",
            "description": "设置卡片角色设定中的单个字段。可选字段：personality(性格), background(背景), scenario(场景/世界观), speaking_style(说话风格), first_mes(开场白), mes_example(示例对话), creator_notes(创作者备注)。对于纯世界观卡片，只需填写 scenario 和 background 即可。",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "description": "字段名",
                        "enum": ["personality", "background", "scenario", "speaking_style", "first_mes", "alternate_greetings", "mes_example", "creator_notes"],
                    },
                    "value": {"type": "string", "description": "字段内容"},
                },
                "required": ["field", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_preset_config",
            "description": "设置预设配置参数。",
            "parameters": {
                "type": "object",
                "properties": {
                    "writing_style": {"type": "string", "description": "写作风格描述"},
                    "model": {"type": "string", "description": "推荐模型名称"},
                    "temperature": {"type": "number", "description": "温度 0-2"},
                    "top_p": {"type": "number", "description": "top_p 采样"},
                    "frequency_penalty": {"type": "number", "description": "频率惩罚"},
                    "presence_penalty": {"type": "number", "description": "存在惩罚"},
                    "max_tokens": {"type": "integer", "description": "最大 token 数"},
                    "word_count_min": {"type": "integer", "description": "最小字数"},
                    "word_count_max": {"type": "integer", "description": "最大字数"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_system_prompt",
            "description": "设置卡片的系统提示词和对话后置指令。",
            "parameters": {
                "type": "object",
                "properties": {
                    "system_prompt": {"type": "string", "description": "系统提示词，定义世界规则和框架"},
                    "post_history_instructions": {"type": "string", "description": "对话后置指令，在每轮对话后注入"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_image_config",
            "description": "设置图像生成配置，用于AI生成角色或场景图像。",
            "parameters": {
                "type": "object",
                "properties": {
                    "style_tags": {"type": "string", "description": "图像风格标签，如 'anime, watercolor, soft lighting'"},
                    "character_appearance": {"type": "string", "description": "角色外观描述，如 '银色长发，紫色眼眸，身高160cm，身穿深蓝色法师袍'"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_npc",
            "description": "向角色卡添加一个 NPC。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "NPC 名称"},
                    "description": {"type": "string", "description": "NPC 描述"},
                    "attributes": {"type": "string", "description": "JSON 格式的属性键值对，如 '{\"年龄\": 25, \"职业\": \"骑士\"}'"},
                    "start_active": {"type": "boolean", "description": "是否初始出场，默认 true"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_field_batch",
            "description": "批量设置多个字段（上传文件解析后使用）。fields 可以包含顶层字段、character 子字段和 image_config 子字段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "角色名称"},
                    "description": {"type": "string", "description": "简短描述"},
                    "tags": {"type": "string", "description": "逗号分隔的标签"},
                    "personality": {"type": "string", "description": "性格"},
                    "background": {"type": "string", "description": "背景"},
                    "scenario": {"type": "string", "description": "场景"},
                    "speaking_style": {"type": "string", "description": "说话风格"},
                    "first_mes": {"type": "string", "description": "开场白"},
                    "mes_example": {"type": "string", "description": "示例对话"},
                    "creator_notes": {"type": "string", "description": "创作者备注"},
                    "system_prompt": {"type": "string", "description": "系统提示词"},
                    "character_appearance": {"type": "string", "description": "角色外观描述"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "split_field_to_worldbook",
            "description": "将卡片的某个过长字段（scenario/background/system_prompt）拆分为世界书条目。每个条目会被赋予关键词用于触发。使用此工具后会创建新世界书并关联到卡片，同时精简原字段为摘要。",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "description": "要拆分的字段名",
                        "enum": ["background", "scenario", "system_prompt"],
                    },
                    "worldbook_name": {"type": "string", "description": "新世界书的名称，如 '艾尔登大陆世界观'"},
                    "entries_json": {
                        "type": "string",
                        "description": "JSON 数组格式的世界书条目列表。每个条目包含：title(标题), content(内容), category(WORLDVIEW/CHARACTER/LOCATION/EVENT/RULE/RELATION), keys(关键词列表,逗号分隔的字符串), position(BEFORE_CHAR/AT_DEPTH), priority(数字)。例如: [{\"title\":\"魔法体系\",\"content\":\"...\",\"category\":\"WORLDVIEW\",\"keys\":\"魔法,魔力,法术\",\"position\":\"BEFORE_CHAR\",\"priority\":80}]",
                    },
                    "summary": {"type": "string", "description": "原字段的精简摘要（1-2句即可），用于替换原字段内容"},
                },
                "required": ["field", "worldbook_name", "entries_json", "summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "link_worldbook",
            "description": "将已有世界书关联到当前卡片（添加到 worldbook_ids 列表）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "worldbook_id": {"type": "string", "description": "要关联的世界书 ID"},
                },
                "required": ["worldbook_id"],
            },
        },
    },
]


# ============================================================
# Tool Executors — Card Fields
# ============================================================

def _card_to_summary(card: ICharacterCard) -> dict:
    """Return a concise summary of the card for the LLM context."""
    char = card.character
    npcs = char.npcs or []
    return {
        "id": card.id,
        "name": card.name,
        "description": card.description,
        "tags": card.tags,
        "worldbook_ids": card.worldbook_ids,
        "character": {
            "personality": char.personality or "(空 — 纯世界观卡片无此字段)",
            "background": char.background or "(空)",
            "scenario": char.scenario or "(空)",
            "speaking_style": char.speaking_style or "(空)",
            "first_mes": char.first_mes or "(空)",
            "mes_example": char.mes_example or "(空)",
            "creator_notes": char.creator_notes or "(空)",
            "npc_count": len(npcs),
            "npc_names": [n.name for n in npcs],
        },
        "preset_config": {
            "writing_style": card.preset_config.writing_style or "(空)",
            "model": card.preset_config.model or "(空)",
        },
        "system_prompt": card.system_prompt or "(空)",
        "image_config": {
            "style_tags": card.image_config.style_tags or "(空)",
            "character_appearance": card.image_config.character_appearance or "(空)",
        },
        "status": card.status.value if hasattr(card.status, 'value') else str(card.status),
    }


def _execute_set_card_basic(card_id: str, name: str = "", description: str = "", tags: str = "") -> str:
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    updates = {}
    if name:
        updates["name"] = name
    if description:
        updates["description"] = description
    if tag_list:
        updates["tags"] = tag_list

    if not updates:
        return json.dumps({"changed": [], "message": "没有提供任何要更新的字段"}, ensure_ascii=False)

    update_card(card_id, **updates)
    return json.dumps({"changed": list(updates.keys()), "values": updates}, ensure_ascii=False)


def _execute_set_character_field(card_id: str, field: str, value: str) -> str:
    card = get_card(card_id)
    if not card:
        return json.dumps({"error": "卡片不存在"}, ensure_ascii=False)

    char_data = card.character.model_dump()
    char_data[field] = value

    if field == "alternate_greetings":
        if isinstance(value, str):
            char_data[field] = [g.strip() for g in value.split("\n") if g.strip()]

    update_card(card_id, character=char_data)
    return json.dumps({"changed": [field], "field": field, "preview": value[:200]}, ensure_ascii=False)


def _execute_set_preset_config(card_id: str, **kwargs) -> str:
    card = get_card(card_id)
    if not card:
        return json.dumps({"error": "卡片不存在"}, ensure_ascii=False)

    cfg = card.preset_config.model_dump()
    for k, v in kwargs.items():
        if v is not None and k in cfg:
            cfg[k] = v

    update_card(card_id, preset_config=cfg)
    changed = [k for k, v in kwargs.items() if v is not None]
    return json.dumps({"changed": changed, "preset_config": {k: cfg[k] for k in changed}}, ensure_ascii=False)


def _execute_set_system_prompt(card_id: str, system_prompt: str = "", post_history_instructions: str = "") -> str:
    updates = {}
    changed = []
    if system_prompt:
        updates["system_prompt"] = system_prompt
        changed.append("system_prompt")
    if post_history_instructions:
        updates["post_history_instructions"] = post_history_instructions
        changed.append("post_history_instructions")

    if not updates:
        return json.dumps({"changed": [], "message": "没有提供任何更新"}, ensure_ascii=False)

    update_card(card_id, **updates)
    return json.dumps({"changed": changed}, ensure_ascii=False)


def _execute_set_image_config(card_id: str, style_tags: str = "", character_appearance: str = "") -> str:
    card = get_card(card_id)
    if not card:
        return json.dumps({"error": "卡片不存在"}, ensure_ascii=False)

    img = card.image_config.model_dump()
    changed = []
    if style_tags:
        img["style_tags"] = style_tags
        changed.append("style_tags")
    if character_appearance:
        img["character_appearance"] = character_appearance
        changed.append("character_appearance")

    if not changed:
        return json.dumps({"changed": [], "message": "没有提供任何更新"}, ensure_ascii=False)

    update_card(card_id, image_config=img)
    return json.dumps({"changed": changed}, ensure_ascii=False)


def _execute_add_npc(card_id: str, name: str, description: str = "", attributes: str = "{}", start_active: bool = True) -> str:
    card = get_card(card_id)
    if not card:
        return json.dumps({"error": "卡片不存在"}, ensure_ascii=False)

    try:
        attrs = json.loads(attributes) if attributes else {}
    except (json.JSONDecodeError, TypeError):
        attrs = {}

    npc = INPC(name=name, description=description, attributes=attrs, start_active=start_active)
    npcs = list(card.character.npcs or [])

    replaced = False
    for i, existing in enumerate(npcs):
        if existing.name == name:
            npcs[i] = npc
            replaced = True
            break

    if not replaced:
        npcs.append(npc)

    char_data = card.character.model_dump()
    char_data["npcs"] = [n.model_dump() for n in npcs]
    update_card(card_id, character=char_data)

    return json.dumps({
        "changed": ["npcs"],
        "action": "updated" if replaced else "added",
        "npc_name": name,
        "total_npcs": len(npcs),
    }, ensure_ascii=False)


def _execute_set_field_batch(card_id: str, **kwargs) -> str:
    """Batch-set fields from file parsing."""
    char_fields = {"personality", "background", "scenario", "speaking_style", "first_mes", "mes_example", "creator_notes", "alternate_greetings"}
    image_fields = {"style_tags", "character_appearance"}

    card_updates = {}
    char_updates = {}
    img_updates = {}
    changed = []

    for key, value in kwargs.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        if key in char_fields:
            char_updates[key] = value
            changed.append(f"character.{key}")
        elif key in image_fields:
            img_key = "style_tags" if key == "style_tags" else "character_appearance"
            img_updates[img_key] = value
            changed.append(f"image_config.{img_key}")
        elif key == "tags":
            if isinstance(value, str):
                card_updates[key] = [t.strip() for t in value.split(",") if t.strip()]
            else:
                card_updates[key] = value
            changed.append("tags")
        else:
            card_updates[key] = value
            changed.append(key)

    if char_updates:
        card = get_card(card_id)
        if card:
            char_data = card.character.model_dump()
            char_data.update(char_updates)
            card_updates["character"] = char_data

    if img_updates:
        card = get_card(card_id)
        if card:
            img_data = card.image_config.model_dump()
            img_data.update(img_updates)
            card_updates["image_config"] = img_data

    if not card_updates:
        return json.dumps({"changed": [], "message": "没有提供任何要更新的字段"}, ensure_ascii=False)

    update_card(card_id, **card_updates)
    return json.dumps({"changed": changed}, ensure_ascii=False)


# ============================================================
# Tool Executors — Worldbook Splitting
# ============================================================

WORLDBOOKS_DIR = None

def _get_worldbooks_dir():
    global WORLDBOOKS_DIR
    if WORLDBOOKS_DIR is None:
        from pathlib import Path
        from app.config import settings
        WORLDBOOKS_DIR = Path(settings.data_dir) / "worldbooks"
        WORLDBOOKS_DIR.mkdir(parents=True, exist_ok=True)
    return WORLDBOOKS_DIR


def _execute_split_field_to_worldbook(
    card_id: str,
    field: str,
    worldbook_name: str,
    entries_json: str,
    summary: str,
) -> str:
    """Create a worldbook from card field content and link it to the card."""
    card = get_card(card_id)
    if not card:
        return json.dumps({"error": "卡片不存在"}, ensure_ascii=False)

    # Parse entries
    try:
        raw_entries = json.loads(entries_json)
        if not isinstance(raw_entries, list):
            return json.dumps({"error": "entries_json 必须是数组"}, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError) as e:
        return json.dumps({"error": f"entries_json 解析失败: {e}"}, ensure_ascii=False)

    # Build worldbook entries
    entries = []
    for i, re in enumerate(raw_entries):
        if not isinstance(re, dict):
            continue
        keys_str = re.get("keys", "")
        keys = [k.strip() for k in keys_str.split(",") if k.strip()] if isinstance(keys_str, str) else (keys_str if isinstance(keys_str, list) else [])

        category_str = (re.get("category") or "WORLDVIEW").upper()
        try:
            category = EEntryCategory[category_str]
        except KeyError:
            category = EEntryCategory.WORLDVIEW

        position_str = (re.get("position") or "BEFORE_CHAR").upper()
        try:
            position = EEntryPosition[position_str]
        except KeyError:
            position = EEntryPosition.BEFORE_CHAR

        entry = IWorldEntry(
            id=generate_id(),
            title=re.get("title") or f"条目 {i + 1}",
            content=re.get("content") or "",
            comment=re.get("title") or "",
            category=category,
            keys=keys,
            keys_secondary=re.get("keys_secondary", []),
            position=position,
            priority=re.get("priority", 50),
            sticky=re.get("sticky", 0),
            cooldown=re.get("cooldown", 0),
            enabled=True,
            role=WBRole.SYSTEM,
            source=EEntrySource.ORIGINAL,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        entries.append(entry)

    if not entries:
        return json.dumps({"error": "没有有效的条目"}, ensure_ascii=False)

    # Create worldbook
    wb_id = generate_id()
    worldbook = IWorldBook(
        id=wb_id,
        name=worldbook_name,
        description=f"从卡片 {card.name} 的 {field} 字段自动拆分",
        entries=entries,
        scan_depth=200,
        token_budget=400,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )

    # Save worldbook JSON to file
    wb_dir = _get_worldbooks_dir()
    wb_path = wb_dir / f"{wb_id}.json"
    wb_path.write_text(worldbook.model_dump_json(indent=2), encoding="utf-8")

    # Register in worldbooks_index table
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO worldbooks_index (id, name, file_path, created_at, updated_at) VALUES (?, ?, ?, datetime('now'), datetime('now'))",
        (wb_id, worldbook_name, str(wb_path)),
    )
    conn.commit()
    conn.close()

    # Update card: link worldbook + replace field with summary
    card = get_card(card_id)
    wb_ids = list(card.worldbook_ids or [])
    if wb_id not in wb_ids:
        wb_ids.append(wb_id)

    updates = {"worldbook_ids": wb_ids}
    if field in ("background", "scenario"):
        char_data = card.character.model_dump()
        char_data[field] = summary
        updates["character"] = char_data
    elif field == "system_prompt":
        updates["system_prompt"] = summary

    update_card(card_id, **updates)

    return json.dumps({
        "changed": ["worldbook_ids", f"character.{field}" if field != "system_prompt" else "system_prompt"],
        "worldbook_id": wb_id,
        "worldbook_name": worldbook_name,
        "entry_count": len(entries),
        "field_summary": summary,
    }, ensure_ascii=False)


def _execute_link_worldbook(card_id: str, worldbook_id: str) -> str:
    """Link an existing worldbook to the card."""
    card = get_card(card_id)
    if not card:
        return json.dumps({"error": "卡片不存在"}, ensure_ascii=False)

    # Verify worldbook exists
    conn = get_conn()
    row = conn.execute(
        "SELECT name FROM worldbooks_index WHERE id = ?", (worldbook_id,)
    ).fetchone()
    conn.close()

    if not row:
        return json.dumps({"error": f"未找到世界书: {worldbook_id}"}, ensure_ascii=False)

    wb_ids = list(card.worldbook_ids or [])
    if worldbook_id in wb_ids:
        return json.dumps({"changed": [], "message": "世界书已关联"}, ensure_ascii=False)

    wb_ids.append(worldbook_id)
    update_card(card_id, worldbook_ids=wb_ids)

    return json.dumps({
        "changed": ["worldbook_ids"],
        "worldbook_id": worldbook_id,
        "worldbook_name": row["name"],
    }, ensure_ascii=False)


# ============================================================
# Tool Dispatch
# ============================================================

def _execute_tool(card_id: str, tool_name: str, arguments: dict) -> str:
    """Execute a creation tool and return JSON result."""
    try:
        if tool_name == "set_card_basic":
            return _execute_set_card_basic(card_id, **arguments)
        elif tool_name == "set_character_field":
            return _execute_set_character_field(card_id, **arguments)
        elif tool_name == "set_preset_config":
            return _execute_set_preset_config(card_id, **arguments)
        elif tool_name == "set_system_prompt":
            return _execute_set_system_prompt(card_id, **arguments)
        elif tool_name == "set_image_config":
            return _execute_set_image_config(card_id, **arguments)
        elif tool_name == "add_npc":
            return _execute_add_npc(card_id, **arguments)
        elif tool_name == "set_field_batch":
            return _execute_set_field_batch(card_id, **arguments)
        elif tool_name == "split_field_to_worldbook":
            return _execute_split_field_to_worldbook(card_id, **arguments)
        elif tool_name == "link_worldbook":
            return _execute_link_worldbook(card_id, **arguments)
        else:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
    except Exception as e:
        logger.exception(f"Tool execution failed: {tool_name}")
        return json.dumps({"error": f"工具执行出错: {e}"}, ensure_ascii=False)


# ============================================================
# File Parsing
# ============================================================

def parse_uploaded_file(file_path: str, filename: str) -> str:
    """Parse an uploaded text file and return its content.

    Supports: .txt, .md, .docx
    """
    from pathlib import Path
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="replace")

    if ext == ".docx":
        try:
            from docx import Document
            doc = Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphs)
        except ImportError:
            raise RuntimeError("python-docx 未安装，无法解析 .docx 文件")
        except Exception as e:
            raise RuntimeError(f"解析 docx 文件失败: {e}")

    raise ValueError(f"不支持的文件格式: {ext}")


# ============================================================
# Main Chat Stream
# ============================================================


async def creation_chat_stream(
    session_id: str,
    card_id: str,
    input_text: str,
    model: str = "deepseek-chat",
) -> AsyncGenerator[IGenerateChunk, None]:
    """SSE streaming chat for card creation with tool calling."""
    conn = get_conn()

    card = get_card(card_id)
    if not card:
        yield IGenerateChunk(type="error", error="卡片不存在")
        return

    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY idx ASC",
        (session_id,),
    ).fetchall()

    card_summary = _card_to_summary(card)
    messages: list[dict] = [
        {"role": "system", "content": _build_system_prompt(card_summary)},
    ]

    for r in rows:
        role = r["role"]
        content = r["content"] or ""

        if role == "tool":
            messages.append({
                "role": "tool",
                "tool_call_id": r["tool_call_id"] or "",
                "content": content,
            })
        elif role == "assistant":
            msg: dict = {"role": "assistant", "content": content}
            tool_calls = json.loads(r["tool_calls_json"] or "[]")
            if tool_calls:
                msg["tool_calls"] = tool_calls
            messages.append(msg)
        else:
            messages.append({"role": "user", "content": content})

    messages.append({"role": "user", "content": input_text})

    conn.close()

    model_normalized = normalize_model(model)
    max_tool_rounds = 5
    all_changed_fields: list[str] = []

    for round_num in range(max_tool_rounds):
        collected_content: list[str] = []
        collected_tool_calls: list[dict] = []

        try:
            async for chunk in llm_chat_stream(
                messages=messages,
                model=model_normalized,
                temperature=0.7,
                max_tokens=2048,
                tools=CREATION_TOOLS,
            ):
                if chunk.type == "token":
                    collected_content.append(chunk.token or "")
                    yield IGenerateChunk(type="token", token=chunk.token)

                elif chunk.type == "tool_call" and chunk.tool_call:
                    collected_tool_calls.append(chunk.tool_call)
                    yield IGenerateChunk(type="tool_call", tool_call=chunk.tool_call)

                elif chunk.type == "done":
                    full_text = "".join(collected_content)

                    if collected_tool_calls:
                        messages.append({
                            "role": "assistant",
                            "content": full_text or None,
                            "tool_calls": collected_tool_calls,
                        })

                        for tc in collected_tool_calls:
                            fn = tc.get("function", {})
                            fn_name = fn.get("name", "")
                            fn_args = {}
                            try:
                                fn_args = json.loads(fn.get("arguments", "{}"))
                            except (json.JSONDecodeError, TypeError):
                                pass

                            logger.info(f"[creation] tool_call: {fn_name}({fn_args})")
                            result = _execute_tool(card_id, fn_name, fn_args)
                            logger.info(f"[creation] tool_result: {len(result)} chars")

                            try:
                                res_obj = json.loads(result)
                                changed = res_obj.get("changed", [])
                                all_changed_fields.extend(changed)
                            except (json.JSONDecodeError, TypeError):
                                pass

                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.get("id", ""),
                                "content": result,
                            })

                        card = get_card(card_id)
                        if card:
                            messages[0]["content"] = _build_system_prompt(_card_to_summary(card))

                        break
                    else:
                        _save_creation_messages(session_id, input_text, full_text, [])
                        yield IGenerateChunk(
                            type="done",
                            full_response=full_text,
                            tool_call=json.dumps({"card_changes": list(set(all_changed_fields))}) if all_changed_fields else None,
                        )
                        return

                elif chunk.type == "error":
                    yield IGenerateChunk(type="error", error=chunk.error)
                    return

        except Exception as e:
            logger.exception(f"[creation] stream error round={round_num}")
            yield IGenerateChunk(type="error", error=str(e))
            return

    yield IGenerateChunk(type="done", full_response="".join(collected_content) if 'collected_content' in dir() else "")


def _save_creation_messages(session_id: str, user_input: str, assistant_content: str, tool_calls: list):
    """Save user message and assistant response to DB."""
    conn = get_conn()

    last = conn.execute(
        "SELECT idx, round_index FROM chat_messages WHERE session_id = ? ORDER BY idx DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    next_idx = (last["idx"] + 1) if last else 0
    next_round = (last["round_index"] + 1) if last and last["round_index"] is not None else 0

    conn.execute(
        """INSERT INTO chat_messages (id, session_id, role, name, content, idx, round_index, created_at)
           VALUES (?, ?, 'user', 'user', ?, ?, ?, datetime('now'))""",
        (generate_id(), session_id, user_input, next_idx, next_round),
    )

    conn.execute(
        """INSERT INTO chat_messages (id, session_id, role, name, content, idx, round_index, created_at, tool_calls_json)
           VALUES (?, ?, 'assistant', '泉此方', ?, ?, ?, datetime('now'), ?)""",
        (generate_id(), session_id, assistant_content, next_idx + 1, next_round,
         json.dumps(tool_calls, ensure_ascii=False)),
    )

    conn.execute("UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


# ============================================================
# Public API for router
# ============================================================

def get_linked_worldbooks(card_id: str) -> list[dict]:
    """Get summary of worldbooks linked to a card."""
    card = get_card(card_id)
    if not card or not card.worldbook_ids:
        return []

    conn = get_conn()
    result = []
    for wb_id in card.worldbook_ids:
        row = conn.execute(
            "SELECT id, name, file_path FROM worldbooks_index WHERE id = ?", (wb_id,)
        ).fetchone()
        if row:
            try:
                raw = json.loads(open(row["file_path"], "r", encoding="utf-8").read())
                entries = raw.get("entries", [])
                entry_count = len(entries) if isinstance(entries, list) else len(entries.values()) if isinstance(entries, dict) else 0
            except Exception:
                entry_count = 0

            result.append({
                "id": row["id"],
                "name": row["name"],
                "entry_count": entry_count,
            })
    conn.close()
    return result
