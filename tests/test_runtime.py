from agent import Agent, MockLLM, SessionManager
from agent.session import SessionConfig
from agent.trace import Tracer


def _silent_tracer():
    return Tracer(verbose=False)


def _dump(session):
    for m in session.history:
        print(f"      [{m.role}] {m.content}")


def test_direct_reply_no_tool():
    llm = MockLLM(scripted=['{"thought": "greeting", "final": "Hi! How can I help?"}'])
    agent = Agent(llm, tracer=_silent_tracer())
    s = SessionManager().create()
    res = agent.run(s, "hello")
    print("    用户: hello")
    print(f"    Agent: {res.answer}  (turns={res.turns}, error={res.error})")
    assert res.answer == "Hi! How can I help?"
    assert res.turns == 1 and res.error is None


def test_single_tool_then_final():
    llm = MockLLM(scripted=[
        '{"thought": "need math", "action": {"tool": "calculator", "args": {"expression": "21*2"}}}',
        '{"thought": "have result", "final": "The answer is 42."}'])
    agent = Agent(llm, tracer=_silent_tracer())
    s = SessionManager().create()
    res = agent.run(s, "what is 21*2?")
    print("    用户: what is 21*2?")
    print("    对话轨迹:")
    _dump(s)
    print(f"    Agent 最终: {res.answer}  (turns={res.turns})")
    assert "42" in res.answer and res.turns == 2
    assert any("Observation from calculator" in m.content for m in s.history)


def test_multi_tool_chain_weather_then_todo():
    llm = MockLLM(scripted=[
        '{"thought": "check weather", "action": {"tool": "weather", "args": {"city": "Beijing"}}}',
        '{"thought": "record it", "action": {"tool": "todo", "args": {"action": "add", "task": "bring umbrella"}}}',
        '{"thought": "done", "final": "Checked Beijing weather and added a todo."}'])
    agent = Agent(llm, tracer=_silent_tracer())
    s = SessionManager().create()
    res = agent.run(s, "check weather in Beijing and add a todo")
    print("    用户: check weather in Beijing and add a todo")
    print("    对话轨迹:")
    _dump(s)
    print(f"    最终待办 -> {[t['task'] for t in s.todo_store.list()]}  (turns={res.turns})")
    assert res.turns == 3
    assert [t["task"] for t in s.todo_store.list()] == ["bring umbrella"]


def test_parse_error_recovery():
    llm = MockLLM(scripted=["this is not json at all",
                            '{"thought": "now valid", "final": "recovered"}'])
    agent = Agent(llm, tracer=_silent_tracer())
    s = SessionManager().create()
    res = agent.run(s, "hi")
    print("    第1轮模型输出非法JSON -> 循环追加纠错提示 -> 第2轮恢复")
    _dump(s)
    print(f"    Agent 最终: {res.answer}  (turns={res.turns})")
    assert res.answer == "recovered" and res.turns == 2


def test_unknown_tool_is_handled():
    llm = MockLLM(scripted=[
        '{"thought": "bad tool", "action": {"tool": "nope", "args": {}}}',
        '{"thought": "recover", "final": "ok"}'])
    agent = Agent(llm, tracer=_silent_tracer())
    s = SessionManager().create()
    res = agent.run(s, "hi")
    unknown = [m.content for m in s.history if "unknown tool" in m.content]
    print(f"    调用未知工具的观测回灌 -> {unknown[-1] if unknown else None}")
    print(f"    Agent 最终: {res.answer}")
    assert res.answer == "ok" and unknown


def test_max_turns_guard():
    loop_resp = '{"thought": "loop", "action": {"tool": "search", "args": {"query": "x"}}}'
    llm = MockLLM(responder=lambda msgs: loop_resp)
    agent = Agent(llm, tracer=_silent_tracer())
    s = SessionManager(config=SessionConfig(max_turns=3)).create()
    res = agent.run(s, "loop forever")
    print(f"    模型永远只调工具，max_turns=3 -> 停在第 {res.turns} 轮")
    print(f"    兜底答案: {res.answer}")
    print(f"    error: {res.error}")
    assert res.turns == 3 and res.error is not None and "max_turns" in res.error


def test_followup_remembers_state_with_tools():
    def responder(msgs):
        last_user = [m for m in msgs if m["role"] == "user"][-1]["content"]
        if "add" in last_user:
            return '{"thought": "add", "action": {"tool": "todo", "args": {"action": "add", "task": "report"}}}'
        if "Observation" in last_user:
            return '{"thought": "done", "final": "added"}'
        return '{"thought": "list", "action": {"tool": "todo", "args": {"action": "list"}}}'

    agent = Agent(MockLLM(responder=responder), tracer=_silent_tracer())
    s = SessionManager().create()
    agent.run(s, "please add report to my todos")
    print("    第1条消息: 添加待办 'report'")
    res = agent.run(s, "how many todos?")
    obs = [m.content for m in s.history if "Observation from todo" in m.content]
    print("    第2条消息(追问): how many todos?")
    print(f"    列出待办的观测 -> {obs[-1]}")
    assert obs and "report" in obs[-1] and res.error is None


def test_llm_error_is_graceful():
    class Boom(MockLLM):
        def complete(self, messages):
            from agent.llm import LLMError
            raise LLMError("backend down")

    agent = Agent(Boom(), tracer=_silent_tracer())
    s = SessionManager().create()
    res = agent.run(s, "hi")
    print(f"    LLM 抛错时 -> Agent 兜底: {res.answer}")
    print(f"    error 标记: {res.error}")
    assert res.error is not None and "couldn't complete" in res.answer