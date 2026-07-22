from agent.session import Session, SessionConfig, SessionManager


def test_sessions_are_isolated():
    mgr = SessionManager()
    s1 = mgr.create(name="window1")
    s2 = mgr.create(name="window2")
    s1.todo_store.add("check weather")
    s2.todo_store.add("write weekly report")
    print(f"    window1({s1.id[:8]}) 待办 -> {[t['task'] for t in s1.todo_store.list()]}")
    print(f"    window2({s2.id[:8]}) 待办 -> {[t['task'] for t in s2.todo_store.list()]}")
    print("    两个窗口 id 不同、待办互不影响")
    assert s1.id != s2.id
    assert [t["task"] for t in s1.todo_store.list()] == ["check weather"]
    assert [t["task"] for t in s2.todo_store.list()] == ["write weekly report"]
    assert mgr.get(s1.id) is s1 and mgr.get(s2.id) is s2


def test_get_or_create():
    mgr = SessionManager()
    a = mgr.get_or_create("fixed-id")
    b = mgr.get_or_create("fixed-id")
    print(f"    get_or_create('fixed-id') 两次 -> 同一对象: {a is b}")
    assert a is b


def test_memory_facts_in_prompt():
    s = Session(name="s")
    s.remember_fact("user prefers metric units")
    s.remember_fact("user prefers metric units")  # dedup
    prompt = s.system_prompt("base")
    print(f"    记忆去重后 facts = {s.facts}")
    print(f"    system prompt 含该 fact 次数 = {prompt.count('user prefers metric units')}")
    print(f"    system prompt 含工具清单: {'Available tools' in prompt}")
    assert prompt.count("user prefers metric units") == 1
    assert "Available tools" in prompt


def test_compression_summarizes_old_history():
    cfg = SessionConfig(max_history_messages=6, keep_recent_messages=2)
    s = Session(name="s", config=cfg)
    for i in range(8):
        s.add_message("user", f"message {i}")
    print(f"    压缩前历史条数 = {len(s.history)}，needs_compression={s.needs_compression()}")
    ran = s.compress(llm=None)  # 无LLM时走启发式回退
    print(f"    压缩已执行 = {ran}，压缩后历史条数 = {len(s.history)}")
    print(f"    summary(前80字) = {s.summary[:80]!r}")
    assert ran and len(s.history) == 2 and s.summary
    assert not s.needs_compression()


def test_build_messages_includes_system_first():
    s = Session(name="s")
    s.add_message("user", "hi")
    msgs = s.build_messages("base prompt")
    print(f"    组装后消息角色顺序 -> {[m['role'] for m in msgs]}")
    print(f"    第2条 -> {msgs[1]}")
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {"role": "user", "content": "hi"}