"""Optional Resolve adapter boundary; never imported by offline conversion."""
from typing import Any, Dict

def import_fusion_comp(resolve_object: Any, timeline_item: Any, comp_path: str) -> Dict[str, Any]:
    """Call documented TimelineItem.ImportFusionComp and return host evidence."""
    if not hasattr(timeline_item, "ImportFusionComp"):
        raise RuntimeError("Resolve TimelineItem.ImportFusionComp is unavailable")
    result = timeline_item.ImportFusionComp(comp_path)
    return {"method": "TimelineItem.ImportFusionComp", "path": comp_path, "result": bool(result), "host": str(resolve_object)}
