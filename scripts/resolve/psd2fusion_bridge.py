"""Thin command-line bridge used by the Resolve/Fusion launcher.

The converter remains in :mod:`psd2fusion`; this file only makes the repository
importable when Resolve starts Python from an arbitrary working directory.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from psd2fusion.cli import run  # noqa: E402  (path is prepared above)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="psd2fusion-bridge",
        description="Run the PSD2Fusion converter from Resolve/Fusion.",
    )
    parser.add_argument("psd", help="source PSD file")
    parser.add_argument("--output", required=True, help="output directory")
    parser.add_argument(
        "--force",
        action="store_true",
        help="allow writing into an existing non-empty output directory",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run(args.psd, args.output, args.force)
    except Exception as exc:
        print("psd2fusion: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
