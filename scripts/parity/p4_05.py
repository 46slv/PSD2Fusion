"""Exercise clipping boundaries at existing group/nesting boundaries.

Each case uses the same fixed-matte clipping recipe.  The checks focus on
where the local chain and its one outer Merge live relative to GroupOperator,
not on host render behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psd2fusion.fusion_comp import compile_comp
from psd2fusion.semantic import ClippingChain, SemanticDocument, SemanticLayer
from scripts.validate_clipping_subtrees import parse_tools


SOURCE_HASH = "p405" + "0" * 60
CASES = ("direct", "isolated", "pass_through", "nested_isolated", "adjacent")


def _chain(base_id: str, member_ids: Sequence[str], label: str) -> Tuple[List[SemanticLayer], ClippingChain]:
    base = SemanticLayer(
        id=base_id,
        name="P4-05 %s base" % label,
        asset_path="assets/%s-base.png" % label,
        clipping_members=list(member_ids),
    )
    members = [
        SemanticLayer(
            id=member_id,
            name="P4-05 %s member %d" % (label, index),
            asset_path="assets/%s-member-%d.png" % (label, index),
            clipping_base_id=base_id,
            blend="Multiply" if index == 2 else "Normal",
            opacity=0.75 if index == 2 else 1.0,
        )
        for index, member_id in enumerate(member_ids, 1)
    ]
    return [base] + members, ClippingChain(
        base_id=base_id,
        member_ids=list(member_ids),
        blend_clipped_as_group=True,
        blend_clipped_as_group_provenance="photoshop_default_true",
    )


def _group(group_id: str, name: str, children: Sequence[SemanticLayer], pass_through: bool = False) -> SemanticLayer:
    return SemanticLayer(
        id=group_id,
        name=name,
        kind="group",
        children=list(children),
        pass_through=pass_through,
        isolated=not pass_through,
        blend="Normal",
        opacity=1.0,
    )


def fixture_documents() -> Dict[str, SemanticDocument]:
    docs: Dict[str, SemanticDocument] = {}

    direct_layers, direct_chain = _chain(
        "p405dbase", ("p405dm001", "p405dm002"), "direct"
    )
    docs["direct"] = SemanticDocument(
        source_path="p4-05-direct.psd",
        source_sha256=SOURCE_HASH,
        parser="fixture",
        parser_version="1",
        width=8,
        height=8,
        children=[
            SemanticLayer(
                id="p405dout",
                name="P4-05 direct outer",
                asset_path="assets/direct-outer.png",
            ),
            *direct_layers,
        ],
        clipping_chains=[direct_chain],
    )

    isolated_layers, isolated_chain = _chain(
        "p405isobas", ("p405isom01", "p405isom02"), "isolated"
    )
    docs["isolated"] = SemanticDocument(
        source_path="p4-05-isolated.psd",
        source_sha256=SOURCE_HASH,
        parser="fixture",
        parser_version="1",
        width=8,
        height=8,
        children=[
            SemanticLayer(
                id="p405isoout",
                name="P4-05 isolated outer",
                asset_path="assets/isolated-outer.png",
            ),
            _group("p405isogrp", "P4-05 isolated group", isolated_layers),
        ],
        clipping_chains=[isolated_chain],
    )

    pass_layers, pass_chain = _chain(
        "p405ptbase", ("p405ptm001", "p405ptm002"), "pass-through"
    )
    docs["pass_through"] = SemanticDocument(
        source_path="p4-05-pass-through.psd",
        source_sha256=SOURCE_HASH,
        parser="fixture",
        parser_version="1",
        width=8,
        height=8,
        children=[
            SemanticLayer(
                id="p405ptout",
                name="P4-05 pass-through outer",
                asset_path="assets/pass-through-outer.png",
            ),
            _group("p405ptgrp", "P4-05 pass-through group", pass_layers, True),
        ],
        clipping_chains=[pass_chain],
    )

    nested_layers, nested_chain = _chain(
        "p405nbase1", ("p405nm001x", "p405nm002x"), "nested"
    )
    inner = _group("p405nestin", "P4-05 inner isolated", nested_layers)
    outer_group = _group("p405nestout", "P4-05 outer isolated", [inner])
    docs["nested_isolated"] = SemanticDocument(
        source_path="p4-05-nested.psd",
        source_sha256=SOURCE_HASH,
        parser="fixture",
        parser_version="1",
        width=8,
        height=8,
        children=[
            SemanticLayer(
                id="p405nestback",
                name="P4-05 nested outer",
                asset_path="assets/nested-outer.png",
            ),
            outer_group,
        ],
        clipping_chains=[nested_chain],
    )

    adjacent_layers, adjacent_chain = _chain(
        "p405abase1", ("p405am001x", "p405am002x"), "adjacent"
    )
    lower_leaf = SemanticLayer(
        id="p405adjlowleaf",
        name="P4-05 lower boundary leaf",
        asset_path="assets/adjacent-lower.png",
    )
    upper_leaf = SemanticLayer(
        id="p405adjhighleaf",
        name="P4-05 upper boundary leaf",
        asset_path="assets/adjacent-upper.png",
    )
    docs["adjacent"] = SemanticDocument(
        source_path="p4-05-adjacent.psd",
        source_sha256=SOURCE_HASH,
        parser="fixture",
        parser_version="1",
        width=8,
        height=8,
        children=[
            SemanticLayer(
                id="p405adjout",
                name="P4-05 adjacent outer",
                asset_path="assets/adjacent-backdrop.png",
            ),
            _group("p405adjlow", "P4-05 lower boundary group", [lower_leaf]),
            *adjacent_layers,
            _group("p405adjhigh", "P4-05 upper boundary group", [upper_leaf]),
        ],
        clipping_chains=[adjacent_chain],
    )
    return docs


def _artifact(path: Path) -> Dict[str, Any]:
    data = path.read_bytes()
    return {"path": str(path), "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _role(tools: Sequence[Dict[str, Any]], prefix: str, layer_id: str) -> List[Dict[str, Any]]:
    suffix = "_" + layer_id[:10]
    return [
        tool
        for tool in tools
        if tool["name"].startswith(prefix)
        and (tool["name"].endswith(suffix) or suffix + "_" in tool["name"])
    ]


_FLOW_TOOL_RE = re.compile(
    r"(?m)^[ \t]*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(Background|Loader|Merge|AlphaDivide|ChannelBoolean|"
    r"BrightnessContrast|AlphaMultiply|MediaOut|GroupOperator|Note)\s*\{"
)


def _balanced_block_end(text: str, opening: int) -> int:
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


def _flow_tools(comp_path: Path) -> List[Dict[str, Any]]:
    """Read every Flow tool, including tools nested inside GroupOperators.

    The shared offline parser intentionally exposes a compact view and some
    versions omit inputs belonging to a nested tool.  P4-05 needs the actual
    source edges at group boundaries, so supplement that view from the comp
    text while keeping its existing fields intact.
    """

    text = comp_path.read_text(encoding="utf-8")
    tools: List[Dict[str, Any]] = []
    for match in _FLOW_TOOL_RE.finditer(text):
        opening = text.find("{", match.start(), match.end())
        end = _balanced_block_end(text, opening)
        block = text[match.start() : end]
        tool: Dict[str, Any] = {
            "name": match.group(1),
            "type": match.group(2),
            "start": match.start(),
            "end": end,
        }
        for field, key in (
            ("Background", "background"),
            ("Foreground", "foreground"),
            ("Input", "input"),
            ("EffectMask", "effect_mask"),
        ):
            input_match = re.search(
                r"(?m)^[ \t]*"
                + re.escape(field)
                + r"\s*=\s*Input\s*\{([^\r\n]*)",
                block,
            )
            if input_match is not None:
                source_match = re.search(
                    r'SourceOp\s*=\s*"([^"]+)"', input_match.group(1)
                )
                if source_match is not None:
                    tool[key] = source_match.group(1)
        for field, key in (("Operator", "operator"), ("ApplyMode", "apply_mode")):
            input_match = re.search(
                r"(?m)^[ \t]*"
                + re.escape(field)
                + r"\s*=\s*Input\s*\{([^\r\n]*)",
                block,
            )
            if input_match is not None:
                value_match = re.search(
                    r'Value\s*=\s*(FuID\s*\{\s*"[^"]+"\s*\}|[^,}]+)',
                    input_match.group(1),
                )
                if value_match is not None:
                    tool[key] = value_match.group(1).strip()
        for field, key in (
            ("Blend", "blend"),
            ("ProcessAlpha", "process_alpha"),
            ("ToAlpha", "to_alpha"),
            ("ClipBlack", "clip_black"),
            ("ClipWhite", "clip_white"),
        ):
            input_match = re.search(
                r"(?m)^[ \t]*"
                + re.escape(field)
                + r"\s*=\s*Input\s*\{([^\r\n]*)",
                block,
            )
            if input_match is not None:
                value_match = re.search(
                    r"Value\s*=\s*([^,}]+)", input_match.group(1)
                )
                if value_match is not None:
                    tool[key] = value_match.group(1).strip()
        comment_match = re.search(
            r'(?m)^[ \t]*Comments\s*=\s*Input\s*\{\s*'
            r'Value\s*=\s*"((?:\\.|[^"])*)"',
            block,
        )
        if comment_match is not None:
            tool["comments"] = comment_match.group(1)
        tools.append(tool)
    return tools


def _all_tools(comp_path: Path) -> List[Dict[str, Any]]:
    """Merge the shared parser view with complete nested Flow source edges."""

    indexed: Dict[str, Dict[str, Any]] = {}
    for tool in parse_tools(comp_path):
        indexed[tool["name"]] = dict(tool)
    for tool in _flow_tools(comp_path):
        indexed.setdefault(tool["name"], {}).update(tool)
    return sorted(indexed.values(), key=lambda tool: tool["start"])


def _group_layers(items: Sequence[SemanticLayer]) -> Iterable[SemanticLayer]:
    for layer in items:
        if not layer.is_group:
            continue
        yield layer
        for child in _group_layers(layer.children):
            yield child


def _balanced_group_block(text: str, group_name: str) -> str:
    match = re.search(
        r"(?m)^[ \t]*" + re.escape(group_name) + r"\s*=\s*GroupOperator\s*\{",
        text,
    )
    if match is None:
        return ""
    opening = text.find("{", match.start(), match.end())
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
                return text[match.start() : index + 1]
    return ""


def _proxy_source(block: str, name: str, kind: str) -> Dict[str, str] | None:
    match = re.search(
        r"%s\s*=\s*%s\s*\{\s*"
        r"SourceOp\s*=\s*\"([^\"]+)\"\s*,\s*"
        r"Source\s*=\s*\"([^\"]+)\""
        % (re.escape(name), re.escape(kind)),
        block,
    )
    if match is None:
        return None
    return {"source_op": match.group(1), "source": match.group(2)}


def _proxy_contracts(
    comp_path: Path, groups: Sequence[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    text = comp_path.read_text(encoding="utf-8")
    contracts: Dict[str, Dict[str, Any]] = {}
    for group in groups:
        block = _balanced_group_block(text, group["name"])
        proxy_input = _proxy_source(block, "MainInput1", "InstanceInput")
        proxy_output = _proxy_source(block, "MainOutput1", "InstanceOutput")
        contracts[group["name"]] = {
            "input": proxy_input,
            "output": proxy_output,
        }
    return contracts


def _source_consumers(
    tools: Sequence[Dict[str, Any]], source_name: str
) -> List[Dict[str, str]]:
    consumers: List[Dict[str, str]] = []
    for tool in tools:
        for input_name in ("background", "foreground", "input", "effect_mask"):
            if tool.get(input_name) == source_name:
                consumers.append(
                    {
                        "tool": tool["name"],
                        "input": input_name,
                        "source": source_name,
                    }
                )
    return consumers


def _group_parent_merges(
    tools: Sequence[Dict[str, Any]], layer: SemanticLayer
) -> List[Dict[str, Any]]:
    suffix = "_" + layer.id[:10]
    return [
        tool
        for tool in tools
        if tool["type"] == "Merge"
        and tool["name"].endswith(suffix)
        and str(tool.get("comments", "")).strip().strip('"').startswith(
            "PSD layer merge:"
        )
    ]


def _group_proxy_shape(
    comp_path: Path,
    tools: Sequence[Dict[str, Any]],
    groups: Sequence[Dict[str, Any]],
    document: SemanticDocument,
) -> List[Dict[str, Any]]:
    contracts = _proxy_contracts(comp_path, groups)
    layers = list(_group_layers(document.children))
    shapes: List[Dict[str, Any]] = []
    for group in groups:
        layer = next(
            (
                candidate
                for candidate in layers
                if group["name"].endswith("_" + candidate.id[:10])
            ),
            None,
        )
        contract = contracts[group["name"]]
        render_source = contract["output"]
        parent_merges = _group_parent_merges(tools, layer) if layer is not None else []
        if render_source is not None:
            parent_merges = [
                merge
                for merge in parent_merges
                if merge.get("foreground") == render_source["source_op"]
            ]
        parent_merge = parent_merges[0] if len(parent_merges) == 1 else None
        render_consumers = _source_consumers(
            tools,
            render_source["source_op"] if render_source is not None else "",
        )
        # Some parser versions expose nested GroupOperator tools but omit the
        # containing group's nested consumer list.  The unique parent Merge is
        # still an inspectable runtime edge, so retain it as the consumer
        # record only when it is proven to use the same internal terminal.
        if (
            not render_consumers
            and parent_merge is not None
            and render_source is not None
            and parent_merge.get("foreground") == render_source["source_op"]
        ):
            render_consumers = [
                {
                    "tool": parent_merge["name"],
                    "input": "foreground",
                    "source": render_source["source_op"],
                }
            ]
        shape = dict(group)
        shape.update(
            {
                "layer_id": layer.id if layer is not None else None,
                "proxy": contract,
                "render_source": render_source,
                "render_consumers": render_consumers,
                "group_proxy_consumers": _source_consumers(tools, group["name"]),
                "parent_merge": parent_merge,
                "input_target": (
                    contract["input"]["source_op"]
                    if contract["input"] is not None
                    else None
                ),
            }
        )
        shapes.append(shape)
    return shapes


def _chain_shape(tools: Sequence[Dict[str, Any]], base_id: str, member_ids: Sequence[str]) -> Dict[str, Any]:
    base_loaders = _role(tools, "Loader", base_id)
    outer_merges = [
        tool
        for tool in _role(tools, "Merge", base_id)
        if "PSD clipping chain merge:" in tool["comments"]
    ]
    previous = base_loaders[0]["name"] if len(base_loaders) == 1 else None
    rows: List[Dict[str, Any]] = []
    for member_id in member_ids:
        loaders = _role(tools, "Loader", member_id)
        clips = [tool for tool in _role(tools, "ClipIn", member_id) if tool["type"] == "Merge"]
        base_straights = [tool for tool in _role(tools, "BlendBaseStraight", member_id) if tool["type"] == "AlphaDivide"]
        base_opaques = [tool for tool in _role(tools, "BlendBaseOpaque", member_id) if tool["type"] == "ChannelBoolean"]
        member_straights = [tool for tool in _role(tools, "BlendMemberStraight", member_id) if tool["type"] == "AlphaDivide"]
        member_opaques = [tool for tool in _role(tools, "BlendMemberOpaque", member_id) if tool["type"] == "ChannelBoolean"]
        blend_functions = [tool for tool in _role(tools, "BlendFunction", member_id) if tool["type"] == "Merge"]
        blend_clamps = [tool for tool in _role(tools, "BlendClamp", member_id) if tool["type"] == "BrightnessContrast"]
        blend_coverages = [tool for tool in _role(tools, "BlendCoverage", member_id) if tool["type"] == "ChannelBoolean"]
        blend_premults = [tool for tool in _role(tools, "BlendPremult", member_id) if tool["type"] == "AlphaMultiply"]
        blend_restores = [tool for tool in _role(tools, "BlendRestoreAlpha", member_id) if tool["type"] == "ChannelBoolean"]
        stacks = [tool for tool in _role(tools, "ClipStack", member_id) if tool["type"] == "Merge"]
        row = {
            "loader": loaders[0] if len(loaders) == 1 else None,
            "clip": clips[0] if len(clips) == 1 else None,
            "base_straight": base_straights[0] if len(base_straights) == 1 else None,
            "base_opaque": base_opaques[0] if len(base_opaques) == 1 else None,
            "member_straight": member_straights[0] if len(member_straights) == 1 else None,
            "member_opaque": member_opaques[0] if len(member_opaques) == 1 else None,
            "blend_function": blend_functions[0] if len(blend_functions) == 1 else None,
            "blend_clamp": blend_clamps[0] if len(blend_clamps) == 1 else None,
            "blend_coverage": blend_coverages[0] if len(blend_coverages) == 1 else None,
            "blend_premult": blend_premults[0] if len(blend_premults) == 1 else None,
            "blend_restore": blend_restores[0] if len(blend_restores) == 1 else None,
            "stack": stacks[0] if len(stacks) == 1 else None,
        }
        row["pass"] = bool(
            len(base_loaders) == 1
            and row["loader"] is not None
            and row["clip"] is not None
            and row["base_straight"] is not None
            and row["base_opaque"] is not None
            and row["member_straight"] is not None
            and row["member_opaque"] is not None
            and row["blend_function"] is not None
            and row["blend_clamp"] is not None
            and row["blend_coverage"] is not None
            and row["blend_premult"] is not None
            and row["blend_restore"] is not None
            and row["stack"] is not None
            and row["clip"]["background"] == base_loaders[0]["name"]
            and row["clip"]["foreground"] == row["loader"]["name"]
            and row["clip"]["operator"] == 'FuID { "In" }'
            and row["base_straight"]["input"] == previous
            and row["base_opaque"]["background"] == row["base_straight"]["name"]
            and row["base_opaque"]["to_alpha"] == "16"
            and row["member_straight"]["input"] == row["loader"]["name"]
            and row["member_opaque"]["background"] == row["member_straight"]["name"]
            and row["member_opaque"]["to_alpha"] == "16"
            and row["blend_function"]["background"] == row["base_opaque"]["name"]
            and row["blend_function"]["foreground"] == row["member_opaque"]["name"]
            and row["blend_function"]["blend"] == "1.000000"
            and row["blend_clamp"]["input"] == row["blend_function"]["name"]
            and row["blend_clamp"]["clip_black"] == "1"
            and row["blend_clamp"]["clip_white"] == "1"
            and row["blend_clamp"]["process_alpha"] == "0"
            and row["blend_coverage"]["background"] == row["blend_clamp"]["name"]
            and row["blend_coverage"]["foreground"] == row["clip"]["name"]
            and row["blend_coverage"]["to_alpha"] == "3"
            and row["blend_premult"]["input"] == row["blend_coverage"]["name"]
            and row["blend_restore"]["background"] == row["blend_premult"]["name"]
            and row["blend_restore"]["foreground"] == row["loader"]["name"]
            and row["blend_restore"]["to_alpha"] == "3"
            and row["stack"]["background"] == previous
            and row["stack"]["foreground"] == row["blend_restore"]["name"]
            and row["stack"]["apply_mode"] == 'FuID { "Normal" }'
            and row["stack"]["process_alpha"] == "0"
        )
        if row["stack"] is not None:
            previous = row["stack"]["name"]
        rows.append(row)
    outer = outer_merges[0] if len(outer_merges) == 1 else None
    chain_pass = bool(
        len(base_loaders) == 1
        and len(outer_merges) == 1
        and rows
        and all(row["pass"] for row in rows)
        and outer["foreground"] == rows[-1]["stack"]["name"]
        and outer["start"] > max(row["stack"]["start"] for row in rows)
    )
    return {
        "base_loader": base_loaders[0] if len(base_loaders) == 1 else None,
        "members": rows,
        "outer": outer,
        "pass": chain_pass,
    }


def build(output: Path) -> Dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    case_reports: Dict[str, Any] = {}
    for case, document in fixture_documents().items():
        comp_path = output / ("p4_05_%s.comp" % case)
        stats = compile_comp(document, str(comp_path))
        tools = _all_tools(comp_path)
        chain = document.clipping_chains[0]
        shape = _chain_shape(tools, chain.base_id, chain.member_ids)
        groups = [tool for tool in tools if tool["type"] == "GroupOperator"]
        group_shapes = _group_proxy_shape(comp_path, tools, groups, document)
        group_names = {group["name"] for group in groups}
        render_input_names = ("background", "foreground", "input", "effect_mask")
        ordinary_render_inputs_avoid_group_proxy = all(
            tool.get(input_name) not in group_names
            for tool in tools
            for input_name in render_input_names
        )
        outer = shape["outer"]
        containing_groups = [
            group
            for group in group_shapes
            if outer is not None and group["start"] < outer["start"] < group["end"]
        ]
        proxy_ports_exist = all(
            group["proxy"]["output"] is not None for group in group_shapes
        )
        render_sources_are_internal = all(
            group["render_source"] is not None
            and group["render_source"]["source_op"] != group["name"]
            for group in group_shapes
        )
        render_sources_are_attached = all(
            group["render_consumers"] for group in group_shapes
        )
        render_inputs_do_not_consume_group_proxy = all(
            not group["group_proxy_consumers"] for group in group_shapes
        )
        parent_render_inputs_use_internal_terminal = all(
            (
                group["parent_merge"] is not None
                and group["parent_merge"]["foreground"]
                == group["render_source"]["source_op"]
            )
            for group in group_shapes
            if case != "pass_through"
        )
        pass_through_group = next(
            (
                group
                for group in group_shapes
                if group["proxy"]["input"] is not None
            ),
            None,
        )
        pass_through_proxy_targets_first_consumer = (
            case != "pass_through"
            or (
                pass_through_group is not None
                and outer is not None
                and pass_through_group["proxy"]["input"]["source_op"]
                == outer["name"]
                and pass_through_group.get("input_target") == outer["name"]
            )
        )
        pass_through_uses_actual_parent_backdrop = (
            case != "pass_through"
            or (
                outer is not None
                and bool(outer.get("background"))
                and pass_through_group is not None
                and outer["background"] != pass_through_group["name"]
            )
        )
        direct_chain_stays_in_parent_stream = (
            case != "direct"
            or (len(groups) == 0 and len(containing_groups) == 0)
        )
        expected_group_count = {
            "direct": 0,
            "isolated": 1,
            "pass_through": 1,
            "nested_isolated": 2,
            "adjacent": 2,
        }[case]
        case_checks = {
            "clipping_recipe_inside_existing_stream": shape["pass"],
            "expected_group_count": len(groups) == expected_group_count,
            "direct_chain_stays_in_parent_stream": direct_chain_stays_in_parent_stream,
            "isolated_chain_is_inside_group": case != "isolated"
            or len(containing_groups) == 1,
            "pass_through_chain_is_inside_group_and_consumes_input": case
            == "pass_through"
            and len(containing_groups) == 1
            and containing_groups[0]["input_target"] == outer["name"]
            if case == "pass_through" and outer is not None and containing_groups
            else case != "pass_through",
            "nested_chain_is_inside_both_group_boundaries": case != "nested_isolated"
            or len(containing_groups) == 2,
            "adjacent_chain_stays_between_group_boundaries": case != "adjacent"
            or (
                len(containing_groups) == 0
                and len(groups) == 2
                and outer is not None
                and groups[0]["end"] < outer["start"] < groups[1]["start"]
            ),
            "group_proxy_ports_exist": proxy_ports_exist,
            "render_sources_are_internal_terminals": render_sources_are_internal,
            "render_sources_are_attached": render_sources_are_attached,
            "render_inputs_do_not_consume_group_proxy": render_inputs_do_not_consume_group_proxy,
            "ordinary_render_inputs_avoid_group_proxy": ordinary_render_inputs_avoid_group_proxy,
            "parent_render_inputs_use_internal_terminal": parent_render_inputs_use_internal_terminal,
            "pass_through_proxy_targets_first_backdrop_consumer": pass_through_proxy_targets_first_consumer,
            "pass_through_uses_actual_parent_backdrop": pass_through_uses_actual_parent_backdrop,
        }
        case_reports[case] = {
            "status": "PASS" if all(case_checks.values()) else "FAIL",
            "pass": all(case_checks.values()),
            "stats": stats,
            "checks": case_checks,
            "groups": group_shapes,
            "containing_groups": [group["name"] for group in containing_groups],
            "chain": shape,
            "artifact": _artifact(comp_path),
        }

    checks = {
        "all_cases_pass": all(case_report["pass"] for case_report in case_reports.values()),
        "all_cases_keep_fixed_matte_recipe": all(
            case_report["checks"]["clipping_recipe_inside_existing_stream"]
            for case_report in case_reports.values()
        ),
        "all_cases_keep_group_proxy_render_split": all(
            case_report["checks"]["group_proxy_ports_exist"]
            and case_report["checks"]["render_sources_are_internal_terminals"]
            and case_report["checks"]["render_sources_are_attached"]
            and case_report["checks"]["render_inputs_do_not_consume_group_proxy"]
            and case_report["checks"]["ordinary_render_inputs_avoid_group_proxy"]
            and case_report["checks"]["parent_render_inputs_use_internal_terminal"]
            and case_report["checks"]["pass_through_proxy_targets_first_backdrop_consumer"]
            and case_report["checks"]["pass_through_uses_actual_parent_backdrop"]
            for case_report in case_reports.values()
        ),
        "direct_case_has_no_group_boundary": case_reports["direct"]["checks"][
            "direct_chain_stays_in_parent_stream"
        ],
    }
    report: Dict[str, Any] = {
        "schema_version": 1,
        "task": "PARITY-004",
        "item": "P4-05",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "pass": all(checks.values()),
        "recipe": "operator_in_fixed_matte_local_stack",
        "cases": case_reports,
        "checks": checks,
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    report = build(args.output)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
