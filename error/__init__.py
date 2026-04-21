"""
PyHand Error and Diagnostics Subsystem.

Provides context-aware exceptions, custom traceback formatting, 
and stack trace filtering for the pyhand framework.

Modules:
--------
- `exception`:
    Domain-specific errors (e.g., OverloadError) that 
    preserve function signatures and execution context.

-  `tracer`:
    Utilities for cleaning and filtering internal call stacks.
"""

from error.exception import *
