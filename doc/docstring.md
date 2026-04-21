<!-- docstring.md -->
# Docstring & Naming Style Guide

This document defines the conventions used in this project for writing
docstrings and naming APIs. The goal is to keep documentation concise,
consistent, and aligned with Python standard library style.

---

## 1. General Principles

* Follow **PEP 257** (multi-line docstrings).
* Prefer **short, precise descriptions** over long explanations.
* Describe **behavior**, not implementation details.
* Use **stdlib-like tone** (similar to `typing`, `inspect`, `functools`).

---

## 2. Docstring Format

### Structure

```python
def func(...) -> object:
    """
    Summary sentence.

    Optional additional description.
    """
```

### Rules

* Triple quotes on separate lines.
* First line: **summary sentence**.
* Leave one blank line before additional text.
* Do not use `Args:` / `Returns:` sections.
* Use **natural sentences**, not bullet-heavy descriptions.

---

## 3. Code Formatting in Docstrings

* Use **single backticks** for inline code:

  ```text
  `value`
  ```

* Markdown code blocks (` ```python `) are allowed for examples.

---

## 4. Writing Style

### Preferred

```text
Return the name of a type.

Check whether `value` satisfies `type_info`.
```

### Avoid

```text
This function will...
Use this function to...
Internally it uses...
```

---

## 5. Abstraction Rules

### Good (behavior-focused)

```text
Return a qualified name when available.
```

### Bad (implementation detail)

```text
Return `value.__qualname__`.
```

---

## 6. Docstring Length

* Keep docstrings **short by default**
* Add details only when necessary
* Prefer **2–5 lines**

---

## 7. Examples

### Minimal

```python
"""
Return the name of a type.
"""
```

### Standard

```python
"""
Return the name of a type or object.

If `qualname` is true, a qualified name is returned when available.
"""
```

### With Example

````python
"""
Return the result of `foo`.

```python
foo = get_foo()
result = use_foo(foo)
```
"""

---

## 8. Module Docstring

Include:

1. Short description
2. Key features
3. Main APIs
4. Optional usage example

### Example

```python
"""
Utilities for working with `foo`.

This module provides helpers for creating and validating `foo`
objects.

Main APIs:

- `get_foo`
- `use_foo`
"""
```

---

## 9. Design Philosophy

* Keep APIs **predictable and explicit**
* Favor **clarity over cleverness**
* Align with **Python standard library style**
* Build **composable, low-level utilities**

---

## 10. Summary

This project follows a style that is:

* Minimal
* Explicit
* Pythonic
* Standard-library inspired

The goal is to produce documentation that is easy to read,
easy to maintain, and consistent across the entire codebase.
