"""Input handler wrapping prompt_toolkit."""

from __future__ import annotations

from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory, History
from prompt_toolkit.patch_stdout import patch_stdout


class InputHandler:
    """Async input handler wrapping prompt_toolkit.

    Provides async prompt with history and reverse-i-search.
    Uses ``patch_stdout`` to prevent prompt corruption if other
    coroutines write to stdout.
    """

    def __init__(
        self,
        *,
        history: History | None = None,
        multiline: bool = False,
    ) -> None:
        self._history = history or InMemoryHistory()
        self._session: PromptSession[str] = PromptSession(
            history=self._history,
            multiline=multiline,
        )

    async def prompt(
        self,
        message: str = "> ",
        **kwargs: Any,
    ) -> str:
        """Get user input asynchronously."""
        with patch_stdout():
            result: str = await self._session.prompt_async(
                message,
                **kwargs,
            )
        return result

    def prompt_sync(self, message: str = "> ", **kwargs: Any) -> str:
        """Synchronous prompt for non-async usage."""
        return self._session.prompt(message, **kwargs)
