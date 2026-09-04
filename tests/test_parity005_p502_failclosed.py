"""PARITY-005 P5-19: strict fail-closed test for the clbl=false path.

Stage S5 / Coordinator. S4 decision authority is REJECT: strict lowering
must raise on an explicit clbl=false span instead of emitting the legacy
approximate graph. Compatibility policy keeps the explicitly labelled
H2-characterization fallback (never parity proof).
"""
import tempfile
import unittest
from pathlib import Path

from psd2fusion.evaluation import evaluate_document
from psd2fusion.fusion_comp import compile_comp
from psd2fusion.semantic import ClippingChain, SemanticDocument, SemanticLayer


def _doc():
    base = SemanticLayer(
        id="base000001",
        name="base",
        asset_path="assets/base.png",
        blend="Normal",
        clipping_members=["mem00000001"],
    )
    mem = SemanticLayer(
        id="mem00000001",
        name="mem",
        asset_path="assets/mem.png",
        blend="Multiply",
        opacity=0.5,
        clipping_base_id="base000001",
    )
    return SemanticDocument(
        source_path="fixture.psd",
        source_sha256="0" * 64,
        parser="fixture",
        parser_version="1",
        width=4,
        height=4,
        children=[base, mem],
        clipping_chains=[
            ClippingChain(
                base_id=base.id,
                member_ids=[mem.id],
                blend_clipped_as_group=False,
                blend_clipped_as_group_provenance="explicit_psd_clbl",
            )
        ],
    )


class FailClosedTests(unittest.TestCase):
    def test_strict_evaluation_rejects(self):
        plan = evaluate_document(_doc(), policy="strict")
        span = [d for d in plan.decisions if d.operation == "clipping_span"]
        self.assertEqual(1, len(span))
        self.assertEqual("rejected", span[0].status)
        self.assertIn("clbl=false", span[0].reason)

    def test_strict_lowering_raises_no_graph(self):
        # S-FAILOPEN repair: strict must not emit the legacy fallback.
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "fix.comp"
            with self.assertRaisesRegex(ValueError, "clbl=false"):
                compile_comp(_doc(), str(out))
            self.assertFalse(out.exists(), "strict must write no .comp on reject")

    def test_compatibility_lowering_labels_fallback(self):
        # Compatibility keeps the explicitly labelled fallback (not parity).
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "fix.comp"
            compile_comp(_doc(), str(out), "compatibility")
            text = out.read_text(encoding="utf-8")
            self.assertIn("PSD clipped layer fallback (clbl=false)", text)
            plan = evaluate_document(_doc(), policy="strict")
            self.assertTrue(
                any(dd.status == "rejected" for dd in plan.decisions),
                "emitted fallback must coincide with a strict rejected decision",
            )

    def test_invalid_policy_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "policy"):
                compile_comp(_doc(), str(Path(d) / "fix.comp"), "silent")


if __name__ == "__main__":
    unittest.main()
