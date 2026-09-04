"""PARITY-005 P5-04: expected-RGBA matrix fixture x hypothesis (offline).

Reads scripts/parity/p5_03_oracles.py only. No psd2fusion production import
(oracle-independence ban). Deterministic float semantics at Python float
precision; rounds only for artifact stability (6dp).
Usage:
  python scripts/parity/p5_04_matrix.py --out <path> [--head <hex>]
  python scripts/parity/p5_04_matrix.py --check [--eps 0.01]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import p5_03_oracles as O  # noqa: E402  (local oracle only)

SCHEMA = "psd2fusion-parity-005-p504-matrix.v1"
ROUND_DP = 6
HIDS = ["H1", "H2", "H3", "H4", "H5"]


def _m(rgba, mode, op):
    return (tuple(float(v) for v in rgba), mode, float(op))


FIXTURES = {
    "p503-01": {
        "backdrop": (0.2, 0.4, 0.6, 1.0),
        "base": (0.8, 0.5, 0.2, 1.0),
        "members": [_m((0.3, 0.7, 0.4, 0.9), "Multiply", 1.0)],
        "base_mode": "Normal",
        "base_opacity": 1.0,
    },
    "p503-02": {
        "backdrop": (0.2, 0.4, 0.6, 0.5),
        "base": (0.8, 0.5, 0.2, 1.0),
        "members": [_m((0.3, 0.7, 0.4, 0.9), "Multiply", 1.0)],
        "base_mode": "Normal",
        "base_opacity": 1.0,
    },
    "p503-03": {
        "backdrop": (0.2, 0.4, 0.6, 1.0),
        "base": (0.8, 0.5, 0.2, 1.0),
        "members": [_m((0.3, 0.7, 0.4, 0.9), "Multiply", 1.0)],
        "base_mode": "Multiply",
        "base_opacity": 1.0,
    },
    "p503-04": {
        "backdrop": (0.2, 0.4, 0.6, 1.0),
        "base": (0.8, 0.5, 0.2, 1.0),
        "members": [_m((0.3, 0.7, 0.4, 0.9), "Multiply", 1.0)],
        "base_mode": "Normal",
        "base_opacity": 0.5,
    },
    "p503-05": {
        "backdrop": (0.2, 0.4, 0.6, 1.0),
        "base": (0.8, 0.5, 0.2, 1.0),
        "members": [
            _m((0.9, 0.2, 0.3, 0.8), "Multiply", 1.0),
            _m((0.2, 0.8, 0.9, 0.6), "Screen", 1.0),
        ],
        "base_mode": "Normal",
        "base_opacity": 1.0,
    },
    "p503-05R": {
        "backdrop": (0.2, 0.4, 0.6, 1.0),
        "base": (0.8, 0.5, 0.2, 1.0),
        "members": [
            _m((0.2, 0.8, 0.9, 0.6), "Screen", 1.0),
            _m((0.9, 0.2, 0.3, 0.8), "Multiply", 1.0),
        ],
        "base_mode": "Normal",
        "base_opacity": 1.0,
    },
    "p503-06": {
        "backdrop": (0.2, 0.4, 0.6, 1.0),
        "base": (0.8, 0.5, 0.2, 0.4),
        "members": [_m((0.3, 0.7, 0.4, 0.9), "Multiply", 1.0)],
        "base_mode": "Normal",
        "base_opacity": 1.0,
    },
    "p503-07": {
        "backdrop": (0.2, 0.4, 0.6, 1.0),
        "base": (0.8, 0.5, 0.2, 0.0),
        "members": [_m((0.3, 0.7, 0.4, 0.9), "Multiply", 1.0)],
        "base_mode": "Normal",
        "base_opacity": 1.0,
    },
}


def _canon_fixture(f):
    ms = [{"rgba": list(m[0]), "mode": m[1], "opacity": m[2]} for m in f["members"]]
    return {
        "backdrop": list(f["backdrop"]),
        "base": list(f["base"]),
        "members": ms,
        "base_mode": f["base_mode"],
        "base_opacity": f["base_opacity"],
    }


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _assert_no_production_leak():
    # Source-scan only: this file and the oracle must never contain a
    # production import statement. A sys.modules scan is intentionally NOT
    # used here because the full test-suite process legitimately imports
    # psd2fusion for unrelated tests in the same interpreter.
    for path in (__file__, os.path.join(_HERE, "p5_03_oracles.py")):
        with open(path, "r", encoding="utf-8") as h:
            for line in h.read().splitlines():
                stripped = line.strip()
                if stripped.startswith("import psd2fusion") or stripped.startswith(
                    "from psd2fusion"
                ):
                    raise AssertionError(
                        "production import in %s: %s"
                        % (os.path.basename(path), stripped)
                    )


def build_matrix():
    _assert_no_production_leak()
    if not O.determinism_guard({k: dict(v) for k, v in FIXTURES.items()}, repeats=3):
        raise AssertionError("determinism_guard failed")
    with open(os.path.join(_HERE, "p5_03_oracles.py"), "rb") as h:
        oracle_sha = _sha256_bytes(h.read())
    fixtures, preds = {}, {}
    for fid in sorted(FIXTURES):
        f = FIXTURES[fid]
        canon = _canon_fixture(f)
        fixtures[fid] = dict(
            canon, input_sha256=_sha256_bytes(repr(canon).encode())
        )
        preds[fid] = {}
        for hid in HIDS:
            r = O.run_oracle(
                hid,
                backdrop=f["backdrop"],
                base=f["base"],
                members=list(f["members"]),
                base_mode=f["base_mode"],
                base_opacity=f["base_opacity"],
            )
            preds[fid][hid] = [round(float(v), ROUND_DP) for v in r]
    _assert_no_production_leak()
    return {
        "schema": SCHEMA,
        "oracle": {
            "file": "scripts/parity/p5_03_oracles.py",
            "sha256": oracle_sha,
            "modes": list(O.MODES),
            "hypotheses": list(HIDS),
        },
        "fixture_ids": sorted(FIXTURES),
        "fixtures": fixtures,
        "predictions": preds,
        "rounding_dp": ROUND_DP,
        "determinism": {"guard": True, "repeats": 3, "tolerance": 0.0},
        "production_imports": "none",
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--head", default=None)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--eps", type=float, default=0.01)
    a = ap.parse_args(argv)
    doc = build_matrix()
    if a.check:
        import itertools

        live = list(HIDS)
        missing = []
        for x, y in itertools.combinations(live, 2):
            best = max(
                max(
                    abs(r - s)
                    for r, s in zip(doc["predictions"][f][x], doc["predictions"][f][y])
                )
                for f in doc["fixture_ids"]
            )
            if best < a.eps:
                missing.append((x, y, best))
        if missing:
            print("S-NONDISCRIMINATING pairs (eps=%g): %r" % (a.eps, missing))
            return 10
        print(
            "P5-04 check OK: %d fixtures x %d H, guard True, all pairs >= %g"
            % (len(doc["fixture_ids"]), len(HIDS), a.eps)
        )
        return 0
    doc.update(
        {
            "task": "PARITY-005",
            "queue_id": "P5-04",
            "branch": "codex/parity-005",
            "candidate_HEAD": a.head or "unrecorded",
            "discrimination_eps": a.eps,
        }
    )
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8") as h:
            h.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
