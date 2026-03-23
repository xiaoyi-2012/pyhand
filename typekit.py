# Copyright XiaoYi 2026. MIT license, see LICENSE file.
"""
Runtime type checking utilities.

This module implements a lightweight runtime type checking system
based on Python's typing module. It allows validating values against
type specifications at runtime, similar to tools such as typeguard
or beartype.

Features:

- Support for standard types and `None`
- Union types (`|` and `typing.Union`)
- `TypeVar` with bounds and constraints
- Type aliases
- `TypedDict` validation
- Protocol checking (including `@runtime_checkable`)
- Callable signature validation
- Parameterized container types (e.g. `list[int]`, `dict[str, int]`)

Main APIs:

- `typecheck(value, type_info)`:
  Validate a value against a type specification.

- `typechecked`:
  Decorator that enforces runtime type checking on function
  arguments and return values.

The module also includes various low-level utilities for working
with typing constructs, such as `deep_origin`, `split_generic`,
and `specialform_check`.
"""
from __future__ import annotations

import os
import inspect
import types
import typing
import collections.abc as cabc
import functools

from typing import (
    TypeAliasType,
    TypeVar,
    _SpecialForm as SpecialForm,
    _GenericAlias, # type: ignore
)
from error import Suppress, TypeHintError

GenericAlias = types.GenericAlias | _GenericAlias
TypeForm = type | GenericAlias | TypeAliasType | SpecialForm | types.UnionType | TypeVar


def cast_type(values: cabc.Sequence[object]) -> tuple[type, ...]:
    """
    Return the types corresponding to `values`.

    Elements that are already types are returned unchanged.
    """
    return tuple((t if isinstance(t, type) else type(t)) for t in values)

def typename(value: TypeForm, qualname: bool = False) -> str:
    """
    Return the name of a type or object.

    By default, the function returns `value.__name__`. If `qualname` is
    true, the qualified name (`value.__qualname__`) is returned instead.

    If the requested attribute is not available, `str(value)` is returned
    as a fallback.
    """
    if isinstance(value, (SpecialForm, GenericAlias)):
        return repr(value)

    if not isinstance(value, type):
        value = type(value)

    with Suppress(AttributeError):
        if not qualname:
            return value.__name__
        return value.__qualname__
    return str(value)



C = typing.TypeVar("C", bound=object)

def construct(cls: type[C]) -> C | None:
    """
    Create a new instance of `cls`.

    The instance is created without invoking the class initializer.
    """

    with Suppress(Exception):
        return object.__new__(cls)



def direct_setattr(obj: object, name: str, value: object) -> bool:
    """
    Set an attribute on `obj` directly.

    The attribute `name` is assigned the given `value`. If the assignment
    succeeds, `True` is returned. If an `AttributeError` occurs, the
    exception is suppressed and `False` is returned instead.
    """
    with Suppress(AttributeError):
        object.__setattr__(obj, name, value)
        return True
    return False # Failed: Pre-existing fixed memory (__slots__)



P = typing.ParamSpec("P")
R = typing.TypeVar("R")

def noexcept(func: cabc.Callable[P, R]) -> cabc.Callable[P, R]:
    """
    Decorator indicating that the wrapped function must not raise exceptions.

    If any exception occurs during execution, an error message is printed and
    the program terminates immediately.

    ```python
    @noexcept
    def foo() -> None:
        ...
    ```
    """
    assert callable(func), "noexcept can only decorate callable objects"
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except Exception as e: # pylint: disable=broad-except
            print(f"{typename(e)} occurred while running {func.__name__}")
            os._exit(1)
    return wrapper



def isclass(value: object, cls: TypeForm | tuple[TypeForm]) -> bool:
    """
    Check whether `value` is exactly of type `cls`.

    Unlike `isinstance`, this requires an exact type match.
    """
    if isinstance(cls, TypeVar):
        if cls.__bound__ is not None:
            return isinstance(value, cls.__bound__)
        if cls.__constraints__ is not None:
            return isinstance(value, cls.__constraints__)
        return True
    if isinstance(cls, type):
        return type(value) is cls # pylint: disable=unidiomatic-typecheck
    for t in cls:
        if type(value) is t: # pylint: disable=unidiomatic-typecheck
            return True
    return False


def deep_origin(tp: object) -> object:
    """
    Return the innermost origin of a type.

    Repeatedly unwraps `__origin__` until a non-parameterized type is reached.
    """
    while True:
        origin = getattr(tp, "__origin__", None)
        if origin is None:
            return tp
        tp = origin


def split_generic(tp: GenericAlias) -> tuple[TypeForm, tuple[TypeForm, ...]] | None:
    """
    Split a generic type into its origin and arguments.

    Return a tuple of `(origin, args)` if `tp` is a parameterized type,
    otherwise return `None`.
    """
    if not typing.get_origin(tp):
        return
    return typing.get_origin(tp), typing.get_args(tp)



def specialform_check(value: object, specialform: SpecialForm | GenericAlias) -> bool:
    """
    Check whether `value` conforms to a typing special form.

    Supports `Any`, `Never`, `NoReturn`, `LiteralString`, `TypeAlias`,
    `Literal[...]`, and selected wrapper forms such as `ClassVar`
    and `Final`.

    Return true if `value` matches or unsupported `form`, 
    otherwise false.
    """
    if specialform is typing.Any:
        return True
    if specialform in (typing.Never, typing.NoReturn):
        return False

    if typing.get_origin(specialform) in (typing.ClassVar, typing.Final):
        args = typing.get_args(specialform)
        if not args:
            return True
        return typecheck(value, typing.get_args(specialform)[0])

    if specialform is typing.TypeAlias:
        return isinstance(value, type)

    if typing.get_origin(specialform) is typing.Literal:
        return any(value is v for v in typing.get_args(specialform))

    if typing.get_origin(specialform) is typing.Union:
        return any(typecheck(value, t) for t in typing.get_args(specialform))

    return True # Unsupported types, assume it is true


def callable_check(obj: object, tp: GenericAlias) -> bool:
    """
    Check whether `obj` conforms to a callable type.

    The callable signature and return annotation are compared against
    `tp` when available. Incomplete or unsupported annotations are
    treated as compatible.
    """
    empty = inspect.Parameter.empty

    if not callable(obj):
        return False

    args = typing.get_args(tp)
    if not args:
        return True
    args_t, ret_t = args

    # Ignoring complex situations
    if args_t is Ellipsis or isinstance(
        args_t,
        (typing.ParamSpec, typing.ParamSpecArgs, typing.ParamSpecKwargs)
    ):
        return True

    try:
        hints = typing.get_type_hints(obj)
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return False

    params = list(sig.parameters.values())
    if len(params) < len(args_t):
        return False

    for p, t in zip(params, args_t):
        ann = hints.get(p.name, empty)
        if ann is empty:
            continue
        if ann != t:
            return False

    ret = hints.get("return", empty)
    if ret is not empty and ret != ret_t:
        return False

    return True


def typeddict_check(value: object, type_info: TypeForm) -> bool:
    """
    Check whether `value` conforms to a `TypedDict` definition.

    Required keys must be present, and each value is validated against
    its annotated type. Extra keys are not allowed.
    """
    if not isinstance(value, dict):
        return False

    try:
        annotations = typing.get_type_hints(type_info, include_extras=True)
    except Exception: # pylint: disable=broad-exception-caught
        annotations = getattr(type_info, "__annotations__", {})

    total = getattr(type_info, "__total__", True)
    required_keys = set()

    for k, t in annotations.items():
        origin = typing.get_origin(t)

        if origin is typing.Required or t is typing.Required:
            required_keys.add(k)
        elif origin is typing.NotRequired or t is typing.NotRequired:
            pass
        elif total:
            required_keys.add(k)

    for key in required_keys:
        if key not in value:
            return False

    for key, t in annotations.items():
        if key not in value:
            continue

        val = value[key]
        origin = typing.get_origin(t)

        if origin is typing.Required or origin is typing.NotRequired:
            t = typing.get_args(t)[0]
        if not typecheck(val, t):
            return False

    for key in value:
        if key not in annotations:
            return False

    return True


def typecheck(value: object, type_info: TypeForm | None) -> bool:
    """
    Check whether `value` satisfies the type specification `type_info`.

    Supports standard types, `None`, unions, `TypeVar`, type aliases,
    protocols, typed dictionaries, callables, and parameterized
    container types.

    Return true` if the check succeeds, otherwise false.
    """
    origin = typing.get_origin(type_info)
    args = typing.get_args(type_info)

    if type_info is None or type_info is types.NoneType:
        return value is None

    if isinstance(type_info, typing.TypeVar):
        if type_info.__bound__ is not None:
            return typecheck(value, type_info.__bound__)
        if type_info.__constraints__:
            return any(typecheck(value, t) for t in type_info.__constraints__)
        return True

    # type MyAlias = ...
    # assert isinstance(MyAlias, TypeAliasType) -> True
    if isinstance(origin, typing.TypeAliasType):
        return typecheck(value, origin.__value__)

    if origin is None and not args:
        if type_info is int and isclass(value, bool):
            return False
        with Suppress(TypeError):
            return isinstance(value, type_info) # type: ignore

    if origin is None:
        origin = type_info
    origin = deep_origin(origin) # Stripping the typing `_alias`
    origin = typing.cast(type, origin)


    if isinstance(origin, SpecialForm):
        return specialform_check(value, type_info)

    if isinstance(origin, types.UnionType):
        return any(typecheck(value, t) for t in args)

    if typing.is_typeddict(type_info):
        return typeddict_check(value, type_info)

    if getattr(origin, '_is_protocol', False):
        # If `@runtime_checkable` is present, it directly
        # uses the underlying C high-speed channel for checking.
        if getattr(origin, '_is_runtime_protocol', False):
            return isinstance(value, origin)

        # Scan all public properties and
        # methods defined in the Protocol.
        for attr in dir(origin):
            # Skipping private properties and built-in methods
            if not attr.startswith("_") and not hasattr(value, attr):
                return False
        return True

    if not isinstance(value, origin):
        return False

    # Mapping
    if issubclass(origin, (cabc.Mapping,cabc.MappingView)):
        value = typing.cast(cabc.Mapping, value)
        if len(args) == 0:
            return isinstance(value, origin)
        if len(args) != 2:
            name = typename(origin)
            raise TypeHintError(f"The {name} type hint should be {name}[K, V] or {name}")
        kt, vt = args
        for k, v in value.items():
            if not (typecheck(k, kt) and typecheck(v, vt)):
                return False
        return True

    # Tuple
    if origin is tuple:
        value = typing.cast(tuple, value)
        if args == ((),):
            return len(value) == 0

        # Variable length: tuple[T, ...]
        if len(args) == 2 and args[1] is Ellipsis:
            return all(typecheck(v, args[0]) for v in value)

        # Fixed length
        if len(args) != len(value):
            return False
        return all(typecheck(v, t) for v, t in zip(value, args))

    # Sequence, Iterable, Generator, Set, frozenset, bytearray...
    if issubclass(origin, (cabc.Collection, cabc.Iterable)):
        value = typing.cast(cabc.Collection, value)
        if len(args) > 1:
            name = typename(origin)
            raise TypeHintError(f"The {name} type hint should be {name}[T] or {name}")
        if len(args) == 0:
            return isinstance(value, origin)
        return all(typecheck(v, args[0]) for v in value)

    if origin is cabc.Callable:
        return callable_check(value, type_info)

    return True


def typechecked(func: cabc.Callable[P, R]) -> cabc.Callable[P, R]:
    """
    Decorator that enforces runtime type checking.

    Arguments and return values are validated against type annotations.
    A `TypeError` is raised if a mismatch is detected.
    """
    # Reconstruct the entire string into a type.
    hint = typing.get_type_hints(func, include_extras=True)
    sig = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        arg = sig.bind(*args, **kwargs)
        arg.apply_defaults()

        for pn, pv in arg.arguments.items():
            if pn in hint and not typecheck(pv, hint[pn]):
                raise TypeError(
                    f"Arguments \"{pn}\" must be {typename(hint[pn])}, got {pv} ({typename(pv)})"
                )
        retv = func(*args, **kwargs)
        if "return" in hint and not typecheck(retv, hint["return"]):
            raise TypeError(
                f"Return value must be {typename(hint["return"])}, got {retv} ({typename(retv)})"
            )
        return retv
    return wrapper
