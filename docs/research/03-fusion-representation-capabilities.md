# Fusion representation capabilities

## Core primitives

| Fusion primitive | 確認済み能力 | PSD semanticへの候補写像 | 限界 / 要probe |
|---|---|---|---|
| Loader / MediaIn | PSDのindividual layerまたはmerged resultを選択可能 | direct PSD layer source | transform/adjustment layerは公式にunsupported。group/mask semanticsは未記載 |
| Background | comp canvas/resolutionを固定 | PSD document canvas | color management、bit depthの一致が必要 |
| Merge | FG/BG alpha composite、Apply Mode、Blend、Center/Size/Angle、Effect Mask | z-order、blend、opacity、position、mask | Photoshop group/clipping semanticsは単一Mergeでは不足 |
| Merge Operator `In` | BG alphaでFGをclip | clipping base alphaの一部 | base自身＋複数clipped layer＋base blend scopeまで一式ではない |
| Effect Mask | Merge resultの作用範囲をgrayscale maskで制限 | layer/group pixel mask候補 | mask bbox、feather、density、linked transform、vector pathは別処理 |
| Transform | image placement/scale/rotation | PSD layer bbox/placed transform | cropped bounds、canvas外、filter/premult edgeの検証が必要 |
| MatteControl / Channel tools | alpha操作、invert、combine | mask/clipping補助 | exact graphはhost検証が必要 |
| Fusion Group | node collectionをcollapse/expand | graph organization / macro boundary | Photoshop compositing isolationを自動では作らない |
| Underlay | nodesの視覚的整理 | PSD groupの可視化 | **compositing semanticsなし** |
| Macro / GroupOperator | inputsを公開し再利用可能なtool化 | Generator/template packaging | semantic correctnessは内部graph次第 |

Primary source: [Fusion 20.3 Reference Manual](https://documents.blackmagicdesign.com/UserManuals/FusionManual.pdf) chapters 3, 18, 35, 42.

## Merge capability

Blackmagic公式資料ではMergeはForeground、Background、Effect Maskを持ち、Backgroundがoutput resolutionを決める。Foregroundにはnormalized `Center X/Y`、`Size`、`Angle`がある。Apply Modeには少なくとも次が記載される。

- Normal, Screen, Dissolve
- Darken, Multiply, Color Burn, Linear Burn
- Lighten, Color Dodge, Linear Dodge
- Overlay, Soft Light, Hard Light, Vivid Light, Linear Light, Pin Light
- Difference, Exclusion
- Hue, Saturation, Color, Luminosity
- Fusion固有のHypotenuse, Geometric

Normal/Screen時のOperatorにはOver、In、Held Out、Atop、XOrがあり、Porter–Duff型のalpha演算が可能。Fusion Fuse SDKはさらにUnder等を列挙する。

### PSD blend mappingの分類

| 分類 | PSD例 | 状態 |
|---|---|---|
| 名前上の直接候補あり | Normal, Dissolve, Darken, Multiply, Color Burn, Linear Burn, Lighten, Screen, Color Dodge, Linear Dodge, Overlay, Soft/Hard/Vivid/Linear/Pin Light, Difference, Exclusion, Hue, Saturation, Color, Luminosity | **CONFIRMED capability / HOST-PROBE parity** |
| manual/SDKの名称差を確認要 | Darker Color, Lighter Color | Fuse SDKには記載、対象Resolve InspectorでID確認要 |
| 対応が公式一覧で確認できない | Hard Mix, Subtract, Divide | fallbackを決めず、target Resolveでnode input/valueをprobe |
| Photoshop group専用 | Pass Through | Fusion Merge Apply Modeとは別semantic |

同名modeでもPhotoshopとFusionで色空間、alpha handling、clampingが一致するとは限らない。名前一致はvisual parityの証明ではない。

Sources: [Fusion 20.3 Manual](https://documents.blackmagicdesign.com/UserManuals/FusionManual.pdf), [Fusion Fuse SDK](https://documents.blackmagicdesign.com/UserManuals/Fusion_Fuse_SDK.pdf), [Adobe PSD blend keys](https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/).

## Opacity mapping

Fusion Mergeの`Blend`はforeground composite resultを0–1でmixするため、単純pixel layerのoverall opacity候補になる。しかし次は別扱いが必要。

- Photoshop Fill Opacity
- layer effectsを含むoverall opacity
- group opacity（subtree全体に一度作用）
- clipping base opacity/mode inheritance
- adjustment layerのscope

**INFERENCE:** simple raster layer＋effectsなし＋clippingなし＋isolated z-orderでのみ、`layer.opacity / 255 → Merge.Blend`を直接候補にできる。一般則として固定しない。

## Position and canvas

PSDのbboxはtop-left originのpixel coordinates。Fusion Merge Centerはreference sizeに対するnormalized centerで、Y方向の座標系も確認が必要。2つの実装方式がある。

1. **Cropped raster + placement:** layer bboxだけをPNG/PSD layer channelとして読み、Transform/Merge Centerでdocument positionへ戻す。
2. **Full-canvas raster:** 各layerをPSD canvasサイズへ貼り、Centerを0.5/0.5に固定する。

前者はstorageが小さくpositionがeditableだが、negative/overscan bbox、mask bbox、irregular layer size、filter edgeに注意。後者はgraphが単純だがstorage/I/Oが大きく、semantic transformをrasterへ焼く。

Resolve/Fusionは20.3.1で「irregularly sized layers」のPSD import修正を出しているため、bbox edge caseは既知のversion-sensitive領域である。[Blackmagic Support](https://www.blackmagicdesign.com/support/)

## Masks and clipping

### Pixel/vector layer mask

候補は、maskをBitmap/Loaderで読みEffect Maskへ接続するか、alphaへprecomposeする方法。Effect Maskはwhite/blackでMergeの作用を制御できるが、Photoshop layer maskの次を自動では再現しない。

- mask bbox/default color
- layerとmaskのlinked/unlinked transform
- invert、disabled、density、feather
- pixel maskとvector maskのcombine order
- group outputに対するmask

### Clipping mask

Merge Operator `In`はBG alphaでFGをclipできるためbuilding blockにはなる。ただしPhotoshop clipping stackはbase layerも最終出力へ残り、複数clipped layersをbase alpha内で相互blendし、base mode/opacity/`Blend Clipped Layers As Group`のscopeが関与する。

**INFERENCE:** clipping groupは概念上、`base alpha matte`と`clipped subtree composite`と`base+clipped resultの外部blend`を分離したsubgraphが必要になる可能性が高い。正確なgraphはfixture probe前に固定しない。

## Group representation

Fusion Group/Underlayはorganization機能。Photoshop non-Pass groupの「childrenを透明backdrop上で合成→group resultを外へblend」は、明示的なsubtree compositeとgroup-level Mergeが必要。Pass Throughは逆に外部backdropをchildrenが参照するため、同じsubtreeをtransparent backgroundへ閉じ込めると結果が変わる。

したがって:

- Underlay = layout metadata only
- Fusion Group = packaging only
- Photoshop group = compositing/evaluation boundary

この3つを同一視しない。

## Premultiplied alpha

Fusion ManualはMerge foregroundがpremultiplied alphaを期待すると説明する。straight imageをadditive側で合成するとedge fringeが出得る。color correctionはstraightで行い、Mergeやtransform/filter前後のpre-divide/post-multiplyを重複させない必要がある。

PNG分解でもdirect PSDでも、以下をmanifest/probeへ含める。

- source pixelがstraightかpremultipliedか
- transparent RGBの保持状態
- LoaderのAlpha Mode / Post-Multiply設定
- MergeのAdditive/Subtractive状態
- color transformをalpha divide前後のどちらで行うか

Source: [Fusion 20.3 Manual](https://documents.blackmagicdesign.com/UserManuals/FusionManual.pdf), chapters 18 and 35.

## Graph generation routes

| 経路 | できること | 長所 | 短所 / boundary |
|---|---|---|---|
| `.comp`生成→`ImportFusionComp` | composition全体をtext artifactとして生成/import | diffable、offline生成、host-independent testがしやすい | undocumented serialization detail、path escaping、version input IDのprobe必要 |
| live Fusion scripting | `AddTool`, `ConnectInput`, `SetInput`, FlowView layout | hostの実node ID/inputを検証しながら生成、Undo/Lock可能 | Resolve起動・security設定・host stateが必要 |
| `.setting` / Macro / Generator | toolsetをpackage、Inspector inputsを公開 | user install後の再利用に向く | global template installation、wrapper boilerplate、whole compではない |
| prebuilt `.comp`/`.drb` template＋差替え | host検証済みgraph骨格を使う | serializer量を減らせる | graph variationが大きいPSDではtemplate explosion |
| native `Fusion > Import > PSD` | Blackmagic importerにgraph生成を委任 | native behaviorを得る | Resolve scripting READMEにPSD import APIなし。UI-onlyでautomationとversion controlが弱い |

### Current host evidence

このPCのResolve binaryは`21.0.3.7`（edition未確認）。同梱の `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\README.txt`（last updated 2026-07-15、SHA-256 `7C3D76A82EF111725F5D3C9E3B0E3020BBD650802573380644FA1580649245E9`）は次を記載する。

- `Timeline.InsertFusionCompositionIntoTimeline()`
- `TimelineItem.GetFusionCompByIndex()`
- `TimelineItem.AddFusionComp()`
- `TimelineItem.ImportFusionComp(path)`
- `TimelineItem.ExportFusionComp(path, compIndex)`

PSD Import UIを直接呼ぶmethodは同READMEから確認できない。

Local evidence reproduction:

```powershell
Get-Item 'C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe' |
  Select-Object -ExpandProperty VersionInfo
Get-FileHash 'C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\README.txt' -Algorithm SHA256
Select-String -Path 'C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\README.txt' -Pattern 'InsertFusionCompositionIntoTimeline|ImportFusionComp|ExportFusionComp|AddFusionComp'
```

Sources: [Fusion Scripting Guide](https://documents.blackmagicdesign.com/UserManuals/Fusion8_Scripting_Guide.pdf), current-host SDK README lines 436, 471–474, 500–504.

## 未確定の表現能力

次はFusion primitiveが存在してもPhotoshop parityが未証明。

- all blend mode math and alpha interaction
- non-Pass group isolation
- Pass Through with external backdrop
- group opacity placement
- multi-layer clipping stack
- masks with offsets/density/feather/vector paths
- Blend If/knockout/channel restrictions
- Photoshop adjustments/effects/text/smart object editability
- ICC/profile and 16/32bpc behavior
