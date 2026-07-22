import pytest

from agent.parser import ParseError, parse


def test_parse_final():
    raw = '{"thought": "easy", "final": "hello there"}'
    d = parse(raw)
    print(f"    输入: {raw}")
    print(f"    解析: thought={d.thought!r} final={d.final!r} is_final={d.is_final}")
    assert d.is_final and d.final == "hello there"
    assert d.thought == "easy" and not d.is_tool_call


def test_parse_tool_call():
    raw = '{"thought": "need math", "action": {"tool": "calculator", "args": {"expression": "1+1"}}}'
    d = parse(raw)
    print(f"    输入: {raw}")
    print(f"    解析: tool={d.tool!r} args={d.args}")
    assert d.is_tool_call and d.tool == "calculator" and d.args == {"expression": "1+1"}


def test_parse_top_level_tool():
    raw = '{"tool": "search", "args": {"query": "x"}}'
    d = parse(raw)
    print(f"    输入(顶层tool): {raw}  ->  tool={d.tool!r} args={d.args}")
    assert d.tool == "search"


def test_parse_with_code_fence_and_prose():
    raw = 'Sure!\n```json\n{"thought": "t", "final": "done"}\n```\nthanks'
    d = parse(raw)
    print(f"    输入(带```json和废话): {raw!r}")
    print(f"    解析 final={d.final!r}")
    assert d.final == "done"


def test_parse_embedded_json_with_braces_in_strings():
    raw = 'noise {"thought": "use {braces} here", "final": "a}b"} trailing'
    d = parse(raw)
    print(f"    输入(字符串内含花括号): {raw!r}")
    print(f"    解析 final={d.final!r} thought={d.thought!r}")
    assert d.final == "a}b"


def test_parse_errors():
    bads = ["", "no json here", '{"thought": "x"}', '{"action": {"tool": "t", "args": "notdict"}}']
    for bad in bads:
        with pytest.raises(ParseError) as e:
            parse(bad)
        print(f"    非法输入 {bad!r:45} -> ParseError: {e.value}")