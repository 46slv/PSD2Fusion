# Architecture implications

## この文書の境界

最終architectureを決定しない。Evidenceから、維持/破棄すべき前提、選択肢、tradeoff、次回決定事項を抽出する。

## 維持すべき前提

1. **PSD parse、semantic model、asset materialization、Fusion graph generation、host verificationを分離する。**
   - prior artはこの分離で部分的成功している。
   - parserやhost routeを変更してもsemantic policyを再利用できる。

2. **Fusion graphは明示的に生成・検証する。**
   - node IDs、connections、ApplyMode、Blend、position、maskをassert可能にする。
   - native importer outputもoracle候補であって仕様そのものではない。

3. **source PSDと変換provenanceを保持する。**
   - parser version、source hash、Resolve target version、fallback/bake理由をmanifest化する余地を残す。

4. **visual parityは自動render比較でgateする。**
   - graph shapeだけではalpha/color/group semanticsの誤りを検出できない。

5. **unsupported semanticsを検出可能にする。**
   - silent Normal/100%/visible fallbackは不可。

## 捨てるべき前提

1. **「layerごとにPNGを出せばPSDを再現できる」**
   - group pass-through、clipping、fill opacity、effects、masks、adjustmentsを失う。

2. **「groupはFusion Group/Underlayへ入れればよい」**
   - Fusion organizationとPhotoshop compositing boundaryは別。

3. **「clipping maskはclipped layerへbase alphaを掛ければ終わり」**
   - multiple clipped layers、base blend/opacity、`Blend Clipped Layers As Group`が残る。

4. **「同名blend modeなら同じ見た目」**
   - color space、alpha、clamping、unsupported mode fallbackをprobeする必要がある。

5. **「`psd-tools.composite()`はPhotoshop reference」**
   - rendererにdocumented limitationとTODOがある。

6. **「Resolve純正Importerの挙動は安定した仕様」**
   - 20.1.1、20.3.1、21.0.3でPSD関連修正が続く。

7. **「native importerをResolve scriptingから直接呼べる」**
   - current official scripting surfaceにPSD Import methodを確認できない。

8. **「既存3 repoのどれかを基盤にすれば完成する」**
   - いずれも重点semanticを網羅せず、一部は未完/license不明。

## Design options

以下の各optionとadvantages/risksは、確認済みcapabilityから導いた**INFERENCE / design hypothesis**であり、採用決定ではない。

### Option A — Native PSD references + generated Merge graph

`psd-tools`等でmetadataを読み、Fusion Loader/MediaInはPSD自体のlayer channelを参照し、Merge graphを自前生成する。

Advantages:

- intermediate PNG不要。
- **INFERENCE:** Loader layer referenceが現行Resolveで安定する場合、source PSD更新を反映しやすい。
- native decoderのpixel extractionを使える。
- disk footprintが小さい。

Risks:

- Loader layer indexing/name/hidden behaviorがversion-sensitive。
- transformation/adjustment layer unsupported。
- group/clipping/maskのpixel extraction boundaryが不明。
- native PSD import APIがなく、Loader layer selectionのhost input IDに依存。
- target Resolveなしではend-to-end testできない。

Evidence needed: `L01/G/C/M/P/A` host probes、layer-index stability、missing PSD behavior。

### Option B — Semantic reconstruction + per-layer PNG

PSD parserでpixels/metadataを取り、raster layers/masksをPNG化してFusion graphを生成する。

Advantages:

- deterministic artifact、portable path、host decoder差を減らせる。
- masksやunsupported subtreeを任意粒度でbake可能。
- generated graphをoffline testしやすい。

Risks:

- `psd-tools` rendererはPhotoshop parityを保証しない。
- intermediate storage/I/O、更新同期、cache invalidationが必要。
- straight/premult/ICC/bit depth処理でhalo/color drift。
- text/vector/effects/editabilityを失いやすい。

Evidence needed: canonical rasterizer choice、color/alpha pipeline、cache manifest、bake granularity。

### Option C — Full-canvas PNG per logical layer

各logical layer/subtreeをdocument canvasでexportし、Fusion placementを固定する。

Advantages:

- coordinate mathが単純。
- irregular bounds/negative offsetのリスクが小さい。
- prior artが実装済み。

Risks:

- storageとdecode bandwidthが最大。
- transform editabilityを焼き込む。
- group/clippingのlogical layer定義を先に決める必要。

Evidence needed: representative PSDの容量/性能測定、update granularity。

### Option D — Selective subtree baking / hybrid

simple raster layersはPSD directまたはcropped assetで保持し、group/clipping/effects/adjustment等のunsupported semantic islandだけをparity-capable rasterizer候補でbakeする。source PSDとmanifestは残す。

**Unresolved dependency:** 現時点でPhotoshop parityを満たすrasterizer、automation route、licenseは特定していない。`psd-tools` rendererはこの役割を保証しない。Photoshop-driven exportを含め、probeで選ぶ必要がある。

Advantages:

- editabilityとparityのtradeoffをcase単位で選べる。
- native importer/parser limitationを局所化できる。
- unsupported semanticsを明示的に可視化できる。

Risks:

- capability plannerが最も複雑。
- bake boundaryを誤るとPass Through/adjustment scopeが壊れる。
- source update時のdependency graph/cache invalidationが必要。
- userに「どこまでeditableか」を説明するUI/manifestが必要。

Evidence needed: semantic island partition rule、Photoshop reference/bake engine、manifest UX。

### Option E — Flattened parity output only

PSD全体を1枚のreference compositeとしてFusionへ渡す。

Advantages:

- **INFERENCE:** Photoshopまたは別の信頼できるreference rendererがflattened compositeを生成できる場合、他optionよりvisual parityを達成しやすい可能性が高い。
- graphが単純。

Risks:

- layer editability、animation、selection、semantic valueを失う。
- PSD2Fusionという製品価値と一致しない可能性。

Evidence needed: product requirementとして許容されるfallbackか。

## Graph generation route options

### `.comp` first

- 良い点: artifactがdiffable、offline snapshot test、`ImportFusionComp`公式APIあり。
- 懸念: serializer dialect、path quoting、input IDs、version drift。

### Live scripting first

- 良い点: actual host tool IDs/input attrsを使える、partial failureを検出しやすい、Undo可能。
- 懸念: Resolve running/security/edition、test orchestration、current comp state。

### `.setting`/Generator first

- 良い点: reusable Inspector UI、installation後のuser experience。
- 懸念: global template install、macro wrapper、dynamic PSDごとのgraphには不向き。

### Template + patch

- 良い点: host-validated skeleton、serializer surface縮小。
- 懸念: variable graph topology、template migration、large/nested PSD。

**現時点では選ばない。** Probeでは同一simple graphを`.comp`とlive scriptingの両方で生成し、round-trip差を比較する。

## Direct PSD vs PNG tradeoff summary

| 軸 | Direct PSD | PNG decomposition | Selective hybrid |
|---|---|---|---|
| Source linkage | 強い | manifest/cacheが必要 | 強い＋派生asset |
| Disk/I/O | 小 | 大 | 中 |
| Resolve decoder依存 | 高 | 低 | 中 |
| Parser/rasterizer依存 | metadata中心 | pixelまで高 | case依存 |
| Editability | layer accessを保ちやすい | bake粒度次第 | 最も制御可能 |
| Group/clipping parity | importer/自前graphに依存 | bake可能だがrasterizer品質依存 | unsupported islandだけbake可能 |
| Offline test | 限定 | 強い | 中 |
| Version drift | 高 | graph/API側中心 | 中 |
| Color/alpha risk | native Loader挙動 | export/import両方 | 両方を管理 |
| Complexity | 中 | 中 | 高 |

## Decisions for the next architecture review

優先順に決める。

1. **Product contract:** visual parity、editability、source updateの優先順位。
2. **Supported PSD subset:** v1でnative/reconstruct/bake/rejectするsemantic matrix。
3. **Reference renderer:** Photoshop exportをtest dependencyにするか、embedded compositeを使うか。
4. **Target host matrix:** Resolve最低version、Free/Studio、Windows/macOS。
5. **Asset strategy:** direct PSD、cropped PNG、full-canvas PNG、selective subtree bakeの許容組合せ。
6. **Group/clipping model:** probe結果を基にevaluation boundaryをformalize。
7. **Color/alpha contract:** working space、bit depth、straight/premult、transparent RGB。
8. **Graph route:** `.comp`、live API、`.setting`、templateのprimary/fallback。
9. **Manifest/cache:** source hash、stable IDs、capability decisions、derived assets、warnings。
10. **Failure policy:** unsupported/ambiguous semanticsをfail、warn+bake、flattenのどれにするか。
11. **License policy:** MIT code reuse基準、license不明sampleの非移植、GPL隔離。
12. **Parity gate:** fixture corpus、metrics、threshold、Resolve version regression。

## Recommended sequence for the next turn — not an architecture decision

1. Product contractとsupported subsetを暫定化する。
2. `L01/G01/G02/G03/C01/C02/M01/P01/A01`のhost probesを行う。
3. 結果からsemantic intermediate modelの最小fieldを定義する。
4. Option A/B/Dを同じ2–3 fixtureでsmall spike比較する。
5. graph generation routeをround-trip/automation evidenceで選ぶ。
6. その後に初めてarchitecture decision recordを作る。

この順序は、既存案を擁護せず、Resolve実機Evidenceで設計空間を狭めるための作業順である。
