"""Slash command registry."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommandEntry:
    """A registered slash command."""

    name: str
    handler: Callable[..., Awaitable[None]]
    help_text: str = ""


class CommandRegistry:
    """Stores and retrieves slash command handlers."""

    def __init__(self) -> None:
        self._commands: dict[str, CommandEntry] = {}

    def register(
        self,
        name: str,
        handler: Callable[..., Awaitable[None]],
        *,
        help_text: str = "",
    ) -> None:
        """Register a command handler."""
        self._commands[name] = CommandEntry(
            name=name, handler=handler, help_text=help_text
        )

    def get(self, name: str) -> CommandEntry | None:
        """Look up a command by name."""
        return self._commands.get(name)

    def names(self) -> list[str]:
        """Return all registered command names."""
        return list(self._commands.keys())

    def entries(self) -> list[CommandEntry]:
        """Return all registered command entries."""
        return list(self._commands.values())
