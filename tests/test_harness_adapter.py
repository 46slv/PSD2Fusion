"""Contract checks for the PSD2Fusion ProjectAdapter projection."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from psd2fusion.harness_adapter import PSD2FusionAdapter


class PSD2FusionAdapterTests(unittest.TestCase):
    def _repo(self) -> Path:
        root = Path(self._temporary.name)
        (root / ".control" / "evidence" / "PARITY-004" / "fixture").mkdir(parents=True)
        (root / "scripts").mkdir()
        (root / ".control" / "current.json").write_text(
            json.dumps(
                {
                    "program_id": "PSD2FUSION-COMPOSITING-PARITY",
                    "status": "active",
                    "active_task_id": "PARITY-004",
                    "tasks": [
                        {
                            "id": "PARITY-004",
                            "status": "in_progress",
                            "verification": "pending",
                        }
                    ],
                    "reference_case": {
                        "psd_path_windows": "D:\\Downloads\\a.psd",
                        "reference_png_path_windows": "D:\\Downloads\\ref.png",
                    },
                }
            ),
            encoding="utf-8",
        )
        (root / ".control" / "CURRENT_GOAL.md").write_text("Goal: PARITY-004\n", encoding="utf-8")
        (root / ".control" / "PARITY-004_TODO.md").write_text("Next: P4-09\n", encoding="utf-8")
        (root / ".control" / "evidence" / "PARITY-004" / "fixture" / "summary.json").write_text(
            json.dumps({"status": "BLOCKED", "summary": "bounded fixture evidence"}),
            encoding="utf-8",
        )
        (root / "scripts" / "check.ps1").write_text("check\n", encoding="utf-8")
        (root / "scripts" / "remote_completion_guard.ps1").write_text("guard\n", encoding="utf-8")
        (root / "scripts" / "remote_completion_guard.py").write_text("guard\n", encoding="utf-8")
        return root

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def test_projection_is_bounded_and_does_not_leak_repo_root(self) -> None:
        root = self._repo()
        adapter = PSD2FusionAdapter()
        value = adapter.load_goal_state(root)
        encoded = json.dumps(value, ensure_ascii=False)
        self.assertNotIn(str(root), encoded)
        self.assertEqual(value["goal"]["active_task_id"], "PARITY-004")
        self.assertEqual(value["state"]["active_task"]["id"], "PARITY-004")
        self.assertTrue(value["state"]["latest_evidence"])

    def test_transition_marker_is_idempotent_and_state_stays_unchanged(self) -> None:
        root = self._repo()
        adapter = PSD2FusionAdapter()
        before = (root / ".control" / "current.json").read_bytes()
        transition = {
            "schema": "psd2fusion-parity-004.harness-transition.v1",
            "status": "RECORDED",
            "run_id": "run-001",
            "task_id": "P4-HARNESS-001",
            "goal_item_id": "PARITY-004",
            "completion_scope": "TRANCHE",
            "verifier_verdict": "PASS",
            "changed_paths": ["psd2fusion/harness_adapter.py"],
        }
        first = adapter.apply_canonical_transition(root, transition)
        second = adapter.apply_canonical_transition(root, transition)
        self.assertEqual(first, second)
        self.assertEqual(before, (root / ".control" / "current.json").read_bytes())
        self.assertTrue((root / first["marker_relpath"]).is_file())

    def test_latest_runner_feedback_is_bounded_and_points_to_current_artifact(self) -> None:
        root = self._repo()
        harness = root / ".control" / "evidence" / "PARITY-004" / "harness"
        harness.mkdir(parents=True)
        run_id = "p4-harness-test-001"
        (harness / "current.json").write_text(
            json.dumps({"run_id": run_id, "status": "TEST_FAILED", "phase": "RUNNER_TESTS"}),
            encoding="utf-8",
        )
        (harness / run_id).mkdir()
        (harness / run_id / "runner-tests.json").write_text(
            json.dumps(
                {
                    "status": "FAIL",
                    "failed": 1,
                    "passed": 0,
                    "results": [{"command": "python -m unittest", "status": "FAIL", "exit_code": 1}],
                }
            ),
            encoding="utf-8",
        )

        value = PSD2FusionAdapter().load_goal_state(root)
        feedback = value["state"]["latest_runner_feedback"]
        self.assertEqual("FAIL", feedback["runner_status"])
        self.assertEqual(
            ".control/evidence/PARITY-004/harness/p4-harness-test-001/runner-tests.json",
            feedback["runner_tests_path"],
        )
        self.assertEqual("FAIL", feedback["results"][0]["status"])
        self.assertNotIn(str(root), json.dumps(feedback, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
