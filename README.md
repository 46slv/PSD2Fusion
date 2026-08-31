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
under `assets/`, and `manifest.json`. Open/import the `.comp` in Resolve/Fusion
or use the documented `TimelineItem.ImportFusionComp(path)` scripting call.
The exact manual host-smoke procedure and any environment blocker are recorded
in `docs/host-smoke-handoff.md`.
Unsupported layer kinds are retained in the manifest and selectively baked
when `psd-tools` can provide pixels; no Photoshop parity is implied.
