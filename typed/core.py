"""
Runtime-validated data model utilities.

This module provides a lightweight system for defining strongly typed
data models with runtime validation. Unlike frameworks such as Pydantic,
it focuses on minimal overhead and explicit behavior without introducing
additional abstraction layers or complex configuration.

Models are defined by subclassing `TypedBase`, where type annotations
and optional `Field` specifications are collected and transformed into
a validation blueprint at class creation time. Validation is enforced
during both initialization and attribute assignment.

Main APIs
=========

- `TypedBase`
- `Field`
- `get_fields`
- `Undefined`
- `undefined`
"""
from collections.abc import Callable
from typing import (
    Any,
    dataclass_transform,
    get_type_hints
)

from error.exception import UndefinedError
from typekit.typecheck import validate

__all__ = (
    "Undefined",
    "undefined",
    "Field",
    "TypedBase",
    "get_fields"
)



PosKwArgsTuple = tuple[tuple[object, ...], dict[str, object]]

Undefined = type("Undefined", (), {})
undefined: Undefined  = Undefined()




class Field:
    """
    Define a strongly typed field for a model.

    Encapsulate type information, default values, factories, and validation
    logic. These instances are processed by `TypedMeta` during class
    creation to build the runtime validation blueprint.
    """
    # Leave the `name` and `cls` fields blank for now;
    # they will be injected by TypedMeta later.

    name: str
    type_info: object
    default: object| Undefined = undefined
    factory: Callable[[], Any] | None
    validator: Callable[[object, object], None]
    readonly: bool

    def __new__(
        cls,
        default: object| Undefined = undefined,
        factory: Callable | None = None,
        factory_args: PosKwArgsTuple | None = None,
        validator: Callable[[object, object], None] = validate,
        readonly: bool = False
    ) -> Any:
        self = object.__new__(cls)
        self.default = default

        if factory is not None:
            if default is not undefined:
                raise TypeError("Default and Factory cannot exist simultaneously.")
            if factory_args is None:
                self.factory = factory
            else:
                self.factory = lambda: factory(*factory_args[0], **factory_args[1])
        else:
            self.factory = None

        self.readonly = readonly
        self.validator = validator
        return self

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, name, undefined) is undefined:
            super().__setattr__(name, value)
            return
        raise TypeError("Field is immutable.")



class TypedMeta(type):
    """
    Metaclass for creating runtime-validated models.

    Extract type hints and `Field` definitions from the class namespace
    to construct a strictly typed blueprint. It automatically handles
    forward references and prevents namespace pollution.
    """
    __fields__: dict[str, Field]
    __slots__: tuple[str, ...]

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, object],
        **kwargs: object
    ) -> type:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        if name == "TypedBase":
            return cls

        try:
            hints = get_type_hints(cls)
        except NameError:
            hints = {} # Forward reference failed

        fields: dict[str, Field] = {}

        # Binding Field and type hint
        for field_name, field_type in hints.items():
            value = namespace.get(field_name, undefined)

            if isinstance(value, Field):
                f = value
                f.name = field_name
                f.type_info = field_type
                fields[field_name] = f
            else:
                f = Field(default=value) # type: ignore
                f.name = field_name
                f.type_info = field_type
                fields[field_name] = f

            if hasattr(cls, field_name):
                delattr(cls, field_name)

        cls.__fields__ = fields
        cls.__slots__ = tuple(fields.keys()) + ("__fields__",)

        return cls



@dataclass_transform(field_specifiers=(Field,))
class TypedBase(metaclass=TypedMeta):
    """
    Base class for runtime-validated data models.

    Enforce strict type checking during instantiation and attribute
    assignment. Support read-only fields, default factories, and native
    private attribute encapsulation.

    ```python
    class User(TypedBase):
        name: str
        age: int = 18
        email: str | None = Field(readonly=True)
        tags: list[str] = Field(factory=list)
        ...
    ```
    """
    def __init_subclass__(cls) -> None:
        # Confirm that the user has not overridden:
        # __init__, __new__, or __setattr__.
        if cls.__init__ is not TypedBase.__init__ or \
            cls.__new__ is not TypedBase.__new__ or  \
            cls.__setattr__ is not TypedBase.__setattr__:
            raise TypeError("TypedBase cannot be overridden by __new__, __init__, or __setattr__.")

    def __init__(self, *args, **kwargs: object) -> None:
        fields = getattr(self, "__fields__", {}) # type: dict[str, Field]
        names = list(fields.keys())

        # Parameter quantity overflow check
        if len(args) > len(names):
            raise TypeError(
                f"{self.__class__.__name__}() takes {len(names)} "
                f"positional arguments but {len(args)} were given"
            )

        # Map positional arguments (`args`)
        # precisely back to `kwargs`
        for i, argv in enumerate(args):
            name = names[i]

            # Intercepting duplicate assignments of
            # position and keyword
            if name in kwargs:
                raise TypeError(
                    f"{self.__class__.__name__}() got multiple values "
                    f"for argument \"{name}\""
                )
            kwargs[name] = argv

        for name, field in fields.items():
            # Restoring private variable names:
            # Restore `_A__password` to `__password`
            init_key = name
            prefix = f"_{type(self).__name__}__"
            if name.startswith(prefix):
                init_key = f"__{name[len(prefix):]}"

            if init_key in kwargs:
                value = kwargs.pop(init_key)
                field.validator(value, field.type_info)
                object.__setattr__(self, name, value)

            elif field.factory is not None:
                value = field.factory()
                field.validator(value, field.type_info)
                object.__setattr__(self, name, value)

            # The user didn't upload any data,
            # but there are preset values.
            elif field.default is not undefined:
                value = field.default
                field.validator(value, field.type_info)
                object.__setattr__(self, name, value)

            # No factory, no preset value,
            # these are required parameters.
            else:
                raise UndefinedError(
                    "Missing required argument: " + \
                    f"\"{init_key}\" for {type(self).__name__}"
                )

        if kwargs:
            # If kwargs still has items, it means the user passed
            # arguments that are not defined in the fields.
            unexpected = ", ".join(kwargs.keys())
            raise ValueError(
                f"Unexpected arguments for {type(self).__name__}: " + \
                unexpected
            )

    def __setattr__(self, name: str, value: object) -> None:
        if name in getattr(self, "__fields__", {}):
            field = getattr(self, "__fields__", {})[name]
            field.validator(value, field.type_info)
            if field.readonly:
                raise TypeError(f"The field \"{name}\" is readonly.")
            super().__setattr__(name, value)
            return

        # Unknown field
        raise TypeError(f"\"{name}\" is not a field of {type(self).__name__}.")

    def __repr__(self) -> str:
        keys = getattr(self, "__slots__", ())

        args = ", ".join(
            f"{k}={getattr(self, k)!r}"
            for k in keys
            if k != "__fields__"
        )

        return f"{self.__class__.__name__}({args})"


def get_fields(cls: type) -> tuple[str, ...]:
    """
    Return the field names available on `cls`.
    """
    return getattr(cls, "__slots__", None) or getattr(cls, "__dict__")
