#!/usr/bin/env python3
"""Interactive multi-session CLI. Run: python cli.py
Commands: /new [name], /switch <id|name>, /sessions, /todos,
/remember <fact>, /trace, /help, /quit. Other input goes to the agent."""
from __future__ import annotations

import os
import sys

from agent import Agent, MockLLM, OpenAICompatibleLLM, SessionManager, Tracer
from agent.session import SessionConfig

HELP = __doc__


def _make_llm():
    if os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"):
        return OpenAICompatibleLLM()
    print("No LLM_API_KEY found — MOCK mode. Set LLM_API_KEY for real answers.\n", file=sys.stderr)
    return MockLLM(responder=lambda msgs: '{"thought": "mock", "final": "Mock reply. '
                   'Set LLM_API_KEY to use a real model."}')


def _find_session(manager: SessionManager, key: str):
    for snap in manager.list():
        if snap["id"].startswith(key) or snap["name"] == key:
            return manager.get(snap["id"])
    return None


def main() -> int:
    tracer = Tracer(verbose=True, file_path=os.getenv("AGENT_TRACE_FILE", "logs/trace.jsonl"))
    manager = SessionManager(config=SessionConfig())
    agent = Agent(_make_llm(), tracer=tracer)
    current = manager.create(name="main")
    print(f"minimal-agent CLI — session '{current.name}' ({current.id[:8]}). Type /help.")
    while True:
        try:
            line = input(f"\n[{current.name}] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return 0
        if not line:
            continue
        if line.startswith("/"):
            parts = line.split(maxsplit=1)
            cmd, arg = parts[0], (parts[1] if len(parts) > 1 else "")
            if cmd in ("/quit", "/exit"):
                print("bye"); return 0
            elif cmd == "/help":
                print(HELP)
            elif cmd == "/new":
                current = manager.create(name=arg or "")
                print(f"created + switched to '{current.name}' ({current.id[:8]})")
            elif cmd == "/switch":
                found = _find_session(manager, arg)
                if found:
                    current = found; print(f"switched to '{current.name}' ({current.id[:8]})")
                else:
                    print(f"no session matching '{arg}'")
            elif cmd == "/sessions":
                for snap in manager.list():
                    marker = "*" if snap["id"] == current.id else " "
                    print(f" {marker} {snap['id'][:8]}  {snap['name']:<12} "
                          f"msgs={snap['messages']} todos={len(snap['todos'])}")
            elif cmd == "/todos":
                todos = current.todo_store.list()
                if not todos:
                    print("(no todos)")
                for t in todos:
                    print(f"  [{'x' if t['done'] else ' '}] #{t['id']} {t['task']}")
            elif cmd == "/remember":
                if arg:
                    current.remember_fact(arg); print("remembered.")
                else:
                    print("usage: /remember <fact>")
            elif cmd == "/trace":
                tracer.verbose = not tracer.verbose
                print(f"tracing {'on' if tracer.verbose else 'off'}")
            else:
                print(f"unknown command '{cmd}'. /help for help.")
            continue
        result = agent.run(current, line)
        print(f"\nAgent: {result.answer}")
        if result.error:
            print(f"(note: {result.error})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())