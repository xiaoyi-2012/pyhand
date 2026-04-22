"""
Console output and logging utilities.

This module provides a `Console` class for displaying styled messages
with optional level and timestamp metadata. It supports colored output,
custom formatting, and optional file logging.

Main APIs
=========

- `Console`
- `console`
"""
import sys
import os
import time

from typing import Literal
from collections.abc import Callable

from console.color import Color, Colors


__all__ = ("Console", "console")



Level = Literal[0, 1, 2, 3, 4, 5, 6]

level_map: dict[int, tuple[str, Color]] = {
    0: ("TRACE",    Colors.BLACK),
    1: ("DEBUG",    Colors.GREY),
    2: ("INFO",     Colors.GREEN),
    3: ("WARN",     Colors.YELLOW),
    4: ("ERROR",    Colors.RED),
    5: ("FATAL",    Colors.BLUE),
    6: ("CRITICAL", Colors.MAGENTA)
}

class Console:
    """
    Display styled messages to the console with optional log metadata.
    """
    prefix: str
    suffix: str
    sep: str
    file: str | None
    name: str
    baselevel: int
    mode: Callable[[object], str]
    showlevel: bool
    showtimestamp: bool

    def __init__(
        self,
        prefix: str | None = None,
        suffix: str | None = "\n",
        sep: str | None = " ",
        file: str | None = None,
        baselevel: Level = 2,
        name: str = "console",
        mode: Literal["str", "repr"] = "str",
        showlevel: bool = False,
        showtimestamp: bool = False
    ) -> None:
        """
        Initialize the console with output and display options.
        """
        self.prefix = prefix or ""
        self.suffix = suffix or ""
        self.sep = sep or " "
        self.file = file
        self.baselevel = baselevel
        self.name = name
        self.mode = str if mode == "str" else repr
        self.showlevel = showlevel
        self.showtimestamp = showtimestamp

    def log(
        self,
        *data: object,
        color: Color | None = None,
        level: Level = 2,
        write_to_file: bool = True,
        flush: bool = True
    ) -> None:
        """Display a message in the console."""
        message = self.prefix + \
            self.sep.join(map(self.mode, data))

        if level < self.baselevel:
            return
        termout = ""
        if self.showlevel:
            lvltuple = level_map[level]
            termout += f"{lvltuple[1]}[{lvltuple[0]}]{Colors.RESET} "
        if self.showtimestamp:
            termout += time.strftime("%H:%M:%S ")
        termout += f"{color}{message}{Colors.RESET}" if color else message
        sys.stdout.write(termout + self.suffix)
        if flush:
            sys.stdout.flush()

        if not write_to_file or self.file is None:
            return

        try:
            with open(self.file, "a", encoding="utf-8") as f:
                f.write(
                    f"[{level_map[level][0]}] " + \
                    time.strftime("%H:%M:%S ")  + \
                    message + \
                    ("\n" if self.suffix.endswith("\n") else self.suffix)
                )
        except (OSError, ValueError) as e:
            print(f"{Colors.YELLOW}[WARN-FROM-{self.name}]{Colors.RESET} {e}")

    def set_baselevel(self, level: Level) -> None:
        """Set the minimum level that will be displayed."""
        self.baselevel = level

    def set_mode(self, mode: Literal["str", "repr"]) -> None:
        """Set the value formatting mode for output."""
        self.mode = str if mode == "str" else repr

    @staticmethod
    def clear() -> None:
        """
        Clear the active terminal screen.
        """
        os.system("cls" if os.name == "nt" else "clear")

console = Console()
