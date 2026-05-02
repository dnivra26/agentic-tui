"""Diff block — unified diff rendering with syntax highlighting."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.panel import Panel
from rich.text import Text


class DiffBlock:
    """Rich renderable for a unified diff display.

    Renders as a bordered panel with:
    - File path header
    - Per-hunk rendering with line numbers
    - Green for additions, red for deletions, dim for context

    Supports an async ``confirm()`` method that prompts the user
    to accept or reject the diff.
    """

    def __init__(
        self,
        path: str,
        patch: str,
        *,
        on_confirm: Callable[[], Awaitable[bool]] | None = None,
    ) -> None:
        self._path = path
        self._patch = patch
        self._on_confirm = on_confirm
        self._approved: bool | None = None
        self._hunks = _parse_hunks(patch)

    @property
    def path(self) -> str:
        return self._path

    @property
    def approved(self) -> bool | None:
        """None if not yet confirmed, True/False after."""
        return self._approved

    async def confirm(self) -> bool:
        """Prompt the user to accept or reject this diff.

        Delegates to the ``on_confirm`` callback provided by the Turn,
        which handles committing/re-opening the live region.
        """
        if self._on_confirm is not None:
            self._approved = await self._on_confirm()
        else:
            self._approved = True
        return self._approved

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        # Build header
        header = Text()
        header.append(" \u2502 ", style="dim")  # │
        header.append(self._path, style="bold")
        if self._approved is True:
            header.append("  \u2714 approved", style="green")
        elif self._approved is False:
            header.append("  \u2718 rejected", style="red")

        # Build diff content
        lines: list[Text] = []
        for hunk in self._hunks:
            # Hunk header
            hunk_header = Text(hunk.header, style="cyan dim")
            lines.append(hunk_header)
            # Diff lines
            for dl in hunk.lines:
                line = Text()
                if dl.old_no is not None:
                    line.append(f"{dl.old_no:>4} ", style="dim")
                else:
                    line.append("     ", style="dim")
                if dl.new_no is not None:
                    line.append(f"{dl.new_no:>4} ", style="dim")
                else:
                    line.append("     ", style="dim")

                if dl.kind == "+":
                    line.append("+ ", style="green bold")
                    line.append(dl.content, style="green")
                elif dl.kind == "-":
                    line.append("- ", style="red bold")
                    line.append(dl.content, style="red")
                else:
                    line.append("  ", style="dim")
                    line.append(dl.content, style="dim")
                lines.append(line)

        if lines:
            content = Group(header, Text(""), *lines)
        else:
            content = header

        yield Panel(
            content,
            border_style="cyan",
            padding=(0, 1),
        )


class _DiffLine:
    """A single line in a diff hunk."""

    __slots__ = ("kind", "content", "old_no", "new_no")

    def __init__(
        self, kind: str, content: str, old_no: int | None, new_no: int | None
    ) -> None:
        self.kind = kind  # "+", "-", or " "
        self.content = content
        self.old_no = old_no
        self.new_no = new_no


class _Hunk:
    """A parsed hunk from a unified diff."""

    __slots__ = ("header", "lines")

    def __init__(self, header: str) -> None:
        self.header = header
        self.lines: list[_DiffLine] = []


def _parse_hunks(patch: str) -> list[_Hunk]:
    """Parse a unified diff string into hunks with line numbers."""
    hunks: list[_Hunk] = []
    current: _Hunk | None = None
    old_line = 0
    new_line = 0

    for raw_line in patch.splitlines():
        if raw_line.startswith("@@"):
            # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
            current = _Hunk(raw_line)
            hunks.append(current)
            # Extract line numbers
            try:
                parts = raw_line.split("@@")[1].strip()
                old_part, new_part = parts.split(" ")
                old_line = int(old_part.split(",")[0].lstrip("-"))
                new_line = int(new_part.split(",")[0].lstrip("+"))
            except (ValueError, IndexError):
                old_line = 1
                new_line = 1
        elif raw_line.startswith("---") or raw_line.startswith("+++"):
            # File headers — skip, we show path in panel header
            continue
        elif current is not None:
            if raw_line.startswith("+"):
                current.lines.append(
                    _DiffLine("+", raw_line[1:], None, new_line)
                )
                new_line += 1
            elif raw_line.startswith("-"):
                current.lines.append(
                    _DiffLine("-", raw_line[1:], old_line, None)
                )
                old_line += 1
            else:
                content = raw_line[1:] if raw_line.startswith(" ") else raw_line
                current.lines.append(
                    _DiffLine(" ", content, old_line, new_line)
                )
                old_line += 1
                new_line += 1

    return hunks
