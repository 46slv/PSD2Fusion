"""Command-line entry point for the first usable PSD2Fusion slice."""

import argparse
import json
import os
import sys
from typing import Optional, Sequence

from .assets import materialize_assets
from .fusion_comp import compile_comp
from .manifest import write_manifest
from .parse_psd import parse_psd
from .semantic import walk_layers


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="psd2fusion",
        description="Convert ordinary PSD layers, groups, and clipping chains to a Fusion .comp",
    )
    parser.add_argument("psd", help="source PSD file")
    parser.add_argument(
        "-o",
        "--output",
        help="output directory (default: <PSD stem>_fusion beside the source)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="allow writing into an existing non-empty output directory",
    )
    return parser


def _output_dir(source: str, requested: Optional[str]) -> str:
    if requested:
        return os.path.abspath(requested)
    stem = os.path.splitext(os.path.basename(source))[0]
    return os.path.join(os.path.dirname(os.path.abspath(source)), stem + "_fusion")


def _prepare_output(path: str, force: bool) -> None:
    if not os.path.exists(path):
        os.makedirs(path)
        return
    if not os.path.isdir(path):
        raise RuntimeError("Output path is not a directory: %s" % path)
    try:
        nonempty = bool(os.listdir(path))
    except OSError as exc:
        raise RuntimeError("Cannot inspect output directory: %s" % exc)
    if nonempty and not force:
        raise RuntimeError(
            "Output directory is not empty: %s (use --force to replace generated files)"
            % path
        )
    os.makedirs(path, exist_ok=True)


def run(source: str, output: Optional[str] = None, force: bool = False) -> dict:
    source = os.path.abspath(source)
    if not os.path.isfile(source):
        raise FileNotFoundError(source)
    output_dir = _output_dir(source, output)
    _prepare_output(output_dir, force)

    document = parse_psd(source)
    try:
        from psd_tools import PSDImage
    except ImportError as exc:
        raise RuntimeError(
            "psd-tools is required; run `python -m pip install -e .`"
        ) from exc
    psd_obj = PSDImage.open(source)
    assets = materialize_assets(document, psd_obj, output_dir)

    missing = [
        layer.name
        for layer in walk_layers(document.children)
        if layer.effective_visible and not layer.is_group and not layer.asset_path
    ]
    if missing:
        raise RuntimeError(
            "Visible PSD layers could not be rasterized: %s" % ", ".join(missing)
        )

    comp_path = os.path.join(output_dir, "PSD2Fusion.comp")
    graph = compile_comp(document, comp_path)
    manifest_path = write_manifest(document, output_dir, assets, graph)
    return {
        "source": source,
        "output": output_dir,
        "composition": comp_path,
        "manifest": manifest_path,
        "layers": sum(1 for layer in walk_layers(document.children)),
        "assets": len(assets),
        "warnings": len(document.warnings)
        + sum(len(layer.warnings) for layer in walk_layers(document.children)),
        "graph": graph,
    }


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
