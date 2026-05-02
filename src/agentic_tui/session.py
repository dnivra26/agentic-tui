"""Session — the main entry point for agentic_tui.

Owns the Rich Console, LiveRegion, and InputHandler. Provides the
public API for building an agent chat loop.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from types import TracebackType
from typing import Any

from prompt_toolkit.history import History
from rich.console import Console

from agentic_tui._commands import CommandRegistry
from agentic_tui._confirm import choose_prompt, confirm_prompt, input_prompt
from agentic_tui._input import InputHandler
from agentic_tui._live_region import LiveRegion
from agentic_tui.turn import Turn

CommandHandler = Callable[["Session", str], Awaitable[None]]


class Session:
    """Main entry point for agentic_tui.

    Usage::

        async with Session() as ui:
            user_input = await ui.prompt()
            async with ui.assistant_turn() as turn:
                await turn.append_markdown("# Hello")
    """

    def __init__(
        self,
        *,
        width: int | None = None,
        multiline_input: bool = False,
        history: History | None = None,
    ) -> None:
        self._console = Console(
            highlight=False,
            width=width,
            force_terminal=True,
        )
        self._live_region = LiveRegion(self._console)
        self._input = InputHandler(
            history=history,
            multiline=multiline_input,
        )
        self._commands = CommandRegistry()
        self._running: bool = False
        self._register_builtins()

    async def __aenter__(self) -> Session:
        self._running = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._running = False
        if self._live_region.is_active:
            self._live_region.commit()

    # --- Output ---

    def assistant_turn(self) -> Turn:
        """Create a new assistant turn.

        Returns a ``Turn`` to be used as ``async with ui.assistant_turn() as turn:``.
        """
        return Turn(
            live_region=self._live_region,
            console=self._console,
        )

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print to the console (committed immediately to scrollback).

        Delegates to ``rich.console.Console.print`` — supports Rich
        renderables, markup, etc.
        """
        self._console.print(*args, **kwargs)

    # --- Input ---

    async def prompt(self, message: str = "> ", **kwargs: Any) -> str:
        """Get user input with slash command and @-file completion."""
        from agentic_tui._completers import AgentCompleter

        completer = AgentCompleter(self._commands)
        return await self._input.prompt(message, completer=completer, **kwargs)

    # --- Confirmation prompts (v0.2) ---

    async def confirm(self, message: str, *, default: bool = True) -> bool:
        """Yes/no confirmation prompt."""
        if self._live_region.is_active:
            self._live_region.commit()
        return await confirm_prompt(self._input, self._console, message, default=default)

    async def choose(
        self, message: str, options: Sequence[str], *, default: int = 0
    ) -> int:
        """Multi-choice selection. Returns the index of the selected option."""
        if self._live_region.is_active:
            self._live_region.commit()
        return await choose_prompt(
            self._input, self._console, message, options, default=default
        )

    async def input(self, message: str, *, default: str = "") -> str:
        """Free-text input with a default value."""
        if self._live_region.is_active:
            self._live_region.commit()
        return await input_prompt(
            self._input, self._console, message, default=default
        )

    # --- Slash commands (v0.3) ---

    def command(
        self,
        name: str,
        *,
        help_text: str = "",
    ) -> Callable[[CommandHandler], CommandHandler]:
        """Decorator to register a slash command handler.

        Usage::

            @ui.command("greet", help_text="Say hello")
            async def greet(session, args):
                session.print(f"Hello, {args or 'world'}!")
        """

        def decorator(handler: CommandHandler) -> CommandHandler:
            self._commands.register(name, handler, help_text=help_text)
            return handler

        return decorator

    def register_command(
        self,
        name: str,
        handler: CommandHandler,
        *,
        help_text: str = "",
    ) -> None:
        """Register a slash command handler (non-decorator form)."""
        self._commands.register(name, handler, help_text=help_text)

    async def handle_command(self, command: str) -> None:
        """Dispatch a slash command to its registered handler."""
        parts = command.strip().lstrip("/").split(maxsplit=1)
        if not parts:
            return
        name = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        entry = self._commands.get(name)
        if entry is not None:
            await entry.handler(self, rest)
        else:
            self.print(f"[dim]Unknown command: /{name}. Type /help for available commands.[/dim]")

    def _register_builtins(self) -> None:
        """Register built-in slash commands."""
        self._commands.register("help", self._cmd_help, help_text="Show available commands")
        self._commands.register("quit", self._cmd_quit, help_text="Exit the application")
        self._commands.register("exit", self._cmd_quit, help_text="Exit the application")
        self._commands.register("clear", self._cmd_clear, help_text="Clear the screen")

    async def _cmd_help(self, session: Session, args: str) -> None:
        self.print("[bold]Available commands:[/bold]")
        for entry in self._commands.entries():
            help_text = f" - {entry.help_text}" if entry.help_text else ""
            self.print(f"  /{entry.name}{help_text}")

    async def _cmd_quit(self, session: Session, args: str) -> None:
        raise SystemExit(0)

    async def _cmd_clear(self, session: Session, args: str) -> None:
        self._console.clear()

    @property
    def console(self) -> Console:
        """Access the underlying Rich Console."""
        return self._console
