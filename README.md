# agentic_tui

A small, opinionated Python library for building coding-agent terminal UIs.

Streaming markdown, tool-call blocks, unified diffs, confirmation prompts, slash commands, and an @-file picker — all in linear scrollback with zero flicker.

## Why

Every coding agent — Claude Code, Codex, Aider, Toad — converges on the same terminal UX: linear scrollback, streaming markdown that updates in place without flicker, collapsible tool calls, unified diffs, slash commands, an @-file picker. But in Python, no library delivers this shape as a coherent primitive.

The options today are bad:

- **Textual** is a full TUI framework optimized for multi-pane applications. It owns the alt-buffer, breaks native terminal selection, and forces a CSS/widget mental model that's overkill for a chat-shaped agent loop.
- **prompt\_toolkit + Rich** in REPL mode preserves scrollback and copy-paste, but offers no agent-specific primitives. Every project reinvents streaming markdown, tool-call panels, diff rendering, confirmation prompts, and slash commands from scratch.

Other ecosystems have closed this gap — `pi-tui` in TypeScript (powering Mastra Code), `claude-code-kit` (extracted Claude Code components), Bubble Tea + Lip Gloss in Go, Ratatui in Rust. Python had no equivalent.

agentic_tui exists because building a polished agent UI shouldn't require 2000 lines of rendering plumbing. It should take 30.

## Install

```bash
pip install agentic-tui
```

For .gitignore-aware @-file completion:

```bash
pip install agentic-tui[gitignore]
```

## Quick Start

```python
import asyncio
from agentic_tui import Session

async def main():
    async with Session() as ui:
        while True:
            user_input = await ui.prompt("> ")
            if user_input.startswith("/"):
                await ui.handle_command(user_input)
                continue

            async with ui.assistant_turn() as turn:
                async for chunk in your_llm.stream(user_input):
                    await turn.append_markdown(chunk.text)

asyncio.run(main())
```

That's a working agent chat UI in 14 lines.

## Features

### Streaming Markdown

Accepts an async iterator of string chunks. Updates in place using synchronized output (CSI ?2026h/l) — zero flicker on modern terminals, graceful degradation elsewhere. When the turn completes, content commits to permanent scrollback.

```python
async with ui.assistant_turn() as turn:
    async for chunk in stream:
        await turn.append_markdown(chunk)
```

### Tool Call Blocks

Structured rendering with name, JSON-pretty arguments, status badge (pending/running/done/error), and result. Collapses automatically after completion.

```python
async with turn.tool_call("search", {"query": "test", "limit": 5}) as tc:
    result = await execute_search(...)
    await tc.complete(result)
```

### Unified Diffs

Colored diff rendering with line numbers, green additions, red deletions. Supports an inline confirmation prompt.

```python
block = turn.diff("src/main.py", unified_diff_string)
approved = await block.confirm()  # prompts user inline
```

### Confirmation Prompts

Yes/no, multi-choice, and free-text — all keyboard-driven, rendered in scrollback.

```python
if await ui.confirm("Apply changes?"):
    apply()

choice = await ui.choose("Pick a model:", ["gpt-4", "claude", "local"])

name = await ui.input("Project name:", default="my-project")
```

### Slash Commands

Register handlers and get tab-completion for free. Built-ins: `/help`, `/quit`, `/clear`.

```python
@ui.command("model", help_text="Switch the active model")
async def cmd_model(session, args):
    session.print(f"Switched to {args}")
```

### @-File Picker

Type `@` in the prompt to fuzzy-match files in the current directory. Respects `.gitignore` (uses `pathspec` if installed, falls back to basic glob matching).

### Interrupt Handling

Ctrl-C during streaming cancels the in-flight turn. Partial content commits cleanly to scrollback — terminal state is never corrupted.

```python
async with ui.assistant_turn() as turn:
    async for chunk in stream:
        if turn.cancelled:
            break
        await turn.append_markdown(chunk)
```

## Architecture

agentic_tui is a thin orchestration layer over two battle-tested libraries:

- **Rich** — rendering (markdown, syntax highlighting, panels, tables)
- **prompt\_toolkit** — input (history, key bindings, completion)

The core innovation is a **scrollback-aware live region manager**. Only the currently-streaming turn uses a managed region wrapped in synchronized output sequences. When the turn completes, the content becomes ordinary terminal scrollback. Native copy-paste, tmux scrollback, and Cmd-F search keep working.

```
User application (agent loop)
         |
         | render calls + input prompts
         v
agentic_tui
  ┌────────────┐   ┌───────────────┐
  │ Live region │   │ Input session  │
  │ manager     │   │ (slash cmds,   │
  │ (sync out)  │   │  file picker)  │
  └──────┬──────┘   └───────┬───────┘
         │                  │
  ┌──────▼──────┐   ┌───────▼───────┐
  │    Rich     │   │ prompt_toolkit │
  │   Console   │   │ PromptSession  │
  └─────────────┘   └───────────────┘
```

## API Reference

### Session

The main entry point. Async context manager.

| Method | Description |
|---|---|
| `prompt(message)` | Async user input with slash command and @-file completion |
| `assistant_turn()` | Returns a `Turn` async context manager |
| `print(*args)` | Print to scrollback (delegates to Rich Console) |
| `confirm(message, default)` | Yes/no prompt, returns `bool` |
| `choose(message, options, default)` | Multi-choice, returns `int` index |
| `input(message, default)` | Free-text input, returns `str` |
| `handle_command(command)` | Dispatch a `/command` to its handler |
| `command(name, help_text)` | Decorator to register a slash command |
| `register_command(name, handler)` | Non-decorator command registration |

### Turn

A single assistant response. Async context manager opened via `session.assistant_turn()`.

| Method | Description |
|---|---|
| `append_markdown(text)` | Stream a markdown chunk |
| `tool_call(name, args)` | Returns a `ToolCallContext` async context manager |
| `diff(path, patch)` | Render a unified diff block, returns `DiffBlock` |
| `cancelled` | `bool` — whether Ctrl-C was pressed |

### ToolCallContext

Async context manager for tool execution within a turn.

| Method | Description |
|---|---|
| `complete(result)` | Mark done with optional result string |
| `error(message)` | Mark as errored |

### DiffBlock

Rendered diff with optional inline confirmation.

| Method | Description |
|---|---|
| `confirm()` | Async — prompts user to accept/reject, returns `bool` |
| `approved` | `bool | None` — confirmation result |

## Non-Goals

- **Not a general TUI framework.** Use Textual for multi-pane dashboards.
- **Not an agent framework.** No LLM client, no tool dispatcher, no memory store. The library renders; you drive.
- **Not alt-buffer / full-screen.** The whole point is to preserve native scrollback.

## Requirements

- Python 3.13+
- `rich >= 13.0`
- `prompt-toolkit >= 3.0`

## License

MIT
