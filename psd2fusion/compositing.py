"""Deterministic RGBA compositing primitives used by PARITY-003 fixtures.

The converter lowers semantics to Fusion, but it also needs a small, explicit
oracle for fixture generation and boundary tests.  This module intentionally
has no PSD or Fusion dependency.  Pixels are accepted and returned as straight
RGBA tuples in the inclusive ``0..1`` range unless ``clamp=False`` is
requested for an over-range diagnostic.

The default working space is the declared 8-bit sRGB document space.  A
linear-sRGB option is provided so a fixture can make the transfer-function
boundary explicit; it is never selected implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence, Tuple


RGBA = Tuple[float, float, float, float]
RGB = Tuple[float, float, float]

CORE_BLEND_MODES = ("Normal", "Multiply", "Linear Dodge", "Overlay")
COLOR_SPACES = ("sRGB", "linear-sRGB")
TRANSPARENT_RGB_POLICIES = ("canonical_zero", "preserve")


class CompositingError(ValueError):
    """Raised when a fixture asks for an undefined compositing contract."""


@dataclass(frozen=True)
class ColorSpaceSpec:
    """Named color/ICC boundary carried by a fixture.

    ``icc_profile_sha256`` is metadata only.  It lets a caller bind a PNG or
    Photoshop document to the exact profile bytes without hiding a transform
    inside the arithmetic implementation.
    """

    name: str = "sRGB"
    icc_profile_sha256: str | None = None
    transfer: str | None = None

    def __post_init__(self) -> None:
        if self.name not in COLOR_SPACES:
            raise CompositingError("unsupported color space: %s" % self.name)
        expected = "linear" if self.name == "linear-sRGB" else "srgb"
        if self.transfer is None:
            object.__setattr__(self, "transfer", expected)
        elif self.transfer != expected:
            raise CompositingError(
                "color space %s requires transfer=%s" % (self.name, expected)
            )


def _finite(value: float, label: str) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise CompositingError("%s must be numeric" % label) from exc
    if not math.isfinite(value):
        raise CompositingError("%s must be finite" % label)
    return value


def _channel(value: float, label: str, clamp: bool) -> float:
    value = _finite(value, label)
    if clamp:
        return max(0.0, min(1.0, value))
    return value


def _alpha(value: float, label: str) -> float:
    value = _finite(value, label)
    return max(0.0, min(1.0, value))


def _rgba(pixel: Sequence[float], label: str, clamp: bool) -> RGBA:
    if len(pixel) != 4:
        raise CompositingError("%s must contain RGBA" % label)
    return (
        _channel(pixel[0], label + ".r", clamp),
        _channel(pixel[1], label + ".g", clamp),
        _channel(pixel[2], label + ".b", clamp),
        _alpha(pixel[3], label + ".a"),
    )


def _srgb_to_linear(value: float) -> float:
    value = max(0.0, min(1.0, value))
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(value: float) -> float:
    value = max(0.0, min(1.0, value))
    if value <= 0.0031308:
        return value * 12.92
    return 1.055 * (value ** (1.0 / 2.4)) - 0.055


def _to_working(rgb: RGB, color_space: ColorSpaceSpec) -> RGB:
    if color_space.name == "sRGB":
        return rgb
    return tuple(_srgb_to_linear(value) for value in rgb)  # type: ignore[return-value]


def _from_working(rgb: RGB, color_space: ColorSpaceSpec) -> RGB:
    if color_space.name == "sRGB":
        return rgb
    return tuple(_linear_to_srgb(value) for value in rgb)  # type: ignore[return-value]


def _blend_channel(backdrop: float, source: float, mode: str) -> float:
    if mode == "Normal":
        return source
    if mode == "Multiply":
        return backdrop * source
    if mode == "Linear Dodge":
        return backdrop + source
    if mode == "Overlay":
        if backdrop <= 0.5:
            return 2.0 * backdrop * source
        return 1.0 - 2.0 * (1.0 - backdrop) * (1.0 - source)
    raise CompositingError("unsupported blend mode: %s" % mode)


def blend_rgb(
    backdrop: Sequence[float],
    source: Sequence[float],
    mode: str,
    *,
    color_space: ColorSpaceSpec | str = "sRGB",
    clamp: bool = True,
) -> RGB:
    """Evaluate a separable blend function in the declared working space."""

    if isinstance(color_space, str):
        color_space = ColorSpaceSpec(color_space)
    if mode not in CORE_BLEND_MODES:
        raise CompositingError("unsupported blend mode: %s" % mode)
    if len(backdrop) != 3 or len(source) != 3:
        raise CompositingError("blend_rgb expects RGB triples")
    b = tuple(_channel(value, "backdrop", clamp) for value in backdrop)
    s = tuple(_channel(value, "source", clamp) for value in source)
    bw = _to_working(b, color_space)  # type: ignore[arg-type]
    sw = _to_working(s, color_space)  # type: ignore[arg-type]
    result = tuple(_blend_channel(bw[i], sw[i], mode) for i in range(3))
    if clamp:
        result = tuple(max(0.0, min(1.0, value)) for value in result)
    encoded = _from_working(result, color_space)  # type: ignore[arg-type]
    if clamp:
        encoded = tuple(max(0.0, min(1.0, value)) for value in encoded)
    return encoded  # type: ignore[return-value]


def premultiply(pixel: Sequence[float], *, clamp: bool = True) -> RGBA:
    """Convert straight RGBA to premultiplied RGB-alpha."""

    r, g, b, a = _rgba(pixel, "pixel", clamp)
    return (r * a, g * a, b * a, a)


def unpremultiply(pixel: Sequence[float], *, clamp: bool = True) -> RGBA:
    """Convert premultiplied RGBA to straight RGBA without edge fringe."""

    r, g, b, a = _rgba(pixel, "premultiplied", clamp)
    if a <= 0.0:
        return (0.0, 0.0, 0.0, 0.0)
    values = (r / a, g / a, b / a, a)
    if clamp:
        return (
            max(0.0, min(1.0, values[0])),
            max(0.0, min(1.0, values[1])),
            max(0.0, min(1.0, values[2])),
            a,
        )
    return values  # type: ignore[return-value]


def apply_opacity(pixel: Sequence[float], opacity: float, *, clamp: bool = True) -> RGBA:
    """Apply an ordinary opacity stage once to a completed straight pixel."""

    rgba = _rgba(pixel, "pixel", clamp)
    opacity = _alpha(opacity, "opacity")
    # Straight RGB is unchanged by an opacity stage; its alpha is the coverage
    # that the next source-over boundary consumes.
    return (rgba[0], rgba[1], rgba[2], rgba[3] * opacity)


def composite_pixel(
    backdrop: Sequence[float],
    source: Sequence[float],
    mode: str = "Normal",
    opacity: float = 1.0,
    *,
    color_space: ColorSpaceSpec | str = "sRGB",
    clamp: bool = True,
    transparent_rgb: str = "canonical_zero",
) -> RGBA:
    """Composite one straight-alpha source over one straight-alpha backdrop.

    The blend function is evaluated on straight RGB values in the declared
    working space.  RGB is then combined in premultiplied form and converted
    back to straight RGBA exactly once.  A zero-alpha backdrop's hidden RGB is
    canonicalized to black by default, and the source is kept unblended where
    that backdrop is transparent, so transparent pixels cannot create an edge
    fringe or a mode-dependent hidden dependency.
    """

    if isinstance(color_space, str):
        color_space = ColorSpaceSpec(color_space)
    if transparent_rgb not in TRANSPARENT_RGB_POLICIES:
        raise CompositingError(
            "unsupported transparent RGB policy: %s" % transparent_rgb
        )
    b = _rgba(backdrop, "backdrop", clamp)
    s = _rgba(source, "source", clamp)
    opacity = _alpha(opacity, "opacity")
    source_alpha = s[3] * opacity
    backdrop_alpha = b[3]
    backdrop_rgb = b[:3]
    if backdrop_alpha == 0.0 and transparent_rgb == "canonical_zero":
        backdrop_rgb = (0.0, 0.0, 0.0)

    source_work = _to_working(s[:3], color_space)
    blended = blend_rgb(
        backdrop_rgb,
        s[:3],
        mode,
        color_space=color_space,
        clamp=clamp,
    )
    b_work = _to_working(backdrop_rgb, color_space)
    blend_work = _to_working(blended, color_space)
    out_alpha = source_alpha + backdrop_alpha * (1.0 - source_alpha)
    # Blend only where a backdrop exists.  Over a transparent backdrop the
    # source remains visible (and a hidden non-zero backdrop RGB cannot leak
    # into the result); a partial backdrop linearly mixes source and blended
    # colors before source-over alpha is applied.
    blended_source = tuple(
        (1.0 - backdrop_alpha) * source_work[index]
        + backdrop_alpha * blend_work[index]
        for index in range(3)
    )
    premultiplied = tuple(
        source_alpha * blended_source[index]
        + backdrop_alpha * (1.0 - source_alpha) * b_work[index]
        for index in range(3)
    )
    if out_alpha <= 0.0:
        # Canonical transparent RGB prevents a hidden non-zero source/backdrop
        # color from becoming a fringe after a later unpremultiply.
        return (0.0, 0.0, 0.0, 0.0)
    straight_work = tuple(value / out_alpha for value in premultiplied)
    if clamp:
        straight_work = tuple(max(0.0, min(1.0, value)) for value in straight_work)
    result_rgb = _from_working(straight_work, color_space)
    if clamp:
        result_rgb = tuple(max(0.0, min(1.0, value)) for value in result_rgb)
    return (result_rgb[0], result_rgb[1], result_rgb[2], out_alpha)


def composite_layers(
    backdrop: Sequence[float],
    layers: Iterable[tuple[Sequence[float], str, float]],
    *,
    color_space: ColorSpaceSpec | str = "sRGB",
    clamp: bool = True,
    transparent_rgb: str = "canonical_zero",
) -> RGBA:
    """Apply bottom-to-top ``(pixel, mode, opacity)`` layers."""

    result = _rgba(backdrop, "backdrop", clamp)
    for index, (pixel, mode, opacity) in enumerate(layers):
        result = composite_pixel(
            result,
            pixel,
            mode,
            opacity,
            color_space=color_space,
            clamp=clamp,
            transparent_rgb=transparent_rgb,
        )
    return result


def composite_isolated_group(
    backdrop: Sequence[float],
    layers: Iterable[tuple[Sequence[float], str, float]],
    opacity: float = 1.0,
    *,
    color_space: ColorSpaceSpec | str = "sRGB",
    clamp: bool = True,
    transparent_rgb: str = "canonical_zero",
) -> RGBA:
    """Render a group on transparent local backdrop, then apply group opacity."""

    local = composite_layers(
        (0.0, 0.0, 0.0, 0.0),
        layers,
        color_space=color_space,
        clamp=clamp,
        transparent_rgb=transparent_rgb,
    )
    return composite_pixel(
        backdrop,
        local,
        "Normal",
        _alpha(opacity, "group opacity"),
        color_space=color_space,
        clamp=clamp,
        transparent_rgb=transparent_rgb,
    )


def composite_pass_through_group(
    backdrop: Sequence[float],
    layers: Iterable[tuple[Sequence[float], str, float]],
    opacity: float = 1.0,
    *,
    color_space: ColorSpaceSpec | str = "sRGB",
    clamp: bool = True,
    transparent_rgb: str = "canonical_zero",
) -> RGBA:
    """Evaluate a pass-through group only at its explicit supported boundary.

    A pass-through group with opacity is intentionally rejected: applying its
    opacity to each child or to the final parent stream are different
    Photoshop semantics and require a host fixture.  This is a fail-closed
    diagnostic, not an approximation.
    """

    if abs(_alpha(opacity, "group opacity") - 1.0) > 1e-12:
        raise CompositingError("pass-through group opacity requires host proof")
    return composite_layers(
        backdrop,
        layers,
        color_space=color_space,
        clamp=clamp,
        transparent_rgb=transparent_rgb,
    )
