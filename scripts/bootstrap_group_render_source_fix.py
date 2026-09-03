"""Apply the Sol-confirmed GroupOperator proxy/render-source separation.

This is a bounded bootstrap for the dedicated task branch.  The generic/local
harness still owns actual-Fusion proof and any subsequent repair cycle.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "psd2fusion" / "fusion_comp.py"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError("non-unique/missing GroupOperator bootstrap anchor")
    return text.replace(old, new)


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''        self._external_input_target: Optional[str] = None\n        self._root_background_name: Optional[str] = None\n''',
        '''        self._external_input_target: Optional[str] = None\n        # During Pass Through lowering this captures the first internal tool\n        # that consumes the real parent backdrop.  It exists only to expose a\n        # GroupOperator InstanceInput proxy; render connections remain direct.\n        self._group_proxy_backdrop: Optional[_Source] = None\n        self._root_background_name: Optional[str] = None\n''',
    )
    text = replace_once(
        text,
        '''    def mode_id(self, layer: SemanticLayer) -> str:\n''',
        '''    def _capture_group_proxy_input(self, backdrop: Optional[_Source], target: str) -> None:\n        if backdrop is None:\n            return\n        if not backdrop.name:\n            self._external_input_target = target\n            return\n        probe = self._group_proxy_backdrop\n        if (\n            probe is not None\n            and self._external_input_target is None\n            and backdrop.name == probe.name\n            and backdrop.port == probe.port\n        ):\n            self._external_input_target = target\n\n    def mode_id(self, layer: SemanticLayer) -> str:\n''',
    )
    text = replace_once(
        text,
        '''            previous_target = self._external_input_target\n            self._current_tools = inner_tools\n            self._external_input_target = None\n            nested = self.sequence(\n                layer.children,\n                _Source("", "Output"),\n                depth + 1,\n                inner_scope,\n            )\n            input_target = self._external_input_target\n            self._current_tools = previous_tools\n            self._external_input_target = previous_target\n''',
        '''            previous_target = self._external_input_target\n            previous_proxy_backdrop = self._group_proxy_backdrop\n            self._current_tools = inner_tools\n            self._external_input_target = None\n            self._group_proxy_backdrop = backdrop\n            nested = self.sequence(\n                layer.children,\n                backdrop,\n                depth + 1,\n                inner_scope,\n            )\n            input_target = self._external_input_target\n            self._current_tools = previous_tools\n            self._external_input_target = previous_target\n            self._group_proxy_backdrop = previous_proxy_backdrop\n''',
    )
    text = replace_once(
        text,
        '''            return _ItemResult(\n                _Source(group_name, "MainOutput1"),\n                _Source(group_name, "MainOutput1"),\n                # The GroupOperator consumes the caller's stream through its\n                # exposed MainInput1.  Adding a parent Normal merge would\n                # double-composite the pass-through result.\n                consumed_backdrop=True,\n            )\n''',
        '''            return _ItemResult(\n                nested.output,\n                nested.output,\n                # The real parent stream was consumed directly by the internal\n                # sequence.  GroupOperator MainInput/MainOutput are UI proxies\n                # only, so a parent Normal merge would double-composite it.\n                consumed_backdrop=True,\n            )\n''',
    )
    text = replace_once(
        text,
        '''        return _ItemResult(_Source(group_name, "MainOutput1"), _Source(group_name, "MainOutput1"))\n''',
        '''        # GroupOperator is an editable container/proxy boundary, not a\n        # runtime image source.  Parent/sibling/MediaOut consumers must use the\n        # actual internal terminal directly; InstanceOutput remains for Flow UI.\n        return _ItemResult(nested.output, nested.output)\n''',
    )
    text = text.replace(
        '''        if backdrop is not None and not backdrop.name:\n            self._external_input_target = merge_name\n''',
        '''        self._capture_group_proxy_input(backdrop, merge_name)\n''',
    )
    text = text.replace(
        '''        if not backdrop.name:\n            self._external_input_target = merge_name\n''',
        '''        self._capture_group_proxy_input(backdrop, merge_name)\n''',
    )
    PATH.write_text(text, encoding="utf-8", newline="\n")
    print("GroupOperator render-source bootstrap applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
