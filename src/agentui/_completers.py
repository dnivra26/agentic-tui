"""Combined completer for slash commands and @-file references."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterable
from pathlib import Path

from prompt_toolkit.completion import CompleteEvent, Completion, Completer
from prompt_toolkit.document import Document

from agentui._commands import CommandRegistry

# Optional pathspec for .gitignore parsing
try:
    import pathspec

    _HAS_PATHSPEC = True
except ImportError:
    _HAS_PATHSPEC = False

# Max directory depth for file walking
_MAX_DEPTH = 4
# Max files to return to avoid slow completions
_MAX_FILES = 200


class AgentCompleter(Completer):
    """Combined completer for slash commands and @-file references.

    - If the input starts with ``/`` and the cursor is in the first word,
      completes against registered command names.
    - If the input contains ``@`` before the cursor, completes file paths
      relative to the current working directory, respecting ``.gitignore``.
    """

    def __init__(
        self,
        command_registry: CommandRegistry,
        *,
        cwd: Path | None = None,
        use_gitignore: bool = True,
    ) -> None:
        self._commands = command_registry
        self._cwd = cwd or Path.cwd()
        self._use_gitignore = use_gitignore
        self._gitignore_spec: pathspec.PathSpec | None = None
        self._gitignore_patterns: list[str] | None = None
        self._load_gitignore()

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        text = document.text_before_cursor

        # Slash command completion: /prefix at the start of input
        if text.startswith("/"):
            word = text[1:]  # remove the /
            if " " not in word:
                yield from self._complete_commands(word)
                return

        # @-file completion: find the last @ before cursor
        at_pos = text.rfind("@")
        if at_pos >= 0:
            # Only trigger if @ is at start or preceded by a space
            if at_pos == 0 or text[at_pos - 1] == " ":
                query = text[at_pos + 1 :]
                yield from self._complete_files(query)
                return

    def _complete_commands(self, prefix: str) -> Iterable[Completion]:
        """Match command names against prefix."""
        for name in self._commands.names():
            if name.startswith(prefix):
                entry = self._commands.get(name)
                meta = entry.help_text if entry else ""
                yield Completion(
                    name,
                    start_position=-len(prefix),
                    display_meta=meta,
                )

    def _complete_files(self, query: str) -> Iterable[Completion]:
        """Match file paths against query, respecting .gitignore."""
        files = self._walk_files()
        query_lower = query.lower()
        count = 0
        for path in files:
            if count >= _MAX_FILES:
                break
            path_lower = path.lower()
            # Fuzzy: all query chars appear in order in the path
            if _fuzzy_match(query_lower, path_lower):
                yield Completion(
                    path,
                    start_position=-len(query),
                )
                count += 1

    def _walk_files(self) -> list[str]:
        """Walk cwd recursively up to _MAX_DEPTH, filtered by gitignore."""
        results: list[str] = []
        self._walk_dir(self._cwd, self._cwd, 0, results)
        results.sort()
        return results

    def _walk_dir(
        self, base: Path, current: Path, depth: int, results: list[str]
    ) -> None:
        if depth > _MAX_DEPTH or len(results) >= _MAX_FILES * 2:
            return
        try:
            entries = sorted(os.scandir(current), key=lambda e: e.name)
        except PermissionError:
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            rel = os.path.relpath(entry.path, base)
            if self._is_ignored(rel, entry.is_dir()):
                continue
            if entry.is_file():
                results.append(rel)
            elif entry.is_dir():
                self._walk_dir(base, Path(entry.path), depth + 1, results)

    def _is_ignored(self, rel_path: str, is_dir: bool) -> bool:
        """Check if a path should be ignored based on .gitignore."""
        if not self._use_gitignore:
            return False
        if _HAS_PATHSPEC and self._gitignore_spec is not None:
            check_path = rel_path + "/" if is_dir else rel_path
            return self._gitignore_spec.match_file(check_path)
        if self._gitignore_patterns is not None:
            return _basic_gitignore_match(rel_path, is_dir, self._gitignore_patterns)
        return False

    def _load_gitignore(self) -> None:
        """Load .gitignore patterns from cwd."""
        gitignore_path = self._cwd / ".gitignore"
        if not gitignore_path.is_file():
            return
        try:
            lines = gitignore_path.read_text().splitlines()
            patterns = [
                line.strip()
                for line in lines
                if line.strip() and not line.strip().startswith("#")
            ]
        except OSError:
            return

        if _HAS_PATHSPEC:
            self._gitignore_spec = pathspec.PathSpec.from_lines(
                "gitwildmatch", patterns
            )
        else:
            self._gitignore_patterns = patterns


def _fuzzy_match(query: str, target: str) -> bool:
    """Check if all characters in query appear in order in target."""
    if not query:
        return True
    qi = 0
    for ch in target:
        if ch == query[qi]:
            qi += 1
            if qi == len(query):
                return True
    return False


def _basic_gitignore_match(
    rel_path: str, is_dir: bool, patterns: list[str]
) -> bool:
    """Basic .gitignore matching without pathspec.

    Handles simple glob patterns: ``*.ext``, ``dirname/``, ``**/pattern``.
    """
    parts = rel_path.replace("\\", "/").split("/")
    for pattern in patterns:
        # Directory-only pattern
        if pattern.endswith("/"):
            dir_pattern = pattern.rstrip("/")
            if is_dir and fnmatch.fnmatch(parts[-1], dir_pattern):
                return True
            if any(fnmatch.fnmatch(part, dir_pattern) for part in parts[:-1]):
                return True
            continue
        # ** prefix
        if pattern.startswith("**/"):
            sub = pattern[3:]
            if any(fnmatch.fnmatch(part, sub) for part in parts):
                return True
            continue
        # Simple pattern — match against filename or full path
        if fnmatch.fnmatch(parts[-1], pattern):
            return True
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False
