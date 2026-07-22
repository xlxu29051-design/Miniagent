"""Session and context management. A Session owns isolated state: its own
conversation history (working memory), to-do list + tool registry, durable
facts (long-term memory recalled every turn), and a running summary from
compression. SessionManager maps ids to sessions so windows don't interfere.

Memory assembly each turn (build_messages):
  1. system prompt = base + tool schemas + facts + latest summary
  2. history = most recent messages
When history exceeds max_history_messages, older turns compress into summary."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .llm import LLM, LLMError
from .tools import ToolRegistry, build_default_registry
from .tools.todo import TodoStore


@dataclass
class Message:
    role: str  # system|user|assistant|tool
    content: str
    ts: float = field(default_factory=time.time)

    def as_llm(self) -> Dict[str, str]:
        role = self.role if self.role in ("system", "user", "assistant") else "user"
        return {"role": role, "content": self.content}


@dataclass
class SessionConfig:
    max_turns: int = 8               # max loop iterations per user message
    max_history_messages: int = 20   # trigger compression beyond this many
    keep_recent_messages: int = 8    # messages kept verbatim after compaction


class Session:
    def __init__(self, session_id: Optional[str] = None, name: str = "",
                 config: Optional[SessionConfig] = None) -> None:
        self.id = session_id or uuid.uuid4().hex
        self.name = name or self.id[:8]
        self.config = config or SessionConfig()
        self.todo_store = TodoStore()
        self.registry: ToolRegistry = build_default_registry(self.todo_store)
        self.history: List[Message] = []
        self.facts: List[str] = []
        self.summary: str = ""
        self.created_at = time.time()

    def add_message(self, role: str, content: str) -> None:
        self.history.append(Message(role=role, content=content))

    def remember_fact(self, fact: str) -> None:
        fact = fact.strip()
        if fact and fact not in self.facts:
            self.facts.append(fact)

    def system_prompt(self, base_prompt: str) -> str:
        parts = [base_prompt, "\nAvailable tools:", self.registry.render_for_prompt()]
        if self.facts:
            parts.append("\nRemembered facts about this session:")
            parts.extend(f"- {f}" for f in self.facts)
        if self.summary:
            parts.append("\nSummary of earlier conversation:\n" + self.summary)
        return "\n".join(parts)

    def build_messages(self, base_prompt: str) -> List[Dict[str, str]]:
        msgs: List[Dict[str, str]] = [{"role": "system", "content": self.system_prompt(base_prompt)}]
        msgs.extend(m.as_llm() for m in self.history)
        return msgs

    def needs_compression(self) -> bool:
        return len(self.history) > self.config.max_history_messages

    def compress(self, llm: Optional[LLM]) -> bool:
        if not self.needs_compression():
            return False
        keep = self.config.keep_recent_messages
        old, recent = self.history[:-keep], self.history[-keep:]
        if not old:
            return False
        transcript = "\n".join(f"{m.role}: {m.content}" for m in old)
        new_summary = self._summarize(transcript, llm)
        self.summary = (self.summary + "\n" + new_summary).strip() if self.summary else new_summary
        self.history = recent
        return True

    def _summarize(self, transcript: str, llm: Optional[LLM]) -> str:
        if llm is not None:
            prompt = [{"role": "system", "content": "Summarise the conversation into concise "
                       "bullet points capturing user goals, decisions, tool results and open "
                       "threads. Under 150 words."},
                      {"role": "user", "content": transcript}]
            try:
                return llm.complete(prompt).strip()
            except LLMError:
                pass
        return transcript[-800:]

    def snapshot(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "messages": len(self.history),
                "facts": list(self.facts), "todos": self.todo_store.list(),
                "has_summary": bool(self.summary)}


class SessionManager:
    def __init__(self, config: Optional[SessionConfig] = None) -> None:
        self._sessions: Dict[str, Session] = {}
        self._default_config = config

    def create(self, name: str = "", session_id: Optional[str] = None) -> Session:
        session = Session(session_id=session_id, name=name, config=self._default_config)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            raise KeyError(f"no session '{session_id}'")
        return self._sessions[session_id]

    def get_or_create(self, session_id: str, name: str = "") -> Session:
        if session_id in self._sessions:
            return self._sessions[session_id]
        return self.create(name=name, session_id=session_id)

    def list(self) -> List[Dict[str, Any]]:
        return [s.snapshot() for s in self._sessions.values()]