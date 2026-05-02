"""Streaming markdown renderer.

Accumulates text chunks and re-renders the full buffer as Rich Markdown.
Decoupled from LiveRegion — notifies its owner via an ``on_update`` callback
so the owner (Turn) can compose multiple segments into a single render.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from rich.markdown import Markdown

from agentic_tui._constants import DEFAULT_REFRESH_RATE


class StreamingMarkdownRenderer:
    """Accumulates text chunks and renders them as Rich Markdown.

    On each append, the full accumulated text is re-parsed as Markdown.
    This ensures proper structure (e.g., a code block that opens in
    chunk 3 and closes in chunk 7 renders correctly at every step).

    A time-based throttle skips renders when chunks arrive faster than
    the refresh rate. Call ``flush()`` to force a final render.
    """

    def __init__(
        self,
        *,
        on_update: Callable[[], None] | None = None,
        refresh_rate: float = DEFAULT_REFRESH_RATE,
    ) -> None:
        self._on_update = on_update
        self._refresh_rate = refresh_rate
        self._buffer: str = ""
        self._dirty: bool = False
        self._last_render_time: float = 0.0

    @property
    def renderable(self) -> Markdown:
        """Return the current buffer as a Rich Markdown renderable."""
        return Markdown(self._buffer)

    def append(self, text: str) -> None:
        """Add a text chunk. Notifies owner if enough time has elapsed."""
        self._buffer += text
        now = time.monotonic()
        if now - self._last_render_time >= self._refresh_rate:
            self._notify()
            self._last_render_time = now
            self._dirty = False
        else:
            self._dirty = True

    async def append_async(self, text: str) -> None:
        """Async version of append. Yields to the event loop after render."""
        self.append(text)
        await asyncio.sleep(0)

    def flush(self) -> None:
        """Force a final render if there are un-rendered changes."""
        if self._dirty:
            self._notify()
            self._dirty = False

    def _notify(self) -> None:
        """Notify the owner that content has changed."""
        if self._on_update is not None:
            self._on_update()

    @property
    def text(self) -> str:
        """The raw accumulated text."""
        return self._buffer
