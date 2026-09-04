import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from psd2fusion.fusion_comp import FUSION_BLEND_IDS
from scripts.parity.p4_fusion_boundary_fixture import (
    CASES,
    MEMBER_OPACITY,
    MODES,
    SCOPES,
    build,
)


class P4FusionBoundaryFixtureTests(unittest.TestCase):
    def test_builds_eight_host_ready_cases_with_assets_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = build(root)

            self.assertTrue(manifest["pass"])
            self.assertEqual("PASS", manifest["status"])
            self.assertEqual(8, len(manifest["cases"]))
            self.assertEqual(list(CASES), manifest["case_order"])
            self.assertEqual(set(MODES), {case["mode"] for case in manifest["cases"].values()})
            self.assertEqual(set(SCOPES), {case["scope"] for case in manifest["cases"].values()})
            for case in manifest["cases"].values():
                comp = root / case["comp"]["path"]
                self.assertTrue(comp.is_file())
                self.assertEqual(case["comp"]["sha256"], hashlib.sha256(comp.read_bytes()).hexdigest())
                for role, digest in case["asset_hashes"].items():
                    asset = root / manifest["assets"][role]["path"]
                    self.assertEqual(digest, hashlib.sha256(asset.read_bytes()).hexdigest())
                self.assertTrue(case["host_required"])
                self.assertEqual("none", case["pixel_claim"])

    def test_repeat_generation_is_byte_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = build(root)
            first_manifest_bytes = (root / "manifest.json").read_bytes()
            first_files = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

            second = build(root)
            second_manifest_bytes = (root / "manifest.json").read_bytes()
            second_files = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

            self.assertEqual(first["case_order"], second["case_order"])
            self.assertEqual(first_manifest_bytes, second_manifest_bytes)
            self.assertEqual(first_files, second_files)
            self.assertEqual(
                json.loads(first_manifest_bytes), json.loads(second_manifest_bytes)
            )

    def test_all_scopes_reuse_exact_same_fractional_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = build(Path(directory))

        inputs = [case["inputs"] for case in manifest["cases"].values()]
        self.assertTrue(inputs)
        self.assertTrue(all(value == inputs[0] for value in inputs))
        self.assertEqual(manifest["inputs"]["base_alpha"], inputs[0]["base_alpha"])
        self.assertEqual(manifest["inputs"]["member_alpha"], inputs[0]["member_alpha"])
        self.assertEqual(MEMBER_OPACITY, inputs[0]["member_opacity"])
        self.assertNotEqual(0.0, inputs[0]["base_alpha"])
        self.assertNotEqual(1.0, inputs[0]["base_alpha"])
        self.assertNotEqual(0.0, inputs[0]["member_alpha"])
        self.assertNotEqual(1.0, inputs[0]["member_alpha"])
        base_red = inputs[0]["assets"]["base"]["rgba8"][0]
        member_red = inputs[0]["assets"]["member"]["rgba8"][0]
        self.assertGreater(base_red + member_red, 255)
        self.assertGreater(
            base_red
            + member_red
            * inputs[0]["member_alpha"]
            * inputs[0]["member_opacity"],
            base_red
            + (255 - base_red)
            * inputs[0]["member_alpha"]
            * inputs[0]["member_opacity"],
        )

    def test_ordinary_render_inputs_never_consume_group_operator_output(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = build(Path(directory))

        for case in manifest["cases"].values():
            self.assertTrue(case["checks"]["ordinary_render_inputs_avoid_group_proxy"])
            self.assertTrue(case["checks"]["scope_boundary_matches_document"])
            if case["scope"] == "ungrouped":
                self.assertIsNone(case["boundaries"]["group"])
                self.assertEqual(0, case["group_operator_count"])
            else:
                group = case["boundaries"]["group"]
                self.assertIsNotNone(group)
                self.assertIsNotNone(group["proxy_output"])
                self.assertNotEqual(group["operator"], group["internal_terminal"])
                self.assertEqual([], group["group_proxy_consumers"])
                self.assertTrue(group["render_consumers"])

    def test_expected_mode_and_control_placement_is_recorded_and_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = build(Path(directory))

        for case in manifest["cases"].values():
            mode = case["mode"]
            controls = case["expected_controls"]
            observed = case["observed"]
            self.assertEqual(
                'FuID { "%s" }' % FUSION_BLEND_IDS[mode],
                controls["blend_function_apply_mode"],
            )
            self.assertEqual(controls["blend_function_apply_mode"], observed["blend_function"]["apply_mode"])
            self.assertEqual('FuID { "In" }', observed["clip_in"]["operator"])
            self.assertEqual('FuID { "Normal" }', observed["clip_in"]["apply_mode"])
            self.assertEqual("1.000000", observed["clip_in"]["blend"])
            self.assertEqual('FuID { "Normal" }', observed["clip_stack"]["apply_mode"])
            if mode == "Linear Dodge":
                # Late-clamp Linear Dodge carries member opacity in the
                # float32 attenuate Gain; the local stack then replaces.
                self.assertEqual("1.000000", observed["clip_stack"]["blend"])
                self.assertEqual("%.6f" % MEMBER_OPACITY, observed["member_attenuate"]["gain"])
                self.assertEqual("0", observed["member_attenuate"]["process_alpha"])
                self.assertEqual("%.6f" % MEMBER_OPACITY, controls["member_attenuate_gain"])
            else:
                self.assertEqual("%.6f" % MEMBER_OPACITY, observed["clip_stack"]["blend"])
                self.assertIsNone(observed["member_attenuate"])
                self.assertIsNone(controls["member_attenuate_gain"])
            self.assertEqual("0", observed["clip_stack"]["process_alpha"])
            self.assertEqual('FuID { "Normal" }', observed["parent_merge"]["apply_mode"])
            self.assertEqual("1.000000", observed["parent_merge"]["blend"])
            self.assertEqual(4, len(observed["channel_boolean"]))
            self.assertTrue(case["checks"]["blend_function_has_member_mode"])
            self.assertTrue(case["checks"]["clip_stack_has_member_opacity_and_fixed_alpha"])
            self.assertTrue(case["checks"]["one_parent_merge_after_clip_stack"])


if __name__ == "__main__":
    unittest.main()
