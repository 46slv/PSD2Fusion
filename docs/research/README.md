# PSD2Fusion implementation research

初回調査日: 2026-08-31  
基礎構造追補: 2026-09-01  
対象ホスト: Windows / DaVinci Resolve `21.0.3.7`（初回調査時点）  
状態: **Evidence / research baseline。現行の製品architecture authorityはroot `ARCHITECTURE.md`。**

## この調査の目的

PSDのbinary structureと意味論、Fusionの表現能力、Resolve純正PSD Importer、既存実装を独立に確認し、PSD2Fusionの設計・実装判断を根拠付きで行える状態を維持する。

このfolderはarchitectureそのものではなく、その判断を支えるEvidence層である。FIRST_USABLEの現在の実装境界はroot `ARCHITECTURE.md`を正本とする。

歴史的には、2026-08-31の初回調査開始時点でローカル対象directoryは空かつGit管理外であり、本調査群が最初のrepo成果物だった。その後architecture freezeとFIRST_USABLE実装が進んでいるため、初回文書内の「未決定」「未実装」等の記述は各文書の調査時点にscopeされる。

## Evidenceラベル

- **CONFIRMED**: 一次資料、対象commitの実コード、または対象hostの読み取り専用観測で確認。
- **INFERENCE**: 複数の確認済み事実からの設計上の推論。事実と分離して記載。
- **HOST-PROBE**: Resolve/Photoshop実機で未確認。最終仕様に昇格させない。
- **CONFLICT**: 文書、実装、version間に不一致がある。

Adobe PSD File Format Specificationはデータ構造を規定するが、仕様書自身が機能の見た目上の解釈は説明しないと明記している。したがって、byte/tagの存在はPSD仕様、Photoshop上の意味はAdobe Helpまたは実機、Resolveへの変換はBlackmagic資料またはhost probeを根拠に分離する。

## 成果物

0. [PSD file format foundations](00-psd-file-format-foundations.md) — PSD/PSBの5 section、LayerRecord/channel、tagged block、Descriptor、PSB差、parser invariants
1. [Prior-art comparison](01-prior-art-comparison.md)
2. [PSD semantic requirements](02-psd-semantic-requirements.md)
3. [Fusion representation capabilities](03-fusion-representation-capabilities.md)
4. [Native importer observations](04-native-importer-observations.md)
5. [Unresolved questions and host probes](05-unresolved-questions-and-host-probes.md)
6. [Architecture implications](06-architecture-implications.md)

## 現時点の最重要結論

- PSD/PSBは「RGBA画像のlayer stack」ではなく、document resources、flat LayerRecord群、別置きのchannel pixel data、mask/blending ranges、4-character tagged blocks、Descriptor、stored compositeから成る編集状態container。
- PSDの「layerから画像を取り出せる」ことと「Photoshopの合成意味を再現できる」ことは別問題。
- low-level group hierarchyはrecursive treeではなく、flat layer recordsと`lsct`等のsection dividerから復元される。
- `Group` は単なるfolderではない。`Pass Through` とisolated groupではbackdropへの作用範囲が変わる。
- clipping maskは単純な各layer alpha maskではない。連続sibling、base alpha、base blend/opacity、`Blend Clipped Layers As Group` が関与する。
- layer transparency、pixel mask、real/combined mask、vector mask、document alphaは別概念。
- overall opacityとfill opacityは別。`psd-tools` current sourceはfill opacityをundocumented `iOpa` tagged blockとして扱う。
- Text、Smart Object、Shape/Stroke、Effects、Artboard等のmodern featureはTagged Block内のDescriptor/raw engine dataへ広く分散する。
- `psd-tools` はsemantic parserとして有力だが、rendererはPhotoshop parity oracleではない。
- Fusion `Merge` は多数のblend/operator、opacity相当、位置、effect maskを表現できるが、Fusion Group/UnderlayはPhotoshop group compositing semanticsを自動では与えない。
- Blackmagic公式文書は純正Importerのlayer/Merge生成を確認する一方、group、clipping、mask、effects等の完全な変換契約を説明していない。
- Resolve Importer挙動はversion-pinned host probeなしに設計前提へ固定しない。
- unknown resource/tagは存在前提で、length-safeにskip/preserveし、silent semantic lossを避ける。

## Researchと実装の境界

- binary/file-format foundations → `00-psd-file-format-foundations.md`
- Photoshop semantic inventory → `02-psd-semantic-requirements.md`
- Fusion表現能力 → `03-fusion-representation-capabilities.md`
- host facts → `04-*`, `05-*`, `docs/host-smoke-handoff.md`
- durable product architecture → root `ARCHITECTURE.md`
- current Goal / stopping condition → current task/Goal authority

新しい知見は、一番近いownerへだけ追記し、同じ説明を複数文書へ複製しない。
