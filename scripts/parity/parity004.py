"""Deterministic grouped/default clipping fixtures and validator.

The fixture manifest is an executable contract oracle for ``clbl`` absent /
default-true and explicit-true spans.  Expected pixels are calculated by the
independent reference equations below, then compared with the implementation
under test.  An actual Fusion render and comparison with the real-case golden
PNG are required before any Fusion pixel claim can be promoted. Photoshop
evidence is optional historical/additional evidence; an optional GIMP
cross-render may supplement the independent fixture and PSD-structure gates.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from PIL import Image, ImageCms

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psd2fusion.compositing import CORE_BLEND_MODES, composite_clipping_span
from scripts.parity.parity import compare_images


RGBA = Tuple[float, float, float, float]
RGB = Tuple[float, float, float]

BACKDROPS: Tuple[Tuple[str, RGBA], ...] = (
    ("transparent", (0.73, 0.31, 0.12, 0.0)),
    ("black", (0.0, 0.0, 0.0, 1.0)),
    ("white", (1.0, 1.0, 1.0, 1.0)),
    ("gray", (0.5, 0.5, 0.5, 1.0)),
    ("saturated", (0.08, 0.86, 0.25, 1.0)),
    ("partial-alpha", (0.18, 0.42, 0.76, 0.5)),
)
BASE_ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0)
MEMBER_ALPHAS = (0.0, 0.5, 1.0)
OPACITY_VALUES = (0.0, 0.5, 1.0)
OPACITY_PAIRS = tuple((base, member) for base in OPACITY_VALUES for member in OPACITY_VALUES)
EDGE_ALPHAS = (0.125, 0.375, 0.625, 0.875)
EDGE_OPACITY_PAIRS = ((0.25, 0.75), (0.75, 0.25))
CLBL_PROVENANCES = ("photoshop_default_true", "explicit_psd_clbl")


def _byte(value: float) -> int:
    return int(round(max(0.0, min(1.0, float(value))) * 255.0))


def _rgba_ref(pixel: Sequence[float], clamp: bool) -> RGBA:
    if len(pixel) != 4:
        raise ValueError("RGBA pixel must contain four channels")
    values = [float(value) for value in pixel]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("RGBA pixel must contain finite channels")
    if clamp:
        values[:3] = [max(0.0, min(1.0, value)) for value in values[:3]]
    values[3] = max(0.0, min(1.0, values[3]))
    return tuple(values)  # type: ignore[return-value]


def _opacity_ref(value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("opacity must be finite")
    return max(0.0, min(1.0, value))


def _srgb_to_linear_ref(value: float) -> float:
    value = max(0.0, min(1.0, value))
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _linear_to_srgb_ref(value: float) -> float:
    value = max(0.0, min(1.0, value))
    if value <= 0.0031308:
        return value * 12.92
    return 1.055 * (value ** (1.0 / 2.4)) - 0.055


def _to_work_ref(rgb: RGB, color_space: str) -> RGB:
    if color_space == "sRGB":
        return rgb
    if color_space == "linear-sRGB":
        return tuple(_srgb_to_linear_ref(value) for value in rgb)  # type: ignore[return-value]
    raise ValueError("unsupported color space: %s" % color_space)


def _from_work_ref(rgb: RGB, color_space: str) -> RGB:
    if color_space == "sRGB":
        return rgb
    if color_space == "linear-sRGB":
        return tuple(_linear_to_srgb_ref(value) for value in rgb)  # type: ignore[return-value]
    raise ValueError("unsupported color space: %s" % color_space)


def _blend_channel_ref(backdrop: float, source: float, mode: str) -> float:
    if mode == "Normal":
        return source
    if mode == "Multiply":
        return backdrop * source
    if mode == "Screen":
        return backdrop + source - backdrop * source
    if mode == "Linear Dodge":
        return backdrop + source
    if mode == "Overlay":
        if backdrop <= 0.5:
            return 2.0 * backdrop * source
        return 1.0 - 2.0 * (1.0 - backdrop) * (1.0 - source)
    raise ValueError("unsupported blend mode: %s" % mode)


def _blend_rgb_ref(backdrop: Sequence[float], source: Sequence[float], mode: str,
                   color_space: str, clamp: bool) -> RGB:
    b = tuple(float(value) for value in backdrop)
    s = tuple(float(value) for value in source)
    if len(b) != 3 or len(s) != 3:
        raise ValueError("blend RGB values must contain three channels")
    if clamp:
        b = tuple(max(0.0, min(1.0, value)) for value in b)
        s = tuple(max(0.0, min(1.0, value)) for value in s)
    bw = _to_work_ref(b, color_space)  # type: ignore[arg-type]
    sw = _to_work_ref(s, color_space)  # type: ignore[arg-type]
    blended = tuple(_blend_channel_ref(bw[i], sw[i], mode) for i in range(3))
    if clamp:
        blended = tuple(max(0.0, min(1.0, value)) for value in blended)
    encoded = _from_work_ref(blended, color_space)  # type: ignore[arg-type]
    if clamp:
        encoded = tuple(max(0.0, min(1.0, value)) for value in encoded)
    return encoded  # type: ignore[return-value]


def _composite_pixel_ref(backdrop: Sequence[float], source: Sequence[float], mode: str,
                         opacity: float, color_space: str, clamp: bool,
                         transparent_rgb: str = "canonical_zero") -> RGBA:
    b = _rgba_ref(backdrop, clamp)
    s = _rgba_ref(source, clamp)
    opacity = _opacity_ref(opacity)
    source_alpha = s[3] * opacity
    backdrop_alpha = b[3]
    backdrop_rgb = (0.0, 0.0, 0.0) if backdrop_alpha == 0.0 and transparent_rgb == "canonical_zero" else b[:3]
    source_work = _to_work_ref(s[:3], color_space)
    blended = _blend_rgb_ref(backdrop_rgb, s[:3], mode, color_space, clamp)
    b_work = _to_work_ref(backdrop_rgb, color_space)
    blend_work = _to_work_ref(blended, color_space)
    out_alpha = source_alpha + backdrop_alpha * (1.0 - source_alpha)
    blended_source = tuple(
        (1.0 - backdrop_alpha) * source_work[index] + backdrop_alpha * blend_work[index]
        for index in range(3)
    )
    premultiplied = tuple(
        source_alpha * blended_source[index]
        + backdrop_alpha * (1.0 - source_alpha) * b_work[index]
        for index in range(3)
    )
    if out_alpha <= 0.0:
        return (0.0, 0.0, 0.0, 0.0)
    straight_work = tuple(value / out_alpha for value in premultiplied)
    if clamp:
        straight_work = tuple(max(0.0, min(1.0, value)) for value in straight_work)
    result_rgb = _from_work_ref(straight_work, color_space)  # type: ignore[arg-type]
    if clamp:
        result_rgb = tuple(max(0.0, min(1.0, value)) for value in result_rgb)
    return (result_rgb[0], result_rgb[1], result_rgb[2], out_alpha)


def _clipping_reference(backdrop: Sequence[float], base: Sequence[float],
                        members: Iterable[tuple[Sequence[float], str, float]],
                        base_mode: str, base_opacity: float, color_space: str,
                        clamp: bool, transparent_rgb: str = "canonical_zero") -> RGBA:
    """Reference equations for M-fixed local blending, independent of the SUT."""

    b = _rgba_ref(backdrop, clamp)
    base_rgba = _rgba_ref(base, clamp)
    base_alpha = base_rgba[3]
    local_rgb = base_rgba[:3]
    for member_pixel, member_mode, member_opacity in members:
        member = _rgba_ref(member_pixel, clamp)
        if base_alpha <= 0.0:
            local_rgb = (0.0, 0.0, 0.0)
            continue
        source_alpha = member[3] * _opacity_ref(member_opacity)
        if source_alpha <= 0.0:
            continue
        blended = _blend_rgb_ref(local_rgb, member[:3], member_mode, color_space, clamp)
        local_work = _to_work_ref(local_rgb, color_space)
        blended_work = _to_work_ref(blended, color_space)
        local_work = tuple(
            (1.0 - source_alpha) * local_work[channel]
            + source_alpha * blended_work[channel]
            for channel in range(3)
        )  # type: ignore[assignment]
        if clamp:
            local_work = tuple(max(0.0, min(1.0, value)) for value in local_work)
        local_rgb = _from_work_ref(local_work, color_space)
        if clamp:
            local_rgb = tuple(max(0.0, min(1.0, value)) for value in local_rgb)  # type: ignore[assignment]
    return _composite_pixel_ref(
        b,
        local_rgb + (base_alpha,),
        base_mode,
        base_opacity,
        color_space,
        clamp,
        transparent_rgb,
    )


def _case(backdrop_name: str, backdrop: RGBA, mode: str, base_alpha: float,
          member_alpha: float, base_opacity: float, member_opacity: float,
          order: int, provenance: str, *, color_space: str = "sRGB",
          clamp: bool = True, base_rgb: RGB = (0.23, 0.57, 0.91),
          first_rgb: RGB = (0.91, 0.19, 0.07),
          second_rgb: RGB = (0.11, 0.83, 0.39)) -> Dict[str, Any]:
    base = base_rgb + (base_alpha,)
    first = (first_rgb + (member_alpha,), mode, member_opacity)
    second = (second_rgb + (0.75,), "Normal", 0.5)
    members = [first, second] if order == 0 else [second, first]
    expected = _clipping_reference(
        backdrop, base, members, base_mode=mode, base_opacity=base_opacity,
        color_space=color_space, clamp=clamp,
    )
    return {
        "id": "%s-%s-ba%03d-ma%03d-bo%03d-mo%03d-r%d-%s" % (
            mode.lower().replace(" ", "_"), backdrop_name,
            round(base_alpha * 1000), round(member_alpha * 1000),
            round(base_opacity * 1000), round(member_opacity * 1000), order,
            "default" if provenance == CLBL_PROVENANCES[0] else "explicit"),
        "backdrop": list(backdrop), "base": list(base),
        "members": [[list(pixel), member_mode, member_opacity] for pixel, member_mode, member_opacity in members],
        "base_mode": mode, "base_opacity": base_opacity,
        "clbl": True, "clbl_provenance": provenance,
        "color_space": color_space, "clamp": bool(clamp),
        "transparent_rgb": "canonical_zero",
        "expected": list(expected), "expected_rgba8": [_byte(v) for v in expected],
        "axes": {
            "backdrop": backdrop_name, "base_alpha": base_alpha,
            "member_alpha": member_alpha, "base_opacity": base_opacity,
            "member_opacity": member_opacity, "order": order,
            "clbl_provenance": provenance,
        },
    }


def cases() -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for mode in CORE_BLEND_MODES:
        for backdrop_name, backdrop in BACKDROPS:
            for base_alpha in BASE_ALPHAS:
                for member_alpha in MEMBER_ALPHAS:
                    for base_opacity, member_opacity in OPACITY_PAIRS:
                        for order in (0, 1):
                            result.append(_case(
                                backdrop_name, backdrop, mode, base_alpha,
                                member_alpha, base_opacity, member_opacity, order,
                                CLBL_PROVENANCES[order],
                            ))
    # Fractional/antialiased edge values are separate so their coverage is
    # visible in the manifest rather than hidden in an aggregate mean.
    for mode in CORE_BLEND_MODES:
        for backdrop_name in ("transparent", "partial-alpha"):
            backdrop = dict(BACKDROPS)[backdrop_name]
            for base_alpha in EDGE_ALPHAS:
                for member_alpha in EDGE_ALPHAS:
                    for base_opacity, member_opacity in EDGE_OPACITY_PAIRS:
                        for order in (0, 1):
                            result.append(_case(
                                "edge-" + backdrop_name, backdrop, mode,
                                base_alpha, member_alpha, base_opacity,
                                member_opacity, order, CLBL_PROVENANCES[order],
                            ))
    # Explicit working-space and over-range rows retain the PARITY-003 color
    # contract while exercising the clipping boundary.
    for mode in CORE_BLEND_MODES:
        result.append(_case(
            "partial-alpha", dict(BACKDROPS)["partial-alpha"], mode, 0.625,
            0.75, 0.75, 0.25, 0, "photoshop_default_true",
            color_space="linear-sRGB",
        ))
    result.append(_case(
        "partial-alpha", (0.82, 0.45, 0.15, 1.0), "Linear Dodge", 0.75,
        1.0, 1.0, 1.0, 0, "explicit_psd_clbl", clamp=False,
        base_rgb=(0.9, 0.8, 0.1), first_rgb=(0.8, 0.7, 0.9),
    ))
    return result


def _evaluate(record: Dict[str, Any]) -> RGBA:
    members = [(tuple(item[0]), item[1], float(item[2])) for item in record["members"]]
    return composite_clipping_span(
        tuple(record["backdrop"]), tuple(record["base"]), members,
        base_mode=record["base_mode"], base_opacity=float(record["base_opacity"]),
        color_space=record.get("color_space", "sRGB"),
        clamp=bool(record.get("clamp", True)),
        transparent_rgb=record.get("transparent_rgb", "canonical_zero"),
    )


def generate(output: Path) -> Dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    manifest_cases = cases()
    manifest = {
        "schema_version": 2, "task": "PARITY-004", "policy": "clbl-true-only",
        "cases": manifest_cases, "case_count": len(manifest_cases),
        "axes": {
            "modes": list(CORE_BLEND_MODES),
            "backdrops": [x[0] for x in BACKDROPS],
            "base_alpha": list(BASE_ALPHAS) + list(EDGE_ALPHAS),
            "member_alpha": list(MEMBER_ALPHAS) + list(EDGE_ALPHAS),
            "base_opacity": list(OPACITY_VALUES) + [0.25, 0.75],
            "member_opacity": list(OPACITY_VALUES) + [0.25, 0.75],
            "orders": [0, 1], "clbl_provenance": list(CLBL_PROVENANCES),
            "color_spaces": ["sRGB", "linear-sRGB"],
        },
        "reference_equations": {
            "local_span": "J=member coverage relative to fixed M; S=(1-q)S+q*blend(S,member); alpha(S)=M",
            "outer_boundary": "composite(D,S,base mode,base opacity) once",
            "expected_pixels": "independent equations in this script; validator compares both reference and implementation",
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "status": "PASS", "output": str(output), "case_count": len(manifest_cases),
        "clbl_policy": "absent/default true and explicit true only",
        "clbl_provenance_counts": {
            provenance: sum(1 for record in manifest_cases if record["clbl_provenance"] == provenance)
            for provenance in CLBL_PROVENANCES
        },
    }


def validate(fixtures: Path) -> Dict[str, Any]:
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    failures: List[str] = []
    max_oracle_error = 0.0
    max_reference_error = 0.0
    records = manifest.get("cases", [])
    provenance_counts = {provenance: 0 for provenance in CLBL_PROVENANCES}
    for record in records:
        provenance = record.get("clbl_provenance")
        if provenance in provenance_counts:
            provenance_counts[provenance] += 1
        if record.get("clbl") is not True or provenance not in provenance_counts:
            failures.append(str(record.get("id", "unknown")) + ":invalid-clbl-provenance")
        if "false" in json.dumps(record.get("clbl", "")).lower():
            failures.append(str(record.get("id", "unknown")) + ":clbl-false-present")
        expected = tuple(float(value) for value in record["expected"])
        reference = _clipping_reference(
            tuple(record["backdrop"]), tuple(record["base"]),
            [(tuple(item[0]), item[1], float(item[2])) for item in record["members"]],
            record["base_mode"], float(record["base_opacity"]),
            record.get("color_space", "sRGB"), bool(record.get("clamp", True)),
            record.get("transparent_rgb", "canonical_zero"),
        )
        reference_error = max(abs(reference[index] - expected[index]) for index in range(4))
        max_reference_error = max(max_reference_error, reference_error)
        if reference_error > 1e-12:
            failures.append(str(record.get("id", "unknown")) + ":reference-mismatch")
        actual = _evaluate(record)
        oracle_error = max(abs(actual[index] - expected[index]) for index in range(4))
        max_oracle_error = max(max_oracle_error, oracle_error)
        if oracle_error > 1e-12:
            failures.append(str(record.get("id", "unknown")) + ":oracle-mismatch")

    # Metamorphic guards for fixed matte and local scope.
    base = (0.2, 0.4, 0.8, 0.5)
    no_member = composite_clipping_span(
        (0.0, 0.0, 0.0, 1.0), base, [((1, 0, 0, 1), "Normal", 0)],
    )
    base_only = composite_clipping_span((0.0, 0.0, 0.0, 1.0), base, [])
    if no_member != base_only:
        failures.append("opacity-zero-member-not-no-op")
    zero = composite_clipping_span(
        (0.1, 0.2, 0.3, 0.5), (1, 0, 0, 0),
        [((1, 1, 1, 1), "Linear Dodge", 1)],
    )
    if zero != (0.1, 0.2, 0.3, 0.5):
        failures.append("zero-alpha-base-leaks-members")
    transparent_member_a = composite_clipping_span(
        (0.2, 0.3, 0.4, 1.0), base, [((1.0, 0.0, 0.0, 0.0), "Overlay", 1.0)],
    )
    transparent_member_b = composite_clipping_span(
        (0.2, 0.3, 0.4, 1.0), base, [((0.0, 1.0, 1.0, 0.0), "Overlay", 1.0)],
    )
    if transparent_member_a != transparent_member_b:
        failures.append("transparent-member-rgb-leaks")
    for alpha in BASE_ALPHAS + EDGE_ALPHAS:
        value = composite_clipping_span(
            (0.0, 0.0, 0.0, 0.0), (0.2, 0.4, 0.8, alpha),
            [((0.9, 0.1, 0.3, 1.0), "Normal", 0.5)],
        )
        if abs(value[3] - alpha) > 1e-12:
            failures.append("local-alpha-invariant:%s" % alpha)
    isolated_a = composite_clipping_span(
        (0.0, 0.0, 0.0, 1.0), (0.2, 0.4, 0.8, 1.0),
        [((0.9, 0.1, 0.3, 0.75), "Multiply", 0.5)],
        base_mode="Normal", base_opacity=1.0,
    )
    isolated_b = composite_clipping_span(
        (0.8, 0.7, 0.6, 1.0), (0.2, 0.4, 0.8, 1.0),
        [((0.9, 0.1, 0.3, 0.75), "Multiply", 0.5)],
        base_mode="Normal", base_opacity=1.0,
    )
    if isolated_a != isolated_b:
        failures.append("outer-backdrop-consumed-by-local-span")
    default = _case("transparent", dict(BACKDROPS)["transparent"], "Normal", 0.5, 0.75, 1.0, 0.5, 0, CLBL_PROVENANCES[0])
    explicit = dict(default)
    explicit["clbl_provenance"] = CLBL_PROVENANCES[1]
    explicit["axes"] = dict(default["axes"], clbl_provenance=CLBL_PROVENANCES[1])
    if _evaluate(default) != _evaluate(explicit):
        failures.append("default-true-explicit-true-diverge")
    if not all(provenance_counts.values()):
        failures.append("clbl-provenance-counts-missing")

    return {
        "status": "PASS" if not failures else "FAIL",
        "case_count": len(records), "recomputed_cases": len(records),
        "max_oracle_error": max_oracle_error,
        "max_reference_error": max_reference_error,
        "metamorphic_failures": failures,
        "clbl_policy": "true only; clbl=false excluded",
        "clbl_provenance_counts": provenance_counts,
        "reference_equations_independent": True,
    }


def compare(fixtures: Path, output: Path) -> Dict[str, Any]:
    """Encode all expected/SUT pixels and run the PARITY-001 comparator."""

    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    records = manifest.get("cases", [])
    if not records:
        return {"status": "FAIL", "reason": "fixture_manifest_empty", "case_count": 0}
    output.mkdir(parents=True, exist_ok=True)
    candidate_values = [_byte(value) for record in records for value in _evaluate(record)]
    reference_values = [int(value) for record in records for value in record["expected_rgba8"]]
    candidate = Image.new("RGBA", (len(records), 1))
    reference = Image.new("RGBA", (len(records), 1))
    candidate.putdata([tuple(candidate_values[index:index + 4]) for index in range(0, len(candidate_values), 4)])
    reference.putdata([tuple(reference_values[index:index + 4]) for index in range(0, len(reference_values), 4)])
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    candidate_path = output / "candidate.png"
    reference_path = output / "reference.png"
    candidate.save(candidate_path, format="PNG", icc_profile=profile)
    reference.save(reference_path, format="PNG", icc_profile=profile)
    metrics = compare_images(candidate_path, reference_path, output / "diff")
    return {
        "status": "PASS" if metrics.get("status") == "PASS" else metrics.get("status", "BLOCKED"),
        "case_count": len(records),
        "candidate": str(candidate_path),
        "reference": str(reference_path),
        "comparator": metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--output", type=Path, required=True)
    val = sub.add_parser("validate")
    val.add_argument("--fixtures", type=Path, required=True)
    cmp = sub.add_parser("compare")
    cmp.add_argument("--fixtures", type=Path, required=True)
    cmp.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "generate":
        result = generate(args.output)
    elif args.command == "validate":
        result = validate(args.fixtures)
    else:
        result = compare(args.fixtures, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
