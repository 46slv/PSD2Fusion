"""Verify the PSDFixtureForge PARITY-004 matrix without a Fusion host.

This verifier keeps four boundaries separate:

* PSDFixtureForge PSD/oracle determinism and psd-tools readback;
* PSD2Fusion semantic IR and materialized source pixels;
* exact uint8 semantic composition against the independent pixel oracle;
* structural/algebraic inspection of the emitted Fusion graph.

It never launches Resolve/Fusion and never treats structural graph evidence as
an actual host-render claim. A fixture canvas background is also reported as a
transport boundary because PSDFixtureForge does not serialize that background
as a PSD layer.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable, Sequence

from PIL import Image
from psd_tools import PSDImage

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psd2fusion.assets import materialize_assets
from psd2fusion.compositing import (
    composite_clipping_span_u8,
    composite_pixel_u8,
)
from psd2fusion.evaluation import evaluate_document
from psd2fusion.fusion_comp import compile_comp
from psd2fusion.manifest import write_manifest
from psd2fusion.parse_psd import parse_psd
from psd2fusion.semantic import SemanticLayer, walk_layers
from scripts.parity.p4_05 import _all_tools
from scripts.validate_clipping_subtrees import validate as validate_clipping


CASE_NAMES = (
    "basic-pixel",
    "fractional-alpha-opacity",
    "clipping-one-member",
    "clipping-multi-member",
    "multiply",
    "screen",
    "nested-isolated-group",
    "pass-through-group",
    "group-clipping",
)
MODE_KEYS = {
    "normal": "norm",
    "multiply": "mul ",
    "screen": "scrn",
    "pass_through": "pass",
}
MODE_NAMES = {
    "normal": "Normal",
    "multiply": "Multiply",
    "screen": "Screen",
    "pass_through": "Pass Through",
}


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _artifact(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": str(path),
        "bytes": len(data),
        "sha256": sha256(data).hexdigest(),
    }


def _raw_blend(layer: Any) -> str:
    value = layer.blend_mode.value
    return value.decode("ascii") if isinstance(value, bytes) else str(value)


def _forge_signature(layer: Any) -> dict[str, Any]:
    return {
        "name": layer.name,
        "group": layer.kind == "group",
        "blend": MODE_KEYS[layer.blend_mode],
        "opacity": layer.opacity,
        "visible": layer.visible,
        "clipping": layer.clipping,
        "open_folder": layer.open_folder if layer.kind == "group" else None,
        "children": [_forge_signature(child) for child in layer.children],
    }


def _psd_tools_signature(layer: Any) -> dict[str, Any]:
    group = bool(layer.is_group())
    return {
        "name": layer.name,
        "group": group,
        "blend": _raw_blend(layer),
        "opacity": int(layer.opacity),
        "visible": bool(layer.visible),
        "clipping": bool(layer.clipping),
        "open_folder": bool(layer.open_folder) if group else None,
        "children": (
            [_psd_tools_signature(child) for child in layer] if group else []
        ),
    }


def _semantic_signature(layer: SemanticLayer) -> dict[str, Any]:
    return {
        "name": layer.name,
        "group": layer.is_group,
        "blend": layer.raw_blend,
        "opacity": int(round(layer.opacity * 255.0)),
        "visible": layer.visible,
        "clipping": layer.clipping_base_id is not None,
        "pass_through": layer.pass_through,
        "isolated": layer.isolated,
        "children": [_semantic_signature(child) for child in layer.children],
    }


def _expected_semantic_signature(layer: Any) -> dict[str, Any]:
    group = layer.kind == "group"
    pass_through = group and layer.blend_mode == "pass_through"
    return {
        "name": layer.name,
        "group": group,
        "blend": MODE_KEYS[layer.blend_mode],
        "opacity": layer.opacity,
        "visible": layer.visible,
        "clipping": layer.clipping,
        "pass_through": pass_through,
        "isolated": group and not pass_through,
        "children": [
            _expected_semantic_signature(child) for child in layer.children
        ],
    }


def _source_image(layer: Any, rasterize_primitive: Any) -> Image.Image:
    if layer.pixels is not None:
        image = Image.new("RGBA", (layer.width, layer.height))
        image.putdata(layer.pixels)
        return image
    return rasterize_primitive(layer.primitive, layer.width, layer.height)


def _paste_clipped(
    canvas: Image.Image, source: Image.Image, left: int, top: int
) -> None:
    dst_left = max(0, left)
    dst_top = max(0, top)
    src_left = max(0, -left)
    src_top = max(0, -top)
    width = min(source.width - src_left, canvas.width - dst_left)
    height = min(source.height - src_top, canvas.height - dst_top)
    if width <= 0 or height <= 0:
        return
    crop = source.crop((src_left, src_top, src_left + width, src_top + height))
    canvas.alpha_composite(crop, (dst_left, dst_top))


def _asset_pixels_valid(
    forge_layers: Sequence[Any],
    semantic_layers: Sequence[SemanticLayer],
    assets: dict[str, dict[str, Any]],
    output: Path,
    size: tuple[int, int],
    rasterize_primitive: Any,
    offset_x: int = 0,
    offset_y: int = 0,
) -> bool:
    if len(forge_layers) != len(semantic_layers):
        return False
    for expected, actual in zip(forge_layers, semantic_layers):
        if expected.kind == "group":
            if not _asset_pixels_valid(
                expected.children,
                actual.children,
                assets,
                output,
                size,
                rasterize_primitive,
                offset_x + expected.x,
                offset_y + expected.y,
            ):
                return False
            continue
        record = assets.get(actual.id)
        if record is None:
            return False
        expected_canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        _paste_clipped(
            expected_canvas,
            _source_image(expected, rasterize_primitive),
            offset_x + expected.x,
            offset_y + expected.y,
        )
        with Image.open(output / record["path"]) as asset_source:
            asset = asset_source.convert("RGBA")
            if asset.size != size or asset.tobytes() != expected_canvas.tobytes():
                return False
    return True


def _pixels(image: Image.Image) -> list[tuple[int, int, int, int]]:
    data = image.convert("RGBA").tobytes()
    return [tuple(data[index : index + 4]) for index in range(0, len(data), 4)]  # type: ignore[list-item]


def _semantic_pixels(
    document: Any,
    assets: dict[str, dict[str, Any]],
    output: Path,
    backdrop: tuple[int, int, int, int],
) -> list[tuple[int, int, int, int]]:
    count = document.width * document.height
    asset_pixels: dict[str, list[tuple[int, int, int, int]]] = {}
    for layer in walk_layers(document.children):
        record = assets.get(layer.id)
        if record is None:
            continue
        with Image.open(output / record["path"]) as source:
            values = _pixels(source)
        if len(values) != count:
            raise ValueError("materialized asset dimensions do not match document")
        asset_pixels[layer.id] = values

    transparent = [(0, 0, 0, 0)] * count

    def render(layer: SemanticLayer) -> list[tuple[int, int, int, int]]:
        if layer.is_group:
            if layer.pass_through:
                raise ValueError("pass-through group has no isolated render source")
            return sequence(list(transparent), layer.children)
        return list(asset_pixels[layer.id])

    def sequence(
        current: list[tuple[int, int, int, int]],
        layers: Sequence[SemanticLayer],
    ) -> list[tuple[int, int, int, int]]:
        index = 0
        while index < len(layers):
            layer = layers[index]
            if not layer.effective_visible:
                index += 1
                continue
            if layer.is_group and layer.pass_through:
                current = sequence(current, layer.children)
                index += 1
                continue
            if layer.clipping_base_id is not None:
                raise ValueError("orphan clipping member in semantic sequence")

            base_pixels = render(layer)
            members: list[SemanticLayer] = []
            end = index + 1
            while (
                end < len(layers)
                and layers[end].clipping_base_id == layer.id
            ):
                members.append(layers[end])
                end += 1
            if members:
                member_pixels = [(member, render(member)) for member in members]
                current = [
                    composite_clipping_span_u8(
                        current[pixel_index],
                        base_pixels[pixel_index],
                        [
                            (
                                values[pixel_index],
                                member.blend,
                                member.opacity,
                            )
                            for member, values in member_pixels
                            if member.effective_visible
                        ],
                        layer.blend,
                        layer.opacity,
                    )
                    for pixel_index in range(count)
                ]
                index = end
                continue

            current = [
                composite_pixel_u8(
                    current[pixel_index],
                    base_pixels[pixel_index],
                    layer.blend,
                    layer.opacity,
                )
                for pixel_index in range(count)
            ]
            index += 1
        return current

    return sequence([backdrop] * count, document.children)


def _graph_structure(
    document: Any, comp_path: Path, psd_path: Path
) -> dict[str, Any]:
    tools = _all_tools(comp_path)
    text = comp_path.read_text(encoding="utf-8")
    group_names = {
        tool["name"] for tool in tools if tool["type"] == "GroupOperator"
    }
    render_inputs = ("background", "foreground", "input", "effect_mask")
    proxy_consumers = [
        {"tool": tool["name"], "input": input_name, "group": tool.get(input_name)}
        for tool in tools
        for input_name in render_inputs
        if tool.get(input_name) in group_names
    ]
    non_normal_functions = []
    malformed_functions = []
    for tool in tools:
        if tool["type"] != "Merge":
            continue
        apply_mode = tool.get("apply_mode")
        if apply_mode in (None, 'FuID { "Normal" }'):
            continue
        row = {
            "name": tool["name"],
            "mode": apply_mode,
            "background": tool.get("background"),
            "foreground": tool.get("foreground"),
            "blend": tool.get("blend"),
        }
        non_normal_functions.append(row)
        if not all(
            (
                "BlendFunction" in tool["name"],
                "Opaque" in str(tool.get("background")),
                "Opaque" in str(tool.get("foreground")),
                tool.get("blend") == "1.000000",
            )
        ):
            malformed_functions.append(row)

    non_normal_layers = [
        layer
        for layer in walk_layers(document.children)
        if layer.effective_visible
        and layer.blend not in ("Normal", "Pass Through")
    ]
    function_suffixes = {
        tool["name"].rsplit("_", 1)[-1]
        for tool in tools
        if tool["type"] == "Merge" and "BlendFunction" in tool["name"]
    }
    missing_mode_functions = [
        layer.id
        for layer in non_normal_layers
        if layer.id[:10] not in function_suffixes
    ]
    loaders = [tool for tool in tools if tool["type"] == "Loader"]
    by_name = {tool["name"]: tool for tool in tools}
    materialization_rows = []
    for loader in loaders:
        suffix = loader["name"][len("Loader") :]
        depth = by_name.get("MaterializeDepth" + suffix)
        premult = by_name.get("MaterializePremult" + suffix)
        materialization_rows.append(
            {
                "loader": loader["name"],
                "depth": depth["name"] if depth else None,
                "premult": premult["name"] if premult else None,
                "pass": bool(
                    loader.get("post_multiply") == "0"
                    and depth is not None
                    and depth.get("type") == "ChangeDepth"
                    and depth.get("input") == loader["name"]
                    and depth.get("depth") == "4"
                    and depth.get("dither") == "0"
                    and premult is not None
                    and premult.get("type") == "AlphaMultiply"
                    and premult.get("input") == depth["name"]
                ),
            }
        )
    clipping = validate_clipping(str(psd_path), str(comp_path))
    checks = {
        "loader_float32_materialization": bool(loaders)
        and all(row["pass"] for row in materialization_rows),
        "nonnormal_only_on_straight_opaque_functions": not malformed_functions,
        "every_nonnormal_layer_has_function": not missing_mode_functions,
        "group_proxy_has_no_render_consumers": not proxy_consumers,
        "clipping_fixed_matte_structure": bool(clipping["pass"]),
    }
    return {
        "pass": all(checks.values()),
        "checks": checks,
        "tool_count": len(tools),
        "loader_count": len(loaders),
        "loader_materialization": materialization_rows,
        "group_count": len(group_names),
        "nonnormal_functions": non_normal_functions,
        "malformed_functions": malformed_functions,
        "missing_mode_function_layer_ids": missing_mode_functions,
        "group_proxy_consumers": proxy_consumers,
        "clipping": clipping,
    }


def _maximum_delta(
    left: Iterable[Sequence[int]], right: Iterable[Sequence[int]]
) -> int:
    maximum = 0
    for expected, actual in zip(left, right):
        maximum = max(
            maximum,
            *(abs(int(a) - int(b)) for a, b in zip(expected, actual)),
        )
    return maximum


def run(
    fixture_forge: Path,
    output: Path,
    expected_fixture_head: str | None = None,
) -> dict[str, Any]:
    fixture_forge = fixture_forge.resolve()
    output = output.resolve()
    fixture_src = fixture_forge / "src"
    matrix_path = fixture_forge / "examples/parity004-production-matrix.json"
    if not fixture_src.is_dir() or not matrix_path.is_file():
        raise ValueError("not a PSDFixtureForge production candidate: %s" % fixture_forge)

    fixture_head = _git(fixture_forge, "rev-parse", "HEAD")
    fixture_status = _git(fixture_forge, "status", "--porcelain=v1")
    if expected_fixture_head and fixture_head != expected_fixture_head:
        raise ValueError(
            "PSDFixtureForge HEAD mismatch: expected %s, got %s"
            % (expected_fixture_head, fixture_head)
        )
    if fixture_status:
        raise ValueError("PSDFixtureForge candidate worktree is not clean")
    if importlib.metadata.version("psd-tools") != "1.18.0":
        raise ValueError("psd-tools 1.18.0 is required")

    sys.path.insert(0, str(fixture_src))
    from psd_fixture_forge.compositor import composite
    from psd_fixture_forge.primitives import rasterize_primitive
    from psd_fixture_forge.psd_writer import psd_bytes
    from psd_fixture_forge.spec import parse_spec

    writer_source = (fixture_src / "psd_fixture_forge/psd_writer.py").read_text(
        encoding="utf-8"
    )
    compositor_source = (
        fixture_src / "psd_fixture_forge/compositor.py"
    ).read_text(encoding="utf-8")
    oracle_independence = all(
        (
            "from .compositor" not in writer_source,
            "import compositor" not in writer_source,
            "psd_writer" not in compositor_source,
            "psd_tools" not in compositor_source,
        )
    )

    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    raw_cases = matrix.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("production matrix cases must be a list")
    names = tuple(case.get("name") for case in raw_cases)
    if names != CASE_NAMES:
        raise ValueError("unexpected production matrix case order: %r" % (names,))

    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in raw_cases:
        name = case["name"]
        spec = parse_spec(case["spec"])
        first_psd = psd_bytes(spec)
        second_psd = psd_bytes(parse_spec(case["spec"]))
        expected = composite(spec).convert("RGBA")
        repeated_expected = composite(parse_spec(case["spec"])).convert("RGBA")
        deterministic = (
            first_psd == second_psd
            and expected.tobytes() == repeated_expected.tobytes()
        )

        case_root = output / name
        converted = case_root / "psd2fusion"
        case_root.mkdir(parents=True, exist_ok=True)
        converted.mkdir(parents=True, exist_ok=True)
        psd_path = case_root / "fixture.psd"
        expected_path = case_root / "expected.png"
        psd_path.write_bytes(first_psd)
        expected.save(expected_path, format="PNG", optimize=False)

        raw_psd = PSDImage.open(psd_path)
        expected_readback = [_forge_signature(layer) for layer in spec.layers]
        actual_readback = [_psd_tools_signature(layer) for layer in raw_psd]
        psd_tools_readback = expected_readback == actual_readback

        document = parse_psd(str(psd_path))
        raw_psd_for_assets = PSDImage.open(psd_path)
        assets = materialize_assets(document, raw_psd_for_assets, str(converted))
        semantic_expected = [
            _expected_semantic_signature(layer) for layer in spec.layers
        ]
        semantic_actual = [_semantic_signature(layer) for layer in document.children]
        semantic_ir_valid = semantic_expected == semantic_actual
        asset_rgba_valid = _asset_pixels_valid(
            spec.layers,
            document.children,
            assets,
            converted,
            (spec.width, spec.height),
            rasterize_primitive,
        )

        comp_path = converted / "PSD2Fusion.comp"
        graph = compile_comp(document, str(comp_path))
        first_comp = comp_path.read_bytes()
        graph_repeat = compile_comp(document, str(comp_path))
        second_comp = comp_path.read_bytes()
        comp_deterministic = first_comp == second_comp and graph == graph_repeat
        plan = evaluate_document(document, policy="strict")
        manifest_path = Path(
            write_manifest(document, str(converted), assets, graph, plan)
        )

        expected_pixels = _pixels(expected)
        semantic_pixels = _semantic_pixels(
            document, assets, converted, tuple(spec.background)
        )
        semantic_math_exact = semantic_pixels == expected_pixels
        maximum_delta = _maximum_delta(expected_pixels, semantic_pixels)
        rejected = [
            decision.operation
            for decision in plan.decisions
            if decision.status == "rejected"
        ]
        structure = _graph_structure(document, comp_path, psd_path)
        canvas_transported = tuple(spec.background) == (0, 0, 0, 0)

        rows.append(
            {
                "name": name,
                "fixture_valid": psd_tools_readback,
                "oracle_valid": deterministic and oracle_independence,
                "psd_tools_1_18_readback": psd_tools_readback,
                "deterministic_bytes": deterministic,
                "psd2fusion_semantic_ir_valid": semantic_ir_valid,
                "materialized_asset_rgba_valid": asset_rgba_valid,
                "strict_rejected_operations": rejected,
                "semantic_math_exact": semantic_math_exact,
                "semantic_math_max_channel_delta": maximum_delta,
                "lowering_structural": structure,
                "comp_deterministic": comp_deterministic,
                "fixture_canvas_background": list(spec.background),
                "fixture_canvas_background_serialized_as_psd_layer": canvas_transported,
                "oracle_math_backdrop_source": "fixture_spec.canvas.background",
                "artifacts": {
                    "psd": _artifact(psd_path),
                    "expected_png": _artifact(expected_path),
                    "comp": _artifact(comp_path),
                    "manifest": _artifact(manifest_path),
                },
                "graph": graph,
            }
        )

    count = len(rows)
    counts = {
        "fixture_valid": sum(row["fixture_valid"] for row in rows),
        "oracle_valid": sum(row["oracle_valid"] for row in rows),
        "psd_tools_1_18_readback": sum(
            row["psd_tools_1_18_readback"] for row in rows
        ),
        "deterministic_bytes": sum(row["deterministic_bytes"] for row in rows),
        "psd2fusion_semantic_ir_valid": sum(
            row["psd2fusion_semantic_ir_valid"] for row in rows
        ),
        "materialized_asset_rgba_valid": sum(
            row["materialized_asset_rgba_valid"] for row in rows
        ),
        "strict_without_rejection": sum(
            not row["strict_rejected_operations"] for row in rows
        ),
        "semantic_math_exact": sum(row["semantic_math_exact"] for row in rows),
        "lowering_structural": sum(
            row["lowering_structural"]["pass"] for row in rows
        ),
        "comp_deterministic": sum(row["comp_deterministic"] for row in rows),
        "fixture_canvas_background_transport": sum(
            row["fixture_canvas_background_serialized_as_psd_layer"]
            for row in rows
        ),
    }
    required = (
        "fixture_valid",
        "oracle_valid",
        "psd_tools_1_18_readback",
        "deterministic_bytes",
        "psd2fusion_semantic_ir_valid",
        "materialized_asset_rgba_valid",
        "strict_without_rejection",
        "semantic_math_exact",
        "lowering_structural",
        "comp_deterministic",
    )
    report = {
        "schema": "psd2fusion.psdfixtureforge-offline.v1",
        "status": "PASS" if all(counts[key] == count for key in required) else "FAIL",
        "host_status": "NOT_RUN_PROHIBITED",
        "host_claim": "NOT_MADE",
        "fixture_forge": {
            "root": str(fixture_forge),
            "head": fixture_head,
            "worktree_clean": not fixture_status,
            "oracle_independence": oracle_independence,
        },
        "psd2fusion": {
            "root": str(ROOT),
            "head_at_run": _git(ROOT, "rev-parse", "HEAD"),
            "worktree_status_at_run": _git(ROOT, "status", "--porcelain=v1"),
        },
        "dependencies": {
            "psd_tools": importlib.metadata.version("psd-tools"),
            "pillow": importlib.metadata.version("Pillow"),
        },
        "case_count": count,
        "counts": counts,
        "transport_exceptions": [
            row["name"]
            for row in rows
            if not row["fixture_canvas_background_serialized_as_psd_layer"]
        ],
        "cases": rows,
    }
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-forge", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--expected-fixture-head")
    args = parser.parse_args(argv)
    report = run(
        args.fixture_forge,
        args.output,
        args.expected_fixture_head,
    )
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "status": report["status"],
                "host_status": report["host_status"],
                "fixture_forge_head": report["fixture_forge"]["head"],
                "psd2fusion_head_at_run": report["psd2fusion"]["head_at_run"],
                "case_count": report["case_count"],
                "counts": report["counts"],
                "transport_exceptions": report["transport_exceptions"],
                "summary": str(args.summary.resolve()) if args.summary else None,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
