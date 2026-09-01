"""Thin command-line bridge used by the Resolve/Fusion launcher.

The converter remains in :mod:`psd2fusion`; this file only makes the repository
importable when Resolve starts Python from an arbitrary working directory.

The ``--request`` form is intentionally small: the Resolve Lua script passes
only an ASCII temporary-file path through the Windows shell and the actual PSD
and output paths travel as UTF-8 JSON.  This keeps Unicode Windows paths out of
``cmd.exe`` argument parsing while preserving the direct positional CLI for
manual use and diagnostics.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from psd2fusion.cli import run  # noqa: E402  (path is prepared above)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="psd2fusion-bridge",
        description="Run the PSD2Fusion converter from Resolve/Fusion.",
    )
    parser.add_argument("psd", nargs="?", help="source PSD file")
    parser.add_argument("--output", help="output directory")
    parser.add_argument(
        "--request",
        help="UTF-8 JSON request file containing psd, output, and optional force",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="allow writing into an existing non-empty output directory",
    )
    return parser


def _load_request(request_path: str) -> Tuple[str, str, bool]:
    """Read and validate the UTF-8 request used by the Resolve launcher."""

    with open(request_path, "r", encoding="utf-8") as handle:
        request: Any = json.load(handle)
    if not isinstance(request, dict):
        raise ValueError("bridge request must be a JSON object")

    psd = request.get("psd")
    output = request.get("output")
    force = request.get("force", False)
    if not isinstance(psd, str) or not psd:
        raise ValueError("bridge request field 'psd' must be a non-empty string")
    if not isinstance(output, str) or not output:
        raise ValueError("bridge request field 'output' must be a non-empty string")
    if not isinstance(force, bool):
        raise ValueError("bridge request field 'force' must be a boolean")
    return psd, output, force


def _arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> Tuple[str, str, bool]:
    """Resolve either the direct CLI arguments or the UTF-8 request form."""

    if args.request:
        if args.psd is not None or args.output is not None:
            parser.error("--request cannot be combined with a PSD positional argument or --output")
        return _load_request(args.request)
    if args.psd is None or args.output is None:
        parser.error("a PSD positional argument and --output are required unless --request is used")
    return args.psd, args.output, bool(args.force)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        psd, output, force = _arguments(parser, args)
    except Exception as exc:
        print("PSD2FUSION_PHASE=bridge_request", file=sys.stderr)
        print("psd2fusion: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 2

    print("PSD2FUSION_PHASE=converter_start", file=sys.stderr)
    try:
        result = run(psd, output, force)
    except Exception as exc:
        print("PSD2FUSION_PHASE=converter_failed", file=sys.stderr)
        print("psd2fusion: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 2
    print("PSD2FUSION_PHASE=converter_complete", file=sys.stderr)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
