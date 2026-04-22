"""
Color representation and ANSI formatting utilities.

This module provides a `Color` type for working with RGB-based colors,
including conversion to HSL, HSV, and hex formats. Colors are normalized
and cached to ensure consistent identity.

It also supports generating ANSI escape sequences for terminal output,
allowing colors to be applied directly to strings.

Main APIs
=========

- `Color`
- `Colors`
"""
import colorsys

from typing import TypeVar
from error.exception import FormatError


Rgb3Tuple = tuple[int, int, int] | tuple[float, float, float]
IntOrFloat = TypeVar("IntOrFloat", int, float)


def _clamp(rgb: Rgb3Tuple) -> tuple[float, float, float]:
    if len(rgb) != 3:
        raise TypeError("Color arguments must be of length 3.")

    r, g, b = rgb
    if not type(r) == type(g) == type(b): # pylint: disable=unidiomatic-typecheck
        raise TypeError("Color arguments must be of the same type.")

    if isinstance(r, float):
        return (
            min(max(float(rgb[0]), 0.0), 1.0),
            min(max(float(rgb[1]), 0.0), 1.0),
            min(max(float(rgb[2]), 0.0), 1.0),
            )
    if isinstance(r, int):
        return (
            min(max(int(rgb[0]), 0), 255) / 255.0,
            min(max(int(rgb[1]), 0), 255) / 255.0,
            min(max(int(rgb[2]), 0), 255) / 255.0,
        )
    raise TypeError("Color arguments must be either all floats or all ints")

class Color:
    """
    Represent a color normalized to floating-point RGB values.

    A `Color` can be converted to RGB, HSL, HSV, and hex forms. It can
    also produce ANSI foreground escape sequences for terminal output.
    Converting the object to `str` returns the ANSI code from
    `to_ansi()`, so it can be written directly before console text.
    """
    __slots__ = "_rgb",

    _rgb: tuple[float, float, float]
    _instances: dict[Rgb3Tuple, "Color"] = {}


    def __new__(
        cls,
        r: IntOrFloat,
        g: IntOrFloat,
        b: IntOrFloat
    ) -> "Color":
        norm = _clamp((r, g, b))

        if norm in cls._instances: # Cached
            return cls._instances[norm]

        instance = super().__new__(cls)
        instance._rgb = norm

        cls._instances[norm] = instance
        return instance

    @property
    def rgb255(self) -> tuple[int, int, int]:
        """Return the color as `0..255` RGB values."""
        return \
            round(self._rgb[0] * 255), \
            round(self._rgb[1] * 255), \
            round(self._rgb[2] * 255)

    @property
    def hex(self) -> str:
        """Return the color as an uppercase hex string."""
        r, g, b = self.rgb255
        return f"#{r:02x}{g:02x}{b:02x}".upper()

    @property
    def hsl(self) -> tuple[float, float, float]:
        """Return the color as an HSL tuple."""
        return colorsys.rgb_to_hls(*self._rgb)

    @property
    def hsv(self) -> tuple[float, float, float]:
        """Return the color as an HSV tuple."""
        return colorsys.rgb_to_hsv(*self._rgb)

    @property
    def rgb(self) -> tuple[float, float, float]:
        """Return the color as normalized RGB values."""
        return self._rgb

    def to_ansi(self) -> str:
        """
        Return the ANSI foreground escape sequence for this color.
        """
        r, g, b = self.rgb255
        return f"\033[38;2;{r};{g};{b}m"

    @classmethod
    def from_hex(cls, hex_code: str) -> "Color":
        """Return a color parsed from a hex string."""
        hex_code = hex_code.lstrip("#")
        if len(hex_code) != 6:
            raise FormatError(f"Invalid hex color: {hex_code}")

        r, g, b = (int(hex_code[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
        return cls(r, g, b)

    @classmethod
    def from_hsl(cls, h: float, s: float, l: float) -> "Color":
        """Return a color converted from HSL values."""
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return cls(r, g, b)

    @classmethod
    def from_hsv(cls, h: float, s: float, v: float) -> "Color":
        """Return a color converted from HSV values."""
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return cls(r, g, b)

    def __str__(self) -> str:
        """Return the ANSI escape sequence for this color."""
        return self.to_ansi()

    def __repr__(self) -> str:
        """Return the representation of this color."""
        return f"Color(r={self._rgb[0]:.2f}, g={self._rgb[1]:.2f}, b={self._rgb[2]:.2f})"

    def __add__(self, other: str) -> str:
        if not isinstance(other, str):
            return NotImplemented
        return self.to_ansi() + other

class Colors:
    """
    Standard color constants defined as `Color` objects.

    This class provides a collection of predefined colors.
    """
    RESET   = "\033[0m"
    WHITE   = Color(1.0, 1.0, 1.0)
    BLACK   = Color(0.0, 0.0, 0.0)
    RED     = Color(1.0, 0.0, 0.0)
    GREEN   = Color(0.0, 1.0, 0.0)
    BLUE    = Color(0.0, 0.0, 1.0)
    CYAN    = Color(0.0, 1.0, 1.0)
    YELLOW  = Color(1.0, 1.0, 0.0)
    MAGENTA = Color(1.0, 0.0, 1.0)
    GREY    = Color(0.5, 0.5, 0.5)
    ORANGE  = Color(1.0, 0.5, 0.0)
    PURPLE  = Color(0.5, 0.0, 0.5)
    BROWN   = Color(0.6, 0.4, 0.2)
    PINK    = Color(1.0, 0.7, 0.7)
    TEAL    = Color(0.0, 0.5, 0.5)
    LIME    = Color(0.0, 1.0, 0.0)
    OLIVE   = Color(0.5, 0.5, 0.0)
    SILVER  = Color(0.7, 0.7, 0.7)
    GOLD    = Color(1.0, 0.8, 0.0)
    NAVY    = Color(0.0, 0.0, 0.5)
    FUCHSIA = Color(1.0, 0.0, 0.5)
    MAROON  = Color(0.5, 0.0, 0.0)
    AQUA    = Color(0.0, 1.0, 1.0)
