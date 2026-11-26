"""Tool name -> class. Only the tools named in agent.yaml are instantiated."""

from __future__ import annotations

from pathlib import Path

from forge.runtime.tools.base import Tool
from forge.runtime.tools.calculator import CalculatorTool
from forge.runtime.tools.csv_lookup import CsvLookupTool
from forge.runtime.tools.current_date import CurrentDateTool
from forge.runtime.tools.http_weather import WeatherTool
from forge.schemas.agent_def import ToolBinding

REGISTRY: dict[str, type[Tool]] = {
    "csv_lookup": CsvLookupTool,
    "calculator": CalculatorTool,
    "http_weather": WeatherTool,
    "current_date": CurrentDateTool,
}


def build_tools(bindings: list[ToolBinding], base_dir: Path) -> dict[str, Tool]:
    tools: dict[str, Tool] = {}
    for b in bindings:
        cls = REGISTRY.get(b.name)
        if cls is None:
            raise ValueError(f"unknown tool '{b.name}' in agent definition. Known tools: {sorted(REGISTRY)}")
        tools[b.name] = cls(config=b.config, base_dir=base_dir)
    return tools
