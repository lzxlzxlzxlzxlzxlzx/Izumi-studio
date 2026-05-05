"""
TemplateRenderer — Lightweight Handlebars-compatible template engine.

Supports:
- {{variable}} and {{obj.prop}} substitution
- {{#if var}}...{{/if}}, {{#unless var}}...{{/unless}}, with {{else}}
- {{#each list}}...{{/each}} with {{this}} and {{@index}}
- ST-compatible macros: {{setvar::key::value}}, {{getvar::key}}, {{trim}}
- Compilation cache for performance
"""

from __future__ import annotations
import re
from typing import Any, Optional

# ---------------------------------------------------------------
# Macro storage
# ---------------------------------------------------------------

_template_vars: dict[str, str] = {}


def _setvar(match: re.Match) -> str:
    _template_vars[match.group(1)] = match.group(2)
    return ""


def _getvar(match: re.Match) -> str:
    return _template_vars.get(match.group(1), "")


_MACRO_SETVAR = re.compile(r'\{\{setvar::([^:}]+)::([^:}]*)\}\}')
_MACRO_GETVAR = re.compile(r'\{\{getvar::([^:}]+)\}\}')
_MACRO_TRIM = re.compile(r'\{\{trim\}\}', re.IGNORECASE)


def substitute_macros(text: str) -> str:
    """Apply ST-compatible macros: setvar, getvar, trim."""
    text = _MACRO_SETVAR.sub(_setvar, text)
    text = _MACRO_GETVAR.sub(_getvar, text)
    text = _MACRO_TRIM.sub("", text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ---------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------

_tok_re = re.compile(
    r'\{\{(#if|#unless|#each|\/if|\/unless|\/each|else)\s*([^}]*?)\}\}'
    r'|\{\{([^#\/][^}]*?)\}\}',
    re.DOTALL,
)


def _tokenize(template: str) -> list[dict]:
    """Parse a Handlebars template into a list of tokens."""
    tokens: list[dict] = []
    pos = 0

    for m in _tok_re.finditer(template):
        text = template[pos:m.start()]
        if text:
            tokens.append({"type": "text", "value": text})

        if m.group(1):  # Block tag: #if, #unless, #each, /if, /unless, /each, else
            tag = m.group(1)
            arg = m.group(2).strip()
            if tag in ("/if", "/unless", "/each"):
                tokens.append({"type": tag})  # "end" is implicit via "/"
            elif tag == "else":
                tokens.append({"type": "else"})
            else:  # #if, #unless, #each
                tokens.append({"type": tag, "arg": arg})
        else:  # Simple expression
            expr = m.group(3).strip()
            tokens.append({"type": "expr", "value": expr})

        pos = m.end()

    text = template[pos:]
    if text:
        tokens.append({"type": "text", "value": text})

    return tokens


# ---------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------

def _eval_expr(expr: str, vars_: dict[str, Any]) -> str:
    """Evaluate a simple Handlebars expression."""
    expr = expr.strip()

    if expr == "this":
        val = vars_.get("this", "")
        return str(val) if not isinstance(val, dict) else ""

    if expr == "@index":
        return str(vars_.get("@index", ""))

    if "." in expr:
        parts = expr.split(".")
        val: Any = vars_
        for p in parts:
            if isinstance(val, dict) and p in val:
                val = val[p]
            elif hasattr(val, p):
                val = getattr(val, p)
            else:
                return ""
        return str(val) if val is not None else ""

    val = vars_.get(expr, "")
    if val is None:
        return ""
    if isinstance(val, bool):
        return str(val).lower()
    return str(val)


# ---------------------------------------------------------------
# Recursive renderer
# ---------------------------------------------------------------

def _find_matching_end(tokens: list[dict], start: int, block_tag: str) -> tuple[int, Optional[int]]:
    """
    Find matching /tag (and optional else) from position `start`.
    Returns (end_index, else_index_or_None).
    """
    end_tag = "/" + block_tag[1:]
    depth = 1
    else_idx: Optional[int] = None

    for i in range(start, len(tokens)):
        tt = tokens[i]["type"]
        if tt == block_tag:
            depth += 1
        elif tt == end_tag:
            depth -= 1
            if depth == 0:
                return i, else_idx
        elif tt == "else" and depth == 1:
            else_idx = i

    return len(tokens) - 1, else_idx


def _render_tokens(tokens: list[dict], vars_: dict[str, Any]) -> str:
    """Render parsed tokens with the given variable context."""
    result: list[str] = []
    i = 0

    while i < len(tokens):
        t = tokens[i]
        tt = t["type"]

        if tt == "text":
            result.append(t["value"])
            i += 1

        elif tt == "expr":
            result.append(_eval_expr(t["value"], vars_))
            i += 1

        elif tt in ("#if", "#unless", "#each"):
            end_idx, else_idx = _find_matching_end(tokens, i + 1, tt)

            if tt == "#each":
                list_name = t["arg"]
                items = vars_.get(list_name, [])
                if not isinstance(items, list):
                    items = []
                inner = tokens[i + 1:end_idx]
                for idx, item in enumerate(items):
                    item_vars = dict(vars_)
                    if isinstance(item, dict):
                        item_vars.update(item)
                    item_vars["this"] = item
                    item_vars["@index"] = idx
                    result.append(_render_tokens(inner, item_vars))

            elif tt in ("#if", "#unless"):
                condition = bool(_eval_expr(t["arg"], vars_)) if t["arg"] else False
                if tt == "#unless":
                    condition = not condition

                if condition:
                    inner = tokens[i + 1:(else_idx if else_idx is not None else end_idx)]
                    result.append(_render_tokens(inner, vars_))
                elif else_idx is not None:
                    inner_else = tokens[else_idx + 1:end_idx]
                    result.append(_render_tokens(inner_else, vars_))

            i = end_idx + 1

        elif tt in ("/if", "/unless", "/each", "else"):
            # These are handled by parent block — skip
            i += 1

        else:
            i += 1

    return "".join(result)


# ---------------------------------------------------------------
# Cache
# ---------------------------------------------------------------

_compile_cache: dict[str, list[dict]] = {}
_cache_hits: int = 0


def compile_template(template: str) -> list[dict]:
    """Parse and cache a template. Returns the token list."""
    global _cache_hits
    if template in _compile_cache:
        _cache_hits += 1
        return _compile_cache[template]
    tokens = _tokenize(template)
    _compile_cache[template] = tokens
    return tokens


def render(template: str, vars_: Optional["TemplateVars"] = None) -> str:
    """
    Render a Handlebars template with the given variables.

    Args:
        template: Handlebars template string
        vars_: TemplateVars instance (empty vars used if None)

    Returns:
        Rendered string with macros applied
    """
    if vars_ is None:
        vars_ = TemplateVars()

    var_dict = vars_.to_dict()

    # ST-compatible formatting
    if var_dict.get("personality") and var_dict.get("char"):
        var_dict["personality"] = f"{var_dict['char']}'s personality: {var_dict['personality']}"
    if var_dict.get("scenario"):
        var_dict["scenario"] = f"Scenario: {var_dict['scenario']}"
    if var_dict.get("description") and var_dict.get("char"):
        var_dict["description"] = f"{var_dict.get('char', '')}'s description: {var_dict['description']}"

    tokens = compile_template(template)
    rendered = _render_tokens(tokens, var_dict)
    rendered = substitute_macros(rendered)
    return rendered


def clear_cache() -> None:
    """Clear the template compilation cache and macro variables."""
    global _cache_hits
    _compile_cache.clear()
    _template_vars.clear()
    _cache_hits = 0


# ---------------------------------------------------------------
# TemplateVars
# ---------------------------------------------------------------

class TemplateVars:
    """Variable bag matching ST's story string template context."""

    def __init__(
        self,
        system: str = "",
        description: str = "",
        personality: str = "",
        scenario: str = "",
        persona: str = "",
        char: str = "",
        user: str = "",
        wi_before: str = "",
        wi_after: str = "",
        mes_examples: str = "",
    ):
        self.system = system
        self.description = description
        self.personality = personality
        self.scenario = scenario
        self.persona = persona
        self.char = char
        self.user = user
        self.wi_before = wi_before
        self.wi_after = wi_after
        self.mes_examples = mes_examples

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "description": self.description,
            "personality": self.personality,
            "scenario": self.scenario,
            "persona": self.persona,
            "char": self.char,
            "user": self.user,
            "wiBefore": self.wi_before,
            "wiAfter": self.wi_after,
            "mesExamples": self.mes_examples,
        }
