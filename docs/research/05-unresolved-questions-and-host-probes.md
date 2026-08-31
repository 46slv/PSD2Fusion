# Unresolved questions and host probes

## Probe policy

- semanticを1つずつ変える最小fixtureを使う。
- target Resolve version、edition、OS、project color settingsを固定して記録する。
- Photoshop reference、PSD raw semantic dump、native import graph、Resolve renderを同じcase IDで保存する。
- graphの見た目だけで合否を決めず、pixel/alpha outputも比較する。
- importerが変わり得るため、probe結果は`version-scoped`とする。
- current user projectを使わず、disposable project/libraryで行う。

## Fixture matrix

| ID | PSD fixture | 変えるsemantic | Native importerで記録するもの | 合否の観点 |
|---|---|---|---|---|
| `L01a` | 3色、全layer Normal/100%、stack orderだけ入替 | layer order | node count/order、Merge connection | Photoshop referenceとのz-order差 |
| `L01b` | L01aの中間layerだけScreenまたはMultiply | blend mode | Merge ApplyMode | referenceとのRGB/alpha差 |
| `L01c` | L01aの中間layerだけ50% opacity | layer opacity | Merge Blend等 | opacity curveの一致 |
| `L02a` | 1 layerだけhidden | visibility | node有無、enabled state、merged result | 21.0.3 disabled-layer fixの確認 |
| `L02b` | 1 layer maskだけdisabled | mask enabled state | mask graph/value | enabled pairとの差 |
| `L02c` | 1 empty layerを追加 | empty layer | node/index有無 | layer index/orderへの影響 |
| `G01` | group Pass Through、child Screen、group外backdrop | pass-through | group/underlay/subgraph、Merge order | childが外backdropへ作用するか |
| `G02` | 同一内容でgroup mode Normal | isolated group | G01との差 | childrenを先にisolated compositeするか |
| `G03a` | nested group、全opacity 100% | nested boundary | subtree/order | nestingだけの影響 |
| `G03b` | single group opacity 50% | group opacity | Blend placement | subtree全体へ一度作用するか |
| `G03c` | inner/outer opacity各50% | nested opacity interaction stress test | Blend placement | 各境界で一度ずつ作用するか |
| `C01` | alpha shapeのbase＋bounds外へ広がるclipped layer | basic clipping | mask/operator node有無、source bounds | base alpha外が消え、baseも残るか |
| `C02a` | base＋2 successive clipped layers、全Normal | clipping stack | merge order、matte reuse | multiple clipの基本順序 |
| `C02b` | C02aの1 clipped layerだけScreen | clipping＋blend interaction stress test | merge order、ApplyMode | clipped layers同士と外部のblend順 |
| `C03` | `Blend Clipped Layers As Group` on/off pair | base blend scope | on/off graph/value差 | Photoshop pairの差を再現するか |
| `M01a` | hard-edge pixel mask、default offset | pixel mask baseline | mask node、bbox | alpha separately compare |
| `M01b` | M01aからmask offsetだけ変更 | mask placement | mask bbox/transform | exact alpha position |
| `M01c` | M01aからgray valueだけ変更 | partial mask | mask value | alpha level |
| `M01d` | featherだけ変更、densityだけ変更するparameterized pair | feather / density | soft edge/value | 各parameterを独立比較 |
| `M02a` | vector mask only | vector mask baseline | path/raster/mask node | edge/transform parity |
| `M02b` | M02aからinvertだけ変更 | vector invert | input/value | inverted pairとの差 |
| `M02c` | M02aからdisabledだけ変更 | vector enabled state | node/value | disabled pairとの差 |
| `M03a` | pixel＋vector mask共存 | mask-combine interaction stress test | combine order | Photoshop combined alphaとの一致 |
| `M03b` | groupにpixel mask | group mask scope | subtree/mask connection | child別適用になっていないか |
| `B01` | all PSD/Fusion common blend modes | blend math | ApplyMode ID/fallback | linearized per-mode pixel test |
| `B02` | Hard Mix/Subtract/Divide/Darker/Lighter | unsupported/ambiguous modes | Inspector value、warning/fallback | silent Normal fallback禁止 |
| `P01` | small cropped layer、negative/overscan、irregular bounds | placement | Loader size、Center/Transform | exact document pixel position |
| `A01` | straight/premult edge colors | alpha semantics | Loader alpha mode、Merge add/sub | fringe、transparent RGB |
| `D01a` | same profileで8/16/32bpcを個別pair | bit depth | loader depth、render | normalized linear output |
| `D01b` | same depthでsRGB/Display P3等を個別pair | color profile | loader profile、render | normalized color output |
| `X01a`–`X01e` | adjustment / effect / Fill Opacity / Blend If / knockoutを1 caseずつ | advanced semanticを個別に | imported node/type/fallback | support/bake/reject policy根拠 |
| `X02a`–`X02d` | text / shape / embedded Smart Object / linked Smart Objectを1 caseずつ | editable layer typeを個別に | rasterかeditable nodeか | reference render＋editability |

## Capture protocol

各fixtureで最低限次を保存する。

1. `case.psd`
2. Photoshopからexportしたcanonical reference（ICC/profileとalphaを明記）
3. `psd-tools` semantic dump（version、layer IDs、tree/order、bbox、blend、opacity/fill、clipping、mask/effect tags）
4. Media Pool → MediaInのLayer dropdown一覧とselected layer render
5. `Fusion > Import > PSD`後のnode graph screenshot
6. exported `.comp` text
7. tool dump: tool ID/name/enabled、inputs、connections、FlowView position
8. Resolve Saver output（RGBとalphaをlosslessで保持）
9. comparison metrics＋difference image
10. `probe.json`: Resolve version/edition/OS/project settings/result/notes

## Minimal host procedure

### Phase A — graph-only

1. disposable Resolve projectを作る。
2. fixtureを`Fusion > Import > PSD`でimport。
3. node graphをexport/copyし、tool IDs、connections、ApplyMode、Blend、Center、mask inputsを記録。
4. Media Pool routeでも同じPSDを読み、Layer dropdownを記録。
5. projectを保存せず閉じても再取得できるよう、artifactだけrepo外probe outputへ保存する。

### Phase B — pixel parity

1. Photoshop referenceとResolve outputを同一canvas、同一profile、同一bit depthへ揃える。
2. RGBはlinear lightで比較し、alphaは独立channelで比較。
3. transparent RGBも別途確認し、premult fringeを見落とさない。
4. absolute max/mean、failed-pixel ratio、difference imageを必須とする。
5. SSIMやDelta Eは補助指標。alpha/position/orderの構造的失敗を平均指標で隠さない。

### Phase C — round-trip/automation feasibility

1. target compで`AddTool/ConnectInput/SetInput`を実行し、同等graphを再構築できるか確認。
2. `.comp` importとlive API buildをexportして正規化比較。
3. path escaping、日本語file name、relative/absolute path、missing sourceの挙動を確認。
4. Undo/rollbackとpartial failure時のcleanupを確認。

## Visual parity metrics

推奨する多層判定:

1. **Exact structural:** dimensions、channel count、alpha presence、metadata policy。
2. **Exact/near pixel:** max/mean absolute RGBA、pixels above threshold、hard-fail outlier。
3. **Alpha-specific:** alpha absolute error、edge band error、opaque/transparent region confusion。
4. **Perceptual:** SSIM、必要ならLab Delta E 2000。
5. **Diagnostic:** absolute difference image、heatmap、bbox of differences。

[OpenImageIO `idiff`](https://openimageio.readthedocs.io/en/stable/idiff.html)はabsolute/relative threshold、failed-pixel percentage、hard fail、difference imageを提供する。[scikit-image SSIM](https://scikit-image.org/docs/stable/api/skimage.metrics.html)はperceptual補助になるが、float imageでは`data_range`を明示する。[Colour](https://colour.readthedocs.io/en/latest/generated/colour.delta_E.html)はDelta E 2000を提供する。

合否閾値はfixture baseline取得後に決める。現時点で数値を固定しない。

## Open questions for design review

### Product requirement

- parityの対象はPhotoshop merged compositeか、各layerの編集可能性か、両方か。
- unsupported semanticをrejectするか、警告付きbakeするか。
- Photoshopが必須dependencyになってよいか。
- target Resolve version/editionの最低線は何か。

### PSD semantics

- clipping baseのopacity/modeをどの段で適用するか。
- pass-through groupをFusion graphで厳密に再構築できる範囲。
- Fill Opacity、Blend If、knockout、layer effectsのv1 policy。
- linked Smart Objectのpath解決とmissing behavior。

### Fusion/host

- 21.0.3.7 importerがgroup/clipping/masksをbake、drop、graph化のどれにするか。
- unsupported blend modeのInspector/API value。
- PSD Loader layer indexがtree/order/hidden layerとどう対応するか。
- `.comp` serializer fieldのversion stability。
- Free版とStudio版のmultilayer behavior差。

## Probe completion gate

次のarchitecture reviewでhost routeを選ぶ前のcore gateは、host version/editionを記録した上で`L01a`–`L02c`, `G01`–`G03c`, `C01`–`C03`, `M01a`–`M03b`, `B02`, `P01`, `A01`をtarget Resolveで通すこと。

Supported-subsetを確定する前のconditional gate:

- 8-bit sRGB以外をsupport候補に残すなら`D01a`–`D01b`を実行する。実行しない場合はv1 scopeを8-bit sRGBへ明示的に制限する。
- advanced featuresをv1非対象にしても`X01a`–`X01e`は個別検出と明示fallbackを確認する。
- text/shape/Smart Objectのeditabilityを候補に残すなら`X02a`–`X02d`を実行する。raster-onlyと決める場合も検出とloss reportingは確認する。
