"""Unit tests for TemplateRenderer."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.template_renderer import (
    render, clear_cache, substitute_macros,
    TemplateVars, _template_vars, _tokenize, _render_tokens,
)
import app.services.template_renderer as tr


def setup():
    clear_cache()


def test_basic_render():
    """Simple template with one variable."""
    result = render("Hello {{char}}!", TemplateVars(char="艾莉丝"))
    assert result == "Hello 艾莉丝!"


def test_full_render():
    """All TemplateVars filled."""
    template = (
        "System: {{system}}\n"
        "{{description}}\n"
        "{{personality}}\n"
        "{{scenario}}\n"
        "Persona: {{persona}}\n"
        "Char: {{char}}, User: {{user}}\n"
        "WI Before: {{wiBefore}}\n"
        "WI After: {{wiAfter}}\n"
        "Examples: {{mesExamples}}"
    )
    vars_ = TemplateVars(
        system="You are an elf",
        description="A tall elf with silver hair",
        personality="Calm and wise",
        scenario="Deep forest at dawn",
        persona="A traveler",
        char="艾莉丝",
        user="旅行者",
        wi_before="[Forest setting]",
        wi_after="[Magic aura]",
        mes_examples="艾莉丝: Hello there",
    )
    result = render(template, vars_)
    assert "You are an elf" in result
    assert "silver hair" in result
    assert "Calm and wise" in result
    assert "Deep forest at dawn" in result
    assert "旅行者" in result
    assert "艾莉丝" in result
    assert "[Forest setting]" in result
    assert "Hello there" in result


def test_empty_vars():
    """Optional vars not passed → no crash, empty strings."""
    clear_cache()
    result = render("Hello {{char}}!")
    assert result == "Hello !"


def test_if_conditional_true():
    """{{#if var}}...{{/if}} with truthy value."""
    result = render("{{#if description}}Description: {{description}}{{/if}}",
                    TemplateVars(description="An elf"))
    assert "Description: An elf" in result


def test_if_conditional_false():
    """{{#if var}}...{{/if}} with falsy value."""
    clear_cache()
    result = render("Before{{#if description}}HIDDEN{{/if}}After",
                    TemplateVars(description=""))
    assert result == "BeforeAfter", f"Got: {result!r}"


def test_unless_conditional():
    """{{#unless var}}...{{/unless}} — inverse of #if."""
    clear_cache()
    result = render("{{#unless description}}No description{{/unless}}",
                    TemplateVars(description=""))
    assert "No description" in result

    result2 = render("{{#unless description}}No description{{/unless}}",
                     TemplateVars(description="Has desc"))
    assert "No description" not in result2


def test_if_else():
    """{{#if var}}A{{else}}B{{/if}}"""
    clear_cache()
    template = "{{#if description}}Has desc{{else}}No desc{{/if}}"
    result = render(template, TemplateVars(description="An elf"))
    assert "Has desc" in result
    assert "No desc" not in result

    result2 = render(template, TemplateVars(description=""))
    assert "No desc" in result2, f"Got: {result2!r}"
    assert "Has desc" not in result2


def test_each_loop():
    """{{#each list}}...{{/each}}"""
    template = "Tags: {{#each tags}}{{this}}, {{/each}}done"
    tokens = _tokenize(template)
    result = _render_tokens(tokens, {"tags": ["fantasy", "adventure", "mystery"]})
    assert "fantasy" in result
    assert "adventure" in result
    assert "mystery" in result


def test_each_with_index():
    """{{#each list}}{{@index}}: {{this}}{{/each}}"""
    template = "{{#each items}}{{@index}}:{{this}} {{/each}}"
    tokens = _tokenize(template)
    result = _render_tokens(tokens, {"items": ["a", "b", "c"]})
    assert "0:a" in result
    assert "1:b" in result
    assert "2:c" in result


def test_setvar_macro():
    """{{setvar::key::value}} stores value and returns empty string."""
    clear_cache()
    result = substitute_macros("Before{{setvar::hp::100}}After")
    assert result == "BeforeAfter"
    assert _template_vars.get("hp") == "100"


def test_getvar_macro():
    """{{getvar::key}} retrieves stored value."""
    clear_cache()
    _template_vars["hp"] = "100"
    result = substitute_macros("HP: {{getvar::hp}}")
    assert result == "HP: 100"


def test_trim_macro():
    """{{trim}} removes itself."""
    result = substitute_macros("line1\n{{trim}}\nline2")
    assert "line1" in result
    assert "line2" in result


def test_compile_cache():
    """Same template compiled only once (cached on second call)."""
    clear_cache()
    template = "Hello {{char}} CACHE_TEST!"
    # First call: compile and cache
    render(template, TemplateVars(char="A"))
    # Second call with same template: should hit cache
    hits_before = tr._cache_hits
    render(template, TemplateVars(char="B"))
    assert tr._cache_hits > hits_before, f"Cache not hit: {tr._cache_hits} <= {hits_before}"


def test_dot_path():
    """{{obj.prop}} dot-path access."""
    template = "{{char.name}} the {{char.race}}"
    tokens = _tokenize(template)
    result = _render_tokens(tokens, {"char": {"name": "艾莉丝", "race": "elf"}})
    assert "艾莉丝" in result
    assert "elf" in result


def test_none_value():
    """None values should render as empty string."""
    clear_cache()
    result = render("Value: {{description}}", TemplateVars(description=None))
    # substitute_macros strips whitespace, so trailing space is removed
    assert result == "Value:", f"Got: {result!r}"


if __name__ == "__main__":
    tests = [
        ("Basic render", test_basic_render),
        ("Full render all vars", test_full_render),
        ("Empty vars no crash", test_empty_vars),
        ("#if conditional true", test_if_conditional_true),
        ("#if conditional false", test_if_conditional_false),
        ("#unless conditional", test_unless_conditional),
        ("#if-else", test_if_else),
        ("#each loop", test_each_loop),
        ("#each with @index", test_each_with_index),
        ("setvar macro", test_setvar_macro),
        ("getvar macro", test_getvar_macro),
        ("trim macro", test_trim_macro),
        ("Compile cache", test_compile_cache),
        ("Dot-path access", test_dot_path),
        ("None value", test_none_value),
    ]

    setup()
    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            import traceback
            print(f"  FAIL  {name}: {e}")
            traceback.print_exc()

    print(f"\n{passed}/{len(tests)} tests passed")
