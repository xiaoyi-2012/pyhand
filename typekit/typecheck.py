# pylint: disable=protected-access
"""
Runtime type checking utilities.

This module provides helpers for validating values against type
annotations at runtime.

Main Components
===============

- `typecheck`
- `validate`
- `validate_call`

Usage
=====

```python
@validated
def add(a: int, b: int) -> int:
    return a + b

add(123, 546) # Ok
add("a", "b") # TypeError
```

"""
import inspect
import types
import functools
import typing

from collections.abc import (
    Callable,
    Mapping, MappingView,
    Collection, Iterable
)

from typekit.utils import typename, iter_hint
from error.exception import TypeHintError


__all__ = (
    "typecheck",
    "validate",
    "validate_call"
)

def _is_protocol(
    obj: object
) -> typing.TypeGuard[type[typing.Protocol]]: # type: ignore
    return getattr(obj, "_is_protocol", False)


def _typeerr_msg(
    expected: str,
    value: object,
    displey_value: bool = True,
    name: str | None = None
):
    prefix = f"The {name if name else "type"} was expected to be "
    if not displey_value:
        return prefix + f"{expected}, got {typename(value)}."
    name = typename(value)
    if isinstance(value, Iterable):
        name = iter_hint(value)
    return prefix + f"{expected}, got {repr(value)} ({name})."



def _special_check[T](
    value: object,
    form: T, strict: bool = False
) -> typing.TypeGuard[T]:
    if form is typing.Any:
        return True
    if form is typing.Never or form is typing.NoReturn:
        return False

    if form is typing.TypeAlias:
        # e.g.
        # MyAlias: TypeAlias = ...
        return isinstance(value, type)
    if typing.get_origin(form) is typing.LiteralString:
        # LiteralString cannot be confirmed at runtime.
        # currently, it can only be determined whether it is a string.
        return isinstance(value, str)

    if typing.get_origin(form) is typing.Literal:
        if strict:
            return any(value is v for v in typing.get_args(form))
        return value in typing.get_args(form)

    if typing.get_origin(form) is typing.Union:
        return any(typecheck(value, t, strict) \
            for t in typing.get_args(form)
        )

    if typing.get_origin(form) is typing.TypeGuard:
        return value.__class__ is bool

    if typing.get_origin(form) is not None:
        args = typing.get_args(form)
        if not args:
            return True
        return typecheck(value, typing.get_args(form)[0], strict)

    return not strict



def _callable_msg(obj: object, callable_t: object) -> str | None:
    if not callable(obj):
        return _typeerr_msg(typename(callable_t), obj)

    args = typing.get_args(callable_t)
    if not args:
        return _typeerr_msg(typename(callable_t), obj)

    if len(args) == 1:
        args = args[0], typing.Any

    args_t, ret_t = args

    try:
        hints = typing.get_type_hints(obj)
        # The built-in function inspect.signature
        # will attempt to access the `__text_signature__`
        # property without raising an error.
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return

    params = sig.parameters.values()

    if args_t is not Ellipsis and not isinstance(args_t, (
        typing.ParamSpec,
        typing.ParamSpecArgs,
        typing.ParamSpecKwargs
    )):
        args_t = tuple(args_t)
        params = [
            p for p in params
            if p.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]

        if len(params) < len(args_t):
            return (
                f"Callable expected at least {len(args_t)} positional parameter(s), "
                f"got {len(params)}."
            )

        for p, expected in zip(params, args_t):
            ann = hints.get(p.name)
            if ann is None:
                continue
            if ann != expected:
                return (
                    f"Callable parameter \"{p.name}\" was expected to be "
                    f"{typename(expected)}, got {typename(ann)}."
                )

    ret_ann = hints.get("return")
    if ret_ann is not None and ret_t is not typing.Any:
        if ret_t is None:
            ret_t = types.NoneType

        if not typecheck(ret_ann, ret_t):
            return (
                f"Callable return type was expected to be {typename(ret_t)}, "
                f"got {typename(ret_ann)}."
            )

    return




def _typeddict_msg(
    obj: object,
    typeddict: type,
    allowed_unk: bool = True
) -> str | None:

    if not isinstance(obj, Mapping):
        return "The object is not a dictionary."

    try:
        ann = typing.get_type_hints(typeddict, include_extras=True)
    except (NameError, TypeError, AttributeError, SyntaxError):
        ann = getattr(typeddict, "__annotations__", {})

    total = getattr(typeddict, "__total__", True)

    required = set()
    proc: dict[str, object] = {}

    for k, t in ann.items():
        origin = typing.get_origin(t)

        if origin is typing.Required or t is typing.Required:
            required.add(k)
            t = typing.get_args(t)[0]
        elif origin is typing.NotRequired:
            t = typing.get_args(t)[0]
        elif total:
            required.add(k)

        proc[k] = t

    for k in required:
        if k not in obj:
            return f"Missing required key: \"{k}\"."

    for k, v in obj.items():
        if k not in proc:
            if not allowed_unk:
                return f"Unknown key: \"{k}\"."
            continue

        if not typecheck(v, proc[k]):
            return _typeerr_msg(typename(proc[k]), v, True, k)

    return None


def _protocol_msg(value: object, cls: type[typing.Protocol]) -> str | None: # type: ignore
    if getattr(value, "_is_protocol", False) and isinstance(cls, type):
        return "cls is not a protocol type."

    if getattr(cls, "_is_runtime_protocol", False):
        try:
            if isinstance(value, cls):
                return None
            return f"{typename(value)}'s attribute or method is missing."
        except TypeError:
            pass

    members = {
        name for name in vars(cls)
        if not name.startswith("_")
    }
    members.update(
        name for name in getattr(cls, "__annotations__", {})
        if not name.startswith("_")
    )

    for name in members:
        if not hasattr(value, name):
            return f"{typename(value)} is missing attribute or method \"{name}\"."

    return None





def typecheck[T](
    value: object,
    type_info: T,
    strict: bool = False,
    class_context: type | None = None
) -> typing.TypeGuard[T]:
    """
    Check whether `value` satisfies the type specification `type_info`.

    Supports standard types, `None`, unions, `typing.TypeVar`, type aliases, 
    protocols, typed dictionaries, callables, and parameterized 
    container types.

    Return True if `value` is compatible with `type_info`.
    """
    origin, args = typing.get_origin(type_info), typing.get_args(type_info)

    if type_info is None or type_info is types.NoneType:
        return value is None

    if isinstance(type_info, typing.TypeVar):
        if type_info.__bound__ is not None:
            return typecheck(value, type_info.__bound__, strict)
        if type_info.__constraints__:
            return any(typecheck(value, t, strict) for t in type_info.__constraints__)
        return True

    if type_info is typing.Self:
        if class_context is None:
            raise TypeError("Cannot resolve \"Self\" without a class_context.")
        return isinstance(value, class_context)

    if isinstance(type_info, typing._SpecialForm):
        return _special_check(value, type_info, strict)
    if isinstance(origin, typing._SpecialForm):
        return _special_check(value, type_info, strict)

    if isinstance(origin, typing.TypeAliasType):
        return typecheck(value, origin.__value__, strict)

    if _is_protocol(type_info):
        return _protocol_msg(value, type_info) is None
    if origin is None and not args:
        if type_info is int and value.__class__ is bool:
            return False
        try:
            return isinstance(value, type_info) # type: ignore
        except TypeError:
            pass

    if origin is None:
        origin = type_info

    if _is_protocol(type_info):
        return _protocol_msg(value, type_info) is None

    if not isinstance(origin, type):
        raise TypeError(f"Unsupported type hint: {typename(type_info)}.")

    if origin is type and args:
        if not isinstance(value, type):
            return False
        return issubclass(value, args[0])


    if  isinstance(type_info, types.UnionType):
        return any(typecheck(value, t) for t in args)

    if typing.is_typeddict(type_info) and isinstance(type_info, type):
        return _typeddict_msg(value, type_info, not strict) is None

    if issubclass(origin, (Mapping, MappingView)):
        if not isinstance(value, Mapping):
            return False
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

    if issubclass(origin, tuple):
        if not isinstance(value, tuple) or len(args) != len(value):
            return False
        if args == ((),):
            return len(value) == 0
        if len(args) == 2 and args[1] is Ellipsis:
            return all(typecheck(v, args[0]) for v in value)
        if len(args) != len(value):
            return False
        return all(typecheck(v, t) for v, t in zip(value, args))

    if issubclass(origin, (Collection, Iterable)):
        if not isinstance(value, origin):
            return False
        if len(args) > 1:
            name = typename(origin)
            raise TypeHintError(f"The {name} type hint should be {name}[T] or {name}")
        if len(args) == 0:
            return isinstance(value, origin)
        return all(typecheck(v, args[0]) for v in value)

    if origin is Callable or origin is typing.Callable:
        if strict:
            return _callable_msg(value, type_info) is None
        return callable(value)

    return not strict



def validate(
    value: object,
    type_info: object,
    strict: bool = False,
    name: str | None = None,
    class_context: type | None = None,
) -> None:
    """
    Validate `value` against `type_info`.

    A `TypeError` is raised if validation fails. Typed dictionaries 
    are checked with optional strict key validation.
    """
    name = name or ""

    if typing.is_typeddict(type_info) and isinstance(type_info, type):
        msg = _typeddict_msg(value, type_info, not strict)
        if msg is not None:
            raise TypeError(msg)
        return

    if _is_protocol(type_info):
        msg = _protocol_msg(value, type_info)
        if msg is not None:
            raise TypeError(msg)
        return

    if typing.get_origin(type_info) is Callable:
        msg = _callable_msg(value, type_info)
        if msg is not None:
            raise TypeError(msg)
        return

    if not typecheck(value, type_info, strict, class_context):
        expected = typename(type_info)
        raise TypeError(_typeerr_msg(expected, value, True, name))


P = typing.ParamSpec("P")
R = typing.TypeVar("R")

def validate_call(func: Callable[P, R]) -> Callable[P, R]:
    """
    Decorate `func` to validate annotated arguments and return values.

    Argument binding and type checking are performed at runtime. If `func` 
    is an instance or class method, the class context is automatically 
    extracted to resolve `typing.Self` annotations.

    ```python
    class SimpleDict(dict[str, int]):
        @validate_call
        @classmethod
        def from_json(cls, filename: str) -> Self: ...

    data = SimpleDict.from_json("data.json")
    ```

    Note:
    -----

    While standard tools like `Pydantic` excel at static 
    schema generation, they intentionally sacrifice 
    runtime dynamic context for performance. 

    `pyhand.typekit` is explicitly designed to cover these 
    exact blind spots, offering uncompromising runtime 
    type safety where others fallback to throwing errors.
    """

    hints = typing.get_type_hints(func, include_extras=True)
    sig = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()

        cls_ctx = None
        if bound.arguments:
            # Retrieve the name of the first parameter in the signature.
            firstname = next(iter(sig.parameters))
            firstarg = bound.arguments[firstname]

            if firstname == "self":
                cls_ctx = firstarg.__class__
            elif firstname == "cls" and isinstance(firstarg, type):
                cls_ctx = firstarg

            for name, value in bound.arguments.items():
                hint = hints.get(name)
                if hint is not None:
                    validate(
                        value, hint,
                        name=name,
                        class_context=cls_ctx,
                    )
        retv = func(*args, **kwargs)

        ret_hint = hints.get("return")
        if ret_hint is not None:
            validate(
                retv, ret_hint,
                name="return value",
                class_context=cls_ctx,
            )
        return retv

    return wrapper
