import json
import os
from typing import Any, Dict
from .semantic import SemanticDocument

def write_manifest(doc: SemanticDocument, output_dir: str, assets: Dict[str, Dict[str, Any]], graph: Dict[str, str], evaluation=None):
    data = doc.to_dict()
    data["artifacts"] = {"composition": "PSD2Fusion.comp", "assets": assets}
    data["graph"] = graph
    if evaluation is not None:
        data["evaluation"] = evaluation.to_dict() if hasattr(evaluation, "to_dict") else evaluation
    target = os.path.join(output_dir, "manifest.json")
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    return target
