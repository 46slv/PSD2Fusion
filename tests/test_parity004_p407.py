import unittest

from scripts.parity.p4_07 import representative_indices


class P407RepresentativeSelectionTests(unittest.TestCase):
    def test_selection_spans_size_and_nesting_depth_extremes(self):
        rows = [
            {"chain": 1, "member_count": 3, "depth": 3},
            {"chain": 2, "member_count": 6, "depth": 4},
            {"chain": 3, "member_count": 1, "depth": 2},
            {"chain": 4, "member_count": 2, "depth": 4},
        ]
        selected = representative_indices(rows)
        selected_rows = [row for row in rows if row["chain"] in selected]
        self.assertGreaterEqual(len(selected_rows), 2)
        self.assertEqual({2, 3}, set(selected))
        self.assertEqual({1, 6}, {row["member_count"] for row in selected_rows})
        self.assertEqual({2, 4}, {row["depth"] for row in selected_rows})


if __name__ == "__main__":
    unittest.main()
