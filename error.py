# Copyright XiaoYi 2026. MIT license, see LICENSE file.
"""
Exception handling and diagnostic utilities.

This module provides structured exception handling, enhanced traceback
rendering, and a collection of custom exception types.

It introduces a context-based error model (`ExceptContext`,
`TracebackContext`) for capturing and processing exceptions in a
consistent and serializable form. It also includes an extensible
exception hook (`ExceptionHandler`) for formatting and displaying
tracebacks with configurable output behavior.

Main components:

- `ExceptionHandler`:
  A configurable exception hook for rendering enhanced tracebacks.

- `ExceptContext` / `TracebackContext`:
  Immutable representations of exceptions and traceback frames.

- `Suppress`:
  A context manager for safely suppressing exceptions.

- Custom exception types:
  A set of domain-specific error classes such as `TypeHintError`,
  `OverloadError`, and `StateError`.

This module is designed to integrate with runtime type checking
systems and provides a foundation for building robust error handling
and debugging workflows.
"""
from __future__ import annotations

import sys
import os
import builtins
import re
import enum
import dis
import keyword
import ast
import linecache

from collections.abc import Iterator, Callable
from dataclasses import dataclass
from functools import lru_cache
from types import TracebackType, CodeType

__all__ = (
    "ExceptLevel",
    "ExceptContext",
    "TracebackContext",
    "OutputContext",
    "ExceptionHandler",
    "Suppress",
    "ImmutableError",
    "OverloadError",
    "LengthError",
    "DirNotFoundError",
    "StateError",
    "UndefinedError",
    "FormatError",
    "InterfaceError"
)

class ExceptLevel(enum.IntEnum):
    """
    Error levels for categorizing the severity of errors.
    It can be used to handle exceptions after installing PyHand excepthook; default is `GENERAL`.

    - `IGNORE`:  Errors that can be safely ignored or handled without significant consequences.
    - `GENERAL`: This indicates a general error that needs to be handled.
    - `SERIOUS`: This indicates a serious error, and the program should be terminated immediately.

    Usage example:
    ```python 
    raise OSError("OS has serious error!", ExceptLevel.SERIOUS)
    ```

    You can get it using `ExceptionContext(Exception).level`
    """
    GENERAL = 0x1
    SERIOUS = 0x2

class ImmutableError(AttributeError):
    """
    An error occurred when attempting to modify the 
    properties of an immutable object.
    """

class OverloadError(TypeError):
    """Error caused by overloads that cannot find matching parameters."""

class LengthError(ValueError, OverflowError):
    """An error occurred when the length of a serializable object exceeded the limit."""

class DirNotFoundError(FileNotFoundError):
    """Dir not found."""

class StateError(RuntimeError):
    """States error."""

class UndefinedError(TypeError, NameError):
    """Undefined error."""

class FormatError(ValueError):
    """Errors caused by using unsupported or incorrect formats."""

class TypeHintError(TypeError):
    """
    Error raised for invalid or unsupported type hints.

    Example:
    ```python
    typecheck(value, dict[str])
    ```
    """

class InterfaceError(NotImplementedError):
    """Errors caused by unimplemented interfaces."""


SpecialExceptions = (SyntaxError, KeyboardInterrupt, SystemExit)
HasTraceback = BaseException | TracebackType


def _get_src(filename: str, lineno: int, complete_statement: bool = False) -> str | None:
    if not complete_statement:
        return linecache.getline(filename, lineno)

    lines = linecache.getlines(filename)
    if not lines:
        return None

    try:
        tree = ast.parse("".join(lines), filename=filename)
    except SyntaxError:
        return linecache.getline(filename, lineno).strip()

    best = None
    best_size = None

    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt):
            continue

        node_lineno = getattr(node, "lineno", None)
        node_end = getattr(node, "end_lineno", None)

        if node_lineno is None or node_end is None:
            continue

        if node_lineno <= lineno <= node_end:
            size = node_end - node_lineno

            if best is None or size <= best_size:
                best = node
                best_size = size

    if best and best.end_lineno:
        start = best.lineno - 1
        end = best.end_lineno
        return "".join(lines[start : end]).strip("\n\r")

    return linecache.getline(filename, lineno).strip()


@lru_cache(maxsize=32)
def _stdcolor(text: str, code: str) -> str:
    if not sys.stderr.isatty() or len(code) == 0: # Color not supported
        return text

    if code.isdigit(): # Standard color code
        return f"\033[{code}m{text}\033[0m"

    r, g, b = (int(code.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))

    # RGB color code
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"



@dataclass(frozen = True, slots = True)
class TracebackContext:
    """
    A persistent snapshot of a traceback frame.

    This class encapsulates execution state at a specific point in the call stack 
    into an immutable object, making it suitable for logging, serialization, 
    or cross-thread error reporting.
    """

    name: str
    filename: str
    lineno: int # If not found, the default value is 1
    source: str | None
    next_tb: TracebackContext | None
    depth: int
    _head: bool
    instr_offset: int
    code_obj: CodeType

    @classmethod
    def extract(
        cls,
        tb: HasTraceback | TracebackContext | None,
    ) -> TracebackContext | None:
        """Create a `TracebackContext` using traceback or exception."""
        if tb is None:
            return
        if isinstance(tb, TracebackContext):
            return tb

        if isinstance(tb, BaseException):
            tb = tb.__traceback__

        tbs = [] # type: list[TracebackType]
        curr = tb
        while curr is not None:
            tbs.append(curr)
            curr = curr.tb_next

        next_node = None
        depth = 1

        for raw in reversed(tbs):
            frame = raw.tb_frame
            co = frame.f_code

            curr_tb = cls(
                co.co_name,
                co.co_filename,
                frame.f_lineno,
                _get_src(co.co_filename, frame.f_lineno),
                next_node,
                depth, depth == len(tbs),
                raw.tb_frame.f_lasti,
                co
            )

            next_node = curr_tb
            depth += 1

        return next_node

    def __iter__(self) -> Iterator[TracebackContext]:
        curr = self
        while curr is not None:
            yield curr
            curr = curr.next_tb

    def is_head(self) -> bool:
        """Return True if this traceback is the head of the traceback chain."""
        return self._head

    def is_tail(self) -> bool:
        """Return True if this traceback is the tail of the traceback chain."""
        return self.next_tb is None

    def __len__(self) -> int:
        return self.depth

    def __repr__(self) -> str:
        attrs = []
        for i in dir(self):
            if not i.startswith("_") and i not in ("next_tb", "code_obj"):
                attrs.append(i)
        return f"TracebackContext({", ".join(f"{n}={getattr(self, n)}" for n in attrs)})"

    def __str__(self) -> str:
        attrs = []
        for i in dir(self):
            if not i.startswith("_") and i not in ("next_tb", "code_obj"):
                attrs.append(i)
        return f"TracebackContext:\n{"\n".join(f"{n}: {getattr(self, n)}" for n in attrs)}"


@dataclass(frozen = True, slots = True)
class ExceptContext:
    """
    A lightweight snapshot object for packaging and serializing exceptions.

    This class captures the state of an exception at a specific point in time,
    converting traceback and arguments into a structured, read-only format.
    """

    raw_args: tuple[object, ...]
    message: str # The first non-ExceptLevel message
    stack: TracebackContext | None
    level: ExceptLevel # If not found, the default value is `ExceptLevel.GENERAL`
    instr_offset: int | None # Instruction offset, for bytecode traceback

    @classmethod
    def extract(
        cls,
        exc: BaseException | ExceptContext | None,
        strmode: str = "str"
    ) -> ExceptContext | None:
        """Create a `ExceptContext` using exception."""
        if isinstance(exc, (ExceptContext, type(None))):
            return

        strfunc = str if strmode == "str" else repr

        msg = []
        level = ExceptLevel.GENERAL
        has_level = False
        if any(isinstance(a, ExceptLevel) for a in exc.args):
            has_level = True

        if has_level and not isinstance(exc, SpecialExceptions):
            for s in exc.args:
                if isinstance(s, ExceptLevel):
                    level = s
                    continue
                msg.append(strfunc(s) if s is not Ellipsis else "...")
            msg = ", ".join(msg) # Join non-level messages with comma
        else:
            msg = str(exc) # Use original exception message if level is not found

        tb = exc.__traceback__

        return cls(
            exc.args, msg,
            TracebackContext.extract(exc.__traceback__),
            level,
            tb.tb_frame.f_lasti if tb else None
        )

    @staticmethod
    def cause(exc: BaseException) -> BaseException | None:
        """Get the cause of an exception."""
        return exc.__cause__ or exc.__context__


class OutputContext(enum.IntFlag):
    """Controlling the output of ExceptionHandler."""
    LINE_NO   = 0x01
    MESSAGE   = 0x02
    LEVEL     = 0x04 # [Level] ExceptionTyp: Message
    BYTECODE  = 0x08 # Fallback, when source code cannot be found
    NAME      = 0x10
    EXIT_CODE = 0x20

    NO_DISPLAY_SOURCE = 0x80 # No output source code
    NO_DISPLAY_EMPTY_TB = 0x100 # No output: `No record.`
    STANDARD = NAME | LINE_NO | MESSAGE | BYTECODE

_CLS, _FUNC, _VAR = set(), set(), set()
_KW = frozenset(keyword.softkwlist + keyword.kwlist) # type: ignore

for name, obj in vars(builtins).items():
    if isinstance(obj, type):
        _CLS.add(name)
        continue
    if callable(obj):
        _FUNC.add(name)
        continue
    if name.startswith("_"):
        _VAR.add(name)

_CLS = frozenset(_CLS)
_FUNC = frozenset(_FUNC)
_VAR = frozenset(_VAR)

RENDER_LINE = re.compile(
    r"(?P<s>"
    r"#[^\n]*"
    r"|\"\"\"[\s\S]*?\"\"\""
    r"|\'\'\'[\s\S]*?\'\'\'"
    r"|\"[^\"\\]*(?:\\.[^\"\\]*)*\""
    r"|\'[^\'\\]*(?:\\.[^\'\\]*)*\'"
    r")"
    r"|(?P<w>\b[a-zA-Z_]\w*\b)"
)

def _render_lines(src: str) -> str:
    def rep(match: re.Match[str]) -> str:
        s = match.group("s")
        if s is not None:
            return _stdcolor(s, "#CE9178")

        w = match.group("w")

        if w in _KW:
            return _stdcolor(w, "#569CD6")
        if w in _FUNC:
            return _stdcolor(w, "#DCDCAA")
        if w in _CLS:
            return _stdcolor(w, "#4EC9B0")
        if w in _VAR:
            return _stdcolor(w, "#9CDCFE")

        return w

    return "\n".join(RENDER_LINE.sub(rep, c) for c in src.splitlines())


WHITE  = "#FFFFFF"
YELLOW = "#FFFF00"
RED    = "#FF000D"
GRAY   = "#333333"
BLUE   = "#2424E7"
CAYN   = "#00B7EB"


class ExceptionHandler:
    """
    Handle exceptions and render enhanced tracebacks.

    This class provides configurable formatting, source rendering, 
    and exit behavior, and can replace the default exception hook.
    """
    __slots__ = (
        "flags", "indent", "color",
        "display_limit",
        "render_src", "complete_stmt",
        "exit_code", "atexit_func"
    )

    flags: OutputContext
    indent: int
    color: tuple[str, str, str] # Title, information, message
    display_limit: int
    render_src: bool
    atexit_func: Callable | None
    complete_stmt: bool
    exit_code: int

    def exit(self, exc: ExceptContext):
        """
        Terminate the program based on the exception level and configuration.
        """
        if self.flags & OutputContext.EXIT_CODE:

            if exc.level == ExceptLevel.SERIOUS:
                sys.stderr.write(_stdcolor(
                    f"Serious error, program terminated, exit code: {self.exit_code}",
                    self.color[1]
                ))
            else:
                sys.stderr.write(_stdcolor(f"Exit code: {self.exit_code}", self.color[1]))
        sys.stderr.flush()

        if exc.level is ExceptLevel.GENERAL:
            sys.exit(1)
        os._exit(1) # Serious error

    def __init__(
        self,
        flags: OutputContext = OutputContext.STANDARD,
        indent: int = 3,
        color: tuple[str, str, str] = ("", CAYN, GRAY),
        display_limit: int = -1,
        render_src: bool = True,
        complete_stmt: bool = True,
        exit_code: int = 1,
        atexit_func: Callable[[], object] | None = None,
    ) -> None:
        self.flags = flags
        self.indent = indent
        self.color = color
        self.display_limit = display_limit
        self.render_src = render_src
        self.complete_stmt = complete_stmt
        self.exit_code = exit_code
        self.atexit_func = atexit_func

    def excepthook(
        self,
        exctype: type[BaseException],
        value: BaseException,
        traceback: TracebackType | None,
        /
    ) -> None:
        """
        Custom exception hook for rendering formatted tracebacks.
        """
        write = sys.stderr.write
        indent = " " * self.indent
        indent2 = indent * 2

        # atexit
        if self.atexit_func:
            try:
                self.atexit_func()
            except Exception as e: # pylint: disable=broad-exception-caught
                write(_stdcolor(f"Error running atexit_func:\n{e}\n", YELLOW))

        # BaseException
        if isinstance(value, BaseException) and not isinstance(value, Exception):
            sys.__excepthook__(exctype, value, traceback)
            return

        exc = ExceptContext.extract(value)
        if not isinstance(exc, ExceptContext):
            return

        # Empty traceback
        if exc.stack is None:
            if self.flags & OutputContext.NO_DISPLAY_EMPTY_TB:
                write(_stdcolor(exctype.__name__, self.color[2]))
                self.exit(exc)
                return

            write(_stdcolor("PyHand Traceback Records:\n", self.color[0]))
            write(indent + _stdcolor("No record.\n", GRAY))
            self.exit(exc)
            return

        write(_stdcolor("PyHand Traceback Records:\n", self.color[0]))

        # SyntaxError
        if isinstance(value, SyntaxError):
            tb = exc.stack
            filename = value.filename or "<unknown>"
            lineno = value.lineno or 0

            write(_stdcolor(f'{indent}File "{filename}"', self.color[1]))

            if self.flags & OutputContext.LINE_NO:
                write(_stdcolor(f", line {lineno}", self.color[1]))
            if self.flags & OutputContext.NAME:
                write(_stdcolor(f", in {tb.name}", self.color[1]))

            write("\n")

            if value.text and not self.flags & OutputContext.NO_DISPLAY_SOURCE:
                text = value.text.rstrip()
                write(indent2 + text + "\n")

                if value.offset:
                    write(indent2 + " " * (value.offset - 1) + "^\n")

            if self.flags & OutputContext.MESSAGE:
                if exc.message:
                    level = f"[{exc.level.name.title()}] "
                    write(
                        level if self.flags & OutputContext.LEVEL else ""
                        f"{_stdcolor(exctype.__name__, '#4EC9B0')}: "
                        f"{_stdcolor(exc.message, self.color[2])}"
                    )
                else:
                    write(_stdcolor(exctype.__name__, "#4EC9B0"))

            self.exit(exc)
            return

        # Traceback
        for i, tb in enumerate(exc.stack):
            if 0 < self.display_limit == i:
                break

            write(_stdcolor(f'{indent}File "{tb.filename}"', self.color[1]))

            if self.flags & OutputContext.LINE_NO:
                write(_stdcolor(f", line {tb.lineno}", self.color[1]))
            if self.flags & OutputContext.NAME:
                write(_stdcolor(f", in {tb.name}", self.color[1]))

            if self.flags & OutputContext.NO_DISPLAY_SOURCE:
                write("\n\n")
                continue

            write(_stdcolor(":\n", self.color[1]))

            src = _get_src(tb.filename, tb.lineno, True) if self.complete_stmt else tb.source

            if src:
                if self.render_src:
                    src = _render_lines(src)
                write(indent2 + src + "\n\n")
                continue

            # Fallback
            write(_stdcolor(indent2 + "Source not found, in bytecode\n", GRAY))

            if self.flags & OutputContext.BYTECODE:
                for instr in dis.get_instructions(tb.code_obj):
                    if instr.offset == tb.instr_offset:
                        write(_stdcolor(
                            f"{indent2}{instr.opname:<15}{instr.argval}\n",
                            self.color[2]
                        ))
                        break

            write("\n")

        # Message
        if self.flags & OutputContext.MESSAGE:
            if exc.message:
                level = f"[{exc.level.name.title()}] " if self.flags & OutputContext.LEVEL else ""
                write(
                    f"{level}{_stdcolor(exctype.__name__, '#4EC9B0')}: "
                    f"{_stdcolor(exc.message, self.color[2])}"
                )
            else:
                write(_stdcolor(exctype.__name__, "#4EC9B0"))

        write("\n")
        self.exit(exc)

    def install(self) -> None:
        """
        Install this handler as the global exception hook.
        """
        if sys.excepthook is not self.excepthook:
            sys.excepthook = self.excepthook

    def is_installed(self) -> bool:
        """
        Return whether this handler is currently installed.
        """
        return sys.excepthook is self.excepthook

    @staticmethod
    def is_original() -> bool:
        """
        Return whether the original exception hook is active.
        """
        return sys.excepthook is sys.__excepthook__

    def restore(self) -> None:
        """
        Restore the original exception hook.
        """
        if sys.excepthook is not sys.__excepthook__:
            sys.excepthook = sys.__excepthook__


class Suppress:
    """
    Context manager to suppress specified exceptions

    After the exception is suppressed, execution proceeds with the next
    statement following the with statement.

    ```python
    with Supperess(ImportError):
        import xmodule
    dowork(...)
    # Execution proceeds here even if the module is missing.
    ```
    """
    __slots__ = ("exceptions",)

    exceptions: tuple[type[BaseException], ...]

    def __init__(self, *exceptions: type[BaseException]) -> None:
        self.exceptions = exceptions if exceptions else (Exception,)

    def __enter__(self) -> Suppress:
        return self

    def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None
        ) -> bool:
        """Return True if the exception is suppressed."""
        return bool(exc_type and issubclass(exc_type, self.exceptions))

if __name__ == "__main__":
    ExceptionHandler().install()

    raise RuntimeError(
        "Error information"
    )
