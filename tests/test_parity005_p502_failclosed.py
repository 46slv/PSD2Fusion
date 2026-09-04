"""PARITY-005 P5-02: strict fail-open detector for the clbl=false path.

Stage S0 / Axis C. Records S-FAILOPEN debt: strict EvaluationPlan marks the
clbl=false span "rejected", but Fusion lowering still emits the legacy
FIRST_USABLE approximate graph. This test PASSES while documenting the debt;
P5-19 must replace it with a fail-closed assertion (raise / explicit
bake-reject marker, no silent fallback).
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


class FailOpenDetectorTests(unittest.TestCase):
    def test_strict_evaluation_rejects(self):
        plan = evaluate_document(_doc(), policy="strict")
        span = [d for d in plan.decisions if d.operation == "clipping_span"]
        self.assertEqual(1, len(span))
        self.assertEqual("rejected", span[0].status)
        self.assertIn("clbl=false", span[0].reason)

    def test_strict_lowering_currently_emits_labelled_fallback(self):
        # S-FAILOPEN debt record: strict "rejected" still emits an editable
        # approximate graph with an explicit comment label. This is NOT parity
        # proof. P5-19 must make strict fail closed; then this test is replaced.
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "fix.comp"
            try:
                compile_comp(_doc(), str(out))
            except ValueError:
                return  # fail-closed via reject is acceptable
            text = out.read_text(encoding="utf-8")
            self.assertIn("PSD clipped layer fallback (clbl=false)", text)
            plan = evaluate_document(_doc(), policy="strict")
            self.assertTrue(
                any(dd.status == "rejected" for dd in plan.decisions),
                "emitted fallback must coincide with a strict rejected decision",
            )


if __name__ == "__main__":
    unittest.main()
