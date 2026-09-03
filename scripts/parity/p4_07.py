"""Apply and audit the selected clipping recipe on the real PSD.

This is an offline structural audit.  It reads ``a.psd`` and a generated
composition, checks all default/true chains, and records representative chain
sizes and nesting depths.  It deliberately does not load Fusion or claim
pixel/reference parity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psd2fusion.fusion_comp import FUSION_BLEND_IDS
from psd2fusion.parse_psd import parse_psd
from psd2fusion.semantic import SemanticLayer, index_layers, walk_layers
from scripts.validate_clipping_subtrees import parse_tools, validate


EXPECTED_CHAINS = 23
EXPECTED_MEMBERS = 59


def _artifact(path: Path) -> Dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": str(path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _role(tools: Sequence[Dict[str, Any]], prefix: str, layer_id: str) -> List[Dict[str, Any]]:
    suffix = "_" + layer_id[:10]
    return [
        tool
        for tool in tools
        if tool["name"].startswith(prefix)
        and (tool["name"].endswith(suffix) or suffix + "_" in tool["name"])
    ]


def _depths(children: Iterable[SemanticLayer]) -> Dict[str, int]:
    layers = index_layers(children)
    result: Dict[str, int] = {}
    for layer in layers.values():
        depth = 0
        parent_id = layer.parent_id
        while parent_id is not None:
            depth += 1
            parent_id = layers[parent_id].parent_id
        result[layer.id] = depth
    return result


def representative_indices(rows: Sequence[Dict[str, Any]]) -> List[int]:
    """Select deterministic chains spanning size and nesting-depth extremes."""

    if not rows:
        return []
    candidates = [
        min(rows, key=lambda row: (row["member_count"], row["depth"], row["chain"])),
        max(rows, key=lambda row: (row["member_count"], row["depth"], -row["chain"])),
        min(rows, key=lambda row: (row["depth"], -row["member_count"], row["chain"])),
        max(rows, key=lambda row: (row["depth"], row["member_count"], -row["chain"])),
    ]
    result: List[int] = []
    for row in candidates:
        chain = int(row["chain"])
        if chain not in result:
            result.append(chain)
    return result


def _chain_control_row(
    tools: Sequence[Dict[str, Any]],
    base: SemanticLayer,
    members: Sequence[SemanticLayer],
    chain_index: int,
    depth: int,
    provenance: str,
) -> Dict[str, Any]:
    base_loaders = _role(tools, "Loader", base.id)
    outer_merges = [
        tool
        for tool in _role(tools, "Merge", base.id)
        if "PSD clipping chain merge:" in tool["comments"]
    ]
    previous = base_loaders[0]["name"] if len(base_loaders) == 1 else None
    member_rows: List[Dict[str, Any]] = []
    controls_pass = len(base_loaders) == 1 and len(outer_merges) == 1
    for member in members:
        loaders = _role(tools, "Loader", member.id)
        clips = _role(tools, "ClipIn", member.id)
        clip_rgbs = _role(tools, "ClipRGB", member.id)
        stacks = _role(tools, "ClipStack", member.id)
        visible = member.effective_visible
        row: Dict[str, Any] = {
            "id": member.id,
            "name": member.name,
            "visible": visible,
            "blend": member.blend,
            "opacity": member.opacity,
            "loader_count": len(loaders),
            "clip_count": len(clips),
            "stack_count": len(stacks),
        }
        if not visible:
            row["pass"] = True
            member_rows.append(row)
            continue
        ok = len(loaders) == len(clips) == len(clip_rgbs) == len(stacks) == 1
        if ok:
            clip = clips[0]
            clip_rgb = clip_rgbs[0]
            stack = stacks[0]
            mode_id = FUSION_BLEND_IDS.get(member.blend)
            expected_mode = 'FuID { "%s" }' % mode_id if mode_id else None
            expected_blend = "%.6f" % member.opacity
            ok = all(
                (
                    clip["background"] == (base_loaders[0]["name"] if base_loaders else None),
                    clip["foreground"] == loaders[0]["name"],
                    clip["apply_mode"] == 'FuID { "Normal" }',
                    clip["blend"] == "1.000000",
                    clip["operator"] == 'FuID { "In" }',
                    clip_rgb["background"] == clip["name"],
                    clip_rgb["foreground"] == loaders[0]["name"],
                    stack["background"] == previous,
                    stack["foreground"] == clip_rgb["name"],
                    expected_mode is not None and stack["apply_mode"] == expected_mode,
                    stack["blend"] == expected_blend,
                    stack["process_alpha"] == "0",
                )
            )
            row.update(
                {
                    "loader": loaders[0]["name"],
                    "clip": clip["name"],
                    "clip_rgb": clip_rgb["name"],
                    "stack": stack["name"],
                    "clip_background": clip["background"],
                    "stack_background": stack["background"],
                    "stack_apply_mode": stack["apply_mode"],
                    "stack_blend": stack["blend"],
                    "stack_start": stack["start"],
                    "stack_position": stack["position"],
                }
            )
            previous = stack["name"]
        row["pass"] = ok
        controls_pass = controls_pass and ok
        member_rows.append(row)

    outer = outer_merges[0] if len(outer_merges) == 1 else None
    base_mode_id = FUSION_BLEND_IDS.get(base.blend)
    expected_base_mode = 'FuID { "%s" }' % base_mode_id if base_mode_id else None
    expected_base_blend = "%.6f" % base.opacity
    visible_rows = [row for row in member_rows if row.get("visible")]
    outer_pass = bool(
        outer is not None
        and visible_rows
        and expected_base_mode is not None
        and outer["foreground"] == visible_rows[-1].get("stack")
        and outer["apply_mode"] == expected_base_mode
        and outer["blend"] == expected_base_blend
        and outer["start"] > max(row.get("stack_start", -1) for row in visible_rows)
    )
    return {
        "chain": chain_index,
        "base_id": base.id,
        "base_name": base.name,
        "member_count": len(members),
        "depth": depth,
        "provenance": provenance,
        "base_loader_count": len(base_loaders),
        "outer_count": len(outer_merges),
        "outer": outer,
        "members": member_rows,
        "controls_pass": controls_pass,
        "outer_base_controls_pass": outer_pass,
        "pass": controls_pass and outer_pass,
    }


def build(psd_path: Path, comp_path: Path, output: Path) -> Dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    document = parse_psd(str(psd_path))
    tools = parse_tools(comp_path)
    structural = validate(str(psd_path), str(comp_path))
    depths = _depths(document.children)
    layers = index_layers(document.children)
    rows = [
        _chain_control_row(
            tools,
            layers[chain.base_id],
            [layers[member_id] for member_id in chain.member_ids],
            index,
            depths[chain.base_id],
            chain.blend_clipped_as_group_provenance,
        )
        for index, chain in enumerate(document.clipping_chains, 1)
    ]
    representatives = representative_indices(rows)
    representative_rows = [row for row in rows if row["chain"] in representatives]
    checks = {
        "expected_chain_count": len(document.clipping_chains) == EXPECTED_CHAINS,
        "expected_member_count": sum(len(chain.member_ids) for chain in document.clipping_chains)
        == EXPECTED_MEMBERS,
        "all_default_true": all(chain.blend_clipped_as_group for chain in document.clipping_chains),
        "all_structural_recipe_checks": structural["pass"],
        "all_member_controls_and_base_boundaries": all(row["pass"] for row in rows),
        "group_count_matches_graph": (
            structural["groups_semantic"] == structural["groups_graph"]
        ),
        "all_flow_positions_present": all(
            tool["position"] is not None for tool in tools if tool["type"] != "Note"
        ),
        "representatives_span_size_and_depth": len(representative_rows) >= 2
        and len({row["member_count"] for row in representative_rows}) >= 2
        and len({row["depth"] for row in representative_rows}) >= 2,
    }
    report: Dict[str, Any] = {
        "schema_version": 1,
        "task": "PARITY-004",
        "item": "P4-07",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "pass": all(checks.values()),
        "recipe": "operator_in_fixed_matte_local_stack",
        "scope": {
            "psd_read_only": True,
            "host_load": "NOT_RUN_BY_SCOPE",
            "pixel_reference": "NOT_RUN_BY_SCOPE",
            "clbl_false": "NOT_IN_SCOPE",
        },
        "source": _artifact(psd_path),
        "composition": _artifact(comp_path),
        "graph": {
            "tools": len(tools),
            "groups_semantic": structural["groups_semantic"],
            "groups_graph": structural["groups_graph"],
            "chains": len(document.clipping_chains),
            "members": sum(len(chain.member_ids) for chain in document.clipping_chains),
            "blend_modes": sorted({layer.blend for layer in walk_layers(document.children)}),
        },
        "checks": checks,
        "representative_chain_indices": representatives,
        "representative_chains": representative_rows,
        "chain_rows": rows,
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("psd", type=Path)
    parser.add_argument("comp", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    report = build(args.psd, args.comp, args.output)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
