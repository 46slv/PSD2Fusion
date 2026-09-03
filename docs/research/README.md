# PSD2Fusion implementation research

Initial research: 2026-08-31  
PSD format foundations added: 2026-09-01  
Photoshop compositing semantics deep dive added: 2026-09-03  
Initial host scope: Windows / DaVinci Resolve `21.0.3.7`  
Status: **Evidence/research baseline, not current task state.**

## Authority split

- active task/status -> `.control/current.json`;
- active compositing Goal/architecture/validation -> `.control/CURRENT_GOAL.md`;
- historical FIRST_USABLE path -> root `ARCHITECTURE.md`;
- evidence and unresolved observations -> this directory.

Historical statements such as "undecided" or "unimplemented" remain scoped to their investigation date.

## Evidence labels

- **CONFIRMED**: primary source, exact source commit, executable test, or recorded host observation.
- **INFERENCE**: design consequence drawn from confirmed facts.
- **HOST-PROBE**: version-scoped Photoshop/Resolve evidence.
- **CONFLICT**: sources, versions, or implementations disagree.

Adobe's binary format specification describes storage, not the complete visual compositor. Keep byte/tag facts, Photoshop meaning, Fusion capability, and host observations separate.

## Documents

0. [PSD file format foundations](00-psd-file-format-foundations.md)
1. [Prior-art comparison](01-prior-art-comparison.md)
2. [PSD semantic requirements](02-psd-semantic-requirements.md)
3. [Fusion representation capabilities](03-fusion-representation-capabilities.md)
4. [Native importer observations](04-native-importer-observations.md)
5. [Unresolved questions and host probes](05-unresolved-questions-and-host-probes.md)
6. [Architecture implications](06-architecture-implications.md)
7. [Photoshop compositing semantics deep dive](07-photoshop-compositing-semantics-deep-dive.md) — evaluation scope, advanced blending, color/gamma/alpha, current psd-tools gaps, and future fixture matrix

## Durable conclusions

- PSD/PSB is an editing-state container, not merely a stack of RGBA images.
- Extracting per-layer pixels and reproducing Photoshop compositing are separate problems.
- Group hierarchy is reconstructed from flat records and section dividers.
- Pass Through and isolated groups have different backdrop scope.
- Clipping is a same-parent ordered relationship involving base coverage, member order, base blend/opacity, and `Blend Clipped Layers As Group`.
- Layer transparency, pixel/real/vector masks, and document alpha are distinct.
- Overall and fill opacity are distinct.
- Advanced blending flags such as Blend If, effect grouping/scope, channel restrictions, transparency-shape behavior, and Knockout can alter pixels independently of the ordinary layer blend-mode name.
- Photoshop exposes application Color Settings that can alter RGB compositing, so color/gamma environment evidence belongs in strict pixel-proof records until file-level persistence is proven.
- psd-tools is useful for parsing/raster access and cross-checking but is not the Photoshop visual oracle; current upstream still has explicit advanced-compositor gaps.
- Fusion Group/Underlay does not automatically implement Photoshop group semantics.
- Resolve importer behavior remains version-scoped.
- Unknown resources/tags must be length-safe and visible to capability/loss policy.

Add findings to the nearest owner only. Do not duplicate the same rule across research, Goal, AGENTS, tests, and scripts.
