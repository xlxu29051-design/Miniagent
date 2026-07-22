"""Parse the LLM's raw text output into a structured decision.
Protocol (single JSON object per turn):
  {"thought": "...", "action": {"tool": "calculator", "args": {...}}}
  {"thought": "...", "final": "answer"}
We DON'T use provider-native function-calling; parsing is implemented here.
Defensive: extracts the first balanced {...} even if wrapped in prose/```json."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional


class ParseError(Exception):
    """Raised when model output cannot be parsed."""


@dataclass
class Decision:
    thought: str = ""
    tool: Optional[str] = None
    args: Optional[Dict[str, Any]] = None
    final: Optional[str] = None

    @property
    def is_tool_call(self) -> bool:
        return self.tool is not None

    @property
    def is_final(self) -> bool:
        return self.final is not None


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json_object(text: str) -> str:
    fence = _FENCE_RE.search(text)
    if fence:
        candidate = fence.group(1).strip()
        if candidate.startswith("{"):
            return candidate
    start = text.find("{")
    if start == -1:
        raise ParseError("no JSON object found in model output")
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ParseError("unbalanced JSON object in model output")


def parse(text: str) -> Decision:
    if not text or not text.strip():
        raise ParseError("empty model output")
    raw = _extract_json_object(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ParseError("model output must be a JSON object")
    thought = str(data.get("thought", "")).strip()
    if "final" in data and data["final"] is not None:
        return Decision(thought=thought, final=str(data["final"]))
    action = data.get("action")
    if isinstance(action, dict) and action.get("tool"):
        args = action.get("args", {})
        if not isinstance(args, dict):
            raise ParseError("action.args must be an object")
        return Decision(thought=thought, tool=str(action["tool"]), args=args)
    if data.get("tool"):
        args = data.get("args", {})
        if not isinstance(args, dict):
            raise ParseError("args must be an object")
        return Decision(thought=thought, tool=str(data["tool"]), args=args)
    raise ParseError("output has neither a valid 'action' nor a 'final' field")