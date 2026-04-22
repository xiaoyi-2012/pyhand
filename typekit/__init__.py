"""
TypeKit: The Ultimate Runtime Type Engine for pyhand.

This package bridges the gap between Python's static type hints and 
dynamic execution. It provides a suite of uncompromising, C++-inspired 
tools for runtime type validation and method dispatch.

Modules
=======

- `typecheck`: The core validation engine. It dissects complex Generics, 
  Unions, and dynamic contexts (like `Self`) to enforce strict type 
  safety at execution time.

- `overload`: A true runtime multiple-dispatch system. It resolves 
  `@apply_overload` signatures using Subtyping Distance (MRO) to find 
  the "best match", entirely preventing ambiguous calls.

- `utils`: Hardcore developer ergonomics, including MRO calculation 
  algorithms and interface-constraint utilities (e.g., `used()`).
"""
from typekit import overload, typecheck, utils
