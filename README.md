# PSD2Fusion

## First usable conversion

Install the parser and raster dependencies, then generate a Fusion composition:

```powershell
python -m pip install -e .
python -m psd2fusion path\to\art.psd --output path\to\art_fusion
# Re-run into an existing generated directory only when intended:
python -m psd2fusion path\to\art.psd --output path\to\art_fusion --force
```

The output directory contains `PSD2Fusion.comp`, full-canvas RGBA derivatives
under `assets/`, and `manifest.json`. The Resolve menu integration inserts the
generated graph directly into the currently selected Fusion Composition; the
`.comp`, assets, and manifest remain available as recovery/debug artifacts.
The exact manual host-smoke procedure and any environment blocker are recorded
in `docs/host-smoke-handoff.md`.
Unsupported layer kinds are retained in the manifest and selectively baked
when `psd-tools` can provide pixels; no Photoshop parity is implied.

## DaVinci Resolve launcher

Install the per-user Resolve/Fusion menu launcher from the repository root:

    pwsh -NoProfile -File .\scripts\install_resolve.ps1

Then run Workspace > Scripts > Comp > PSD2Fusion from Resolve's Fusion page.
After selecting a PSD, the generated nodes appear in the current Fusion
Composition without opening the generated `.comp` separately.
The install, uninstall, output, and known-limitation details are in
`docs/resolve-integration.md`.
