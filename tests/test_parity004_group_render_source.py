import tempfile
import unittest
from pathlib import Path

from psd2fusion.fusion_comp import compile_comp
from scripts.parity.p4_05 import fixture_documents
from scripts.validate_clipping_subtrees import parse_tools


class GroupRenderSourceTests(unittest.TestCase):
    def _compile(self, case: str):
        document = fixture_documents()[case]
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / f"{case}.comp"
        compile_comp(document, str(path))
        return path, parse_tools(path)

    def test_ordinary_merge_inputs_never_consume_group_operator_outputs(self):
        for case in ("isolated", "pass_through", "nested_isolated", "adjacent"):
            with self.subTest(case=case):
                _, tools = self._compile(case)
                groups = {tool["name"] for tool in tools if tool["type"] == "GroupOperator"}
                self.assertTrue(groups)
                for tool in tools:
                    if tool["type"] != "Merge":
                        continue
                    self.assertNotIn(tool.get("background"), groups, tool["name"])
                    self.assertNotIn(tool.get("foreground"), groups, tool["name"])

    def test_nested_isolated_parent_consumers_reference_internal_terminals(self):
        _, tools = self._compile("nested_isolated")
        groups = {tool["name"] for tool in tools if tool["type"] == "GroupOperator"}
        merge_foregrounds = {
            tool.get("foreground")
            for tool in tools
            if tool["type"] == "Merge" and tool.get("foreground")
        }
        self.assertFalse(groups & merge_foregrounds)
        # At least one parent-level Merge must consume a tool whose serialized
        # definition is inside a GroupOperator.  That is the canonical Fusion
        # save/readback topology: direct internal terminal, UI proxy retained.
        group_ranges = [
            (tool["start"], tool["end"])
            for tool in tools
            if tool["type"] == "GroupOperator"
        ]
        internal_names = {
            tool["name"]
            for tool in tools
            if tool["type"] != "GroupOperator"
            and any(start < tool["start"] < end for start, end in group_ranges)
        }
        self.assertTrue(merge_foregrounds & internal_names)

    def test_pass_through_proxy_input_targets_a_real_backdrop_consumer(self):
        _, tools = self._compile("pass_through")
        groups = [tool for tool in tools if tool["type"] == "GroupOperator"]
        self.assertEqual(1, len(groups))
        group = groups[0]
        self.assertIsNotNone(group.get("input_target"))
        targets = [tool for tool in tools if tool["name"] == group["input_target"]]
        self.assertEqual(1, len(targets))
        target = targets[0]
        self.assertEqual("Merge", target["type"])
        self.assertTrue(target.get("background"))
        self.assertNotEqual(group["name"], target.get("background"))

    def test_group_proxy_ports_remain_serialized_for_flow_readability(self):
        for case in ("isolated", "pass_through", "nested_isolated"):
            with self.subTest(case=case):
                path, tools = self._compile(case)
                text = path.read_text(encoding="utf-8")
                groups = [tool for tool in tools if tool["type"] == "GroupOperator"]
                self.assertTrue(groups)
                self.assertIn("InstanceOutput", text)
                if case == "pass_through":
                    self.assertIn("InstanceInput", text)


if __name__ == "__main__":
    unittest.main()
