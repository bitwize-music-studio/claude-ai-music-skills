"""Progress indicators for long-running operations."""

import sys


class ProgressBar:
    """Simple progress bar for batch operations.

    Renders a progress bar on TTY stderr. Silent on non-TTY.

    Usage:
        bar = ProgressBar(total=10, prefix="Processing")
        for item in items:
            bar.update(item.name)
        bar.finish()
    """

    def __init__(self, total, prefix="", width=40):
        self.total = total
        self.prefix = prefix
        self.width = width
        self.current = 0
        self.is_tty = sys.stderr.isatty()

    def update(self, item_name=""):
        """Advance the progress bar by one step."""
        self.current += 1
        if self.is_tty:
            filled = int(self.width * self.current / self.total)
            bar = "\u2588" * filled + "\u2591" * (self.width - filled)
            line = f"\r{self.prefix} [{bar}] {self.current}/{self.total}"
            if item_name:
                # Truncate long names to fit terminal
                max_name = 30
                if len(item_name) > max_name:
                    item_name = item_name[:max_name - 3] + "..."
                line += f" {item_name}"
            sys.stderr.write(line)
            sys.stderr.flush()
            if self.current == self.total:
                sys.stderr.write("\n")

    def finish(self):
        """Ensure the progress bar ends with a newline."""
        if self.is_tty and self.current < self.total:
            sys.stderr.write("\n")
