# Copyright XiaoYi 2026. MIT license, see LICENSE file.
from __future__ import annotations

import types

from dataclasses import dataclass
from typing import (
    TypeAliasType,
    TypeVar,
    _SpecialForm as SpecialForm,
    _GenericAlias, # type: ignore
)

GenericAlias = types.GenericAlias | _GenericAlias
TypeForm = type | GenericAlias | TypeAliasType | SpecialForm | types.UnionType | TypeVar


@dataclass(slots=True, frozen=True)
class Ok[T]:
    """
    Immutable container representing a successful result.

    The contained `value` holds the result of a successful computation.
    """
    value: T

    def __bool__(self) -> bool:
        return True


@dataclass(slots=True, frozen=True)
class Err[T]:
    """
    Immutable container representing a failed result.

    The contained `value` typically holds error information.
    """
    value: T

    def __bool__(self) -> bool:
        return False



type Result[O, E] = Ok[O] | Err[E]
"""
Represent a computation that may succeed with `Ok[O]` or fail with `Err[E]`.

This pattern treats errors as values rather than exceptions, requiring
explicit handling of both success and failure cases. It is similar to
Rust's `Result<O, E>`.


- Explicitness:

    The return type clearly indicates possible failure, 
    encouraging callers to handle both outcomes.

- Predictable control flow:

    Error handling becomes part of normal program flow, 
    avoiding complex `try-except` structures.
"""
