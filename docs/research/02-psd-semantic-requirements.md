# PSD semantic requirements

## 要求の読み方

この文書は「v1で全対応する」という仕様ではない。PSDから観測でき、対応しない場合はloss/fallbackを明示すべきsemantic inventoryである。

## Semantic requirements matrix

| 領域 | Photoshop / PSD上の意味 | `psd-tools`での取得 | 変換器が保持すべき情報 | 未対応時の明示policy |
|---|---|---|---|---|
| Document canvas | width/height、color mode、depth、profile、merged composite | `PSDImage.size/viewbox`, low-level resources | canvas、origin、bit depth、color metadata | reject / convert / bakeのどれか |
| Layer order | PSD layer recordsの順序がz-order | tree/list API | stable ID、same-parent sibling order | 順序を変えない |
| Layer bbox | `top,left,bottom,right`のcanvas座標。canvas外もあり得る | `bbox`, `left/top/right/bottom` | cropped pixelsとcanvas placementを分離 | full-canvas bakeまたはTransformで再配置 |
| Visibility | layer flagに加えparent visibilityが効く | `visible`, `is_visible()` | own visibilityとeffective visibility | hiddenをdropせずmanifestへ保持 |
| Group / nested group | section divider recordでtreeを表す | `Group`, recursive descendants | group ID、open/closed、parent、child order | flatten時はsemantic lossを記録 |
| Pass Through group | childrenがgroup外backdropへ直接blend | group `blend_mode=PASS_THROUGH` | pass-through boundary | isolated mergeと同一視しない |
| Non-Pass group | childrenを先に合成し、group resultを1画像として外へblend | blend mode取得可 | isolated subtree、group blend、group opacity | subtree bake候補 |
| Layer opacity | pixels、blend、layer effects全体に作用 | `opacity` 0..255 | layer/group opacityを別field | Merge Blendへ単純写像する範囲を限定 |
| Fill opacity | pixels/shape/textだけに作用しlayer effectsへは作用しない | raw tag `iOpa`; compositorも別値として読む | overall opacityと別field | effects未対応ならlossを報告 |
| Blend mode | layer/groupごとのblend key | `BlendMode` enum | raw PSD key＋canonical enum＋fallback | unsupported modeをNormalへ黙って落とさない |
| Clipping chain | same parentの連続する上位layerが下のbase alphaでclip | `clipping`, `clip_layers` | base ID、ordered clipped IDs、scope | independent layer maskへ短絡しない |
| Blend clipped as group | base modeをclipped stack全体へ適用するか | raw `clbl`; rendererは未実装 | boolean＋default provenance | bake/probe/reject |
| Pixel layer mask | grayscale、独自bbox、default color、disabled/density/feather等 | `mask`, `topil`, raw params | mask pixels、bbox、flags、link | bakeまたはFusion mask graph |
| Vector mask | resolution-independent path、invert/disable/link | `vector_mask`, path data | original path＋raster fallback | Fusion path変換かcontrolled rasterization |
| Pixel+vector mask |両者が共存しcombined real maskを形成 | `real=True` mask等 | componentsとcombined resultを区別 | combined bake時もcomponents lossを記録 |
| Group mask | group compositeへ作用 | group mask API | subtree output mask | childへ個別適用しない |
| Alpha channels | selection等のdocument channel。layer transparency/maskと別 | low-level channels/resources | layer alphaとdocument alphaを区別 | layer maskと混同しない |
| Effects/styles | shadow/glow/bevel/overlay等、overall/fill opacityとの相互作用 | metadataは一部、renderingは限定 | effect descriptor or baked artifact | selective bake / unsupported |
| Adjustment/fill | 下位compositeへ非破壊作用。group boundaryでscopeが変わる | layer kind/descriptor、rendering限定 | adjustment type、params、scope | subtree bake / reject |
| Text | content、transform、style runs、font | TypeLayer APIで一部取得 | editable intentとreference raster | TextPlus変換はfont/layout差をprobe |
| Shape | vector mask/origination/stroke/fill | ShapeLayer API | vector intent＋reference raster | path変換またはbake |
| Smart Object | embedded/linked、transform、filters | metadata/data accessあり | source kind、link、transform、reference render | embedded extract / linked resolve / bake |
| Advanced blending | Blend If、channel restrictions、knockout、interior/transparency shape flags | raw tagged blocks | raw semantic flags | unsupportedを検出してbake/reject |

## Tree reconstruction

PSDのgroupは名前やindentではなく`SectionDivider` (`lsct`)のopen/closed/bounding recordsで表現される。typeはopen folder、closed folder、bounding section divider等を持つ。`psd-tools`もflat layer listからstackでtreeを再構築するため、malformed dividerはedge caseになる。

**Requirement:** parser outputをそのままFusion nodeへ流さず、次を含むintermediate semantic modelを作る余地を残す。

- document-space coordinates
- stable layer/group identity
- raw sibling order
- group isolation/pass-through
- blend/opacity/fill opacity
- clipping relationship
- mask components
- unsupported semantic inventory
- provenance（raw PSD、parser version、fallback method）

Sources: [Adobe PSD File Format Specification — Layer records / Additional Layer Information](https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/), [`psd-tools` PSDImage tree reconstruction](https://github.com/psd-tools/psd-tools/blob/8d44ed0c4c2d43d935b35dff642bbc4e4f767f6d/src/psd_tools/api/psd_image.py), [`psd-tools` layer API](https://github.com/psd-tools/psd-tools/blob/8d44ed0c4c2d43d935b35dff642bbc4e4f767f6d/src/psd_tools/api/layers.py).

## Group semantics

Adobeはgroupのdefault blend modeをPass Throughと説明する。Pass Throughにはgroup自身のblending propertyがなく、childrenが外部backdropへ作用する。groupにPass Through以外を指定すると、childrenを先に合成し、group resultを単一画像として外へblendする。group内adjustment/blendの作用範囲もこの境界で変わる。

したがって、Fusionの見た目上のGroupやUnderlayへchildrenを入れるだけではsemantic mappingにならない。isolated groupにはsubtree composite、pass-throughには外部backdropを含む評価順序が必要になる。

Source: [Adobe — Layer opacity and blending](https://helpx.adobe.com/photoshop/using/layer-opacity-blending.html).

## Clipping semantics

Adobeの定義ではbottom/base layerの非透明部分が、その上の連続layerをrevealする。複数clipped layerはsuccessiveでなければならない。さらにbaseのopacity/mode、および`Blend Clipped Layers As Group`がstack全体のblend scopeに影響する。

**CONFLICT:** `psd-tools`はclipping flagとchainを正しく露出するが、compositor sourceには`BLEND_CLIPPING_ELEMENTS`処理がTODOとして残る。したがって`layer.composite()`結果をPhotoshop clipping parityの正解画像として使えない。

Sources: [Adobe — Clipping masks](https://helpx.adobe.com/photoshop/using/revealing-layers-clipping-masks.html), [`psd-tools` layer clipping API](https://github.com/psd-tools/psd-tools/blob/8d44ed0c4c2d43d935b35dff642bbc4e4f767f6d/src/psd_tools/api/layers.py), [`psd-tools` compositor](https://github.com/psd-tools/psd-tools/blob/8d44ed0c4c2d43d935b35dff642bbc4e4f767f6d/src/psd_tools/composite/composite.py).

## Opacity and alpha

- PSD layer recordのopacity byteは0=transparent、255=opaque。
- Photoshop overall opacityはpixelsとeffectsを含むlayer結果へ作用する。
- Fill opacityはpixels/shape/textへ作用するがeffectsへは作用しない。
- layer transparency、pixel mask、vector mask、document alpha channelは別概念。
- maskはwhite reveal、black conceal、gray partial。ただしraw mask flags/default color/inversionを考慮する。

Sources: [Adobe PSD format](https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/), [Adobe — opacity](https://helpx.adobe.com/photoshop/using/layer-opacity-blending.html), [Adobe — layer masks](https://helpx.adobe.com/photoshop/desktop/create-masks/layer-masks/add-layer-masks.html), [Adobe — vector masks](https://helpx.adobe.com/photoshop/using/masking-layers-vector-masks.html), [Adobe — alpha channels](https://helpx.adobe.com/photoshop/using/saving-selections-alpha-channel-masks.html).

## `psd-tools` capability boundary

調査時点（2026-08-31）のmain `8d44ed0c4c2d43d935b35dff642bbc4e4f767f6d`はversion `1.18.0`、MIT、Python `>=3.10`。以下のsource参照はこのcommitへpinする。

### Parser/APIで得られるもの

- layer/group tree、parent、descendants、kind
- visibility、opacity、blend mode、bbox/offset
- clipping flagとclip chain
- pixel mask、vector mask、combined mask
- Type/Shape/SmartObject/Adjustmentのclass・descriptor/raw tagged blocks
- raw blend/effect/section divider metadata

### Rendererで完全ではないもの

- text font/layout rendering
- 多くのlayer effects
- adjustment layerの多く
- `Blend Clipped Layers As Group` (`clbl`)
- blend interior elements (`infx`)
- pass-through＋knockout等のadvanced interaction
- Photoshopと同一のLAB/Duotone/multichannel/color management

公式usage docsも、保存後の見た目が異なる可能性、effects/adjustments/text等の制約を説明している。

**Conclusion:** `psd-tools`はsemantic extractionとfallback rasterizationの部品候補。Photoshop visual parityのoracleではない。

Sources: [`psd-tools` usage](https://github.com/psd-tools/psd-tools/blob/8d44ed0c4c2d43d935b35dff642bbc4e4f767f6d/docs/usage.rst), [API docs](https://psd-tools.readthedocs.io/en/latest/reference/psd_tools.api.layers.html), [compositor source](https://github.com/psd-tools/psd-tools/blob/8d44ed0c4c2d43d935b35dff642bbc4e4f767f6d/src/psd_tools/composite/composite.py), [project metadata](https://github.com/psd-tools/psd-tools/blob/8d44ed0c4c2d43d935b35dff642bbc4e4f767f6d/pyproject.toml).

## Capability policy required before implementation

各semanticに `native`, `reconstructed`, `selectively-baked`, `flattened`, `rejected`, `unknown` のいずれかを割り当て、変換manifestへ残すべきである。黙ってNormal、visible、full opacityへfallbackする実装はparity failureを発見できないため禁止候補。
