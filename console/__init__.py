"""
Console and terminal output utilities.

This package provides tools for styled console output, stream-based
writing, and color formatting. It includes lightweight abstractions
for logging, ANSI color handling, and C++-style stream operations.

Modules
=======

- `color` for RGB colors and ANSI formatting
- `console` for structured console logging
- `stream` for buffered output with manipulators

The design emphasizes simplicity and composability, offering convenient
output utilities without heavy dependencies or complex configuration.
"""
from console import console, stream, color
