"""
Custom exception types for error handling.

This module defines exception classes used by the error handling
system and related runtime utilities.
"""
import types


__all__ = (
    "ImmutableError",
    "OverloadError",
    "DirNotFoundError",
    "StateError",
    "UndefinedError",
    "FormatError",
    "TypeHintError"
)

class ImmutableError(AttributeError):
    """
    An error occurred when attempting to modify the 
    properties of an immutable object.
    """


class OverloadError(TypeError):
    """Error caused by overloads that cannot find matching parameters."""
    func_name: str | None
    call_args: tuple[object, ...]
    call_kwargs: dict[str, object]

    def __init__(
        self,
        *args: object,
        func_name: str | types.FunctionType | None = None,
        call_args: tuple[object, ...] | None = None,
        call_kwargs: dict[str, object] | None = None
    ) -> None:
        super().__init__(*args)
        self.func_name = \
            func_name if isinstance(func_name, str) else \
            func_name.__code__.co_name if not func_name is None else \
            None
        self.call_args = call_args or ()
        self.call_kwargs = call_kwargs or {}

    def __str__(self) -> str:
        if self.func_name is not None:
            args_s = [repr(a) for a in self.call_args]
            kw_s = [f"{k}={v!r}" for k, v in self.call_kwargs.items()]

            all_args = " ".join(args_s + kw_s)

            return f"No matching signature found for {self.func_name}({all_args})"

        return super().__str__()


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
