"""
TypeKit Overload Engine: C++ Style Multiple Dispatch for Python.

This module shatters the limitations of Python's static-only type hinting 
by providing a true, strict, runtime method resolution engine.

Unlike the standard library's `typing.overload`—which serves merely as 
metadata for IDEs and static analyzers—this module intercepts those 
signatures, compiles them, and dispatches execution to the "best-matching" 
implementation based on inheritance graphs and strict type validation.


Architecture Note:

The engine extracts static signatures via `typing.get_overloads()` and 
compiles them into a highly optimized dispatch registry. Parameter 
validation is deferred to the core `typecheck` engine, ensuring zero-compromise 
support for complex Generics and dynamic contexts (like `Self`).

Example:

```python
@overload
def foo(s: str) -> None:
    print("Got string")

@overload
def foo(n: int) -> None:
        print("Got integer")

@apply_overload
def foo(*args, **kwargs):
    # No implementation is required here,
    # but it must be declared,
    # otherwise it will not work.

    used(args, kwargs) # Avoid warnings from Linter
    return NotImplemented
```
"""

import inspect
import functools

from collections.abc import Callable
from typing import (
    Any,
    ParamSpec,
    TypeAliasType,
    TypeVar,
    get_origin,
    get_type_hints,
    get_overloads
)

from error.exception import OverloadError
from typekit.typecheck import typecheck


__all__ = "apply_overload",


WEIGHT_PENALTY = 10000
EQ_GOOD_ERROR  = True

def _distance(value: object, type_info: object) -> int | None:
    if type_info is Any or type_info is object:
        return WEIGHT_PENALTY

    if isinstance(type_info, TypeVar):
        if type_info.__bound__ is not None:
            type_info = type_info.__bound__
        else:
            # Non bound, treat it as a wildcard that matches
            # anything, but with a penalty
            return WEIGHT_PENALTY

    if isinstance(type_info, TypeAliasType):
        type_info = type_info.__value__

    cls = get_origin(type_info) or type_info

    # MRO index
    if isinstance(cls, type):
        try:
            return type(value).mro().index(cls)
        except ValueError:
            pass

    return 10


P = ParamSpec("P")
R = TypeVar("R")

def apply_overload(func: Callable[P, R]) -> Callable[P, R]:
    """
    Resolve and apply overloaded function signatures at runtime.

    Dispatch execution to the best-matching implementation based on
    type hints and inheritance distance (MRO). If multiple signatures
    are equally viable, an `OverloadError` is raised to prevent
    ambiguous resolution.

    Example:
    --------

    ```python
    @overload
    def foo(s: str) -> None:
        print("Got string")

    @overload
    def foo(n: int) -> None:
        print("Got integer")

    @apply_overload
    def foo(*args, **kwargs):
        # No implementation is required here,
        # but it must be declared,
        # otherwise it will not work.

        return NotImplemented
    ```
    """
    overloads = get_overloads(func)

    if not overloads:
        return func

    registry = [] # type: list[tuple[Callable, inspect.Signature, dict[str, object]]]

    for ov in overloads:
        registry.append((
            ov, inspect.signature(ov),
            get_type_hints(ov)
        ))

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        best = None
        min_d = float("inf")
        ambiguous = []
        for ov, sig, hints in registry:
            try:
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
            except TypeError:
                continue
            match = True
            curr_d = 0
            for k, v in bound.arguments.items():
                expected = hints.get(k)
                if expected is not None:

                    if not typecheck(v, expected):
                        match = False
                        break

                    dist = _distance(v, expected)
                    if dist is None:
                        dist = WEIGHT_PENALTY
                    curr_d += dist

            if match:
                if curr_d < min_d:
                    min_d = curr_d
                    best = ov
                    ambiguous = [ov]
                elif curr_d == min_d:
                    ambiguous.append(ov)

        if best is None:
            raise OverloadError(func_name=func, call_args=args, call_kwargs=kwargs)
        if len(ambiguous) > 1:
            if EQ_GOOD_ERROR:
                funcs_str = ", ".join([f.__name__ for f in ambiguous])
                raise OverloadError(
                    f"Ambiguous overload resolution for {args}, {kwargs}. " + \
                    f"Candidates are equally good: {funcs_str}"
                )
            return ambiguous[0](*args, **kwargs)

        return best(*args, **kwargs)

    return wrapper
