"""Tool base classes and a lightweight registry. Each tool declares name,
description and a JSON-schema of its parameters; the registry exposes schemas
to the LLM so it decides which tool to call."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


class ToolError(Exception):
    """Raised when a tool fails in an expected way (bad args, runtime error)."""


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON-schema
    func: Callable[..., Any]

    def schema(self) -> Dict[str, Any]:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}

    def _validate(self, args: Dict[str, Any]) -> None:
        props = self.parameters.get("properties", {})
        required = self.parameters.get("required", [])
        for key in required:
            if key not in args:
                raise ToolError(f"missing required argument '{key}' for tool '{self.name}'")
        for key in args:
            if props and key not in props:
                raise ToolError(f"unknown argument '{key}' for tool '{self.name}'")

    def run(self, args: Dict[str, Any]) -> Any:
        if not isinstance(args, dict):
            raise ToolError(f"tool arguments must be an object, got {type(args).__name__}")
        self._validate(args)
        try:
            return self.func(**args)
        except ToolError:
            raise
        except TypeError as exc:
            raise ToolError(f"invalid arguments for tool '{self.name}': {exc}") from exc
        except Exception as exc:
            raise ToolError(f"tool '{self.name}' failed: {exc}") from exc


@dataclass
class ToolRegistry:
    _tools: Dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolError(f"unknown tool '{name}'")
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> List[str]:
        return list(self._tools)

    def schemas(self) -> List[Dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    def render_for_prompt(self) -> str:
        import json
        lines: List[str] = []
        for t in self._tools.values():
            lines.append(f"- {t.name}: {t.description}")
            lines.append(f"  parameters: {json.dumps(t.parameters, ensure_ascii=False)}")
        return "\n".join(lines)


def build_default_registry(session_store: Any = None) -> ToolRegistry:
    from .calculator import register as register_calculator
    from .search import register as register_search
    from .todo import register as register_todo
    from .weather import register as register_weather
    registry = ToolRegistry()
    register_calculator(registry)
    register_search(registry)
    register_weather(registry)
    register_todo(registry, session_store)
    return registry