# pylint: disable=protected-access
"""
Utility helpers for runtime type checking.

This module provides helper functions used by `typekit` and related
runtime validation code.

Main APIs
=========

- `typename`
- `direct_setattr`
- `used`
- `iter_hint`
"""
from collections.abc import Iterable, Mapping
from typing import get_origin

__all__ = ("typename", "direct_setattr", "used", "iter_hint")


def typename(obj: object, qualname: bool = False) -> str:
    """
    Return the name of a type or object.

    If `qualname` is True, a qualified name is returned when available.
    Otherwise, a simple name is used.

    If a name cannot be determined, a string representation is returned.
    """

    if get_origin(obj) is not None:
        name = repr(obj)
        if name.startswith("typing.") and not qualname:
            return name[7:]
        return str(obj)

    if hasattr(obj, "_name") and type(obj).__module__ == "typing":
        return str(obj._name) # type: ignore

    if isinstance(obj, type):
        if qualname:
            return obj.__qualname__
        return obj.__name__

    if qualname:
        return type(obj).__qualname__
    return type(obj).__name__



def direct_setattr(obj: object, name: str, value: object) -> bool:
    """
    Set an attribute on `obj` directly.

    The attribute `name` is assigned the given `value`. If the assignment
    succeeds, True is returned. If an `AttributeError` occurs, the
    exception is suppressed and False is returned instead.
    """
    try:
        object.__setattr__(obj, name, value)
        return True
    except AttributeError:
        return False


def _iter_hint(obj: object) -> str:
    if not isinstance(obj, Iterable) or \
        isinstance(obj, (str, bytes)):
        return type(obj).__name__

    name = obj.__class__.__name__

    # tuple[A, B, C...]
    if isinstance(obj, tuple):
        if not obj:
            return f"{name}[()]"
        argt = (_iter_hint(t) for t in obj)
        return f"{name}[{", ".join(argt)}]"

    # dict[A, B]
    if isinstance(obj, Mapping):
        if not obj:
            return f"{name}[Any, Any]"
        kt = " | ".join(sorted(set(_iter_hint(k) for k in obj.keys())))
        vt = " | ".join(sorted(set(_iter_hint(v) for v in obj.values())))
        return f"{name}[{kt}, {vt}]"

    # list[T], set[T], ...
    if not obj:
        return f"{name}[Any]"
    argt = set(_iter_hint(t) for t in obj)
    return f"{name}[{" | ".join(sorted(argt))}]"



def iter_hint(obj: object) -> str:
    """
    Generate a string representation of an iterable's type structure.

    This function recursively inspects the elements of an iterable to 
    construct a type hint string (e.g., `list[int | str]`). It is 
    designed for debugging and runtime type analysis.
    """
    try:
        if isinstance(obj, Iterable) and not \
            isinstance(obj, (str, bytes)):

            if isinstance(obj, Mapping):
                if any(obj is v for v in obj.values()):
                    return f"{type(obj).__name__}[...]"
                # The keys must be hashable objects (not dictionaries)
                # and must not be circularly referenced.

            else:
                if obj in obj:
                    return f"{type(obj).__name__}[...]"

        return _iter_hint(obj)
    except RecursionError:
        return f"{type(obj).__name__}[...]"



def used(*unused_args: object) -> None:
    """
    Explicitly mark variables as intentionally unused.

    This utility performs a zero-cost, no-op assertion to suppress 
    linter warnings (e.g., Flake8, Pylint) and IDE type checker 
    complaints regarding unused variables. It serves as the Python 
    equivalent of C++'s `[[maybe_unused]]` attribute or `(void)arg;` 
    casting.

    Use this to document developer intent when interface contracts, 
    method overrides, or hook definitions force the inclusion of 
    specific parameters that are not needed in the implementation.
    """
    del unused_args
