"""LLM client wrappers. OpenAICompatibleLLM talks to any OpenAI-compatible
endpoint (OpenAI/DeepSeek/Kimi/阿里云百炼/vLLM...). Config via env:
    LLM_API_KEY (required), LLM_BASE_URL (optional), LLM_MODEL (optional).
MockLLM returns scripted responses for offline tests."""
from __future__ import annotations

import os
from typing import Callable, List, Optional, Protocol


class LLM(Protocol):
    def complete(self, messages: List[dict]) -> str: ...


class LLMError(Exception):
    """Raised when the LLM backend fails."""


class OpenAICompatibleLLM:
    def __init__(self, api_key=None, base_url=None, model=None,
                 temperature: float = 0.2, timeout: float = 60.0) -> None:
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise LLMError("no API key: set LLM_API_KEY (and optionally LLM_BASE_URL / LLM_MODEL)")
        self.base_url = base_url or os.getenv("LLM_BASE_URL") or None
        self.model = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        self.temperature = temperature
        self.timeout = timeout
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMError("the 'openai' package is required: pip install openai") from exc
        kwargs = {"api_key": self.api_key, "timeout": timeout}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)

    def complete(self, messages: List[dict]) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self.model, messages=messages, temperature=self.temperature)
        except Exception as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        if not resp.choices:
            raise LLMError("LLM returned no choices")
        content = resp.choices[0].message.content
        if content is None:
            raise LLMError("LLM returned empty content")
        return content


class MockLLM:
    """Deterministic LLM stand-in for tests."""
    def __init__(self, scripted: Optional[List[str]] = None,
                 responder: Optional[Callable[[List[dict]], str]] = None) -> None:
        self.scripted = list(scripted or [])
        self.responder = responder
        self.calls: List[List[dict]] = []

    def complete(self, messages: List[dict]) -> str:
        self.calls.append([dict(m) for m in messages])
        if self.responder is not None:
            return self.responder(messages)
        if not self.scripted:
            raise LLMError("MockLLM ran out of scripted responses")
        return self.scripted.pop(0)