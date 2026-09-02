# PSD2Fusion

PSD2Fusion converts Photoshop PSD structure into a readable DaVinci Resolve/Fusion graph.

## Current development program

The active Goal is Photoshop compositing fidelity for blend modes, opacity, groups, and especially clipping.

A fresh Codex/agent starts here:

1. `AGENTS.md`
2. `.control/current.json`
3. `.control/CURRENT_GOAL.md`
4. the current code/tests/evidence needed by `active_task_id`

Chat history is not required. The real PSD/PNG target is recorded in the Goal as read-only local input and is never committed.

Run repository-level offline checks with:

```powershell
pwsh -NoProfile -File .\scripts\check.ps1
```

## First usable conversion

Install dependencies and generate a Fusion composition:

```powershell
python -m pip install -e .
python -m psd2fusion path\to\art.psd --output path\to\art_fusion
python -m psd2fusion path\to\art.psd --output path\to\art_fusion --force
```

Output contains `PSD2Fusion.comp`, full-canvas RGBA derivatives under `assets/`, and `manifest.json`.

FIRST_USABLE output is not automatically Photoshop pixel parity. The historical boundary is documented in `ARCHITECTURE.md`; the active parity contract is `.control/CURRENT_GOAL.md`.

## DaVinci Resolve launcher

Install the per-user Resolve/Fusion menu launcher:

```powershell
pwsh -NoProfile -File .\scripts\install_resolve.ps1
```

Then run Workspace > Scripts > Comp > PSD2Fusion from Resolve's Fusion page. Integration details are in `docs/resolve-integration.md`.
