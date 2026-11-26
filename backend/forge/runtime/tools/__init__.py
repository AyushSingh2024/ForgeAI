"""The tool registry (4 tools). Only the tools named in agent.yaml get instantiated."""

from forge.runtime.tools.base import Tool, ToolResult
from forge.runtime.tools.registry import REGISTRY, build_tools

__all__ = ["Tool", "ToolResult", "REGISTRY", "build_tools"]
