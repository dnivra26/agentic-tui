"""Assistant turn — a context manager for a single agent response.

Opening a Turn creates a live region; closing it commits the content
to permanent scrollback. The Turn composites multiple segments
(markdown blocks, tool call blocks, diff blocks) into a single render.
"""

from __future__ import annotations

import asyncio
import signal
from types import TracebackType
from typing import Any

from rich.console import Console, Group, RenderableType

from agentui._live_region import LiveRegion
from agentui._renderer import StreamingMarkdownRenderer


class Turn:
    """A single assistant turn in the conversation.

    Used as an async context manager. Opening a Turn starts a live region;
    closing it commits whatever was rendered to permanent scrollback.

    Supports multiple segment types (markdown, tool calls, diffs) that
    are composited into a single render via ``rich.console.Group``.

    Usage::

        async with session.assistant_turn() as turn:
            await turn.append_markdown("Hello **world**")
            async with turn.tool_call("search", {"q": "test"}) as tc:
                await tc.complete("3 results found")
            await turn.append_markdown("Done!")
    """

    def __init__(
        self,
        live_region: LiveRegion,
        console: Console,
    ) -> None:
        self._live_region = live_region
        self._console = console
        self._segments: list[Any] = []
        self._active_md: StreamingMarkdownRenderer | None = None
        self._cancelled: bool = False
        self._original_handler: Any = None
        self._task: asyncio.Task[Any] | None = None

    async def __aenter__(self) -> Turn:
        self._live_region.open()
        # Install interrupt handler (v0.3)
        self._original_handler = signal.getsignal(signal.SIGINT)
        self._task = asyncio.current_task()
        signal.signal(signal.SIGINT, self._handle_interrupt)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        # Restore original signal handler
        if self._original_handler is not None:
            signal.signal(signal.SIGINT, self._original_handler)
            self._original_handler = None
        # Always commit — even on exception — to prevent broken terminal state.
        self._flush_all()
        self._live_region.commit()
        # Suppress CancelledError if it was our interrupt
        if exc_type is asyncio.CancelledError and self._cancelled:
            return True
        return None

    def _handle_interrupt(self, signum: int, frame: Any) -> None:
        """SIGINT handler — cancel the current turn."""
        self._cancelled = True
        if self._task is not None:
            self._task.cancel()

    @property
    def cancelled(self) -> bool:
        """Whether this turn was cancelled via Ctrl-C."""
        return self._cancelled

    async def append_markdown(self, text: str) -> None:
        """Append a chunk of markdown text to this turn's output."""
        renderer = self._ensure_md_renderer()
        await renderer.append_async(text)

    def append_markdown_sync(self, text: str) -> None:
        """Synchronous version of append_markdown."""
        renderer = self._ensure_md_renderer()
        renderer.append(text)

    def tool_call(
        self, name: str, arguments: dict[str, Any] | str
    ) -> "ToolCallContext":
        """Create a tool call block. Returns an async context manager.

        Usage::

            async with turn.tool_call("search", {"q": "test"}) as tc:
                result = await execute_tool(...)
                await tc.complete(result)
        """
        from agentui._tool_call import ToolCallBlock, ToolCallContext

        self._active_md = None  # next markdown goes to a new renderer
        block = ToolCallBlock(name, arguments, on_update=self._rerender)
        self._segments.append(block)
        self._rerender()
        return ToolCallContext(block)

    def diff(self, path: str, patch: str) -> "DiffBlock":
        """Create and display a diff block. Returns the block.

        Usage::

            block = turn.diff("src/main.py", unified_diff_string)
            approved = await block.confirm()
        """
        from agentui._diff import DiffBlock

        self._active_md = None
        block = DiffBlock(path, patch, on_confirm=self._confirm_for_diff)
        self._segments.append(block)
        self._rerender()
        return block

    async def _confirm_for_diff(self) -> bool:
        """Temporarily commit the live region, prompt user, re-open."""
        from agentui._confirm import confirm_prompt
        from agentui._input import InputHandler

        self._live_region.commit()
        handler = InputHandler()
        result = await confirm_prompt(
            handler, self._console, "Apply this diff?"
        )
        self._live_region.open()
        self._rerender()
        return result

    def _ensure_md_renderer(self) -> StreamingMarkdownRenderer:
        """Get or create the active markdown renderer."""
        if self._active_md is None:
            self._active_md = StreamingMarkdownRenderer(
                on_update=self._rerender,
            )
            self._segments.append(self._active_md)
        return self._active_md

    def _rerender(self) -> None:
        """Rebuild the composite renderable and update the live region."""
        renderables: list[RenderableType] = []
        for seg in self._segments:
            if isinstance(seg, StreamingMarkdownRenderer):
                if seg.text:
                    renderables.append(seg.renderable)
            else:
                renderables.append(seg)
        if renderables:
            self._live_region.update(Group(*renderables))

    def _flush_all(self) -> None:
        """Flush all active renderers for a final render."""
        for seg in self._segments:
            if isinstance(seg, StreamingMarkdownRenderer):
                seg.flush()
        self._rerender()
