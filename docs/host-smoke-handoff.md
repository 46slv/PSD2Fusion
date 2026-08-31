# Resolve/Fusion host smoke handoff

Status: **PASS for the FIRST_USABLE load gate** (2026-09-01, Asia/Tokyo).

This is a non-destructive composition-load smoke. No Resolve project or timeline
was edited or saved. The generated composition and its `assets/` directory are
the user-facing handoff; keep that directory beside the `.comp` file.

## Host and artifacts

- Host: DaVinci Resolve Studio 21.0.3.0007 (`21.0.3.7`),
  `C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe`.
- Fusion scripting endpoint: the installed `fuscript.exe` at the same Resolve
  directory.
- Real PSD artifact: `D:\Documents\PSD2Fusion-real-smoke-hair\PSD2Fusion.comp`.
  Source: the user's `Hair.psd`; conversion produced 17 assets, 26 semantic
  layers, 2 PSD groups, and 19 Merge nodes.
- Synthetic Group artifact: `D:\Documents\PSD2Fusion\fixture_out4\PSD2Fusion.comp`.
- Synthetic Clipping artifact: `D:\Documents\PSD2Fusion\clip_out4\PSD2Fusion.comp`.

## Observed host results

After opening the Fusion page, `fusion:LoadComp(path)` returned a composition
for all three artifacts:

| artifact | tools | GroupOperator | Loader | Merge | MediaOut | clipping probe |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| real Hair | 42 | 2 | 17 | 19 | 1 | n/a |
| Group fixture | 8 | 1 | 2 | 3 | 1 | n/a |
| Clipping fixture | 7 | 0 | 2 | 3 | 1 | `ClipInR_d8f0034495`, `Operator=In` |

`MediaOut1` was found in each loaded composition. The clipping probe also
found the generated `Merge` whose `Operator` input is `In`, confirming that
clipping is represented as Fusion graph logic rather than omitted metadata.

The Resolve process remained responsive after the load-only smoke. A separate
exploratory call to the Fusion scripting `Composition:Render` method (not used
by PSD2Fusion and not part of this handoff) disconnected Resolve; it was
stopped and is not treated as product evidence. The accepted smoke is the
load/graph-recognition path above.

## User trial

1. Run the converter against a PSD:

   ```powershell
   python -m psd2fusion path\to\art.psd --output path\to\art_fusion
   ```

2. Open/import `PSD2Fusion.comp` in the Fusion page while retaining its
   sibling `assets/` directory.
3. Inspect the generated Loader/Merge chain, `GroupOperator` containers, and
   `MediaOut1`. For a clipping check, use the clipping fixture above or a PSD
   with a contiguous Photoshop clipping chain.

For scripted host loading, the minimal non-destructive call is:

```lua
local fusion = bmd.scriptapp("Fusion", "localhost")
local comp = fusion:LoadComp("D:\\Documents\\PSD2Fusion-real-smoke-hair\\PSD2Fusion.comp")
assert(comp:FindTool("MediaOut1") ~= nil)
```

## Current limitations

- v1 uses full-canvas RGBA PNG derivatives beside the `.comp`; it does not
  depend on Resolve's version-sensitive direct PSD Loader behavior.
- Pixel masks, native text, smart objects, adjustment layers, layer styles,
  and unsupported blend modes are warned or selectively baked where pixels are
  available; this is not Photoshop parity.
- Advanced Photoshop pass-through/backdrop interactions and
  `Blend Clipped Layers As Group` are explicit approximation/fallback areas.
- The exploratory scripting `Composition:Render` call above is not a supported
  PSD2Fusion entrypoint; use the generated comp through Fusion/Resolve.
