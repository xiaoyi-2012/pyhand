"""
Traceback inspection utilities.

This module provides tools for constructing and traversing structured
traceback chains with access to source code, statements, and frame data.

Main APIs
=========

- `TracebackChain`
- `build_traceback`
"""
import linecache
import ast

from collections.abc import Iterator
from typing import Self, overload
from types import TracebackType
from dataclasses import dataclass, fields

__all__ = ("TracebackChain", "build_traceback")



@dataclass(frozen=True, slots=True)
class TracebackChain:
    """
    Represent a linked chain of traceback frames.

    Each node stores source location, local variables, and the next frame.
    """
    name: str
    filename: str
    lineno: int
    depth: int
    locals: dict[str, object]
    start_lineno: int
    end_lineno: int
    next: Self | None

    @property
    def source(self) -> str | None:
        """
        Return the source line for the current frame.

        If the line cannot be resolved, return `None`.
        """
        return linecache.getline(self.filename, self.lineno).strip() or None

    @property
    def statement(self) -> str | None:
        """
        Return the complete statement containing the current line.

        If the statement cannot be determined, return `None`.
        """
        lines = linecache.getlines(self.filename)
        if not lines:
            return None

        start = self.start_lineno - 1
        end = self.end_lineno
        return "".join(lines[start : end]).rstrip("\r\n") or None


    def __iter__(self) -> Iterator[Self]:
        curr = self
        while curr is not None:
            yield curr
            curr = curr.next

    def __len__(self) -> int:
        return self.depth

    def __repr__(self) -> str:
        attrs  = ", ".join(
            f"{f.name}={getattr(self, f.name)!r}" for f in fields(self)
            if f.name not in ("next", "locals")
            )
        return f"{self.__class__.__name__}({attrs})"



@overload
def build_traceback(tb_or_exc: TracebackType) -> TracebackChain: ...

@overload
def build_traceback(tb_or_exc: None) -> None: ...

@overload
def build_traceback(tb_or_exc: BaseException) -> TracebackChain | None: ...



def build_traceback(tb_or_exc) -> TracebackChain | None:
    """
    Build a linked traceback chain from a traceback object.

    If `tb` is `None`, return `None`.
    """
    if isinstance(tb_or_exc, BaseException):
        tb = tb_or_exc.__traceback__
    else:
        tb = tb_or_exc

    if tb is None:
        return None

    tbs = [] # type: list[TracebackType]
    curr = tb

    while curr is not None:
        tbs.append(curr)
        curr = curr.tb_next

    next_tb: TracebackChain | None = None

    def statement_range(filename: str, lineno: int) -> tuple[int, int]:
        lines = linecache.getlines(filename)
        if not lines:
            return lineno, lineno

        try:
            tree = ast.parse("".join(lines), filename=filename)
        except SyntaxError:
            return lineno, lineno

        best = None # type: ast.stmt | None
        best_size = None # type: int | None

        for node in ast.walk(tree):
            if not isinstance(node, ast.stmt):
                continue

            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None)
            if start is None or end is None or not start <= lineno <= end:
                continue

            size = end - start
            if best is None or size <= best_size:
                best = node
                best_size = size

        if best is None:
            return lineno, lineno

        return best.lineno, best.end_lineno or best.lineno

    for depth, raw_tb in enumerate(reversed(tbs), start=1):
        frame = raw_tb.tb_frame
        code = frame.f_code
        lineno = raw_tb.tb_lineno
        start_lineno, end_lineno = statement_range(code.co_filename, lineno)

        next_tb = TracebackChain(
            name     = code.co_name,
            filename = code.co_filename,
            lineno   = lineno,
            depth    = depth,
            locals   = frame.f_locals.copy(),
            next     = next_tb,
            start_lineno = start_lineno,
            end_lineno   = end_lineno,
        )

    return next_tb
