"""Terminal escape sequences and defaults."""

# Synchronized output (DEC private mode 2026)
SYNC_START: str = "\x1b[?2026h"
SYNC_END: str = "\x1b[?2026l"

# Cursor movement
CURSOR_UP_FMT: str = "\x1b[{}A"  # .format(n) to move up n lines
ERASE_LINE: str = "\x1b[2K"
CARRIAGE_RETURN: str = "\r"

# Cursor visibility
CURSOR_HIDE: str = "\x1b[?25l"
CURSOR_SHOW: str = "\x1b[?25h"

# Defaults
DEFAULT_REFRESH_RATE: float = 0.05  # 50ms = 20fps
