"""Confirmation prompts — yes/no, multi-choice, and free-text input."""

from __future__ import annotations

from collections.abc import Sequence

from rich.console import Console
from rich.text import Text

from agentui._input import InputHandler


async def confirm_prompt(
    input_handler: InputHandler,
    console: Console,
    message: str,
    *,
    default: bool = True,
) -> bool:
    """Yes/no confirmation prompt rendered in scrollback.

    Returns True for yes, False for no. Accepts y/yes/n/no (case-insensitive).
    Empty input returns the default.
    """
    hint = "[Y/n]" if default else "[y/N]"
    prompt_text = f"{message} {hint} "

    while True:
        response = await input_handler.prompt(prompt_text)
        response = response.strip().lower()
        if not response:
            return default
        if response in ("y", "yes"):
            return True
        if response in ("n", "no"):
            return False
        console.print("[dim]Please enter y or n.[/dim]")


async def choose_prompt(
    input_handler: InputHandler,
    console: Console,
    message: str,
    options: Sequence[str],
    *,
    default: int = 0,
) -> int:
    """Multi-choice selection prompt. Returns the index of the selected option.

    Displays numbered options. User types the number to select.
    Empty input returns the default.
    """
    console.print(f"[bold]{message}[/bold]")
    for i, option in enumerate(options):
        marker = ">" if i == default else " "
        style = "bold" if i == default else ""
        console.print(f"  {marker} [{i + 1}] {option}", style=style)

    while True:
        response = await input_handler.prompt(f"Choice [1-{len(options)}]: ")
        response = response.strip()
        if not response:
            return default
        try:
            idx = int(response) - 1
            if 0 <= idx < len(options):
                return idx
        except ValueError:
            pass
        console.print(f"[dim]Please enter a number between 1 and {len(options)}.[/dim]")


async def input_prompt(
    input_handler: InputHandler,
    console: Console,
    message: str,
    *,
    default: str = "",
) -> str:
    """Free-text input prompt with a default value.

    Empty input returns the default.
    """
    if default:
        prompt_text = f"{message} [{default}]: "
    else:
        prompt_text = f"{message}: "

    response = await input_handler.prompt(prompt_text)
    response = response.strip()
    return response if response else default
