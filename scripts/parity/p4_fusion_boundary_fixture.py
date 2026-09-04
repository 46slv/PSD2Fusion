"""Generate the deterministic Fusion-only P4-HOST-PIXEL boundary fixture.

The fixture is deliberately an artifact generator, not a pixel oracle.  It
uses the production :func:`psd2fusion.fusion_comp.compile_comp` lowering for
the same fractional RGBA inputs in eight compositions:

* Normal, Multiply, Linear Dodge and Overlay member controls; and
* an ungrouped and an isolated ``GroupOperator`` scope for every control.

The shared fractional bytes make Linear Dodge overflow before member opacity
is applied, so its native early-clamp behavior is visible at the local taps.

The generated manifest contains only paths relative to the caller-provided
output directory.  This keeps the machine contract stable while the comp
files themselves retain the absolute asset paths required by Fusion Loader.
No host application, formula oracle or image comparator is involved here.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psd2fusion.fusion_comp import FUSION_BLEND_IDS, compile_comp
from psd2fusion.semantic import ClippingChain, SemanticDocument, SemanticLayer
from scripts.validate_clipping_subtrees import materialization_for, parse_tools


SCHEMA = "psd2fusion-parity-004-fusion-boundary-fixture.v2"
MODES: Tuple[str, ...] = ("Normal", "Multiply", "Linear Dodge", "Overlay")
SCOPES: Tuple[str, ...] = ("ungrouped", "isolated")
CASES: Tuple[str, ...] = tuple(
    "%s_%s" % (mode.lower().replace(" ", "_"), scope)
    for mode in MODES
    for scope in SCOPES
)

WIDTH = 8
HEIGHT = 8
MEMBER_OPACITY = 0.625

# These values are intentionally fractional and are kept as 8-bit RGBA input
# facts. The same bytes are used for every mode and scope. Linear Dodge's red
# channel overflows at its named blend function, making the clamp stage
# observable without changing the production graph.
INPUT_RGBA8: Mapping[str, Tuple[int, int, int, int]] = {
    "outer": (41, 109, 181, 89),
    "base": (170, 146, 101, 173),
    "member": (179, 89, 89, 230),
}
ASSET_PATHS: Mapping[str, str] = {
    "outer": "assets/p4fb-outer.png",
    "base": "assets/p4fb-base.png",
    "member": "assets/p4fb-member.png",
}

# The IDs are intentionally longer than the serializer's ten-character role
# suffix.  This avoids prefix collisions in the offline probes.
OUTER_ID = "p4fb_outer01"
BASE_ID = "p4fb_base01"
MEMBER_ID = "p4fb_member01"
GROUP_ID = "p4fb_group01"
SOURCE_HASH = hashlib.sha256(b"psd2fusion-p4-fusion-boundary-fixture-v2").hexdigest()


def _slug(mode: str) -> str:
    return mode.lower().replace(" ", "_")


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _rgba_png(rgba: Sequence[int], width: int = WIDTH, height: int = HEIGHT) -> bytes:
    """Return a minimal deterministic 8-bit RGBA PNG without ancillary data."""

    if len(rgba) != 4 or any(not 0 <= int(channel) <= 255 for channel in rgba):
        raise ValueError("RGBA input must contain four integers in [0, 255]")
    row = bytes((0,)) + bytes(int(channel) for channel in rgba) * width
    raw = row * height
    return b"\x89PNG\r\n\x1a\n" + b"".join(
        (
            _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            _png_chunk(b"IDAT", zlib.compress(raw, level=9)),
            _png_chunk(b"IEND", b""),
        )
    )


def _materialize_assets(output: Path) -> Dict[str, Dict[str, Any]]:
    """Write the three shared fixture assets and return stable asset records."""

    records: Dict[str, Dict[str, Any]] = {}
    for role in ("outer", "base", "member"):
        path = output / ASSET_PATHS[role]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_rgba_png(INPUT_RGBA8[role]))
        records[role] = {
            "path": _relative(path, output),
            "size": path.stat().st_size,
            "sha256": _sha256(path),
            "width": WIDTH,
            "height": HEIGHT,
            "rgba8": list(INPUT_RGBA8[role]),
            "alpha8": INPUT_RGBA8[role][3],
            "alpha": INPUT_RGBA8[role][3] / 255.0,
        }
    return records


def _input_contract(asset_records: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "width": WIDTH,
        "height": HEIGHT,
        "assets": {
            role: {
                "path": str(record["path"]),
                "rgba8": list(record["rgba8"]),
                "rgba_normalized": [channel / 255.0 for channel in record["rgba8"]],
                "alpha8": int(record["alpha8"]),
                "alpha": float(record["alpha"]),
            }
            for role, record in asset_records.items()
        },
        "base_alpha": float(asset_records["base"]["alpha"]),
        "member_alpha": float(asset_records["member"]["alpha"]),
        "member_opacity": MEMBER_OPACITY,
    }


def fixture_document(mode: str, scope: str) -> SemanticDocument:
    """Build one semantic fixture document for the production compiler."""

    if mode not in MODES:
        raise ValueError("unsupported fixture mode: %s" % mode)
    if scope not in SCOPES:
        raise ValueError("unsupported fixture scope: %s" % scope)

    outer = SemanticLayer(
        id=OUTER_ID,
        name="P4 Fusion boundary outer backdrop",
        asset_path=ASSET_PATHS["outer"],
        blend="Normal",
        opacity=1.0,
    )
    base = SemanticLayer(
        id=BASE_ID,
        name="P4 Fusion boundary base",
        asset_path=ASSET_PATHS["base"],
        blend="Normal",
        opacity=1.0,
        clipping_members=[MEMBER_ID],
    )
    member = SemanticLayer(
        id=MEMBER_ID,
        name="P4 Fusion boundary %s member" % mode,
        asset_path=ASSET_PATHS["member"],
        clipping_base_id=BASE_ID,
        blend=mode,
        opacity=MEMBER_OPACITY,
    )
    chain = ClippingChain(
        base_id=BASE_ID,
        member_ids=[MEMBER_ID],
        blend_clipped_as_group=True,
        blend_clipped_as_group_provenance="photoshop_default_true",
    )

    if scope == "isolated":
        group = SemanticLayer(
            id=GROUP_ID,
            name="P4 Fusion boundary isolated group",
            kind="group",
            children=[base, member],
            blend="Normal",
            opacity=1.0,
            isolated=True,
            pass_through=False,
        )
        children = [outer, group]
    else:
        children = [outer, base, member]

    return SemanticDocument(
        source_path="p4-fusion-boundary-fixture.psd",
        source_sha256=SOURCE_HASH,
        parser="fixture",
        parser_version="1",
        width=WIDTH,
        height=HEIGHT,
        color_mode="RGB",
        depth=8,
        children=children,
        clipping_chains=[chain],
    )


def _role(tools: Iterable[Mapping[str, Any]], prefix: str, layer_id: str) -> List[Dict[str, Any]]:
    suffix = "_" + layer_id[:10]
    return [
        dict(tool)
        for tool in tools
        if str(tool.get("name", "")).startswith(prefix)
        and (
            str(tool.get("name", "")).endswith(suffix)
            or suffix + "_" in str(tool.get("name", ""))
        )
    ]


def _one(values: Sequence[Mapping[str, Any]], label: str) -> Optional[Dict[str, Any]]:
    if len(values) != 1:
        return None
    value = dict(values[0])
    value["boundary"] = label
    return value


def _compact_tool(tool: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    if tool is None:
        return None
    fields = (
        "name",
        "type",
        "background",
        "foreground",
        "input",
        "apply_mode",
        "blend",
        "operator",
        "process_alpha",
        "to_alpha",
        "clip_black",
        "clip_white",
        "comments",
    )
    return {field: tool.get(field) for field in fields}


_GROUP_DECLARATION = re.compile(
    r"(?m)^[ \t]*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*GroupOperator\s*\{"
)


def _balanced_end(text: str, opening: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    return len(text)


def _group_block(text: str, group_name: str) -> str:
    match = next(
        (candidate for candidate in _GROUP_DECLARATION.finditer(text) if candidate.group(1) == group_name),
        None,
    )
    if match is None:
        return ""
    opening = text.find("{", match.start(), match.end())
    return text[match.start() : _balanced_end(text, opening)]


def _instance_source(block: str, field: str, kind: str) -> Optional[Dict[str, str]]:
    match = re.search(
        r"%s\s*=\s*%s\s*\{\s*"
        r"SourceOp\s*=\s*\"([^\"]+)\"\s*,\s*"
        r"Source\s*=\s*\"([^\"]+)\"" % (re.escape(field), re.escape(kind)),
        block,
    )
    if match is None:
        return None
    return {"source_op": match.group(1), "source": match.group(2)}


def _source_consumers(tools: Sequence[Mapping[str, Any]], source_name: str) -> List[Dict[str, str]]:
    consumers: List[Dict[str, str]] = []
    for tool in tools:
        for field in ("background", "foreground", "input", "effect_mask"):
            if tool.get(field) == source_name:
                consumers.append(
                    {"tool": str(tool["name"]), "input": field, "source": source_name}
                )
    return consumers


def _case_boundaries(
    comp_path: Path, document: SemanticDocument, mode: str, scope: str
) -> Dict[str, Any]:
    tools = [dict(tool) for tool in parse_tools(comp_path)]
    base_loader = _one(_role(tools, "Loader", BASE_ID), "base_loader")
    member_loader = _one(_role(tools, "Loader", MEMBER_ID), "member_loader")
    base_materialization = materialization_for(tools, BASE_ID)
    member_materialization = materialization_for(tools, MEMBER_ID)
    clip_in = _one(
        [tool for tool in _role(tools, "ClipIn", MEMBER_ID) if tool.get("type") == "Merge"],
        "clip_in",
    )
    channel_boolean = {
        "base_opaque": _one(
            [tool for tool in _role(tools, "BlendBaseOpaque", MEMBER_ID) if tool.get("type") == "ChannelBoolean"],
            "base_opaque",
        ),
        "member_opaque": _one(
            [tool for tool in _role(tools, "BlendMemberOpaque", MEMBER_ID) if tool.get("type") == "ChannelBoolean"],
            "member_opaque",
        ),
        "coverage": _one(
            [tool for tool in _role(tools, "BlendCoverage", MEMBER_ID) if tool.get("type") == "ChannelBoolean"],
            "coverage",
        ),
        "restore_alpha": _one(
            [tool for tool in _role(tools, "BlendRestoreAlpha", MEMBER_ID) if tool.get("type") == "ChannelBoolean"],
            "restore_alpha",
        ),
    }
    blend_function = _one(
        [tool for tool in _role(tools, "BlendFunction", MEMBER_ID) if tool.get("type") == "Merge"],
        "blend_function",
    )
    clip_stack = _one(
        [tool for tool in _role(tools, "ClipStack", MEMBER_ID) if tool.get("type") == "Merge"],
        "clip_stack",
    )
    parent_merges = [
        tool
        for tool in _role(tools, "Merge", BASE_ID)
        if "PSD clipping chain merge:" in str(tool.get("comments", ""))
    ]
    parent_merge = _one(parent_merges, "parent_merge")

    group_boundary: Optional[Dict[str, Any]] = None
    groups = [tool for tool in tools if tool.get("type") == "GroupOperator"]
    if groups:
        group = groups[0]
        group_name = str(group["name"])
        text = comp_path.read_text(encoding="utf-8")
        block = _group_block(text, group_name)
        proxy_input = _instance_source(block, "MainInput1", "InstanceInput")
        proxy_output = _instance_source(block, "MainOutput1", "InstanceOutput")
        internal_name = proxy_output["source_op"] if proxy_output else None
        group_proxy_consumers = _source_consumers(tools, group_name)
        render_consumers = _source_consumers(tools, internal_name or "")
        group_parent_candidates = [
            tool
            for tool in tools
            if tool.get("type") == "Merge"
            and internal_name is not None
            and tool.get("foreground") == internal_name
            and tool.get("name") != (parent_merge or {}).get("name")
        ]
        group_parent_merge = _one(group_parent_candidates, "group_parent_merge")
        group_boundary = {
            "operator": group_name,
            "proxy_input": proxy_input,
            "proxy_output": proxy_output,
            "internal_terminal": internal_name,
            "parent_merge": _compact_tool(group_parent_merge),
            "group_proxy_consumers": group_proxy_consumers,
            "render_consumers": render_consumers,
            "ordinary_render_inputs_avoid_group_proxy": not group_proxy_consumers,
        }

    base_name = base_materialization["source"]
    member_name = member_materialization["source"]
    clip_name = clip_in["name"] if clip_in else None
    stack_name = clip_stack["name"] if clip_stack else None
    channel_names = {
        role: item["name"] if item is not None else None
        for role, item in channel_boolean.items()
    }
    expected_mode = 'FuID { "%s" }' % FUSION_BLEND_IDS[mode]
    checks = {
        "one_base_loader": base_loader is not None and base_materialization["valid"],
        "one_member_loader": member_loader is not None
        and member_materialization["valid"],
        "clip_in_is_fixed_matte_operator_in": bool(
            clip_in
            and clip_in.get("background") == base_name
            and clip_in.get("foreground") == member_name
            and clip_in.get("apply_mode") == 'FuID { "Normal" }'
            and clip_in.get("blend") == "1.000000"
            and clip_in.get("operator") == 'FuID { "In" }'
        ),
        "all_expected_channel_booleans": all(value is not None for value in channel_boolean.values()),
        "blend_function_has_member_mode": bool(
            blend_function
            and blend_function.get("background") == channel_names["base_opaque"]
            and blend_function.get("foreground") == channel_names["member_opaque"]
            and blend_function.get("apply_mode") == expected_mode
            and blend_function.get("blend") == "1.000000"
        ),
        "clip_stack_has_member_opacity_and_fixed_alpha": bool(
            clip_stack
            and clip_stack.get("background") == base_name
            and clip_stack.get("foreground") == channel_names["restore_alpha"]
            and clip_stack.get("apply_mode") == 'FuID { "Normal" }'
            and clip_stack.get("blend") == "%.6f" % MEMBER_OPACITY
            and clip_stack.get("process_alpha") == "0"
        ),
        "one_parent_merge_after_clip_stack": bool(
            parent_merge
            and parent_merge.get("foreground") == stack_name
            and parent_merge.get("apply_mode") == 'FuID { "Normal" }'
            and parent_merge.get("blend") == "1.000000"
        ),
        "scope_boundary_matches_document": (
            (scope == "ungrouped" and not groups and group_boundary is None)
            or (
                scope == "isolated"
                and len(groups) == 1
                and group_boundary is not None
                and group_boundary["proxy_output"] is not None
                and group_boundary["internal_terminal"] != group_boundary["operator"]
                and bool(group_boundary["parent_merge"])
                and not group_boundary["group_proxy_consumers"]
                and bool(group_boundary["render_consumers"])
            )
        ),
        "ordinary_render_inputs_avoid_group_proxy": not any(
            group.get("name") in {
                tool.get(field)
                for tool in tools
                for field in ("background", "foreground", "input", "effect_mask")
            }
            for group in groups
        ),
    }

    compact_channels = {
        role: _compact_tool(item) for role, item in channel_boolean.items()
    }
    return {
        "tools": len(tools),
        "boundaries": {
            "base_loader": base_name,
            "member_loader": member_name,
            "base_raw_loader": base_loader["name"] if base_loader else None,
            "member_raw_loader": member_loader["name"] if member_loader else None,
            "clip_in": clip_name,
            "channel_boolean": channel_names,
            "blend_function": blend_function["name"] if blend_function else None,
            "clip_stack": stack_name,
            "parent_merge": parent_merge["name"] if parent_merge else None,
            "group": group_boundary,
        },
        "observed": {
            "base_loader": _compact_tool(base_loader),
            "member_loader": _compact_tool(member_loader),
            "clip_in": _compact_tool(clip_in),
            "channel_boolean": compact_channels,
            "blend_function": _compact_tool(blend_function),
            "clip_stack": _compact_tool(clip_stack),
            "parent_merge": _compact_tool(parent_merge),
        },
        "expected_controls": {
            "mode": mode,
            "blend_function_apply_mode": expected_mode,
            "clip_in_apply_mode": 'FuID { "Normal" }',
            "clip_in_blend": "1.000000",
            "clip_in_operator": 'FuID { "In" }',
            "clip_stack_apply_mode": 'FuID { "Normal" }',
            "clip_stack_blend": "%.6f" % MEMBER_OPACITY,
            "clip_stack_process_alpha": "0",
            "parent_merge_apply_mode": 'FuID { "Normal" }',
            "parent_merge_blend": "1.000000",
        },
        "checks": checks,
        "pass": all(checks.values()),
        "group_operator_count": len(groups),
        "document_clipping_chain": {
            "base_id": document.clipping_chains[0].base_id,
            "member_ids": list(document.clipping_chains[0].member_ids),
            "blend_clipped_as_group": document.clipping_chains[0].blend_clipped_as_group,
        },
    }


def _artifact(path: Path, output: Path) -> Dict[str, Any]:
    return {
        "path": _relative(path, output),
        "size": path.stat().st_size,
        "sha256": _sha256(path),
    }


def build(output: Path) -> Dict[str, Any]:
    """Materialize all eight deterministic comps and return the manifest."""

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    asset_records = _materialize_assets(output)
    inputs = _input_contract(asset_records)
    case_reports: Dict[str, Dict[str, Any]] = {}

    for mode in MODES:
        for scope in SCOPES:
            case_id = "%s_%s" % (_slug(mode), scope)
            comp_path = output / ("p4_fusion_boundary_%s.comp" % case_id)
            document = fixture_document(mode, scope)
            graph = compile_comp(document, str(comp_path))
            boundaries = _case_boundaries(comp_path, document, mode, scope)
            case_reports[case_id] = {
                "id": case_id,
                "mode": mode,
                "scope": scope,
                "source_sha256": SOURCE_HASH,
                "inputs": copy.deepcopy(inputs),
                "asset_hashes": {
                    role: str(record["sha256"]) for role, record in asset_records.items()
                },
                "comp": _artifact(comp_path, output),
                "graph": graph,
                "boundaries": boundaries["boundaries"],
                "observed": boundaries["observed"],
                "expected_controls": boundaries["expected_controls"],
                "checks": boundaries["checks"],
                "group_operator_count": boundaries["group_operator_count"],
                "document_clipping_chain": boundaries["document_clipping_chain"],
                "pass": boundaries["pass"],
                "host_required": True,
                "pixel_claim": "none",
            }

    manifest: Dict[str, Any] = {
        "schema": SCHEMA,
        "schema_version": 1,
        "task": "PARITY-004",
        "item": "P4-HOST-PIXEL",
        "status": "PASS" if all(case["pass"] for case in case_reports.values()) else "FAIL",
        "pass": all(case["pass"] for case in case_reports.values()),
        "host_required": True,
        "pixel_claim": "none",
        "formula_oracle": "not used",
        "comparator": "not used; host runner owns rendered comparison",
        "production_compiler": "psd2fusion.fusion_comp.compile_comp",
        "recipe": "operator_in_fixed_matte_local_stack",
        "case_order": list(CASES),
        "modes": list(MODES),
        "scopes": list(SCOPES),
        "inputs": inputs,
        "assets": asset_records,
        "cases": case_reports,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="caller-provided artifact directory")
    args = parser.parse_args(argv)
    report = build(args.output)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
