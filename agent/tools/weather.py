"""Mock weather tool: deterministic pseudo-forecast derived from city name."""
from __future__ import annotations

from typing import Any, Dict

from .base import Tool, ToolError, ToolRegistry

_CONDITIONS = ["Sunny", "Cloudy", "Rainy", "Windy", "Snowy", "Foggy"]


def get_weather(city: str, date: str = "today") -> Dict[str, Any]:
    if not isinstance(city, str) or not city.strip():
        raise ToolError("city must be a non-empty string")
    seed = sum(ord(c) for c in city.lower())
    return {"city": city, "date": date, "temperature_c": 10 + (seed % 20),
            "condition": _CONDITIONS[seed % len(_CONDITIONS)], "humidity_percent": 40 + (seed % 50)}


def register(registry: ToolRegistry) -> None:
    registry.register(Tool(
        name="weather",
        description="Get the (mock) weather forecast for a city on a given date.",
        parameters={"type": "object",
                    "properties": {"city": {"type": "string", "description": "City name, e.g. 'Beijing'."},
                                   "date": {"type": "string",
                                            "description": "'today'/'tomorrow'/'YYYY-MM-DD'. Default 'today'."}},
                    "required": ["city"]},
        func=get_weather))