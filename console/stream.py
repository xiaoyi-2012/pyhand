# pylint: disable=invalid-name
import sys

from typing import TextIO, Callable, Self


__all__ = ("Stream", "std", "pyout")


class StreamMode:
    """
    Represent a formatting mode for stream output.
    """
    name: str
    func: Callable
    match_cls: type

    def __new__(
        cls,
        name: str | None,
        func: Callable,
        match_cls: type = object
    ) -> Self:
        self = super().__new__(cls)
        self.name = name or "Stream mode"
        self.func = func
        self.match_cls = match_cls
        return self

    def __call__(self, value: object) -> str:
        """
        Format `value` using this mode.
        """
        if isinstance(value, self.match_cls):
            return str(self.func(value))
        # Type mismatch, use the original method to handle.
        return str(value)


class std:
    """
    Provide predefined stream manipulators and constants.
    """
    endl       = type("_endl",  (), {})()
    flush      = type("_flush", (), {})()

    string     = StreamMode("string",     str)
    repr       = StreamMode("repr",       repr)
    hex        = StreamMode("hex",        hex, int)
    oct        = StreamMode("oct",        oct, int)
    bin        = StreamMode("bin",        bin, int)
    titlecase  = StreamMode("title",      str.title)
    uppercase  = StreamMode("upper",      str.upper)
    lowercase  = StreamMode("lowercase",  str.lower)
    capitalize = StreamMode("capitalize", str.capitalize)
    swapcase   = StreamMode("swapcase",   str.swapcase)


# C++
class Stream:
    """
    Write values to a text stream with C++-style operators.
    """
    file: TextIO
    buf: list[str]
    buf_size: int
    flush: bool
    mode: StreamMode
    auto_reset_mode: bool
    name: str

    def __init__(
        self,
        flush: bool = False,
        buffer_size: int = 8,
        file: TextIO = sys.stdout,
        mode: StreamMode = std.string,
        auto_reset_mode: bool = True,
        name: str = "stream"
    ) -> None:
        """
        Initialize the stream with buffering and formatting options.
        """
        self.name = name
        self.flush = flush
        self.mode = mode
        self.auto_reset_mode = auto_reset_mode

        self.buf = []
        if buffer_size > 0:
            self.buf_size = buffer_size
        else:
            self.buf_size = 16

        self.file = file

    def flush_buf(self) -> None:
        """
        Flush the buffer to the stream.
        """
        try:
            self.file.write("".join(self.buf))
            self.buf.clear()
            self.file.flush()
        except (OSError, AttributeError):
            return

    def __lshift__(self, other: object) -> Self:
        """
        Append a value or manipulator to the stream.
        """
        if self.file is None:
            self.file = sys.__stdout__ or sys.stdout

        if isinstance(other, StreamMode):
            self.mode = other
            return self

        if other is std.endl:
            self.buf.append("\033[0m\n")
            if self.auto_reset_mode:
                self.mode = std.string
            self.flush_buf()
            return self

        if other is std.flush:
            self.flush_buf()
            return self

        self.buf.append(self.mode(other))

        if len(self.buf) >= self.buf_size or self.flush:
            self.flush_buf()

        return self

    def __del__(self) -> None:
        try:
            if self.file is not None and not self.file.closed:
                self.file.write("".join(self.buf))
                self.file.flush()
        except (OSError, AttributeError):
            return


pyout = Stream()
"""
A small stream that lets Python borrow a little C++ energy.

```python
>>> pyout << "Hello World!" << std.endl
>>> Hello World!

>>> pyout << std.uppercase << "Hello World!" << std.endl
>>> HELLO WORLD!

>>> pyout << std.hex << 100 << std.endl
>>> 0x64
...
```

It is not C++, but it can pretend for a while.
"""
