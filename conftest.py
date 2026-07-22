"""给 pytest 输出加上中文说明。运行： python -m pytest -v -s
只负责打印，不改动任何测试逻辑。"""
from __future__ import annotations

_DESCRIPTIONS = {
    "tests/test_tools.py::test_calculator_basic":
        ("calculator 能正确算 2+3*4=14、带括号、sqrt(144)=12、2**10=1024", "要求2·工具·calculator"),
    "tests/test_tools.py::test_calculator_rejects_code":
        ("calculator 用 AST 白名单，拒绝 __import__/os.system 等任意代码、拒绝空表达式", "要求2·工具安全 + 额外要求·异常处理"),
    "tests/test_tools.py::test_search_mock_deterministic":
        ("search(mock) 结果确定可复现，top_k 能限制返回条数", "要求2·工具·search(可mock)"),
    "tests/test_tools.py::test_weather_mock_deterministic_and_varies":
        ("weather(mock) 同城市稳定、不同城市不同，温度在合理范围", "要求2·工具·weather(自定义)"),
    "tests/test_tools.py::test_todo_store_lifecycle":
        ("todo 的 add/list/complete 全流程，complete 不存在的 id 会报错", "要求2·工具·todo(自定义)"),
    "tests/test_tools.py::test_registry_and_schema":
        ("注册表含 calculator/search/weather/todo，且每个都带 name/description/参数Schema", "要求2·工具注册机制"),
    "tests/test_tools.py::test_tool_validates_required_args":
        ("缺必填参数、传未知参数都会抛 ToolError", "要求2·Schema校验 + 异常处理"),
    "tests/test_tools.py::test_todo_tool_isolated_per_store":
        ("两个独立 store 的 todo 互不影响（状态隔离）", "要求2·session管理·状态隔离"),
    "tests/test_parser.py::test_parse_final":
        ("能从 JSON 解析出『最终答案』(final) 与思考过程(thought)", "要求2·解析(思考/最终答案)"),
    "tests/test_parser.py::test_parse_tool_call":
        ("能解析出『工具调用』：tool 名称 + args 参数", "要求2·解析(工具调用)"),
    "tests/test_parser.py::test_parse_top_level_tool":
        ("兼容 tool/args 放在顶层（非 action 包裹）的写法", "要求2·解析鲁棒性"),
    "tests/test_parser.py::test_parse_with_code_fence_and_prose":
        ("被 ```json 代码块和前后废话包裹时也能提取 JSON", "要求2·解析鲁棒性"),
    "tests/test_parser.py::test_parse_embedded_json_with_braces_in_strings":
        ("字符串里含 {} 时按括号配平仍能正确提取 JSON", "要求2·解析鲁棒性"),
    "tests/test_parser.py::test_parse_errors":
        ("空/无JSON/缺字段/args非对象 等非法输出都会抛 ParseError", "要求2·解析 + 异常处理"),
    "tests/test_session.py::test_sessions_are_isolated":
        ("窗口1(查天气记待办)与窗口2(写周报记待办)的待办/历史完全独立", "要求2·session管理(两窗口互不影响)"),
    "tests/test_session.py::test_get_or_create":
        ("同一 session id 反复获取返回同一会话对象", "要求2·session·持续对话"),
    "tests/test_session.py::test_memory_facts_in_prompt":
        ("长期记忆(facts)去重后注入 system prompt，每轮召回", "要求2·记住状态 + memory放置"),
    "tests/test_session.py::test_compression_summarizes_old_history":
        ("历史超阈值触发基础压缩：旧消息进 summary，只留最近若干条", "要求2·context基础压缩"),
    "tests/test_session.py::test_build_messages_includes_system_first":
        ("组装消息：第1条是 system(工具/记忆/摘要)，随后按序历史", "要求2·context组装/放置"),
    "tests/test_runtime.py::test_direct_reply_no_tool":
        ("无需工具的问候，一轮直接返回最终答案", "要求2·Loop·判断直接回复"),
    "tests/test_runtime.py::test_single_tool_then_final":
        ("单次工具调用：calculator 得 42，结果回灌后给最终答案", "要求2·Loop·调用工具→返回"),
    "tests/test_runtime.py::test_multi_tool_chain_weather_then_todo":
        ("多工具链：查天气→记待办→收尾共3轮，待办正确写入", "要求2·Loop·多轮 + 带工具追问"),
    "tests/test_runtime.py::test_parse_error_recovery":
        ("模型先吐非法JSON，追加纠错提示重试，第2轮恢复", "额外要求·异常处理(解析自愈)"),
    "tests/test_runtime.py::test_unknown_tool_is_handled":
        ("调用不存在的工具时转成错误观测回灌、不崩溃", "额外要求·异常处理(未知工具)"),
    "tests/test_runtime.py::test_max_turns_guard":
        ("一直只调工具不给答案时，达 max_turns 安全退出并报告原因", "要求2·context·最大轮次限制"),
    "tests/test_runtime.py::test_followup_remembers_state_with_tools":
        ("同一 session：先加待办，追问『有几个待办』能看到此前状态", "要求2·带工具追问 + 记住状态"),
    "tests/test_runtime.py::test_llm_error_is_graceful":
        ("LLM 后端报错时返回友好兜底、带 error 标记、不抛异常", "额外要求·异常处理(LLM故障)"),
}


def pytest_runtest_setup(item):
    desc = _DESCRIPTIONS.get(item.nodeid)
    if desc:
        what, req = desc
        print(f"\n[验证] {what}\n[要求] {req}")


def pytest_runtest_logreport(report):
    if report.when == "call":
        mark = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP"}.get(report.outcome, report.outcome.upper())
        print(f"[结果] {mark}")