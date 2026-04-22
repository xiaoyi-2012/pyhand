"""
Typed data model and utility primitives.

This package provides a lightweight runtime type system built around
validated data models, generic type utilities, and result handling.
It focuses on explicit behavior and minimal abstraction, offering an
alternative to heavier frameworks.

Core components include:

- Runtime-validated models via `TypedBase` and `Field`
- Runtime generics via `GenericBase` and related metaclasses
- Result types via `Ok`, `Err`, and `Result`

The design emphasizes predictability, composability, and alignment with
Python standard library style.
"""

from typed import core, generic, result
