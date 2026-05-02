"""Example: full-featured agentui demo.

Showcases streaming markdown, tool calls, diffs, confirmations,
slash commands, @-file picker, and interrupt handling (Ctrl-C).
"""

import asyncio

from agentui import Session


async def fake_stream(text: str):
    """Simulate an LLM streaming response, yielding word by word."""
    words = text.split(" ")
    for i, word in enumerate(words):
        yield word + (" " if i < len(words) - 1 else "")
        await asyncio.sleep(0.03)


SAMPLE_RESPONSE = """\
# Analysis Complete

I've looked at your code and found a few things:

## Key Findings

- The **main** function needs error handling
- There's a missing `return` statement in the parser
- The config loader should validate inputs

```python
def main():
    try:
        config = load_config()
        run(config)
    except ConfigError as e:
        print(f"Error: {e}")
        return 1
    return 0
```

Let me fix those issues for you."""


SAMPLE_DIFF = """\
--- a/src/main.py
+++ b/src/main.py
@@ -1,8 +1,12 @@
+import sys
+
 def main():
-    config = load_config()
-    run(config)
+    try:
+        config = load_config()
+        run(config)
+    except ConfigError as e:
+        print(f"Error: {e}", file=sys.stderr)
+        return 1
     return 0
-
-main()
+
+if __name__ == "__main__":
+    sys.exit(main())
"""


async def main():
    async with Session() as ui:
        ui.print("[bold green]agentui v0.3 demo[/bold green]")
        ui.print("[dim]Features: streaming markdown, tool calls, diffs, confirmations[/dim]")
        ui.print("[dim]Try: /help, @filename, Ctrl-C during streaming[/dim]\n")

        # Register a custom command
        @ui.command("echo", help_text="Echo back your input")
        async def cmd_echo(session, args):
            session.print(f"[cyan]{args}[/cyan]")

        @ui.command("demo", help_text="Run the full demo sequence")
        async def cmd_demo(session, args):
            await run_demo(session)

        while True:
            try:
                user_input = await ui.prompt("> ")
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input.strip():
                continue
            if user_input.startswith("/"):
                await ui.handle_command(user_input)
                continue

            # Default: stream a response with tool calls and diff
            await run_demo(ui)


async def run_demo(ui: Session):
    """Run the full demo: streaming markdown + tool call + diff."""
    async with ui.assistant_turn() as turn:
        # Stream markdown
        async for chunk in fake_stream(SAMPLE_RESPONSE):
            if turn.cancelled:
                break
            await turn.append_markdown(chunk)

        if turn.cancelled:
            ui.print("\n[yellow]Stream interrupted.[/yellow]")
            return

        # Tool call
        async with turn.tool_call("read_file", {"path": "src/main.py"}) as tc:
            await asyncio.sleep(0.5)  # simulate work
            await tc.complete("def main():\n    config = load_config()\n    run(config)")

        # Another markdown chunk
        await turn.append_markdown("\n\nHere's the proposed fix:\n")

        # Diff
        turn.diff("src/main.py", SAMPLE_DIFF)

    ui.print("")

    # Confirmation prompt
    approved = await ui.confirm("Apply this change?")
    if approved:
        ui.print("[green]Change applied![/green]\n")
    else:
        ui.print("[yellow]Change skipped.[/yellow]\n")


if __name__ == "__main__":
    asyncio.run(main())
