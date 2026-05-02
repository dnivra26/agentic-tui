"""Live region manager — the core of agentic_tui.

Manages an in-place updateable region of terminal output using
synchronized output (DEC private mode 2026) for flicker-free rendering.

When committed, the content becomes permanent scrollback — no erase,
no rewrite. The terminal's native scrollback, copy-paste, and search
keep working.
"""

from __future__ import annotations

import sys
from io import StringIO

from rich.console import Console, RenderableType

from agentic_tui._constants import (
    CARRIAGE_RETURN,
    CURSOR_HIDE,
    CURSOR_SHOW,
    CURSOR_UP_FMT,
    ERASE_LINE,
    SYNC_END,
    SYNC_START,
)


class LiveRegion:
    """Manages an in-place updateable region of terminal output.

    Wraps render cycles in synchronized output sequences (CSI ?2026h/l)
    so the terminal buffers all updates and displays them atomically.

    Tracks how many lines were last rendered so it can move the cursor
    back up and overwrite on the next update.
    """

    def __init__(
        self,
        console: Console,
    ) -> None:
        self._console = console
        self._active: bool = False
        self._last_line_count: int = 0

    @property
    def is_active(self) -> bool:
        """Whether the live region is currently open for updates."""
        return self._active

    def open(self) -> None:
        """Begin a new live region. Hides cursor."""
        if self._active:
            self.commit()
        self._active = True
        self._last_line_count = 0
        self._raw_write(CURSOR_HIDE)

    def update(self, renderable: RenderableType) -> None:
        """Rewrite the live region content in-place.

        The entire erase+render cycle is wrapped in synchronized output
        so it appears as a single atomic frame to the terminal.
        """
        if not self._active:
            return

        # Render content to a string to get the ANSI output and measure lines.
        rendered = self._capture(renderable)
        new_line_count = self._count_rendered_lines(rendered)

        # Build the atomic frame:
        # 1. Begin synchronized output
        # 2. Move cursor up and erase previous content
        # 3. Write new content
        # 4. End synchronized output
        parts: list[str] = [SYNC_START]

        # Move cursor back to the start of the previous render
        if self._last_line_count > 0:
            parts.append(CARRIAGE_RETURN)
            # Move up (last_line_count - 1) lines — we're already on the last line
            if self._last_line_count > 1:
                parts.append(CURSOR_UP_FMT.format(self._last_line_count - 1))
            # Erase each line
            for i in range(self._last_line_count):
                parts.append(ERASE_LINE)
                if i < self._last_line_count - 1:
                    parts.append("\n")
            # Move back to the top of the erased region
            if self._last_line_count > 1:
                parts.append(CARRIAGE_RETURN)
                parts.append(CURSOR_UP_FMT.format(self._last_line_count - 1))

        # Write the new content
        parts.append(rendered)

        # End synchronized output
        parts.append(SYNC_END)

        # Single write + flush = one atomic frame
        self._raw_write("".join(parts))

        self._last_line_count = new_line_count

    def commit(self) -> None:
        """Finalize the live region.

        The content already on screen becomes permanent scrollback.
        We just stop tracking and show the cursor again.
        """
        if not self._active:
            return
        self._active = False
        self._last_line_count = 0
        self._raw_write(CURSOR_SHOW)

    def _capture(self, renderable: RenderableType) -> str:
        """Render a Rich renderable to an ANSI string.

        Uses a temporary Console with the same width as the real one
        so line wrapping is accurate.
        """
        buf = StringIO()
        temp_console = Console(
            file=buf,
            width=self._console.width,
            force_terminal=True,
            color_system=self._console.color_system,
            highlight=False,
        )
        temp_console.print(renderable, end="")
        return buf.getvalue()

    @staticmethod
    def _count_rendered_lines(rendered: str) -> int:
        """Count terminal lines in a rendered ANSI string.

        Counts newline characters. A trailing newline doesn't add
        an extra line (the cursor is on the last content line).
        """
        if not rendered:
            return 0
        # Number of lines = number of newlines + 1,
        # but if it ends with a newline the cursor is at the start
        # of a new blank line, so that counts.
        count = rendered.count("\n")
        if not rendered.endswith("\n"):
            count += 1
        return count

    def _raw_write(self, data: str) -> None:
        """Write raw string directly to the console's output and flush."""
        f = self._console.file or sys.stdout
        f.write(data)
        f.flush()
