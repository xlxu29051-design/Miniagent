#!/usr/bin/env python3
"""Scripted two-window demo. Run: LLM_API_KEY=... python demo.py"""
from __future__ import annotations

import os
import sys

from agent import Agent, OpenAICompatibleLLM, SessionManager, Tracer


def main() -> int:
    if not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
        print("Set LLM_API_KEY (and optionally LLM_BASE_URL/LLM_MODEL) to run the live demo.")
        return 1
    tracer = Tracer(verbose=True, file_path="logs/trace.jsonl")
    agent = Agent(OpenAICompatibleLLM(), tracer=tracer)
    mgr = SessionManager()
    w1 = mgr.create(name="window1")
    w2 = mgr.create(name="window2")

    def turn(session, text):
        print(f"\n===== [{session.name}] user: {text} =====")
        res = agent.run(session, text)
        print(f"----- [{session.name}] agent: {res.answer}  (turns={res.turns})")

    turn(w1, "What's the weather in Beijing today? Also add 'bring an umbrella' to my todo list.")
    turn(w2, "Help me outline a weekly report about the agent project, and add 'finish weekly report' to my todos.")
    turn(w1, "What did I ask you to remember earlier? List my todos.")
    turn(w2, "Add one more todo: 'review teammates PRs'. Then list them.")
    print("\n===== session snapshots =====")
    for snap in mgr.list():
        print(snap)
    return 0


if __name__ == "__main__":
    sys.exit(main())