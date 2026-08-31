# Third-party notices

PSD2Fusion's first implementation does not copy source files from the prior
art below. It uses their observed, separately reimplemented patterns for
full-canvas raster placement and Fusion `.comp` Loader/Merge serialization.

- [NUROKU/DaVinciResolve_PSDFusionGenerator](https://github.com/NUROKU/DaVinciResolve_PSDFusionGenerator), revision `0b2181699ee4406fcf1e4971f289b2a0ea9066e1` — MIT. Reviewed paths: `PSDFusionGenerator/PSDDivider/psd_divider.py`, `PSDFusionGenerator/SettingCreator/setting_creator.py`, `PSDFusionGenerator/SettingCreator/template_const.py`.
- [bixcl/PSDconverter](https://github.com/bixcl/PSDconverter), revision `5645c270d725357513604037d23185cefc654b58` — README claims MIT, but the revision has no LICENSE file. Only its output shape was inspected; no code is reused.
- [34j/DaVinciResolve.PSDGeneratorBuilder](https://github.com/34j/DaVinciResolve.PSDGeneratorBuilder), revision `85fd7386f8dc9ae4c6a3c4ff38636f513632385c` — MIT, WIP. Only serializer limitations and API shape were inspected; no code is reused.
- [psd-tools](https://github.com/psd-tools/psd-tools), source revision `8d44ed0c4c2d43d935b35dff642bbc4e4f767f6d` — MIT. PSD2Fusion depends on the published package, subject to its license and metadata.

The repository's research baseline records the evidence and license boundary
in more detail under `docs/research/01-prior-art-comparison.md`.
