import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_control_state.py"
SPEC = importlib.util.spec_from_file_location("validate_control_state", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ControlStateTests(unittest.TestCase):
    def test_committed_state_contract_is_valid(self) -> None:
        self.assertEqual([], MODULE.validate(ROOT))


if __name__ == "__main__":
    unittest.main()
