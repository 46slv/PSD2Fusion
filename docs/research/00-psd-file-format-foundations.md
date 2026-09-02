# PSD file format foundations

調査日: 2026-09-01  
対象: Adobe Photoshop PSD / PSB の**基礎バイナリ構造と、その構造から導かれる意味論上の制約**  
目的: PSD2Fusion が PSD を「画像レイヤーの集合」と誤解せず、将来の対応範囲拡張でも壊れない semantic IR / parser boundary を維持するための基礎資料  
Evidence: Adobe Photoshop File Formats Specification、Adobe Photoshop Help、`psd-tools` 1.18.0 documentation/source を中心に確認

> この文書は `02-psd-semantic-requirements.md` の前段に置く「ファイル形式そのもの」の資料である。  
> Adobe のバイナリ仕様はデータの格納形式を記述するが、Photoshop がそのデータをどう見た目へ評価するかを完全には規定しない。  
> したがって **serialization facts** と **Photoshop compositing semantics** は分離して扱う。

---

## 0. 結論 — PSDをどう捉えるべきか

PSD/PSBは、単純な「RGBA画像をレイヤーごとに格納したファイル」ではない。

より正確には、次の3層が重なった **Photoshop編集状態のコンテナ** である。

1. **Document-level container**
   - canvas、color mode、bit depth
   - ICC profile、resolution、XMP、paths、guidesなどの image resources
   - 最終 merged/composite image

2. **Layer records + channel pixel storage**
   - layer bounds、opacity、blend mode、clipping flag、visibility等の固定field
   - RGB/CMYK/alpha/mask等の各channelの圧縮pixel data
   - mask、Blend If、legacy layer name

3. **Extensible tagged metadata**
   - `lsct` group boundary
   - `luni` Unicode layer name
   - `lyid` stable-ish Photoshop layer ID
   - `TySh` text
   - `vmsk` / `vsms` vector mask
   - `lfx2` layer effects
   - `SoLd` / `SoLE` smart object
   - `lnkD` / `lnk2` / `lnk3` linked/embedded data
   - adjustment/fill layers
   - artboards、shape/stroke、knockout、advanced blending
   - 未文書化・将来追加のtag

このため「1 LayerRecord = 1 完成画像 = 1 Fusion node」とは限らない。

**PSD2Fusionで重要な不変条件は、pixel extraction と semantic extraction を分離し、未知のtagを含めたsemantic lossを観測可能にすること。**

---

## 1. 全体の5セクション

Adobe仕様ではPSD/PSB本体は次の5つに分かれる。

```text
+-----------------------------+
| 1. File Header              |  fixed 26 bytes
+-----------------------------+
| 2. Color Mode Data          |  length-delimited
+-----------------------------+
| 3. Image Resources          |  length-delimited
+-----------------------------+
| 4. Layer and Mask Info      |  length-delimited
|    + Layer Info             |
|    |  + Layer Records       |
|    |  + Channel Image Data  |
|    + Global Layer Mask      |
|    + Document Tagged Blocks |
+-----------------------------+
| 5. Image Data               |  merged/composite pixels
+-----------------------------+
```

Adobeは、header以外の4セクションは可変長であり、多数のlength markerとpaddingを持つため、**offsetを固定値で決め打ちせずlengthを正本にして走査する**よう要求している。

全multi-byte値はbig-endian。

### 1.1 パーサーとしての最重要原則

- 既知fieldだけ読んで次のoffsetを推測しない。
- length-delimited blockは必ずblock endを計算して境界を守る。
- paddingを仕様どおり消費する。
- 未知resource/tagは「未知だから壊す」のではなく、lengthに従ってskip/preserveできる設計にする。
- PSDとPSBでは一部length fieldの幅が変わるため、`version` をparse contextとして全階層へ伝える。

---

## 2. File Header — 最初の26 bytes

Headerは固定長26 bytes。

| Offset | Size | 意味 |
|---:|---:|---|
| 0 | 4 | Signature = `8BPS` |
| 4 | 2 | Version: PSD=`1`, PSB=`2` |
| 6 | 6 | Reserved, zero |
| 12 | 2 | document channel count, 1..56 |
| 14 | 4 | height |
| 18 | 4 | width |
| 22 | 2 | depth: 1 / 8 / 16 / 32 bit per channel |
| 24 | 2 | color mode |

主なcolor mode:

| value | mode |
|---:|---|
| 0 | Bitmap |
| 1 | Grayscale |
| 2 | Indexed |
| 3 | RGB |
| 4 | CMYK |
| 7 | Multichannel |
| 8 | Duotone |
| 9 | Lab |

### 2.1 `8BPS` と PSB

PSBでも**File Header signatureは `8BPS`**。PSD/PSBの判定はversionで行い、PSD=`1`、PSB=`2`。

Adobe文書中ではLarge Document Formatを `8BPB/PSB` と呼ぶ箇所があるが、header fieldのsignature定義はPSD/PSBとも `8BPS` である。ここを混同しない。

### 2.2 サイズ

Adobe binary spec:

- PSD: 最大 30,000 × 30,000 px
- PSB: 最大 300,000 × 300,000 px

Adobeの現行Photoshop Help（2026-03確認）は、PSDを最大2GB、より大きな文書にはPSBを使う形式として案内している。

**実装上はwidth/heightだけでPSD/PSBを判定しない。version fieldを正本にする。**

---

## 3. Color Mode Data

構造:

```text
uint32 length
byte[length] data
```

通常:

- Indexed Color: 768 bytesのcolor table
- Duotone: proprietary/undocumented data
- それ以外: length = 0 が基本

ここは「document pixel dataそのもの」ではない。

RGB/CMYK/Labなどの通常documentでゼロだからといって、後続のImage ResourcesやLayer dataを同じものと解釈しない。

---

## 4. Image Resources — document-level non-pixel metadata

構造:

```text
uint32 section_length
repeat until section_end:
    4 bytes signature       usually "8BIM"
    2 bytes resource_id
    Pascal string name      padded to even
    uint32 data_size
    byte[data_size] data    padded to even
```

Image Resourcesはdocument全体のnon-pixel metadataを持つ。

代表例:

- resolution
- ICC profile
- XMP / EXIF / IPTC
- thumbnail
- alpha channel names / identifiers
- paths / clipping path
- grid / guides
- layer comps
- slices
- pixel aspect ratio
- print settings
- timeline-related metadata

### 4.1 Image Resources と Additional Layer Information は別

名前が似た「metadata領域」だが、役割が違う。

- **Image Resources**: document-levelのresource IDベースmetadata
- **Additional Layer Information / Tagged Blocks**: 4-character keyベースで、layer-levelまたはLayer/Mask section末尾のdocument-level extension data

PSD2FusionのIRでは両者を同じgeneric dictionaryへ潰すより、provenanceを分けた方がよい。

---

## 5. Layer and Mask Information — PSDの中心

この第4セクションが、PSD2Fusionに最も重要。

```text
section_length                PSD: uint32 / PSB: uint64

Layer Info
  layer_info_length           PSD: uint32 / PSB: uint64
  int16 layer_count
  LayerRecord[layer_count]
  ChannelImageData[layer_count]

Global Layer Mask Info

Additional Layer Information / Tagged Blocks
```

### 5.1 merged imageはここにない

Adobe仕様上、完成済みmerged/composite imageは最後の`Image Data`にある。

Layer and Mask Infoには、**個々のlayerを再構成するためのrecordとchannel data**がある。

Maximize Compatibilityが無効の場合、仕様上merged/compositeが作られず、最終画像を得るにはlayer dataを評価する必要があるケースがある。

したがって:

- `Image Data` = composite preview/reference
- `Layer Info` = editable layer state

であり、両者を同一のsource of truthとしない。

---

## 6. Layer Info — metadata群の後にpixel data群がまとめて来る

Layer Infoは概念上こう並ぶ。

```text
int16 layer_count

LayerRecord #0
LayerRecord #1
LayerRecord #2
...

ChannelImageData for Layer #0
ChannelImageData for Layer #1
ChannelImageData for Layer #2
...
```

つまり、各LayerRecordの直後にそのpixel bytesが埋め込まれているわけではない。

LayerRecord内の各channelには「対応するchannel dataのlength」が記録され、その後ろのChannel Image Data領域に実データがLayerRecordと同じ順序で並ぶ。

### 6.1 layer countが負の場合

`layer_count < 0` の場合:

- `abs(layer_count)` が実layer数
- merged resultのfirst alpha channelがtransparency dataを含むことを示す

単純にunsignedとして読むと壊れる。

---

## 7. LayerRecord — 1レイヤーの固定骨格

主要field:

```text
top, left, bottom, right      int32 x4
channel_count                 uint16

repeat channel_count:
    channel_id                int16
    channel_data_length       PSD uint32 / PSB uint64

blend_signature               "8BIM"
blend_mode_key                4-char key
opacity                       uint8 0..255
clipping                      uint8 0=base, 1=non-base
flags                          uint8
filler                         uint8

extra_data_length             uint32
    layer_mask_data
    layer_blending_ranges
    legacy_pascal_layer_name
    tagged_blocks...
```

### 7.1 bboxはcanvas内に収まる保証がない

`top, left, bottom, right` はdocument座標。

layer pixelsはこのrectangleの大きさを基準に格納されるが、rectangleがcanvas外へ出ることを前提に扱うべき。

よって:

```text
cropped layer pixels
!=
document-space placement
```

である。

PSD2Fusionで`bbox`をsemantic IRに残しているのは正しい。

### 7.2 blend modeは4文字key

例:

- `norm` Normal
- `mul ` Multiply
- `scrn` Screen
- `over` Overlay
- `pass` Pass Through

raw keyを保持し、変換先enumだけに潰さない方がよい。

### 7.3 opacityとfill opacityは別

LayerRecord固定fieldの`opacity`はoverall opacity。

Fill Opacityは固定LayerRecord fieldではなく、`psd-tools`ではundocumented tagged block `iOpa` (`Tag.BLEND_FILL_OPACITY`) として扱われる。

Adobe公開HTML仕様では`iOpa`を確認できないため、これは:

- Adobe-public-spec confirmed ではなく
- current `psd-tools` source confirmed / undocumented

としてprovenanceを分けるべき。

Photoshop semanticsでもoverall opacityとfill opacityはeffectsとの作用範囲が異なるため、1つのopacityへ統合してはいけない。

---

## 8. Channel — RGB画像1枚として格納されているわけではない

Layer pixel dataはchannel単位。

標準的なchannel ID:

| ID | 意味 |
|---:|---|
| 0 | Red / Cyan / Gray等の1st color channel |
| 1 | Green / Magenta等 |
| 2 | Blue / Yellow等 |
| 3 | Black等 |
| -1 | transparency mask / layer transparency |
| -2 | user layer mask |
| -3 | real user layer mask |

つまりRGBA layerでも「interleaved RGBA byte stream」がそのままあるとは限らず、各channelを別々に展開して組み立てる。

### 8.1 compression

Layer channel dataの先頭:

```text
uint16 compression
```

- 0 = Raw
- 1 = RLE / PackBits
- 2 = ZIP
- 3 = ZIP with prediction

PSBのRLEではscanline byte countが4-byte、PSDでは2-byteになる差がある。

### 8.2 channelとmaskを混同しない

特に重要な4種類:

1. color channel
2. layer transparency (`-1`)
3. user pixel layer mask (`-2`)
4. real user mask (`-3`, pixel/vector combined結果に関係)

さらにdocument-level alpha channelも存在しうる。

**「alpha」という語だけで同じものとみなさない。**

---

## 9. Layer Mask Data

LayerRecord extra dataの先頭にはpixel/user maskに関する構造が入る。

主な情報:

- mask rectangle
- default color 0/255
- relative-to-layer flag
- disabled
- invert（obsolete）
- mask density
- feather
- vector mask density / feather
- real user mask flags/background/rectangle

maskのpixels自体は対応channel data (`-2` / `-3`) 側にある。

したがってmaskは:

```text
mask metadata / geometry
+
mask channel pixels
+
vector mask tagged data（存在する場合）
```

という複数領域の組み合わせ。

「mask objectが1 blockに完結している」と考えない。

---

## 10. Layer Blending Ranges — Blend If系の基礎

LayerRecord extra dataにはblending rangesがある。

- composite gray source/destination
- 各channel source/destination

これはPhotoshopのadvanced blending、特にBlend Ifに関係する領域。

PSD2Fusion FIRST_USABLEで未対応でも、**存在を検出してunsupported semantic inventoryへ上げる価値がある**。

Normalへ黙って落とすと、見た目が変わった理由を追跡できない。

---

## 11. Layer name — legacy Pascal + Unicode `luni`

LayerRecord内にはlegacy Pascal stringのlayer nameがある。

modernなUnicode layer nameはAdditional Layer Informationの:

```text
luni
```

に格納される。

実装では:

- display name: `luni`を優先できる
- legacy name: provenanceとして保持
- identity: nameに依存させない

が安全。

同名layerは普通に存在するため、nameをIDにしてはいけない。

`lyid`が存在する場合はPhotoshop layer IDとして利用できるが、PSD2Fusion内部のdeterministic IDはsource hash + structural path等で別途持つ設計が妥当。

---

## 12. Groups — バイナリ上は「木」ではない

PSD layer structureの重要な罠。

low-level Layer Infoは**flat list**。

group hierarchyは`lsct`（Section Divider Setting）等のspecial tagged blockを持つboundary recordを使って表現される。

`lsct` type:

- 0 = other
- 1 = open folder
- 2 = closed folder
- 3 = bounding section divider

つまりPhotoshop UIで見える:

```text
Group A
  Layer X
  Layer Y
Layer Z
```

という木が、そのままrecursive binary objectとして入っているわけではない。

parserはflat recordsからstack等を使ってtreeを再構築する必要がある。

`psd-tools` low-level docsもこの点を明示し、高-level APIがparent/child treeへ復元している。

### 12.1 UI folder と compositing semantics は別

`lsct`はtree boundaryを復元するために必要だが、Groupの見た目を再現するにはさらに:

- group blend mode
- `pass` / isolated
- group opacity
- mask
- clipping scope
- adjustment layer scope
- knockout / advanced blend flags

を評価する必要がある。

**group reconstructionとgroup compositingは別フェーズ。**

---

## 13. Clipping — LayerRecordの1 byteだけでは完結しない

LayerRecordには:

```text
clipping = 0  # base
clipping = 1  # non-base
```

がある。

しかしPhotoshop clipping maskは、個々のlayerへ独立したmaskが保存される仕組みではない。

意味を得るにはsame-parent sibling orderを見て、連続するclipped layerとbaseの関係を再構築する必要がある。

さらに:

```text
clbl = Blend Clipping Elements / Blend Clipped Layers As Group
```

などのadvanced flagがstackのblend scopeに影響しうる。

従ってsemantic IRでは:

```text
base_layer_id
ordered_clipped_member_ids
same_parent_scope
raw_clipping_flags
clbl provenance
```

のようなrelationshipとして持つのが適切。

---

## 14. Additional Layer Information / Tagged Blocks — PSD拡張性の中心

基本形:

```text
4 bytes signature      "8BIM" or "8B64"
4 bytes key            e.g. "lsct", "luni", "TySh"
length                  usually uint32
data[length]
padding
```

PSBでは特定keyのlengthが8-byteになる。

Adobe仕様は、Layer Info周辺では「section lengthをよく見てparseせよ」と明示している。

### 14.1 Tagged Blocksは2箇所に現れる

概念上:

1. **per-layer**
   - 各LayerRecordのextra data末尾
2. **document-level**
   - Layer and Mask Information section末尾

同じ4-character tag mechanismでもscopeが違う。

IRへ取り込むときはscopeを失わない。

---

## 15. 代表的Tagged Block map

以下は「PSD2Fusionが将来何を検出すべきか」の索引。

### Identity / organization

- `luni` — Unicode layer name
- `lyid` — layer ID
- `lsct` — section divider / group boundary
- `lsdk` — nested section divider variant
- `lclr` — layer color label
- `lspf` — protected setting

### Compositing / advanced blending

- `clbl` — blend clipping elements
- `infx` — blend interior elements
- `knko` — knockout setting
- `tsly` — transparency shapes layer
- `lmgm` — layer mask as global mask
- `vmgm` — vector mask as global mask
- `iOpa` — fill opacity; `psd-tools` marks this undocumented

### Masks / vector

- `vmsk`, `vsms` — vector mask
- `vstk` — vector stroke
- `vscg` — vector stroke content
- `vogk` — vector origination

### Text

- `TySh` — type tool object setting
  - 2D transform matrix
  - text descriptor
  - warp descriptor
  - bounds
- `Txt2` — raw text engine data

Textは単なる文字列ではなく、transform、style runs、font/style/layout engine dataなど複数層を持つ。

### Effects

- `lrFX` — legacy effects
- `lfx2` — object-based layer effects
- `lmfx`, `lfxs` — `psd-tools`ではundocumented effect variantsとして扱われる

### Fill / adjustment

例:

- `SoCo` Solid Color
- `GdFl` Gradient Fill
- `PtFl` Pattern Fill
- `levl` Levels
- `curv` Curves
- `expA` Exposure
- `vibA` Vibrance
- `hue2` Hue/Saturation
- `blnc` Color Balance
- `blwh` Black & White
- `phfl` Photo Filter
- `mixr` Channel Mixer
- `clrL` Color Lookup
- `nvrt` Invert
- `post` Posterize
- `thrs` Threshold
- `grdm` Gradient Map
- `selc` Selective Color

### Smart Object / placed / linked content

- `plLd` / `PlLd` — placed layer data
- `SoLd` — placed/smart-object descriptor data
- `SoLE` — Smart Object layer data
- `lnkD`, `lnk2`, `lnk3`, `lnkE` — linked/embedded layer data families

### Document / modern features

- `artb`, `artd`, `abdd` — artboards
- `cinf` — compositor used, Photoshop 2020
- `PxSc`, `PxSD` — Pixel Source / other raw source data

この一覧はexhaustiveではない。未知tagが現れる前提で作る。

---

## 16. Descriptor — modern Photoshop semanticsの汎用object表現

多くのmodern tagged blocksは固定binary structを直接持つのではなく、**Action Descriptor形式**を使う。

概念:

```text
Descriptor
  name: Unicode string
  classID
  item_count
  repeated:
    key
    type (OSType)
    typed value
```

代表的type:

- `Objc` — nested Descriptor
- `VlLs` — List
- `doub` — Double
- `UntF` — Unit Float
- `TEXT` — Unicode String
- `enum` — Enumerated
- `long` — Integer
- `comp` — 64-bit integer
- `bool` — Boolean
- `type` / `GlbC` — Class
- `alis` — Alias/path-like data
- `tdta` — Raw Data
- reference object families

Unit Floatには:

- angle
- density
- distance
- percent
- pixel

などのunit keyがある。

### 16.1 なぜ重要か

Text、Smart Object、Shape/Stroke、Effects、Artboardなどを将来native変換したい場合、4-character outer tagだけ見ても足りない。

```text
tag key
 -> descriptor
 -> nested keys/types/units
 -> Photoshop semantic object
```

まで読む必要がある。

逆にFIRST_USABLEでnative解釈しないなら、outer tag検出 + safe raster fallbackでもよい。

---

## 17. Image Data — 最後のmerged/composite

第5セクション。

```text
uint16 compression
composite pixel data
```

pixel dataはplanar order:

```text
RRR...
GGG...
BBB...
...
```

compression:

- Raw
- RLE
- ZIP
- ZIP with prediction

これは**document composite**であり、Layer Info内のper-layer channel dataとは別物。

### 17.1 compositeを「正解oracle」と呼び切れない理由

compositeはPhotoshopが保存したreferenceとして非常に有用だが:

- Maximize Compatibility設定
- color management
- Photoshop version
- HDR / unsupported color mode
- embedded profile / working space
- transparency handling

などの条件を固定せず、別rendererの結果とraw pixel equalityだけで意味論の正しさを断定するのは危険。

ただしfixture validationでは、同一PSD内のstored compositeを「保存時Photoshop resultに近いreference」として比較する価値は高い。

---

## 18. PSD と PSB の差

PSBは「別の意味論」ではなく、主に巨大documentを扱うためbinary field幅が拡張された同系統format。

主要差:

| 領域 | PSD | PSB |
|---|---:|---:|
| Header version | 1 | 2 |
| max dimension | 30,000 | 300,000 |
| Layer/Mask section length | 4 bytes | 8 bytes |
| Layer Info length | 4 bytes | 8 bytes |
| per-channel data length | 4 bytes | 8 bytes |
| RLE scanline byte counts | 2 bytes | 4 bytes |
| specific tagged-block length | 4 bytes | 一部8 bytes |

PSBでは`LMsk`, `Lr16`, `Lr32`, `Layr`, `Mt16`, `Mt32`, `Mtrn`, `Alph`, `FMsk`, `lnk2`, `FEid`, `FXid`, `PxSD`等に8-byte length ruleがある。

**parserで `if extension == ".psb"` のような外部情報だけに依存せず、header versionをparse contextにする。**

---

## 19. 16-bit / 32-bit layer info

Adobe仕様では`Layr`, `Lr16`, `Lr32`というAdditional Layer Information keyがあり、Layer Info形式を持つ。

そのため「top-level Layer Infoだけ見れば全depthで十分」と決め打ちしない。

`psd-tools`もこれらを:

- `Tag.LAYER = b"Layr"`
- `Tag.LAYER_16 = b"Lr16"`
- `Tag.LAYER_32 = b"Lr32"`

として定義している。

PSD2Fusion FIRST_USABLEは8-bit RGB/RGBAを主対象にしているので直ちに全対応は不要だが、将来16/32-bitへ拡張する際のparse pathとして認識しておく。

---

## 20. Layer order — raw storageとAPI orderを分ける

「file record order」「Photoshop UIのforeground/background」「parser high-level API order」を混同しない。

`psd-tools` 1.18.0 high-level APIは、iteration orderを:

```text
background -> foreground
```

と明記している。

PSD2Fusionはcompilerが必要とするcanonical orderへ**parser adapterで一度だけnormalize**し、その後のcompilerがraw library orderに依存しない設計が安全。

必ず:

- raw record index
- same-parent sibling index
- normalized compositing order

を必要に応じて区別する。

---

## 21. Visibility — pixelの有無とは別

LayerRecord flagsにvisibility stateがある。

hidden layerも通常はrecord/channel/tag dataを持つ。

したがって:

```text
hidden
!=
absent
!=
no pixels
```

PSD2Fusionでhidden layerをgraphから省略する場合でも、manifest/IRから消さず「存在したが非表示」と記録する方がsemantic fidelityが高い。

parent group visibilityもeffective visibilityへ影響するため:

- own visibility
- effective visibility

を分ける。

---

## 22. 「1 layer」の実体を展開するとこうなる

Photoshop UIで1つに見えるlayerが、binary上では次の断片へ分散する。

```text
LayerRecord
  ├─ bbox
  ├─ channel descriptors
  ├─ blend mode
  ├─ overall opacity
  ├─ clipping flag
  ├─ flags
  └─ extra data
      ├─ mask metadata
      ├─ blending ranges
      ├─ legacy name
      └─ tagged blocks
          ├─ Unicode name
          ├─ ID
          ├─ text / shape / effects / smart object...
          └─ advanced blending...

Later in LayerInfo:
  └─ ChannelImageData
      ├─ color plane 0
      ├─ color plane 1
      ├─ color plane 2
      ├─ transparency
      ├─ pixel mask
      └─ real mask
```

つまり「layer」を扱うhigh-level APIは、この分散データを一つのobjectへ再構成している。

---

## 23. 「見た目」を作る情報も複数階層に分かれる

概念的に:

```text
source pixels / vector / text / smart object
        |
fill opacity
        |
layer effects / shape semantics
        |
pixel mask + vector mask
        |
layer opacity
        |
blend mode / Blend If / advanced flags
        |
clipping relationship
        |
group isolation / pass-through / group mask / group opacity
        |
adjustment layers and sibling backdrop
        |
document color management
        |
final composite
```

実際のPhotoshop compositorはさらに複雑だが、最低限「pixel alpha × opacityしてMerge」だけでは一般PSDを再現できない理由はここにある。

---

## 24. PSD2Fusion semantic IRへの直接的な要求

現行`ARCHITECTURE.md`の「PSD semantic IRを唯一のsemantic source of truthにする」方針は、PSDのbinary構造から見ても妥当。

最低限、IRは次を保持できる形がよい。

### Document

- source identity / hash
- PSD/PSB version
- canvas width/height
- depth
- color mode
- profile/resource metadata summary
- stored composite availability/provenance
- parser/version provenance

### Layer identity / structure

- deterministic internal ID
- raw `lyid` if present
- Unicode name + legacy name
- raw record index
- parent ID
- sibling order
- kind
- group divider/type provenance

### Geometry / pixels

- document-space bbox
- channel inventory
- pixel source/materialized asset provenance
- out-of-canvas boundsを保持

### Compositing

- raw blend key + canonical blend
- overall opacity
- fill opacity + provenance
- own/effective visibility
- clipping relationship
- group pass-through/isolation
- Blend If presence
- advanced blending flags

### Mask

- user pixel mask metadata + pixels
- vector mask path/flags
- real/combined mask
- group mask scope

### Extended semantics

- text
- shape/stroke
- smart object / linked source
- adjustment/fill
- effects
- artboard/other modern features
- unknown tagged-block inventory

### Capability / loss

各semanticに:

- `native`
- `reconstructed`
- `selectively-baked`
- `flattened`
- `rejected`
- `unknown`

を付け、理由とsource evidenceを残す。

---

## 25. Parser boundaryで守るべきinvariants

### P0 — length-safe

すべてのlength-delimited section/blockをend-offsetで管理する。

```text
end = start + declared_length
read known fields
skip/preserve unknown remainder
assert current <= end
seek end including required padding
```

「知っているfield数」ではなくdeclared lengthを境界にする。

### P0 — version-aware

PSD/PSB差をparse contextで扱う。

### P0 — unknown-preserving

未知tag/resourceを黙って捨てない。

少なくとも:

```text
scope
signature
key/id
length
raw-preserved? yes/no
```

をinventoryへ残せると強い。

### P0 — structure before rendering

tree、identity、order、clipping、group、mask、advanced flagsを先にsemantic objectへし、その後にpixel materialize / Fusion compileする。

### P0 — no name identity

layer nameはidentityに使わない。

### P0 — raw + canonical

blend mode、tag、kind等は、Fusion向けcanonical valueだけでなくraw PSD representation/provenanceを保持する。

### P1 — composite/reference separation

stored document composite、psd-tools rasterization、Photoshop実機render、Fusion renderを別originとして記録する。

---

## 26. よくある誤解と正しい理解

### 誤解1: PSDはPNGの束

**誤り。** per-layer pixelsはchannel planesとして圧縮保存され、metadata/semanticsは別領域へ分散する。

### 誤解2: LayerRecordを順に読めばgroup treeが出る

**誤り。** low-levelはflat list。`lsct`等のdividerからtreeを復元する。

### 誤解3: alpha = mask

**誤り。** layer transparency、pixel mask、real mask、vector mask、document alphaは別。

### 誤解4: hidden layerは無視してよい

出力graphから非表示にすることと、semantic modelから消すことは別。

### 誤解5: opacityは1種類

overall opacityとfill opacityは別。

### 誤解6: clippingはmask channel

**誤り。** sibling relationship + base alphaを使うcompositing semantics。

### 誤解7: groupはFusion Groupに入れればよい

**誤り。** Photoshop groupはPass Through/isolatedでbackdrop評価が変わる。

### 誤解8: textは文字列だけ読めばeditable

**誤り。** `TySh` descriptor、transform、warp、bounds、`Txt2` engine data、font/style/layout差がある。

### 誤解9: Smart Objectは画像layer

**不十分。** embedded/linked source、transform、descriptor、filters等を持つsemantic object。

### 誤解10: merged compositeがあるからlayer parserは不要

PSD2Fusionの目的がeditable graphなら不可。さらにAdobe仕様ではcompatibility設定によりcompositeが存在しない場合がある。

---

## 27. PSD2Fusionでの段階的対応モデル

完全対応を一気に目指す必要はない。

ただしparser/IRは「対応していないsemanticを知らないふりをしない」方がよい。

### Tier A — current FIRST_USABLE

- 8-bit RGB/RGBA
- pixel layers
- bbox/order/visibility
- common blend + opacity
- nested groups
- Pass Through / isolated
- clipping chains
- raster fallback

### Tier B — fidelity expansion

- pixel masks
- vector masks
- fill opacity
- Blend If detection/limited reconstruction
- group mask
- more blend modes
- stored-composite comparison harness

### Tier C — editable semantic layers

- Text -> Text+
- shape/vector path
- solid/gradient fill
- adjustment layer mappings
- layer effects

### Tier D — complex document objects

- Smart Object embedded/linked extraction
- smart filters
- artboards
- advanced knockout/interior/transparency-shape semantics
- 16/32-bit / HDR / color-management parity

重要なのはTier A実装中にTier Dを実装することではなく、**Tier Dの存在をIR/parser boundaryで破壊しないこと**。

---

## 28. 基礎fixtureで検証すべきPSD群

parser理解を実装へ固定するには、見た目ではなくbinary/semantic featureを1個ずつ含む小fixtureが有効。

1. 1 pixel layer / RGB / 8-bit
2. transparent pixel layer (`-1`)
3. negative/out-of-canvas bbox
4. hidden layer
5. duplicate layer names + Unicode name
6. nested group (`lsct`)
7. Pass Through group
8. isolated group
9. single clipping member
10. multi-member clipping chain
11. pixel mask (`-2`)
12. pixel + vector / real mask (`-3`)
13. Fill Opacity (`iOpa`)
14. Blend If ranges
15. Text (`TySh` + `Txt2`)
16. Shape (`vmsk` + `vstk`/`vscg`/`vogk`)
17. layer effects (`lfx2`)
18. Smart Object embedded/linked
19. 16-bit (`Lr16`)
20. 32-bit (`Lr32`)
21. PSB version 2
22. file with unknown tagged block preserved/skipped safely

各fixtureで:

```text
raw structure
-> parser model
-> semantic IR
-> capability decision
-> generated graph or controlled fallback
```

を比較できるようにする。

---

## 29. Binary inspectorを将来作るなら

PSD2Fusion本体とは分離して、debug用に次を出せるread-only inspectorがあると強い。

```text
Document
  header
  sections + offsets + declared lengths
  image resources
  layer records
    bbox
    channel ids + stored lengths
    blend/opacity/clipping/flags
    mask metadata
    blending range presence
    tagged block key/length
  channel data compression
  document tagged blocks
  merged image compression
```

JSON例:

```json
{
  "version": 1,
  "size": [1920, 1080],
  "depth": 8,
  "color_mode": "RGB",
  "layers": [
    {
      "raw_index": 0,
      "name": "Title",
      "bbox": [100, 200, 900, 400],
      "channels": [0, 1, 2, -1],
      "blend_key": "norm",
      "opacity": 255,
      "clipping": 0,
      "tags": ["luni", "lyid", "TySh", "Txt2"]
    }
  ]
}
```

これはFusion conversionの責務ではなく、parser/debug evidenceを短縮するtoolにする。

---

## 30. 仕様の限界 / 未文書化領域

Adobe公開PSD binary specificationは現在も基礎一次資料だが、modern Photoshop内部の全tag/descriptor semanticを完全には公開していない。

実際、`psd-tools` current sourceにも`Undocumented`と明示されたtagが複数ある。

したがって「Adobe仕様書にない = PSDに存在しない」ではない。

安全な戦略:

1. Adobe public specでknown structureを読む
2. current upstream parser sourceで実在tagを確認
3. unknownはlength-safeにpreserve/skip
4. Photoshop実機で見た目意味を必要時probe
5. 変換対応はcapability decisionとして明示

---

## 31. PSD2Fusionに対する最終判断

### CONFIRMED

- PSD/PSBはbig-endian。
- 5 major sectionsで構成される。
- Headerは26 bytes固定。
- Layer InfoはLayerRecord群の後にChannel Image Data群を持つ。
- per-layer pixelsはchannel単位。
- group hierarchyはflat records + section divider tagsから復元される。
- Additional Layer Informationは4-character keyの拡張block。
- modern featuresの多くはDescriptorやraw engine dataを使う。
- merged/composite imageは最後のImage Dataにあり、per-layer dataとは別。
- PSD/PSBではversionと複数のlength/RLE field幅が異なる。
- `psd-tools` 1.18.0 high-level iterationはbackground -> foreground。
- `psd-tools`は`iOpa`をFill Opacityのundocumented tagとして扱う。

### INFERENCE / DESIGN CONSEQUENCE

- PSD2Fusionのsemantic IR boundaryは維持すべき。
- compilerが`psd-tools` objectへ直接依存しない現行architectureは正しい。
- unknown tagged block inventoryをIR/manifest側へ持てるようにすると、将来対応でsilent lossを減らせる。
- stored composite / psd-tools raster / Photoshop render / Fusion renderのprovenanceを分けるべき。
- 将来の「完全再現」はpixel extractionの問題より、descriptor、evaluation scope、color management、Photoshop compositor semanticsの問題になる。

---

## Sources

Primary:

- Adobe, **Photoshop File Formats Specification**  
  https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/
- Adobe Photoshop Help, **Image file formats supported in Photoshop**, checked 2026-09-01  
  https://helpx.adobe.com/photoshop/desktop/save-and-export/export-files-to-different-formats/image-file-formats-supported-in-photoshop.html

Current parser implementation/documentation checked:

- `psd-tools` 1.18.0 documentation  
  https://psd-tools.readthedocs.io/en/latest/
- `psd-tools` low-level layer/mask structures  
  https://psd-tools.readthedocs.io/en/latest/reference/psd_tools.psd.layer_and_mask.html
- `psd-tools` usage / high-level iteration order  
  https://psd-tools.readthedocs.io/en/latest/usage.html
- `psd-tools` `constants.py` / tagged block keys  
  https://github.com/psd-tools/psd-tools/blob/main/src/psd_tools/constants.py
- `psd-tools` `api/layers.py` / Fill Opacity API  
  https://github.com/psd-tools/psd-tools/blob/main/src/psd_tools/api/layers.py

Related PSD2Fusion docs:

- `ARCHITECTURE.md`
- `docs/research/02-psd-semantic-requirements.md`
- `docs/research/05-unresolved-questions-and-host-probes.md`
- `docs/research/06-architecture-implications.md`

---

## Maintenance rule

この文書は「PSDの基礎構造」のownerとする。

- Photoshop/Fusionの見た目意味論は`02-psd-semantic-requirements.md`側へ置く。
- FIRST_USABLEの実装境界は`ARCHITECTURE.md`を正本とする。
- parser実装の一時的な詳細やcurrent Goalはここへ入れない。
- 新しいtagを見つけただけでは一覧を無制限に肥大化させず、PSD2Fusionのparse/semantic判断を変えるものだけ追記する。
- Adobe public spec、current `psd-tools`、Photoshop実機で矛盾した場合は、source/version/provenanceを残してCONFLICTとして扱う。
