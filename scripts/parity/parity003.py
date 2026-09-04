"""Generate and validate the deterministic PARITY-003 compositing matrix.

The matrix is an executable software oracle for isolating blend, opacity,
alpha, color-space, clamp and premultiplied-boundary semantics.  It is not a
Photoshop parity claim: promotion remains blocked until the generated host
candidates are rendered by Resolve/Fusion and compared with Photoshop output
under the recorded environment contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from PIL import Image, ImageCms

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psd2fusion.capabilities import registry_snapshot  # noqa: E402
from psd2fusion.compositing import (  # noqa: E402
    CORE_BLEND_MODES,
    ColorSpaceSpec,
    CompositingError,
    apply_opacity,
    composite_isolated_group,
    composite_layers,
    composite_pixel,
    premultiply,
    unpremultiply,
)
from psd2fusion.fusion_comp import compile_comp  # noqa: E402
from psd2fusion.semantic import SemanticDocument, SemanticGroup, SemanticLayer  # noqa: E402
from scripts.parity.parity import compare_images  # noqa: E402


FIXTURE_SCHEMA_VERSION = 1
FIXTURE_SIZE = (16, 16)
SOURCE_RGB = (0.91, 0.22, 0.67)
SOURCE_ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0, 0.125, 0.375, 0.625, 0.875)
OPACITIES = (0.0, 0.25, 0.5, 0.75, 1.0)
PROFILE_NAME = "sRGB IEC61966-2.1"


def _profile_bytes() -> bytes:
    # LittleCMS stamps the profile creation time in bytes 24..35.  A fixture
    # profile must be byte-stable across runs, so freeze that metadata while
    # keeping the actual sRGB transfer/primaries intact.
    raw = bytearray(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    raw[24:36] = b"\x00" * 12
    return bytes(raw)


def _profile_sha256() -> str:
    return hashlib.sha256(_profile_bytes()).hexdigest()


def _byte(value: float) -> int:
    return int(round(max(0.0, min(1.0, float(value))) * 255.0))


def _encode(pixel: Sequence[float]) -> List[int]:
    return [_byte(value) for value in pixel]


def _decode(pixel: Sequence[int]) -> Tuple[float, float, float, float]:
    if len(pixel) != 4:
        raise ValueError("fixture pixel must contain RGBA")
    return tuple(float(value) / 255.0 for value in pixel)  # type: ignore[return-value]


def _save_rgba(path: Path, pixels: Iterable[Sequence[int]], size: Tuple[int, int]) -> None:
    values = [tuple(int(value) for value in pixel) for pixel in pixels]
    if len(values) != size[0] * size[1]:
        raise ValueError("pixel count does not match fixture size")
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size)
    image.putdata(values)
    image.save(path, format="PNG", optimize=False, compress_level=9, icc_profile=_profile_bytes())


def _uniform(path: Path, pixel: Sequence[float], size: Tuple[int, int] = FIXTURE_SIZE) -> None:
    _save_rgba(path, [_encode(pixel)] * (size[0] * size[1]), size)


def _backdrops() -> List[Dict[str, Any]]:
    values: List[Dict[str, Any]] = [
        {"id": "transparent_rgb", "rgba": [0.73, 0.31, 0.12, 0.0]},
        {"id": "black", "rgba": [0.0, 0.0, 0.0, 1.0]},
        {"id": "white", "rgba": [1.0, 1.0, 1.0, 1.0]},
        {"id": "gray", "rgba": [0.5, 0.5, 0.5, 1.0]},
        {"id": "saturated", "rgba": [0.08, 0.86, 0.25, 1.0]},
        {"id": "partial_alpha", "rgba": [0.18, 0.42, 0.76, 0.5]},
    ]
    for index in range(5):
        fraction = float(index) / 4.0
        values.append(
            {
                "id": "gradient_%02d" % index,
                "rgba": [0.05 + 0.9 * fraction, 0.8 - 0.55 * fraction, 0.2 + 0.6 * fraction, 0.75],
            }
        )
    return values


def _case(
    case_id: str,
    kind: str,
    backdrop: Sequence[float],
    source: Sequence[float],
    mode: str,
    opacity: float,
    *,
    color_space: str = "sRGB",
    clamp: bool = True,
    axes: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    result = composite_pixel(
        backdrop,
        source,
        mode,
        opacity,
        color_space=ColorSpaceSpec(color_space),
        clamp=clamp,
        transparent_rgb="canonical_zero",
    )
    return {
        "id": case_id,
        "kind": kind,
        "mode": mode,
        "opacity": float(opacity),
        "color_space": color_space,
        "clamp": bool(clamp),
        "backdrop": [float(value) for value in backdrop],
        "source": [float(value) for value in source],
        "expected": [float(value) for value in result],
        "expected_rgba8": _encode(result),
        "axes": dict(axes or {}),
    }


def blend_cases() -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for mode in CORE_BLEND_MODES:
        for backdrop_record in _backdrops():
            backdrop = tuple(backdrop_record["rgba"])
            for source_alpha in SOURCE_ALPHAS:
                source = SOURCE_RGB + (source_alpha,)
                for opacity in OPACITIES:
                    case_id = "%s-%s-a%03d-o%03d" % (
                        mode.lower().replace(" ", "_"),
                        backdrop_record["id"],
                        int(round(source_alpha * 1000)),
                        int(round(opacity * 1000)),
                    )
                    result.append(
                        _case(
                            case_id,
                            "blend",
                            backdrop,
                            source,
                            mode,
                            opacity,
                            axes={
                                "backdrop": backdrop_record["id"],
                                "source_alpha": source_alpha,
                                "opacity": opacity,
                            },
                        )
                    )
    # Explicit color-space and over-range probes are separate from the main
    # matrix so a failure cannot be hidden by an aggregate mean.
    result.append(
        _case(
            "overlay-linear-srgb-boundary",
            "color_space",
            (0.18, 0.42, 0.76, 1.0),
            SOURCE_RGB + (0.75,),
            "Overlay",
            0.5,
            color_space="linear-sRGB",
            axes={"profile": PROFILE_NAME, "transform": "explicit-srgb-to-linear"},
        )
    )
    result.append(
        _case(
            "linear-dodge-clamp",
            "clamp",
            (0.82, 0.45, 0.15, 1.0),
            (0.71, 0.82, 0.93, 1.0),
            "Linear Dodge",
            1.0,
            axes={"over_range": True},
        )
    )
    unclamped = composite_pixel(
        (0.82, 0.45, 0.15, 1.0),
        (0.71, 0.82, 0.93, 1.0),
        "Linear Dodge",
        1.0,
        clamp=False,
    )
    result.append(
        {
            "id": "linear-dodge-over-range-unclamped",
            "kind": "clamp",
            "mode": "Linear Dodge",
            "opacity": 1.0,
            "color_space": "sRGB",
            "clamp": False,
            "backdrop": [0.82, 0.45, 0.15, 1.0],
            "source": [0.71, 0.82, 0.93, 1.0],
            "expected": [float(value) for value in unclamped],
            "expected_rgba8": _encode(unclamped),
            "axes": {"over_range": True},
        }
    )
    return result


def opacity_cases() -> List[Dict[str, Any]]:
    backdrop = (0.16, 0.44, 0.72, 0.5)
    source = (0.88, 0.21, 0.42, 0.75)
    result: List[Dict[str, Any]] = []
    for opacity in OPACITIES:
        result.append(
            _case(
                "ordinary-opacity-%03d" % int(round(opacity * 100)),
                "ordinary_opacity",
                backdrop,
                source,
                "Normal",
                opacity,
                axes={"source_alpha": source[3], "opacity": opacity},
            )
        )
    return result


def group_cases() -> List[Dict[str, Any]]:
    outer = (0.12, 0.26, 0.58, 0.5)
    layers = [
        ((0.85, 0.18, 0.08, 0.75), "Normal", 1.0),
        ((0.22, 0.88, 0.36, 0.5), "Multiply", 0.75),
    ]
    result: List[Dict[str, Any]] = []
    for opacity in OPACITIES:
        value = composite_isolated_group(outer, layers, opacity)
        result.append(
            {
                "id": "isolated-group-opacity-%03d" % int(round(opacity * 100)),
                "kind": "isolated_group_opacity",
                "outer": list(outer),
                "layers": [
                    {"pixel": list(pixel), "mode": mode, "opacity": member_opacity}
                    for pixel, mode, member_opacity in layers
                ],
                "opacity": opacity,
                "expected": list(value),
                "expected_rgba8": _encode(value),
            }
        )

    inner = composite_isolated_group((0.0, 0.0, 0.0, 0.0), layers, 0.5)
    nested = composite_isolated_group(
        outer,
        [(inner, "Normal", 1.0)],
        0.25,
    )
    result.append(
        {
            "id": "nested-group-opacity-boundaries",
            "kind": "nested_opacity",
            "outer": list(outer),
            "inner_layers": [
                {"pixel": list(pixel), "mode": mode, "opacity": member_opacity}
                for pixel, mode, member_opacity in layers
            ],
            "inner_opacity": 0.5,
            "outer_opacity": 0.25,
            "expected": list(nested),
            "expected_rgba8": _encode(nested),
        }
    )
    return result


def _fixture_document(
    source_hash: str,
    width: int,
    height: int,
    children: Sequence[SemanticLayer],
) -> SemanticDocument:
    return SemanticDocument(
        source_path="parity003-fixture.psd",
        source_sha256=source_hash,
        parser="parity003-fixture",
        parser_version="1",
        width=width,
        height=height,
        profile=PROFILE_NAME,
        children=list(children),
    )


def _host_comp_for_case(root: Path, case: Mapping[str, Any], slug: str) -> Dict[str, Any]:
    out_dir = root / "host" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    _uniform(out_dir / "backdrop.png", case["backdrop"])
    _uniform(out_dir / "source.png", case["source"])
    _uniform(out_dir / "expected.png", _decode(case["expected_rgba8"]))
    source_hash = hashlib.sha256((slug + json.dumps(case, sort_keys=True)).encode("utf-8")).hexdigest()
    backdrop_layer = SemanticLayer(
        id="backdrop-" + slug,
        name="Backdrop",
        asset_path="backdrop.png",
        blend="Normal",
        raw_blend="norm",
    )
    source_layer = SemanticLayer(
        id="source-" + slug,
        name="Source",
        asset_path="source.png",
        blend=case["mode"],
        raw_blend={
            "Normal": "norm",
            "Multiply": "mul ",
            "Screen": "scrn",
            "Linear Dodge": "lddg",
            "Overlay": "over",
        }[case["mode"]],
        opacity=float(case["opacity"]),
    )
    doc = _fixture_document(source_hash, FIXTURE_SIZE[0], FIXTURE_SIZE[1], [backdrop_layer, source_layer])
    comp_path = out_dir / "candidate.comp"
    graph = compile_comp(doc, str(comp_path))
    return {
        "id": case["id"],
        "mode": case["mode"],
        "opacity": case["opacity"],
        "candidate_comp": str(comp_path.relative_to(root)).replace("\\", "/"),
        "render_output": str(Path(str(comp_path.relative_to(root)) + ".parity003-render.png")).replace("\\", "/"),
        "backdrop": str((out_dir / "backdrop.png").relative_to(root)).replace("\\", "/"),
        "source": str((out_dir / "source.png").relative_to(root)).replace("\\", "/"),
        "expected": str((out_dir / "expected.png").relative_to(root)).replace("\\", "/"),
        "graph": graph,
        "host_render": "required_not_run",
    }


def _host_comp_for_group(root: Path, record: Mapping[str, Any]) -> Dict[str, Any]:
    slug = "isolated-group-opacity-050"
    out_dir = root / "host" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    _uniform(out_dir / "backdrop.png", record["outer"])
    for index, layer in enumerate(record["layers"]):
        _uniform(out_dir / ("layer-%d.png" % index), layer["pixel"])
    backdrop_layer = SemanticLayer(id="group-backdrop", name="Backdrop", asset_path="backdrop.png")
    group_layers = [
        SemanticLayer(
            id="group-child-%d" % index,
            name="Group child %d" % index,
            asset_path="layer-%d.png" % index,
            blend=layer["mode"],
            raw_blend={"Normal": "norm", "Multiply": "mul "}[layer["mode"]],
            opacity=float(layer["opacity"]),
        )
        for index, layer in enumerate(record["layers"])
    ]
    group = SemanticGroup(
        id="isolated-group",
        name="Isolated group",
        opacity=float(record["opacity"]),
        children=group_layers,
    )
    source_hash = hashlib.sha256(json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()
    doc = _fixture_document(source_hash, FIXTURE_SIZE[0], FIXTURE_SIZE[1], [backdrop_layer, group])
    comp_path = out_dir / "candidate.comp"
    graph = compile_comp(doc, str(comp_path))
    expected_path = out_dir / "expected.png"
    _uniform(expected_path, record["expected"])
    return {
        "id": record["id"],
        "kind": record["kind"],
        "candidate_comp": str(comp_path.relative_to(root)).replace("\\", "/"),
        "render_output": str(Path(str(comp_path.relative_to(root)) + ".parity003-render.png")).replace("\\", "/"),
        "expected": str(expected_path.relative_to(root)).replace("\\", "/"),
        "graph": graph,
        "host_render": "required_not_run",
    }


def generate(output_dir: str | Path) -> Dict[str, Any]:
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    cases = blend_cases()
    ordinary = opacity_cases()
    groups = group_cases()
    blend_pixels = [case["expected_rgba8"] for case in cases]
    _save_rgba(root / "blend-oracle.png", blend_pixels, (len(blend_pixels), 1))
    _save_rgba(root / "blend-expected.png", blend_pixels, (len(blend_pixels), 1))
    host_candidates: List[Dict[str, Any]] = []
    representative_ids = {
        mode: next(
            case
            for case in cases
            if case["mode"] == mode
            and case["axes"].get("backdrop") == "partial_alpha"
            and abs(case["axes"].get("source_alpha", -1) - 0.75) < 1e-12
            and abs(case["axes"].get("opacity", -1) - 0.5) < 1e-12
        )
        for mode in CORE_BLEND_MODES
    }
    for mode, case in representative_ids.items():
        host_candidates.append(_host_comp_for_case(root, case, mode.lower().replace(" ", "-")))
    host_candidates.append(_host_comp_for_group(root, next(item for item in groups if item["id"] == "isolated-group-opacity-050")))
    manifest = {
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "task": "PARITY-003",
        "fixture": "core-compositing-matrix",
        "profile": {"name": PROFILE_NAME, "icc_profile_sha256": _profile_sha256(), "transform": "none"},
        "alpha_contract": "straight-rgba; premultiply only at source-over boundary",
        "transparent_rgb_policy": "canonical_zero_for_zero_alpha_backdrop",
        "clamp_policy": "channel clamp enabled unless case.clamp=false",
        "blend_modes": list(CORE_BLEND_MODES),
        "axes": {
            "backdrops": [item["id"] for item in _backdrops()],
            "source_alpha": list(SOURCE_ALPHAS),
            "opacity": list(OPACITIES),
            "edge_alpha": [0.125, 0.375, 0.625, 0.875],
            "transparent_rgb": True,
            "partial_backdrop_alpha": True,
            "gradient": True,
        },
        "blend_cases": cases,
        "ordinary_opacity_cases": ordinary,
        "group_cases": groups,
        "host_candidates": host_candidates,
        "capabilities": registry_snapshot(),
        "promotion": {
            "status": "blocked",
            "requires": ["photoshop_reference_pixels", "fusion_host_render", "exact_commit_and_environment"],
            "host_render": "required_not_run",
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"status": "PASS", "output": str(root), "blend_cases": len(cases), "ordinary_opacity_cases": len(ordinary), "group_cases": len(groups), "host_candidates": len(host_candidates), "profile_sha256": manifest["profile"]["icc_profile_sha256"]}


def _almost_equal(a: Sequence[float], b: Sequence[float], tolerance: float = 1e-12) -> bool:
    return all(abs(float(left) - float(right)) <= tolerance for left, right in zip(a, b))


def _validate_metamorphic(manifest: Mapping[str, Any]) -> List[str]:
    failures: List[str] = []
    for case in manifest.get("blend_cases", []):
        backdrop = case["backdrop"]
        source = case["source"]
        mode = case["mode"]
        canonical_backdrop = list(backdrop)
        if canonical_backdrop[3] == 0.0:
            canonical_backdrop[:3] = [0.0, 0.0, 0.0]
        if not _almost_equal(
            composite_pixel(backdrop, source, mode, 0.0), canonical_backdrop
        ):
            failures.append(case["id"] + ": opacity-zero-not-noop")
        transparent_source = list(source)
        transparent_source[3] = 0.0
        expected = composite_pixel(backdrop, transparent_source, mode, case["opacity"])
        canonical_backdrop = list(backdrop)
        if canonical_backdrop[3] == 0.0:
            canonical_backdrop[:3] = [0.0, 0.0, 0.0]
        if not _almost_equal(expected, canonical_backdrop):
            failures.append(case["id"] + ": source-alpha-zero-not-noop")
    layers = [
        ((0.85, 0.18, 0.08, 0.75), "Normal", 1.0),
        ((0.22, 0.88, 0.36, 0.5), "Multiply", 0.75),
    ]
    local_a = composite_layers((0.0, 0.0, 0.0, 0.0), layers)
    local_b = composite_layers((0.91, 0.11, 0.03, 0.0), layers)
    if not _almost_equal(local_a, local_b):
        failures.append("isolated-group-local-result-depends-on-transparent-rgb")
    edge = (0.8, 0.1, 0.2, 0.375)
    if not _almost_equal(unpremultiply(premultiply(edge)), edge, 1e-15):
        failures.append("premult-roundtrip-fringe")
    if unpremultiply((0.4, 0.1, 0.2, 0.0)) != (0.0, 0.0, 0.0, 0.0):
        failures.append("zero-alpha-unpremultiply-not-canonical")
    return failures


def validate(fixtures_dir: str | Path) -> Dict[str, Any]:
    root = Path(fixtures_dir).expanduser().resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return {"status": "BLOCKED", "reason": "missing_manifest", "fixtures": str(root)}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = _validate_metamorphic(manifest)
    recomputed = 0
    recomputed_opacity = 0
    recomputed_groups = 0
    max_error = 0.0
    max_boundary_error = 0.0
    for case in manifest.get("blend_cases", []):
        expected = composite_pixel(
            case["backdrop"],
            case["source"],
            case["mode"],
            case["opacity"],
            color_space=case["color_space"],
            clamp=case["clamp"],
        )
        error = max(abs(float(left) - float(right)) for left, right in zip(expected, case["expected"]))
        max_error = max(max_error, error)
        recomputed += 1
        if error > 1e-12:
            failures.append(case["id"] + ": oracle-mismatch")
    for case in manifest.get("ordinary_opacity_cases", []):
        expected = composite_pixel(
            case["backdrop"],
            case["source"],
            case["mode"],
            case["opacity"],
            color_space=case["color_space"],
            clamp=case["clamp"],
        )
        error = max(abs(float(left) - float(right)) for left, right in zip(expected, case["expected"]))
        max_boundary_error = max(max_boundary_error, error)
        recomputed_opacity += 1
        if error > 1e-12:
            failures.append(case["id"] + ": opacity-oracle-mismatch")
    for case in manifest.get("group_cases", []):
        if case["kind"] == "isolated_group_opacity":
            layers = [
                (tuple(item["pixel"]), item["mode"], float(item["opacity"]))
                for item in case["layers"]
            ]
            expected = composite_isolated_group(case["outer"], layers, case["opacity"])
        elif case["kind"] == "nested_opacity":
            inner_layers = [
                (tuple(item["pixel"]), item["mode"], float(item["opacity"]))
                for item in case["inner_layers"]
            ]
            inner = composite_isolated_group((0.0, 0.0, 0.0, 0.0), inner_layers, case["inner_opacity"])
            expected = composite_isolated_group(
                case["outer"], [(inner, "Normal", 1.0)], case["outer_opacity"]
            )
        else:
            failures.append(case["id"] + ": unknown-group-fixture")
            continue
        error = max(abs(float(left) - float(right)) for left, right in zip(expected, case["expected"]))
        max_boundary_error = max(max_boundary_error, error)
        recomputed_groups += 1
        if error > 1e-12:
            failures.append(case["id"] + ": group-oracle-mismatch")
    with TemporaryDirectory(prefix="parity003-validate-") as temporary:
        scratch = Path(temporary)
        result = compare_images(root / "blend-oracle.png", root / "blend-expected.png", scratch / "comparison")
    if result.get("status") != "PASS":
        failures.append("comparator:" + str(result.get("status")))
    for candidate in manifest.get("host_candidates", []):
        comp = root / candidate["candidate_comp"]
        if not comp.is_file():
            failures.append(candidate["id"] + ":missing-host-comp")
            continue
        text = comp.read_text(encoding="utf-8")
        expected_mode = candidate.get("mode")
        mode_id = str(expected_mode or "").replace(" ", "")
        source_merge_has_mode = (
            expected_mode in (None, "Normal")
            or ('PSD layer merge: Source' in text and ('FuID { "' + mode_id + '" }') in text)
        )
        if "Fusion blend fallback" in text or not source_merge_has_mode:
            failures.append(candidate["id"] + ":silent-normal-fallback")
    statuses = {name: record.get("status") for name, record in manifest.get("capabilities", {}).items() if name in CORE_BLEND_MODES}
    if any(status != "unverified" for status in statuses.values()):
        failures.append("capability-registry-promoted-without-host-proof")
    return {
        "status": "PASS" if not failures else "FAIL",
        "fixtures": str(root),
        "blend_cases": len(manifest.get("blend_cases", [])),
        "recomputed_cases": recomputed,
        "ordinary_opacity_cases": len(manifest.get("ordinary_opacity_cases", [])),
        "recomputed_opacity_cases": recomputed_opacity,
        "group_cases": len(manifest.get("group_cases", [])),
        "recomputed_group_cases": recomputed_groups,
        "max_oracle_error": max_error,
        "max_boundary_error": max_boundary_error,
        "comparator": result,
        "metamorphic_failures": failures,
        "capability_statuses": statuses,
        "promotion": {
            "status": "blocked",
            "blockers": ["photoshop_reference_pixels_not_recorded", "fusion_host_render_not_recorded"],
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--output", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--fixtures", required=True)
    validate_parser.add_argument("--summary")
    args = parser.parse_args(argv)
    if args.command == "generate":
        payload = generate(args.output)
    else:
        payload = validate(args.fixtures)
        if args.summary:
            Path(args.summary).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
