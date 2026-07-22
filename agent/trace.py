"""Execution tracing: each step recorded as a structured event, printed to
stderr and optionally appended to a JSONL file."""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional, TextIO


@dataclass
class TraceEvent:
    kind: str  # user|llm_request|thought|tool_call|tool_result|final|error|compact
    data: Any
    session_id: str = ""
    turn: int = 0
    ts: float = field(default_factory=time.time)


class Tracer:
    def __init__(self, session_id: str = "", stream: Optional[TextIO] = None,
                 file_path: Optional[str] = None, verbose: bool = True) -> None:
        self.session_id = session_id
        self.stream = stream if stream is not None else sys.stderr
        self.file_path = file_path
        self.verbose = verbose
        self.events: List[TraceEvent] = []

    def emit(self, kind: str, data: Any, turn: int = 0) -> TraceEvent:
        event = TraceEvent(kind=kind, data=data, session_id=self.session_id, turn=turn)
        self.events.append(event)
        if self.verbose:
            self._print(event)
        if self.file_path:
            self._append_file(event)
        return event

    def _print(self, event: TraceEvent) -> None:
        icon = {"user": "U", "llm_request": ">", "thought": "T", "tool_call": "*",
                "tool_result": "=", "final": "OK", "error": "!", "compact": "~"}.get(event.kind, ".")
        payload = event.data
        if not isinstance(payload, str):
            payload = json.dumps(payload, ensure_ascii=False)
        if len(payload) > 500:
            payload = payload[:500] + "..."
        print(f"[{event.session_id[:8]} t{event.turn}] {icon} {event.kind}: {payload}",
              file=self.stream, flush=True)

    def _append_file(self, event: TraceEvent) -> None:
        try:
            with open(self.file_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        except OSError:
            pass

    def as_list(self) -> List[dict]:
        return [asdict(e) for e in self.events]