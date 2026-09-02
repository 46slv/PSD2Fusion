import unittest
from psd2fusion.semantic import SemanticDocument, SemanticLayer, SemanticGroup, ClippingChain
from psd2fusion.evaluation import evaluate_document

class EvaluationTests(unittest.TestCase):
    def doc(self, layers, chains=None):
        return SemanticDocument("fixture.psd", "abc", "fixture", "1", 2, 2, children=layers, clipping_chains=chains or [])

    def test_shapes_and_provenance(self):
        base = SemanticLayer("b", "Base", raw_blend="norm", blend="Normal", opacity=.5)
        member = SemanticLayer("m", "Member", raw_blend="mul ", blend="Multiply", clipping_base_id="b")
        group = SemanticGroup("g", "G", pass_through=True, children=[base, member])
        plan = evaluate_document(self.doc([group], [ClippingChain("b", ["m"])]) )
        self.assertEqual(plan.nodes[0].kind, "pass_through")
        self.assertEqual(plan.clipping_spans[0]["member_ids"], ["m"])
        self.assertEqual(plan.nodes[1].provenance["raw_blend"], "norm")
        self.assertIn("m", [n.provenance["source_id"] for n in plan.nodes])

    def test_strict_unknown_rejects_without_normal(self):
        layer = SemanticLayer("x", "X", raw_blend="zzzz", blend="Zzz")
        plan = evaluate_document(self.doc([layer]), "strict")
        self.assertEqual(plan.decisions[0].status, "rejected")
        self.assertEqual(plan.nodes[0].blend, "Zzz")
        self.assertNotEqual(plan.nodes[0].blend, "Normal")

    def test_compatibility_is_explicit(self):
        layer = SemanticLayer("x", "X", raw_blend="zzzz", blend="Zzz", unsupported=["pixel-mask"])
        plan = evaluate_document(self.doc([layer]), "compatibility")
        self.assertEqual(plan.decisions[0].status, "verified_bake")
        self.assertEqual(plan.policy, "compatibility")

    def test_transparent_subtree_and_clbl_false(self):
        group = SemanticGroup("g", "G", effective_visible=False)
        plan = evaluate_document(self.doc([group], [ClippingChain("b", ["m"], False, "explicit_psd_clbl")]))
        self.assertEqual(plan.nodes[0].kind, "transparent_subtree")
        self.assertEqual(plan.decisions[-1].status, "rejected")

if __name__ == "__main__": unittest.main()
