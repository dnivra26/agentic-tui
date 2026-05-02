"""Tool call block — structured rendering for agent tool invocations."""

from __future__ import annotations

import enum
import json
from collections.abc import Callable
from types import TracebackType
from typing import Any

from rich.console import Console, ConsoleOptions, RenderResult
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text


class ToolCallStatus(enum.Enum):
    """Status of a tool call."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


_STATUS_STYLES: dict[ToolCallStatus, tuple[str, str]] = {
    ToolCallStatus.PENDING: ("yellow", "\u25cb"),  # ○
    ToolCallStatus.RUNNING: ("blue", "\u25cf"),  # ●
    ToolCallStatus.DONE: ("green", "\u2714"),  # ✔
    ToolCallStatus.ERROR: ("red", "\u2718"),  # ✘
}


class ToolCallBlock:
    """Rich renderable for a tool call display.

    Renders as a bordered panel with:
    - Header: tool name + status badge
    - Arguments: JSON-pretty printed with syntax highlighting
    - Result: shown when complete/error

    Collapsible — after completion, can be toggled between
    expanded (showing args+result) and collapsed (header only).
    """

    def __init__(
        self,
        name: str,
        arguments: dict[str, Any] | str,
        *,
        on_update: Callable[[], None] | None = None,
    ) -> None:
        self._name = name
        if isinstance(arguments, str):
            self._args_str = arguments
        else:
            self._args_str = json.dumps(arguments, indent=2)
        self._status = ToolCallStatus.PENDING
        self._result: str | None = None
        self._collapsed = False
        self._on_update = on_update

    @property
    def status(self) -> ToolCallStatus:
        return self._status

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    @collapsed.setter
    def collapsed(self, value: bool) -> None:
        self._collapsed = value
        self._notify()

    def set_running(self) -> None:
        """Mark the tool call as running."""
        self._status = ToolCallStatus.RUNNING
        self._notify()

    def complete(self, result: str | None = None) -> None:
        """Mark the tool call as done with an optional result."""
        self._status = ToolCallStatus.DONE
        self._result = result
        self._collapsed = True
        self._notify()

    def error(self, message: str) -> None:
        """Mark the tool call as errored."""
        self._status = ToolCallStatus.ERROR
        self._result = message
        self._notify()

    def _notify(self) -> None:
        if self._on_update is not None:
            self._on_update()

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        color, icon = _STATUS_STYLES[self._status]
        # Header line
        header = Text()
        header.append(f" {icon} ", style=color)
        header.append(self._name, style="bold")
        header.append(f"  [{self._status.value}]", style=f"dim {color}")

        if self._collapsed:
            # Collapsed: just the header in a compact panel
            yield Panel(
                header,
                border_style="dim",
                padding=(0, 1),
            )
        else:
            # Expanded: header + args + optional result
            parts: list[Any] = [header, Text("")]

            # Arguments
            parts.append(Text("Arguments:", style="dim bold"))
            parts.append(
                Syntax(
                    self._args_str,
                    "json",
                    theme="monokai",
                    padding=1,
                )
            )

            # Result (if available)
            if self._result is not None:
                label_style = "red bold" if self._status == ToolCallStatus.ERROR else "dim bold"
                label = "Error:" if self._status == ToolCallStatus.ERROR else "Result:"
                parts.append(Text(label, style=label_style))
                result_style = "red" if self._status == ToolCallStatus.ERROR else ""
                parts.append(Text(self._result, style=result_style))

            from rich.console import Group

            yield Panel(
                Group(*parts),
                border_style=color,
                padding=(0, 1),
            )


class ToolCallContext:
    """Async context manager for a tool call within a Turn.

    Usage::

        async with turn.tool_call("search", {"q": "test"}) as tc:
            result = await run_search(...)
            await tc.complete(result)
    """

    def __init__(self, block: ToolCallBlock) -> None:
        self._block = block

    async def __aenter__(self) -> ToolCallContext:
        self._block.set_running()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None and self._block.status == ToolCallStatus.RUNNING:
            self._block.error(str(exc_val) if exc_val else "Unknown error")
        elif self._block.status == ToolCallStatus.RUNNING:
            self._block.complete()

    async def complete(self, result: str | None = None) -> None:
        """Mark the tool call as completed with a result."""
        self._block.complete(result)

    async def error(self, message: str) -> None:
        """Mark the tool call as errored."""
        self._block.error(message)
