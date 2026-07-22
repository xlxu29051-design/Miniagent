"""Per-session to-do list tool. Stored on a session-scoped store so two
sessions keep independent lists (window1 vs window2)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import Tool, ToolError, ToolRegistry


@dataclass
class TodoStore:
    items: List[Dict[str, Any]] = field(default_factory=list)
    _next_id: int = 1

    def add(self, task: str) -> Dict[str, Any]:
        item = {"id": self._next_id, "task": task, "done": False}
        self._next_id += 1
        self.items.append(item)
        return item

    def list(self) -> List[Dict[str, Any]]:
        return list(self.items)

    def complete(self, item_id: int) -> Dict[str, Any]:
        for item in self.items:
            if item["id"] == item_id:
                item["done"] = True
                return item
        raise ToolError(f"no todo with id {item_id}")


def _make_todo_func(store: TodoStore):
    def todo(action: str, task: Optional[str] = None, id: Optional[int] = None) -> Dict[str, Any]:
        action = (action or "").lower().strip()
        if action == "add":
            if not task or not str(task).strip():
                raise ToolError("'task' is required when action='add'")
            return {"added": store.add(str(task).strip()), "all": store.list()}
        if action == "list":
            return {"all": store.list()}
        if action in ("complete", "done"):
            if id is None:
                raise ToolError("'id' is required when action='complete'")
            return {"completed": store.complete(int(id)), "all": store.list()}
        raise ToolError(f"unknown action '{action}', expected add|list|complete")
    return todo


def register(registry: ToolRegistry, store: TodoStore | None = None) -> None:
    store = store if store is not None else TodoStore()
    registry.register(Tool(
        name="todo",
        description="Manage the current session's to-do list. action='add' with 'task', "
        "action='list', or action='complete' with an 'id'.",
        parameters={"type": "object",
                    "properties": {"action": {"type": "string", "enum": ["add", "list", "complete"],
                                              "description": "The operation."},
                                   "task": {"type": "string", "description": "Task text (for add)."},
                                   "id": {"type": "integer", "description": "Todo id (for complete)."}},
                    "required": ["action"]},
        func=_make_todo_func(store)))