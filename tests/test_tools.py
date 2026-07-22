import math

import pytest

from agent.tools import build_default_registry
from agent.tools.base import ToolError
from agent.tools.calculator import calculate
from agent.tools.search import search
from agent.tools.todo import TodoStore
from agent.tools.weather import get_weather


def test_calculator_basic():
    for expr in ["2 + 3 * 4", "(2 + 3) * 4", "sqrt(144)", "2 ** 10"]:
        out = calculate(expr)
        print(f"    calculate({expr!r}) -> {out['result']}")
    assert calculate("2 + 3 * 4")["result"] == 14
    assert calculate("(2 + 3) * 4")["result"] == 20
    assert calculate("sqrt(144)")["result"] == 12
    assert math.isclose(calculate("2 ** 10")["result"], 1024)


def test_calculator_rejects_code():
    with pytest.raises(ToolError) as e1:
        calculate("__import__('os').system('ls')")
    print(f"    危险输入被拦截 -> ToolError: {e1.value}")
    with pytest.raises(ToolError) as e2:
        calculate("")
    print(f"    空表达式被拦截 -> ToolError: {e2.value}")


def test_search_mock_deterministic():
    r = search("python")
    print(f"    search('python') -> {r}")
    print(f"    两次调用结果一致: {search('python') == r}")
    print(f"    search('anything', top_k=1) 条数 = {len(search('anything', top_k=1)['results'])}")
    assert search("python") == r
    assert r["results"]
    assert len(search("anything", top_k=1)["results"]) == 1


def test_weather_mock_deterministic_and_varies():
    a, b, c = get_weather("Beijing"), get_weather("Beijing"), get_weather("Shanghai")
    print(f"    weather('Beijing') -> {a}")
    print(f"    weather('Shanghai') -> {c}")
    print(f"    同城市稳定: {a == b}；不同城市不同: {a != c}")
    assert a == b and 10 <= a["temperature_c"] <= 29 and a != c


def test_todo_store_lifecycle():
    store = TodoStore()
    store.add("write report")
    store.add("water plants")
    print(f"    add 后列表 -> {store.list()}")
    store.complete(1)
    print(f"    complete(1) 后 -> {store.list()}")
    with pytest.raises(ToolError) as e:
        store.complete(999)
    print(f"    complete(999) 不存在 -> ToolError: {e.value}")
    assert store.list()[0]["done"] is True


def test_registry_and_schema():
    registry = build_default_registry(TodoStore())
    print(f"    已注册工具 -> {registry.names()}")
    for schema in registry.schemas():
        print(f"    schema: name={schema['name']!r} params={list(schema['parameters'].get('properties', {}))}")
        assert "name" in schema and "description" in schema and "parameters" in schema
    assert {"calculator", "search", "weather", "todo"} <= set(registry.names())


def test_tool_validates_required_args():
    registry = build_default_registry(TodoStore())
    with pytest.raises(ToolError) as e1:
        registry.get("calculator").run({})
    print(f"    calculator 缺 expression -> ToolError: {e1.value}")
    with pytest.raises(ToolError) as e2:
        registry.get("weather").run({"city": "X", "bogus": 1})
    print(f"    weather 传未知参数 bogus -> ToolError: {e2.value}")


def test_todo_tool_isolated_per_store():
    s1, s2 = TodoStore(), TodoStore()
    r1 = build_default_registry(s1)
    build_default_registry(s2)
    r1.get("todo").run({"action": "add", "task": "A"})
    print(f"    store1 待办 -> {[t['task'] for t in s1.list()]}")
    print(f"    store2 待办 -> {[t['task'] for t in s2.list()]}  (未受影响)")
    assert len(s1.list()) == 1 and len(s2.list()) == 0