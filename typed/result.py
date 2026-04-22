"""
Result type utilities.

This module provides a minimal implementation of a result type for
representing computations that may succeed or fail without using
exceptions. It follows a pattern similar to Rust's `Result`, treating
errors as values and requiring explicit handling.

Main APIs
=========

- `Ok`
- `Err`
- `Result`
"""
from dataclasses import dataclass

__all__ = ("Ok", "Err", "Result")


@dataclass(slots=True, frozen=True)
class Ok[T]:
    """
    Immutable container representing a successful result.

    The contained `value` holds the result of a successful computation.
    """
    value: T

    def __bool__(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"Ok({repr(self.value)})"


@dataclass(slots=True, frozen=True)
class Err[T]:
    """
    Immutable container representing a failed result.

    The contained `value` typically holds error information.
    """
    value: T

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"Err({repr(self.value)})"


type Result[T, E] = Ok[T] | Err[E]
"""
Represent a computation that may succeed with `Ok[T]` or fail with `Err[E]`.

This pattern treats errors as values rather than exceptions, requiring
explicit handling of both success and failure cases. It is similar to
Rust's `Result<T, E>`.

- Explicitness:
    The return type clearly indicates possible failure, 
    encouraging callers to handle both outcomes.

- Predictable Control Flow:
    Error handling becomes part of normal program flow, 
    avoiding complex `try-except` structures.
"""
