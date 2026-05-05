"""
PresetRenderer — Compiles an IPreset into enriched system prompt content.

For ST-imported presets, extracts the key writing/narrative guidance from
enabled content prompts and produces a supplement string that enriches
the card-based system prompt without replacing the core character identity.
"""

from __future__ import annotations
from typing import Optional
import re

from app.models.preset import IPreset, IPresetPrompt, ERole
from app.models.card import ICharacterCard


# Prompt identifiers whose content contains ST macros to strip
_STRIP_MACROS = re.compile(r'\{\{(setvar|getvar)::[^}]*\}\}')


def _clean_content(content: str, user_name: str = "用户") -> str:
    """Remove ST macro invocations and wrapper tags from content."""
    content = _STRIP_MACROS.sub('', content)
    content = re.sub(r'\{\{//[^}]*\}\}', '', content)  # ST comments
    # Remove meta-dialogue lines BEFORE replacing Master→user_name,
    # so the patterns match the original "Konata:" and "Master:" prefixes
    content = re.sub(r'^(Konata|Master)[：:，,].*\n?', '', content, flags=re.MULTILINE)
    # Remove ST meta-conversation fluff lines
    fluff_patterns = [
        r'^OKOK，.*\n?', r'^好啦，.*\n?', r'^没问题！.*\n?', r'^带点矫情.*\n?',
        r'^又来到了.*\n?', r'^小此来啦.*\n?', r'^小此准备好啦.*\n?',
        r'^下面就是.*\n?', r'^最先看的.*\n?', r'^然后是.*\n?', r'^再之后.*\n?',
        r'^还有几点.*\n?', r'^OK，\s*\n?',
    ]
    for pat in fluff_patterns:
        content = re.sub(pat, '', content, flags=re.MULTILINE)
    # Replace ST placeholders (after meta-dialogue cleanup)
    content = content.replace("{{user}}", user_name)
    content = content.replace("<user>", user_name)
    content = content.replace("Master", user_name)  # ST uses "Master" to refer to the user
    # Remove structural XML tags (keep their content)
    for tag in ['writing_style', 'narrative_config', 'Characterization_settings',
                'Writing_guidance', 'Text_constraints', 'Tone', 'Information',
                'history', 'Admin', 'IzumiKonata', 'basic_IzumiKonata',
                'IzumiKonata_Root', 'main_task', 'identity_isolation',
                'format_settings', 'Output_format', 'Tucao_CoT', 'Tucao_Format',
                'konatan_planning~', 'details', 'summary',
                'content', '/content', 'Character', '/Character']:
        content = re.sub(rf'</?{tag}[^>]*>', '', content)
    # Remove <details> blocks
    content = re.sub(r'<details>.*?</details>', '', content, flags=re.DOTALL)
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()


def _has_substantive_content(text: str) -> bool:
    """Check if text has meaningful writing guidance (not just wrappers/macros)."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    substantive = [l for l in lines
                   if not l.startswith('{{')
                   and not l.startswith('Konata:')
                   and not l.startswith('Master:')
                   and not l.startswith('OKOK')
                   and not l.startswith('没问题')
                   and not l.startswith('好啦')
                   and not l.startswith('又来到了')
                   and not l.startswith('带点矫情')
                   and not l.startswith('小此来啦')
                   and not l.startswith('小此准备好啦')
                   and not l.startswith('下面就是')
                   and not l.startswith('<')
                   and not l.startswith('[')
                   and not l == 'OK，']
    return len(substantive) > 0


def render_preset_supplement(
    preset: Optional[IPreset] = None,
    card: Optional[ICharacterCard] = None,
) -> str:
    """
    Extract writing guidance from a preset's enabled content prompts.

    Only extracts prompts that are:
    - Enabled
    - Have actual content (not marker prompts)
    - Provide writing/narrative guidance (not infrastructure/variables)

    Returns a single concatenated string suitable for appending to the
    card system prompt.
    """
    if not preset or not preset.prompts:
        return ""

    # These identifiers are infrastructure/variable setup - skip them
    skip_identifiers = {
        "141ddc56-5cc3-49de-a577-72690dc98c6c",  # 防媚user
        "c366d63e-b2f6-4eb7-bd55-dbeccf9e4e5e",  # user
        "persnaDescription",  # handled by card data
    }

    # Skip prompts whose names indicate they're infrastructure/Konata-identity/format
    skip_name_patterns = [
        "初始化变量", "别动", "说明", "过渡", "/user", "/角色",
        "user", "角色", "信息结束", "文风开始", "文风结束",
        "思维链开始", "思维链结束", "可选功能开始", "可选功能结束",
        "防429", "第一人称文风↓", "可写NSFW↓", "第三人称文风↓",
        "💾通用主提示", "💾主提示",  # Konata identity — conflicts with char identity
        "吐槽", "吐糟", "头脑风暴", "卡思维链",  # Output format/CoT
        "格式示例", "摘要",  # Format examples, summary
        "自定义缝合处", "指南",  # Infrastructure
        "📋说明",  # Author notes
        "💡可选功能", "🌅文风", "🌐思维链", "🔵概念", "🔵性格",
        "🔵吐槽", "🔴指南", "🔴吐槽", "🔴其它",
    ]

    char_name = card.character.name if card else "{{char}}"
    user_name = "用户"

    sections: list[str] = []

    for p in preset.prompts:
        if not p.enabled:
            continue
        if not p.content:
            continue
        if p.identifier in skip_identifiers:
            continue
        if any(pat in p.name for pat in skip_name_patterns):
            continue
        # Skip marker prompts (these are placeholders for card data)
        if p.system_prompt:
            continue

        content = _clean_content(p.content)
        if not content or not _has_substantive_content(content):
            continue

        # Replace ST macros
        content = content.replace("{{char}}", char_name)
        content = content.replace("{{user}}", user_name)

        sections.append(content)

    if not sections:
        return ""

    return "\n\n".join(sections)


# ---------------------------------------------------------------
# SillyTavern-style prompt ordering & extraction
# ---------------------------------------------------------------

# Standard prompt order for chat completion assembly
PROMPT_ORDER = [
    "worldInfoBefore",
    "main",
    "charDescription",
    "charPersonality",
    "scenario",
    "worldInfoAfter",
    "personaDescription",
]


def get_prompt_by_identifier(preset: Optional[IPreset], identifier: str) -> Optional[IPresetPrompt]:
    """Get an enabled, non-marker prompt by its identifier."""
    if not preset or not preset.prompts:
        return None
    for p in preset.prompts:
        if p.identifier == identifier and p.enabled and not p.marker:
            return p
    return None


def get_ordered_prompts(preset: Optional[IPreset]) -> list[tuple[str, IPresetPrompt]]:
    """
    Return (identifier, prompt) pairs in SillyTavern order:
    worldInfoBefore → main → charDescription → charPersonality → scenario
    → worldInfoAfter → personaDescription → other system_prompt=True prompts.

    Skips marker prompts (they're placeholders for card data injection).
    """
    if not preset or not preset.prompts:
        return []

    by_id: dict[str, IPresetPrompt] = {}
    for p in preset.prompts:
        if p.enabled and not p.marker and p.content:
            by_id[p.identifier] = p

    result: list[tuple[str, IPresetPrompt]] = []
    added_ids: set[str] = set()

    # 1. Known positions in order
    for pid in PROMPT_ORDER:
        if pid in by_id:
            result.append((pid, by_id[pid]))
            added_ids.add(pid)

    # 2. Remaining system_prompt=True prompts (nsfw, enhanceDefinitions, ...)
    for pid, p in by_id.items():
        if pid not in added_ids and p.system_prompt:
            result.append((pid, p))
            added_ids.add(pid)

    return result


def render_prompt_content(
    prompt: IPresetPrompt,
    char_name: str = "",
    card_data: Optional[dict] = None,
) -> str:
    """Clean a prompt's content: strip macros, replace placeholders."""
    if not prompt or not prompt.content:
        return ""
    content = _clean_content(prompt.content)
    content = content.replace("{{char}}", char_name)
    content = content.replace("{{user}}", "用户")
    content = content.replace("<user>", "用户")
    if card_data:
        for key, val in card_data.items():
            if isinstance(val, str):
                content = content.replace(f"{{{{{key}}}}}", val)
    return content.strip()


def get_model_params(preset: Optional[IPreset] = None) -> dict:
    """Extract model parameters from a preset for IPresetConfig defaults."""
    if not preset:
        return {}
    return {
        "temperature": preset.temperature,
        "top_p": preset.top_p,
        "frequency_penalty": preset.frequency_penalty,
        "presence_penalty": preset.presence_penalty,
        "max_tokens": preset.max_tokens,
    }


def get_writer_identity(preset: Optional[IPreset] = None, char_name: str = "") -> str:
    """
    Extract the writer persona identity from a preset's main prompt.

    For ST-imported presets like Izumi, the "main" prompt establishes
    the AI as 泉此方 (Konata Izumi), a story writer whose job is to
    create narrative fiction — NOT to roleplay as characters.

    Returns the cleaned writer identity text, suitable for use as the
    core system prompt establishing who the AI is.
    """
    if not preset or not preset.prompts:
        return ""

    # Priority: main identifier > any prompt whose content establishes Konata identity
    main_candidates = []
    for p in preset.prompts:
        if not p.enabled or not p.content:
            continue
        if p.identifier == "main":
            main_candidates.insert(0, p)
        elif "泉此方" in p.name or "konata" in p.name.lower():
            main_candidates.append(p)

    if not main_candidates:
        return ""

    for p in main_candidates:
        raw = p.content
        if not raw:
            continue

        # Extract identity lines from raw content first (before placeholder substitution
        # confuses the extraction), then clean the result
        id_lines: list[str] = []
        in_task = False
        skip_block = False
        for line in raw.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            # Track task/isolation blocks in raw content
            if "<main_task>" in stripped.lower() or "[main task]" in stripped.lower():
                in_task = True
                continue
            if "</main_task>" in stripped.lower() or "[/main task]" in stripped.lower():
                in_task = False
                continue
            if ("<identity_isolation>" in stripped.lower()
                    or "需要注意元叙事" in stripped
                    or "认知隔离" in stripped):
                skip_block = True
                continue
            if "</identity_isolation>" in stripped.lower():
                skip_block = False
                continue
            if skip_block:
                continue

            # Skip macro-only lines
            if re.match(r'^\{\{(setvar|getvar)::', stripped):
                continue
            # Skip structural brackets
            if stripped in ('[RESET ROLE AND TASK,RECEIVE NEW TASK]',
                           '[Main Task]', '[/Main Task]'):
                continue

            if in_task:
                id_lines.append(stripped)
            elif "你是" in stripped or "泉此方" in stripped:
                if re.match(r'^(Identity|你是|泉此方)', stripped, re.IGNORECASE):
                    id_lines.append(stripped)

        if id_lines:
            result = "\n".join(id_lines)
            # Now clean and substitute
            result = _STRIP_MACROS.sub('', result)
            result = re.sub(r'\{\{//[^}]*\}\}', '', result)
            result = re.sub(r'\{\{getvar::[^}]*\}\}', '', result)
            result = re.sub(r'\{\{setvar::[^}]*\}\}', '', result)
            # Placeholders: {{user}} → Master (Konata's term for the user)
            # <user> → the in-story character name
            result = result.replace("{{user}}", "Master")
            result = result.replace("<user>", char_name or "{{char}}")
            result = re.sub(r'\n{3,}', '\n\n', result)
            return result.strip()

    return ""


def get_writing_style(preset: Optional[IPreset] = None) -> str:
    """
    Extract the writing style guidance specifically.
    Combines the main writing style prompts into a concise string.
    """
    if not preset or not preset.prompts:
        return ""

    # Key writing style prompts by name
    style_names = {
        "✔️小此漫改",
        "🎆文风-日轻小说",
        "✅允许转折",
        "✅反直觉",
        "⚡️推剧情ProMax",
        "⚡️防绝望（光明基调）",
        "⚡️转述",
        "⚡️抢话",
        "👤人称-第三人称",
        "👤扩写输入",
        "⚡️字数加强",
        "🤖自定义（字数）",
        "🔴指南（可改）",
    }

    sections = []
    for p in preset.prompts:
        if not p.enabled or not p.content:
            continue
        if p.name not in style_names:
            continue

        content = _clean_content(p.content)
        if not content or not _has_substantive_content(content):
            continue

        sections.append(content)

    return "\n\n".join(sections)
