# Prior-art comparison

## 比較表

| 実装 | 入力・中間表現 | Fusion生成経路 | group / clipping | blend / opacity / mask | 状態・license | 再利用可能なEvidence |
|---|---|---|---|---|---|---|
| `NUROKU/DaVinciResolve_PSDFusionGenerator` | `psd-tools`で非group layerをPNG化しJSON metadata化 | Generator用`.setting`を生成 | groupは選択UI用metadata/heuristic。`include_clip=False`でclipped layerを除外 | blend、opacity、mask転送なし | MIT、2022、Resolve 18.0.3前提 | bbox→normalized Merge Center、Loader/Merge/Generator serialization |
| `bixcl/PSDconverter` | raster/shape/smart objectをfull-canvas PNG、任意でtextをTextPlus | `.comp` text生成 | recursionはするがFusion groupを作らず、READMEのgroup flatten分岐は実質dead | 6 blend modes、Merge Blend=opacity。mask/effects/adjustmentなし | READMEはMIT主張だがrepoにLICENSE fileなし | `.comp`生成、Transform/Merge chain、editable textとraster fallbackの分岐 |
| `34j/DaVinciResolve.PSDGeneratorBuilder` | `34j/psd2pngs`依存 | typed Lua-like serializerからLoader/Mergeを生成予定 | 実装未完 | placeholder/undefined値が残る | MIT、WIP / NOT WORKING | serializerの小さな試作のみ。製品ロジック再利用不可 |
| `hos_PSDLayers.eyeonscript` | Fusion LoaderのPSD channelを直接選択 | Loader複製＋Merge、またはImagePlane3D/Merge3D | PSD channel列挙。semantic group/clippingは扱わない | Loader設定を複製。blend再構成の証拠なし | 2011、license不明 | historical FusionでPSD layer channelへ直接アクセスしたEvidence。Resolve 21互換性はHOST-PROBE |
| Aaron Carrillos “PSD Splitter” sample | `psd-tools` metadata + native PSD Loader | Fusion Python APIでLoader/Merge生成 | folder metadataをflatten。nested groupでblend offsetが崩れると自記 | 多数のblendとopacityをMergeへ写像 | code sample、license不明、snippetに構文上の疑義 | direct-PSD + semantic metadataのhistorical pattern。現行互換性はHOST-PROBE |
| `NUROKU/PSDRexa` | 明示domain tree + full-canvas PNG | prebuilt `.drb` templateをResolve APIで配置・Loader差替え | nested parent linkは保持するがgeneric PSD graphではない。clipping除外 | Pillow合成はNormal/Multiplyのみ | GPL-3.0、2025 | stable ID/domain tree、template駆動、Resolve API wiring。GPL制約あり |

## 1. NUROKU/DaVinciResolve_PSDFusionGenerator

**CONFIRMED — commit `0b2181699ee4406fcf1e4971f289b2a0ea9066e1`, MIT.**

処理は `main.py` → `PsdDivider.execute()` → `SettingCreator.execute()`。`PsdDivider`は`PSDImage.open()`後、`psd.descendants(include_clip=False)`を走査し、各非group layerを`layer.topil()`でPNG保存する。layer名、親group、visible、width/height、offset、normalized centerをJSONへ書く。

`SettingCreator`はgroupごとにPNG sequence LoaderとComboControlを作り、選択layerに応じて`ClipTime`とMerge Centerを切り替える。最後はBackground canvas＋2D Merge chain＋MediaOutを`GroupOperator`で包み、Edit Generator用`.setting`へserializeする。

設計上の意味:

- groupはPhotoshop compositing boundaryではなく、UI selectorの分類として使われる。
- nested groupは子数を数えるheuristicで、Pass Through/isolated semanticsはない。
- clipped layersは意図的に列挙対象外。
- blend mode、layer/group opacity、pixel/vector maskを移送しない。

Sources: [entrypoint](https://github.com/NUROKU/DaVinciResolve_PSDFusionGenerator/blob/0b2181699ee4406fcf1e4971f289b2a0ea9066e1/main.py#L1-L25), [PSD extraction](https://github.com/NUROKU/DaVinciResolve_PSDFusionGenerator/blob/0b2181699ee4406fcf1e4971f289b2a0ea9066e1/PSDFusionGenerator/PSDDivider/psd_divider.py#L17-L121), [setting generation](https://github.com/NUROKU/DaVinciResolve_PSDFusionGenerator/blob/0b2181699ee4406fcf1e4971f289b2a0ea9066e1/PSDFusionGenerator/SettingCreator/setting_creator.py#L19-L196), [template](https://github.com/NUROKU/DaVinciResolve_PSDFusionGenerator/blob/0b2181699ee4406fcf1e4971f289b2a0ea9066e1/PSDFusionGenerator/SettingCreator/template_const.py#L25-L125), [license/usage](https://github.com/NUROKU/DaVinciResolve_PSDFusionGenerator/blob/0b2181699ee4406fcf1e4971f289b2a0ea9066e1/README.md#L163-L200).

## 2. bixcl/PSDconverter

**CONFIRMED — commit `5645c270d725357513604037d23185cefc654b58`. LicenseはREADMEにMIT記載があるが、cloneにLICENSE fileがなく、再利用前の確認が必要。**

V2 extractorはvisible groupをrecursive traversalし、TypeLayerをtext、Pixel/Shape/SmartObjectをrasterとして保持する。出力時、rasterは`layer.composite()`または`topil()`をPSD全体サイズcanvasへ`left/top`で貼りPNG化する。textはTextPlusまたはPNG rasterizationを選ぶ。

graphはMasterCanvas Background、各layerのLoader/TextPlus、Transform、Merge chain、MediaOut。`NORMAL/MULTIPLY/SCREEN/OVERLAY/SOFT_LIGHT/HARD_LIGHT`だけをApplyModeへmapし、layer opacityをMerge Blendへ入れる。

**CONFLICT:** READMEはgroups flattenedと説明する一方、sourceの`is_group`分岐へ到達するlayer recordが生成されず、実際にはchildrenを平坦なz-orderで流す。この差はREADMEを仕様根拠にできないことを示す。

Sources: [README claims and limitations](https://github.com/bixcl/PSDconverter/blob/5645c270d725357513604037d23185cefc654b58/README.md#L226-L359), [layer extraction](https://github.com/bixcl/PSDconverter/blob/5645c270d725357513604037d23185cefc654b58/source-code/V2/PSDconverterV2.py#L710-L775), [raster export](https://github.com/bixcl/PSDconverter/blob/5645c270d725357513604037d23185cefc654b58/source-code/V2/PSDconverterV2.py#L776-L819), [graph generation](https://github.com/bixcl/PSDconverter/blob/5645c270d725357513604037d23185cefc654b58/source-code/V2/PSDconverterV2.py#L545-L708).

## 3. 34j/DaVinciResolve.PSDGeneratorBuilder

**CONFIRMED — commit `85fd7386f8dc9ae4c6a3c4ff38636f513632385c`, MIT, WIP.**

`setup.py`はGit dependency `34j/psd2pngs`を取り込み、PSD→PNGを前提にする。`generate_settings.py`はundefined variable、更新されない`last_merge`、placeholder expressionが残り、完成した変換器ではない。typed Lua serializerも全scalarを引用しarray handlingがなく、Fusion serializerの要件を満たす証拠はない。

Sources: [setup](https://github.com/34j/DaVinciResolve.PSDGeneratorBuilder/blob/85fd7386f8dc9ae4c6a3c4ff38636f513632385c/setup.py#L8-L20), [unfinished generator](https://github.com/34j/DaVinciResolve.PSDGeneratorBuilder/blob/85fd7386f8dc9ae4c6a3c4ff38636f513632385c/psd_generator_builder/generate_settings.py#L11-L78), [serializer](https://github.com/34j/DaVinciResolve.PSDGeneratorBuilder/blob/85fd7386f8dc9ae4c6a3c4ff38636f513632385c/psd_generator_builder/typed_lua_table_serializer.py#L9-L54).

## 4. Direct-PSD implementations

`hos_PSDLayers.eyeonscript`はselected PSD Loaderの`PSDFormat.Layer` ComboControl文字列を列挙し、Loader設定をsave/loadしてlayerごとのLoaderを複製する。これは2011年当時のFusionでPSD fileを直接参照したままlayer channelを選べた実例だが、group/blend/clipping parityやResolve 21互換性の実例ではない。配布zipのimmutable code snapshot/hashも未取得のため、code reuseではなくhistorical evidenceに限定する。

Aaron CarrillosのPSD Splitter sampleは`psd-tools` metadataとnative PSD Loaderを組み合わせ、Fusion APIでMerge ApplyMode/Blendを設定する。direct source linkを保つpatternを示す反面、sample自身がnested groupでblend offsetが崩れると警告しており、folder flatteningの限界を実証する。license不明・immutable snapshotなし・snippet上の疑義があるためコード移植対象ではなくhistorical architecture evidenceとしてのみ扱う。現行Resolve compatibilityはHOST-PROBE。

Sources: [HoS article/download](https://www.svenneve.com/?p=480), [PSD Splitter sample](https://hyprovisual.com/coding/).

## 5. Adjacent implementation: PSDRexa

**CONFIRMED — commit `d5720e092cef3472fd4438a9127244d9d01c5053`, GPL-3.0.**

generic PSD parity converterではなくcharacter asset exporter。`PsdRepository`はparent link付きdomain tree、visible、opacity、offset、size、blend metadataを保持する。出力はfull-canvas PNGで、Pillow合成はNormal/Multiplyだけ。prebuilt `.drb` templateをMedia Poolへ入れ、Resolve scriptingでFusion compのLoader pathを差し替える。

再利用可能なのは「parser objectを直接serializeせず、stable domain modelを挟む」「prebuilt templateを差し替えて使う」という設計idea。sourceはtemplate使用を示すが、host validationの範囲は不明。GPL-3.0なので、コード再利用はcopyleft方針を先に決める必要がある。

Sources: [README/license](https://github.com/NUROKU/PSDRexa/blob/d5720e092cef3472fd4438a9127244d9d01c5053/README.md#L1-L68), [domain tree](https://github.com/NUROKU/PSDRexa/blob/d5720e092cef3472fd4438a9127244d9d01c5053/PSDRexa/Repository/PsdRepository.py#L29-L142), [limited compositor](https://github.com/NUROKU/PSDRexa/blob/d5720e092cef3472fd4438a9127244d9d01c5053/PSDRexa/Domain/DTO/CompositedImage.py#L62-L110), [Resolve/template path](https://github.com/NUROKU/PSDRexa/blob/d5720e092cef3472fd4438a9127244d9d01c5053/PSDRexa/DataStore/CharacterFusionDataStore.py#L15-L68).

## Cross-implementation findings

### 確認できた共通pattern

1. PSD parse、raster extraction、Fusion serializationは分離できる。
2. layer bboxをfull-canvasへ貼る方式と、cropped image＋Fusion positionで戻す方式がある。
3. `.setting`、`.comp`、Resolve/Fusion live APIの3経路が実際に使われている。
4. historical Fusion実装ではdirect PSD Loaderが可能だった。現行Resolve 21の同等性はHOST-PROBE。

### どの実装も解いていない問題

- Pass Throughとisolated groupの完全な再現
- nested group opacity/blend boundary
- clipping chain＋`Blend Clipped Layers As Group`
- pixel mask＋vector mask＋density/feather/link
- Photoshop layer effects、Blend If、knockout、fill opacity
- color profile、16/32bpc、premultiplicationを含む自動parity gate

### 再利用方針への含意

- MIT repoも、semantic behaviorを確認せずconverter本体へ移植しない。
- license不明sampleはidea/evidenceに限定する。
- GPL-3.0のPSDRexa codeを採用する場合は製品license判断が先。
- serializerやlayoutは再利用候補になり得るが、Photoshop semantic modelとは別moduleとして評価する。
