# Resolve/Fusion native PSD importer observations

## Version scope

- 公式operational evidence: Fusion `20.3` Manual、Resolve `20` training/new-features docs。
- current host: Resolve `21.0.3.7`。Free/Studio editionは未確認。
- **CONFLICT:** current hostはmanualより新しく、21.0.3 release自体がPSD import修正を含む。20.3の説明を21.0.3のpixel/node挙動として無条件に適用しない。

## Documented behavior

### 1. Single-node access

**CONFIRMED:** ResolveでPSDをMedia PoolからFusion Node Editorへdragすると単一`MediaIn`になり、InspectorのLayer dropdownからindividual layerを選べる。Fusion StudioのLoaderもindividual layerまたはcompleted/merged imageを選べる。

**CONFIRMED limitation:** Blackmagic ManualはLoader経路についてtransformation layerとadjustment layerをunsupportedと明記する。

Source: [Fusion 20.3 Reference Manual](https://documents.blackmagicdesign.com/UserManuals/FusionManual.pdf), Fusion Fundamentals chapter 3, pp.85–87.

### 2. Full graph import

**CONFIRMED:** Resolveの`Fusion > Import > PSD`、Fusion Studioの`File > Import > PSD`は、各PSD layerをnodeとして作り、1個以上のMergeで合成する。MergeはPSDのApply modeに設定され、mode名を基にrenameされる。

Resolve 20 VFX Guideのtraining exampleでも3-layer PSDが3 layer nodesと`Normal`/`Normal1` Mergeになる。Media Pool経路は同じPSDでもsingle multilayer MediaInのまま。

Sources: [Fusion 20.3 Manual](https://documents.blackmagicdesign.com/UserManuals/FusionManual.pdf), pp.85–87; [DaVinci Resolve 20 Fusion Visual Effects guide](https://documents.blackmagicdesign.com/UserManuals/DaVinci-Resolve-20-Fusion-Visual-Effects.pdf), lesson 4 pp.96–101.

### 3. Multilayer pipelining

Resolve 20 New Features GuideはStudio-only multilayer EXR/PSD pipeliningを説明し、layer structureをtoolset中に保持し、viewer/nodeでindividual layerへアクセスできるとしている。これはsingle MediaIn/Loader routeの能力であり、Photoshop group/clipping semanticsの再構成を証明しない。current host editionは未確認なので、このStudio-only能力がlocalで利用可能とはまだ扱わない。

Source: [DaVinci Resolve 20 New Features Guide](https://documents.blackmagicdesign.com/SupportNotes/DaVinci_Resolve_20_New_Features_Guide.pdf), p.59.

## What the manuals do not document

以下について、調査したBlackmagic一次資料は変換規則を説明しない。

- group / nested groupをnode graphで保持するかflattenするか
- Pass Throughとnon-Pass group isolation
- group opacity
- clipping mask chainとbase blend/opacity
- `Blend Clipped Layers As Group`
- pixel layer mask、vector mask、group mask
- fill opacity、layer effects、Blend If、knockout
- hidden/disabled/empty layerのnode生成
- smart object、text、shapeのeditable変換かraster layerか
- irregular/negative/overscan layer boundsのposition式
- ICC profile、8/16/32bpc、HDR、alpha premultiplication
- unsupported blend modeのfallback

これらを「純正Importerが処理するはず」と推測して設計前提にしない。

## Version-drift evidence

Blackmagic support notesはPSD importが継続的に変更されたことを示す。

| Version | 公開記述 | 含意 |
|---|---|---|
| Resolve 20.1.1 | PSD importのnode/layer layoutをcleanerにした | serialization/layout goldenはversion依存 |
| Fusion Studio 20.1.1 | PSD handling improved | Loader/import behaviorに変更余地 |
| Fusion Studio 20.3.1 | irregularly sized PSD layersのimport対応 | bbox/offsetは過去versionで不具合領域 |
| Resolve 21.0.3 | PSD imports improved。release detailではdisabled layers import issue修正 | visibility semanticsは少なくとも21.0.3以前にbugがあった |

Primary index（mutable）: [Blackmagic Support Center](https://www.blackmagicdesign.com/support/)（2026-08-31取得）。20.1.1/20.3.1の表記はこのindexに依存し、stable release-note URLは取得できていないため、補助的なversion-drift evidenceとして扱う。

Resolve 21.0.3についてはcurrent installの `C:\Program Files\Blackmagic Design\DaVinci Resolve\Documents\ReadMe.html` lines 50, 57–71がversionと「disabled layersを含むPSD import issue」修正を明記する。SHA-256は`293A710837A9F30C5591B8222FD9F697C1A6F66C50B69C966ACA0F1B3CA72C12`。これはcurrent hostに対するstable local primary evidenceである。

```powershell
Get-FileHash 'C:\Program Files\Blackmagic Design\DaVinci Resolve\Documents\ReadMe.html' -Algorithm SHA256
Select-String -Path 'C:\Program Files\Blackmagic Design\DaVinci Resolve\Documents\ReadMe.html' -Pattern 'DaVinci Resolve 21.0.3|importing PSDs with disabled layers'
```

## Local observations performed in this task

読み取り専用で以下を確認した。

- `Resolve.exe`のfile version: `21.0.3.7`（edition未確認）
- Resolve processは起動中
- 同梱Scripting READMEのAPI surfaceとhash
- PSD native importを呼ぶdocumented scripting methodがないこと

実行しなかったこと:

- current user projectへのmedia import
- Fusion node追加・削除
- timeline/project作成
- native `Import > PSD`実行
- Photoshop reference fixture作成

したがって、この文書のnative importer結果は**公式にdocumentedされた観察**であり、21.0.3.7 local graph/pixel observationではない。

## Evidence vs unknown summary

| 項目 | 状態 |
|---|---|
| PSD individual layer / merged resultを選択可能 | CONFIRMED |
| full importでlayer nodes＋Merge chain | CONFIRMED |
| Merge Apply ModeをPSD modeへ設定 | CONFIRMED |
| Media Pool routeはsingle multilayer node | CONFIRMED |
| transformation / adjustment layer Loader limitation | CONFIRMED |
| groups/nested groupsの正確なgraph | HOST-PROBE |
| clipping/masks | HOST-PROBE |
| visibility on 21.0.3.7 | HOST-PROBE; recent bugfixあり |
| pixel parity | HOST-PROBE |
| layout/serialization stability across versions | HOST-PROBE / known version drift |

## Requested-semantic native-import status

この表は**純正ImporterのEvidenceだけ**を示す。Fusion primitiveが表現可能でも、Importerがそのgraphを生成するとは限らない。

| Requested semantic | Native importer status | Evidence boundary |
|---|---|---|
| Layer nodes / z-order | CONFIRMED at documented level | one node per PSD layer＋Merge cascade。hidden/empty/order edgeは21.0.3.7 HOST-PROBE |
| Group / nested group | HOST-PROBE | Blackmagic docsにconversion ruleなし |
| Blend Mode | CONFIRMED name-level / HOST-PROBE pixel-level | Merge Apply ModeをPSD modeへ設定。unsupported mode/fallback/math parityは不明 |
| Opacity (layer/group/fill) | HOST-PROBE | importerがMerge Blend等へどう写像するか公式記載なし |
| Position / bounds | HOST-PROBE | MergeはCenterを持つが、importerのbbox式、negative/irregular boundsは未確認 |
| Pixel/vector/group Mask | HOST-PROBE | importer graph/bake/dropの公式記載なし |
| Clipping Mask | HOST-PROBE | importer graph/bake/dropの公式記載なし |
| Pass Through / group isolation | HOST-PROBE | importerのevaluation boundaryは公式記載なし |

このタスクではResolve 21.0.3.7でnative PSD graph/pixel probeを実行していない。
