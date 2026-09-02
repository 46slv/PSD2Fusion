import unittest
from unittest.mock import patch
from scripts.remote_completion_guard import evaluate, fetch_remote_branch

class RemoteGuardTests(unittest.TestCase):
    def base(self):
        return {"checks": {k: True for k in ("remote_branch_exists","candidate_reachable","state_reachable","state_matches","remote_expectations")}}
    def test_missing_branch_fails(self):
        s=self.base(); s["checks"]["remote_branch_exists"]=False; self.assertEqual(evaluate(s)["status"],"FAIL")
    def test_missing_candidate_fails(self):
        s=self.base(); s["checks"]["candidate_reachable"]=False; self.assertEqual(evaluate(s)["status"],"FAIL")
    def test_stale_remote_state_fails(self):
        s=self.base(); s["checks"]["state_matches"]=False; self.assertEqual(evaluate(s)["status"],"FAIL")
    def test_matching_remote_passes(self): self.assertEqual(evaluate(self.base())["status"],"PASS")
    def test_unavailable_is_blocked(self): self.assertEqual(evaluate({"blocked":True})["status"],"BLOCKED")

    def test_explicit_branch_fetch_works_without_tracking_ref(self):
        # A main-only clone has no origin/<task-branch> tracking ref.  The
        # guard must issue an explicit source:temporary-ref fetch instead of
        # relying on that absent local ref.
        with patch("scripts.remote_completion_guard.run", return_value="") as mocked:
            ref = fetch_remote_branch("origin", "codex/parity-002", ".")
        self.assertTrue(ref.startswith("refs/guard/"))
        args = mocked.call_args.args[0]
        self.assertEqual(args[:4], ["git", "fetch", "--no-tags", "origin"])
        self.assertIn("refs/heads/codex/parity-002:" + ref, args)

if __name__ == '__main__': unittest.main()
