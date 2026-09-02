import unittest
from scripts.remote_completion_guard import evaluate

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

if __name__ == '__main__': unittest.main()
