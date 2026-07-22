"""The agent runtime — the core loop, from scratch (no framework).
Per user message: build context -> ask LLM -> parse (thought + tool|final)
-> if final return; if tool run+observe and loop -> stop after max_turns."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from .llm import LLM, LLMError
from .parser import Decision, ParseError, parse
from .session import Session
from .tools.base import ToolError
from .trace import Tracer

SYSTEM_PROMPT = """You are a helpful assistant that can reason step by step and call tools.

On every turn you MUST reply with a SINGLE JSON object and nothing else, in one of these two shapes:

  To call a tool:
    {"thought": "<your reasoning>", "action": {"tool": "<tool_name>", "args": { ... }}}

  To answer the user directly (no more tools needed):
    {"thought": "<your reasoning>", "final": "<the answer for the user>"}

Rules:
- Use a tool only when it helps; for greetings or questions you can already answer, return "final" directly.
- Call ONE tool per turn. After you see its result you may call another or give the final answer.
- args must match the tool's parameter schema exactly.
- Never invent tool results; wait for the observation.
- Keep "final" answers concise and directly useful to the user."""


@dataclass
class AgentResult:
    answer: str
    turns: int
    session_id: str
    error: Optional[str] = None


class Agent:
    def __init__(self, llm: LLM, base_prompt: str = SYSTEM_PROMPT,
                 tracer: Optional[Tracer] = None) -> None:
        self.llm = llm
        self.base_prompt = base_prompt
        self.tracer = tracer

    def _trace(self, session: Session, kind: str, data, turn: int) -> None:
        if self.tracer is not None:
            self.tracer.session_id = session.id
            self.tracer.emit(kind, data, turn=turn)

    def run(self, session: Session, user_input: str) -> AgentResult:
        session.add_message("user", user_input)
        self._trace(session, "user", user_input, 0)
        if session.compress(self.llm):
            self._trace(session, "compact", "history compressed into summary", 0)
        max_turns = session.config.max_turns
        last_error: Optional[str] = None
        for turn in range(1, max_turns + 1):
            messages = session.build_messages(self.base_prompt)
            self._trace(session, "llm_request", {"messages": len(messages)}, turn)
            try:
                raw = self.llm.complete(messages)
            except LLMError as exc:
                last_error = f"LLM error: {exc}"
                self._trace(session, "error", last_error, turn)
                break
            try:
                decision: Decision = parse(raw)
            except ParseError as exc:
                last_error = f"parse error: {exc}"
                self._trace(session, "error", f"{last_error} | raw={raw[:200]}", turn)
                session.add_message("assistant", raw)
                session.add_message("user", "Your previous message was not valid JSON in the "
                                     "required format. Reply with exactly one JSON object using "
                                     "'action' or 'final'.")
                continue
            if decision.thought:
                self._trace(session, "thought", decision.thought, turn)
            if decision.is_final:
                session.add_message("assistant", raw)
                self._trace(session, "final", decision.final, turn)
                return AgentResult(answer=decision.final or "", turns=turn, session_id=session.id)
            self._trace(session, "tool_call", {"tool": decision.tool, "args": decision.args}, turn)
            session.add_message("assistant", raw)
            observation = self._run_tool(session, decision, turn)
            session.add_message("tool", f"Observation from {decision.tool}: {observation}")
        if last_error is None:
            last_error = f"reached max_turns ({max_turns}) without a final answer"
            self._trace(session, "error", last_error, max_turns)
        fallback = (f"Sorry, I couldn't complete that request ({last_error}). "
                    "Please try rephrasing or narrowing the question.")
        session.add_message("assistant", fallback)
        return AgentResult(answer=fallback, turns=max_turns, session_id=session.id, error=last_error)

    def _run_tool(self, session: Session, decision: Decision, turn: int) -> str:
        tool_name = decision.tool or ""
        args = decision.args or {}
        if not session.registry.has(tool_name):
            msg = (f"error: unknown tool '{tool_name}'. "
                   f"Available tools: {', '.join(session.registry.names())}")
            self._trace(session, "tool_result", msg, turn)
            return msg
        try:
            result = session.registry.get(tool_name).run(args)
            payload = json.dumps(result, ensure_ascii=False, default=str)
        except ToolError as exc:
            payload = f"error: {exc}"
        except Exception as exc:
            payload = f"unexpected error: {exc}"
        self._trace(session, "tool_result", payload, turn)
        return payload