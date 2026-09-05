"""Group-local Flow layout: independent layout contexts per GroupOperator."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Sequence

from psd2fusion.fusion_comp import compile_comp
from psd2fusion.semantic import SemanticDocument, SemanticLayer
from scripts.parity.p4_05 import fixture_documents
from scripts.validate_clipping_subtrees import parse_tools

SOURCE_HASH = "grouplayo" + "0" * 52


def _leaf(layer_id: str, name: str) -> SemanticLayer:
    return SemanticLayer(id=layer_id, name=name, asset_path="assets/%s.png" % layer_id)


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


def _compile(doc: SemanticDocument, path: Path) -> None:
    compile_comp(doc, str(path))


def _tools(comp: Path) -> List[Dict]:
    return parse_tools(comp)


def _groups(tools: List[Dict]) -> List[Dict]:
    return [t for t in tools if t["type"] == "GroupOperator"]


def _containing_group(tools: List[Dict], tool: Dict) -> Dict | None:
    containers = [g for g in _groups(tools) if g["start"] < tool["start"] and tool["end"] < g["end"]]
    if not containers:
        return None
    return max(containers, key=lambda g: g["start"])


def _flow_level_tools(tools: List[Dict], group: Dict | None) -> List[Dict]:
    """Tools that live directly in one Flow viewport.

    Root uses group=None. A group level includes its direct child tools and
    nested GroupOperator nodes themselves (they occupy a Flow slot), but not
    tools inside deeper groups (separate viewport).
    """
    level = []
    for tool in tools:
        if group is None:
            if _containing_group(tools, tool) is None:
                level.append(tool)
            continue
        if not (tool["start"] > group["start"] and tool["end"] < group["end"]):
            continue
        if tool["name"] == group["name"]:
            continue
        parent = _containing_group(tools, tool)
        if parent is not None and parent["name"] == group["name"]:
            level.append(tool)
            continue
        if tool["type"] == "GroupOperator" and parent is not None and parent["name"] == group["name"]:
            level.append(tool)
    # parse_tools is already file order; keep it for monotonicity checks.
    return level


def _xs(tools: List[Dict]) -> List[float]:
    return [t["position"][0] for t in tools if t["position"] is not None]


def _gaps(values: Sequence[float]) -> List[float]:
    ordered = sorted(values)
    return [b - a for a, b in zip(ordered, ordered[1:])]


def _nearest_gaps(values: Sequence[float]) -> List[float]:
    ordered = sorted(values)
    gaps = []
    for index, value in enumerate(ordered):
        candidates = []
        if index > 0:
            candidates.append(value - ordered[index - 1])
        if index + 1 < len(ordered):
            candidates.append(ordered[index + 1] - value)
        if candidates:
            gaps.append(min(candidates))
    return gaps


class GroupLocalLayoutTests(unittest.TestCase):
    def test_root_flow_compactness(self) -> None:
        docs = fixture_documents()
        with tempfile.TemporaryDirectory() as directory:
            comp = Path(directory) / "root.comp"
            _compile(docs["adjacent"], comp)
            tools = _tools(comp)
        level = _flow_level_tools(tools, None)
        xs = _xs(level)
        self.assertGreaterEqual(len(level), 5)
        self.assertEqual(min(xs), -220.0)
        gaps = _gaps(xs)
        self.assertLessEqual(max(gaps), 400.0 + 1e-6)
        width = max(xs) - min(xs)
        self.assertLessEqual(width, len(level) * 180.0 + 500.0)

    def test_isolated_group_internal_compactness(self) -> None:
        docs = fixture_documents()
        with tempfile.TemporaryDirectory() as directory:
            comp = Path(directory) / "iso.comp"
            _compile(docs["isolated"], comp)
            tools = _tools(comp)
        groups = _groups(tools)
        self.assertEqual(1, len(groups))
        level = _flow_level_tools(tools, groups[0])
        inner = [t for t in level if t["type"] != "GroupOperator"]
        xs = _xs(inner)
        ys = [t["position"][1] for t in inner if t["position"] is not None]
        self.assertEqual(min(xs), 180.0)
        self.assertLessEqual(max(_gaps(xs)), 180.0 + 1e-6)
        self.assertLessEqual(max(xs) - min(xs), len(inner) * 180.0 + 200.0)
        self.assertLessEqual(max(ys) - min(ys), 1000.0)
        self.assertLessEqual(max(_nearest_gaps(xs)), 180.0 + 1e-6)

    def test_pass_through_group_internal_compactness(self) -> None:
        docs = fixture_documents()
        with tempfile.TemporaryDirectory() as directory:
            comp = Path(directory) / "pt.comp"
            _compile(docs["pass_through"], comp)
            tools = _tools(comp)
        groups = _groups(tools)
        self.assertEqual(1, len(groups))
        level = _flow_level_tools(tools, groups[0])
        inner = [t for t in level if t["type"] != "GroupOperator"]
        xs = _xs(inner)
        self.assertEqual(min(xs), 180.0)
        self.assertLessEqual(max(_gaps(xs)), 180.0 + 1e-6)
        self.assertLessEqual(max(xs) - min(xs), len(inner) * 180.0 + 200.0)

    def test_nested_group_internal_compactness(self) -> None:
        docs = fixture_documents()
        with tempfile.TemporaryDirectory() as directory:
            comp = Path(directory) / "nested.comp"
            _compile(docs["nested_isolated"], comp)
            tools = _tools(comp)
        groups = _groups(tools)
        self.assertEqual(2, len(groups))
        outer = max(groups, key=lambda g: g["end"] - g["start"])
        inner_group = min(groups, key=lambda g: g["end"] - g["start"])
        for group in (outer, inner_group):
            level = _flow_level_tools(tools, group)
            xs = _xs(level)
            self.assertEqual(min(xs), 180.0)
            self.assertLessEqual(max(_gaps(xs)), 360.0 + 1e-6)
        inner_level = _flow_level_tools(tools, inner_group)
        inner_tools = [t for t in inner_level if t["type"] != "GroupOperator"]
        self.assertLessEqual(max(_gaps(_xs(inner_tools))), 180.0 + 1e-6)

    def test_layout_cursor_independent_across_groups(self) -> None:
        docs = fixture_documents()
        with tempfile.TemporaryDirectory() as directory:
            comp = Path(directory) / "adj.comp"
            _compile(docs["adjacent"], comp)
            tools = _tools(comp)
        groups = _groups(tools)
        self.assertEqual(2, len(groups))
        mins = []
        for group in groups:
            level = _flow_level_tools(tools, group)
            mins.append(min(_xs(level)))
        # Both groups start from a compact local origin even though the second
        # group is lowered much later in document order (regression: 7960).
        self.assertEqual(mins[0], 180.0)
        self.assertEqual(mins[1], 180.0)
        self.assertLessEqual(abs(mins[1] - mins[0]), 1e-6)

    def test_nested_group_exit_outer_cursor_continues(self) -> None:
        docs = fixture_documents()
        with tempfile.TemporaryDirectory() as directory:
            comp = Path(directory) / "exit.comp"
            _compile(docs["nested_isolated"], comp)
            tools = _tools(comp)
        groups = _groups(tools)
        outer = max(groups, key=lambda g: g["end"] - g["start"])
        nested = min(groups, key=lambda g: g["end"] - g["start"])
        outer_level = _flow_level_tools(tools, outer)
        by_name = {t["name"]: t for t in outer_level}
        self.assertIn(nested["name"], by_name)
        nested_x = by_name[nested["name"]]["position"][0]
        after = [t for t in outer_level if t["position"] is not None and t["position"][0] > nested_x]
        self.assertTrue(after)
        # The next outer tool follows the nested GroupOperator by one Flow
        # slot instead of skipping over the whole nested tool count.
        self.assertLessEqual(min(t["position"][0] for t in after) - nested_x, 360.0 + 1e-6)

        # Root cursor after a group is also independent of the group size.
        leaf_after = SemanticLayer(id="exitafter1", name="after", asset_path="assets/after.png")
        group = _group("exitgrp001", "exit group", [_leaf("exitleaf01", "inside")])
        doc = SemanticDocument(
            source_path="exit.psd", source_sha256=SOURCE_HASH, parser="fixture",
            parser_version="1", width=16, height=16,
            children=[group, leaf_after],
        )
        with tempfile.TemporaryDirectory() as directory:
            second = Path(directory) / "exit2.comp"
            _compile(doc, second)
            tools2 = _tools(second)
        root_level = _flow_level_tools(tools2, None)
        group_tool = [t for t in root_level if t["type"] == "GroupOperator"][0]
        following = [t for t in root_level if t["position"][0] > group_tool["position"][0]]
        self.assertTrue(following)
        self.assertLessEqual(min(t["position"][0] for t in following) - group_tool["position"][0], 3 * 180.0 + 40.0)

    def test_semantic_identity_excluding_positions_and_determinism(self) -> None:
        docs = fixture_documents()
        doc = docs["isolated"]
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "a.comp"
            second = Path(directory) / "b.comp"
            _compile(doc, first)
            _compile(doc, second)
            first_text = first.read_text(encoding="utf-8")
            second_text = second.read_text(encoding="utf-8")
        # Same semantic graph lowers deterministically including layout.
        self.assertEqual(first_text, second_text)
        stripped = re.sub(r"Pos = \{ [^}]+\ \}", "Pos = { STRIPPED }", first_text)
        # Semantic edges survive position stripping: names/connections remain.
        self.assertIn("GroupOperator", stripped)
        self.assertIn("MainOutput1", stripped)
        self.assertIn("PSD Group:", stripped)


if __name__ == "__main__":
    unittest.main()
