"""Tool interface. Every run() validates args, times itself and never raises."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ValidationError


class ToolResult(BaseModel):
    ok: bool
    data: Any = None
    error: str | None = None
    latency_ms: int = 0


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    Args: ClassVar[type[BaseModel]]

    def __init__(self, config: dict[str, Any] | None = None, base_dir: Path | None = None):
        self.config = config or {}
        self.base_dir = base_dir or Path(".")

    def run(self, args: dict[str, Any] | None) -> ToolResult:
        start = time.perf_counter()
        try:
            parsed = self.Args.model_validate(args or {})
            data = self._run(parsed)
            ok, err = True, None
        except ValidationError as exc:
            data, ok, err = None, False, f"invalid arguments: {exc.errors()[:3]}"
        except Exception as exc:  # noqa: BLE001 - a tool error is reported to the model, not raised
            data, ok, err = None, False, f"{exc.__class__.__name__}: {exc}"
        return ToolResult(ok=ok, data=data, error=err, latency_ms=int((time.perf_counter() - start) * 1000))

    @abstractmethod
    def _run(self, args: BaseModel) -> Any: ...

    def spec(self) -> dict[str, Any]:
        schema = self.Args.model_json_schema()
        schema.pop("title", None)
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                                                 "parameters": schema}}

    def describe(self) -> str:
        return f"- {self.name}: {self.description} Arguments JSON schema: {self.spec()['function']['parameters']}"
