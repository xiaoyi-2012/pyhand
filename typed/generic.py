"""
Runtime generic type utilities.

This module provides metaclasses and base classes for creating
runtime-preserving generic types with support for specialization,
introspection, and caching.

Main APIs
=========

- `ConcreteGenericMeta`
- `TypeGenericMeta`
- `GenericBase`
- `TypeGenericBase`
"""
import types
from typing import Any, TypeAliasType

__all__ = (
    "ConcreteGenericMeta",
    "TypeGenericMeta",
    "GenericBase",
    "TypeGenericBase"
)


_GenericCachePool = dict[tuple[type, tuple[Any, ...]], type]
GenericArgsType = type | types.UnionType | types.GenericAlias | types.EllipsisType | None


class ConcreteGenericMeta(type):
    """
    Metaclass that enables runtime generic instantiation.

    This metaclass intercepts subscription syntax (e.g. `Class[T]`)
    and dynamically creates a concrete subclass with bound generic
    arguments stored in `__args__` and `__origin__`.

    Unlike `typing.Generic`, which is erased at runtime, this system
    preserves full runtime type information and allows introspection
    and caching of generated generic classes.

    Generated classes are cached to ensure identity consistency.
    """
    __origin__: Any
    __args__: tuple[Any, ...]

    _cache_pool: _GenericCachePool = {}


    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, object],
        /,
        **unused_args
    ) -> type:
        cls =  super().__new__(
            mcs, name,
            bases,
            namespace,
        )
        if "__origin__" not in namespace:
            cls.__origin__ = cls
        if "__args__" not in namespace:
            cls.__args__ = ()

        return cls

    def __getitem__(cls, args: object) -> type["ConcreteGenericMeta"]:
        if not isinstance(args, tuple):
            args = args,

        # This line usually won't run, Python will first raise a SyntaxError.
        # But this is to prevent users from making direct calls.
        if not args:
            raise TypeError(f"The generic arguments of {cls.__name__} cannot be empty")

        key = (cls, args)
        # Instances in the cache pool
        if key in cls._cache_pool:
            return cls._cache_pool[key]

        namespace = {"__origin__": cls, "__args__": args}
        generic = ", ".join(getattr(arg, "__name__", repr(arg)) for arg in args)
        name = f"{cls.__name__}[{generic}]"

        new_generic = type(name, (cls,), namespace)

        # Store in cache
        cls._cache_pool[key] = new_generic
        return new_generic # type: ignore

    def __repr__(cls) -> str:
        return cls.__name__



class TypeGenericMeta(ConcreteGenericMeta):
    """
    Strict runtime generic metaclass that only accepts type-based arguments.

    This metaclass extends `ConcreteGenericMeta` by enforcing that all
    generic arguments must be actual type objects (or compatible generic
    aliases, union types). Non-type values are rejected at runtime.

    This ensures stronger type safety for runtime generic instantiation,
    preventing invalid or non-type arguments from being used in generic
    construction.
    """
    def __getitem__(cls, args: object) -> type:
        if not isinstance(args, tuple):
            args = args,

        for arg in args:
            if not (isinstance(arg, (
                type,
                types.UnionType,
                TypeAliasType,
                types.GenericAlias,
                )) \
                or args is None or arg is ...
            ):
                # _SpecialForm and _BaseGenericAlias do not support typing
                raise TypeError(f"Invalid generic arguments: {arg!r}")
        return super().__getitem__(args)




class GenericBase(metaclass=ConcreteGenericMeta):
    """
    Base class for runtime generic types.

    Subclasses of this class support subscription syntax (e.g. `MyType[int]`)
    which generates a new concrete class instance at runtime.

    Each generated class contains:
    - `__origin__`: the original generic base class
    - `__args__`: the type arguments used for instantiation

    This enables runtime type introspection and identity-preserving caching
    of generic specializations.

    Note:
        This system is independent of `typing.Generic` and is not erased
        at runtime.
    """
    __origin__: Any
    __args__: tuple[Any, ...]


class TypeGenericBase(metaclass=TypeGenericMeta):
    """
    Strict runtime generic base class that enforces type-only parameters.

    This class behaves like `GenericBase`, but adds an additional constraint:
    all generic arguments must be valid type objects.

    It is designed for systems that require strong runtime validation of
    generic parameters, ensuring that only concrete type information is
    accepted during specialization.

    Invalid arguments (e.g. values, instances, or unsupported generics)
    will raise a TypeError at runtime.
    """
    __origin__: Any
    __args__: tuple[GenericArgsType, ...]
