# PSD2Fusion implementation research

調査日: 2026-08-31  
対象ホスト: Windows / DaVinci Resolve `21.0.3.7`（Free/Studio editionは未確認）  
状態: **設計判断前のEvidence収集。最終architectureは未決定。**

## この調査の目的

現在の実装案を正当化するのではなく、PSDの意味論、Fusionの表現能力、Resolve純正PSD Importer、既存実装を独立に確認し、次の設計レビューで前提から見直せる状態を作る。

開始時点で `D:\Documents\PSD2Fusion` は空かつGit管理外で、repo固有の `AGENTS.md`・README・仕様・既存実装は存在しなかった。このため本調査資料が最初のrepo成果物であり、製品実装やscaffoldは含まない。

## Evidenceラベル

- **CONFIRMED**: 一次資料、対象commitの実コード、またはこのホストの読み取り専用観測で確認。
- **INFERENCE**: 複数の確認済み事実からの設計上の推論。事実と分離して記載。
- **HOST-PROBE**: Resolve/Photoshop実機で未確認。最終仕様に昇格させない。
- **CONFLICT**: 文書、実装、version間に不一致がある。

Adobe PSD File Format Specificationはデータ構造を規定するが、仕様書自身が機能の見た目上の解釈は説明しないと明記している。したがって、byte/tagの存在はPSD仕様、Photoshop上の意味はAdobe Helpまたは実機、Resolveへの変換はBlackmagic資料またはhost probeを根拠に分離した。

## 成果物

1. [Prior-art comparison](01-prior-art-comparison.md)
2. [PSD semantic requirements](02-psd-semantic-requirements.md)
3. [Fusion representation capabilities](03-fusion-representation-capabilities.md)
4. [Native importer observations](04-native-importer-observations.md)
5. [Unresolved questions and host probes](05-unresolved-questions-and-host-probes.md)
6. [Architecture implications](06-architecture-implications.md)

## 現時点の最重要結論

- PSDの「layerを画像として取り出せる」ことと「Photoshopの合成意味を再現できる」ことは別問題。
- `Group` は単なるfolderではない。`Pass Through` とisolated groupではbackdropへの作用範囲が変わる。
- clipping maskは単純な各layer alpha maskではない。連続sibling、base alpha、base blend/opacity、`Blend Clipped Layers As Group` が関与する。
- `psd-tools` はsemantic parserとして有力だが、rendererはPhotoshop parity oracleではない。
- Fusion `Merge` は多数のblend/operator、opacity相当、位置、effect maskを表現できるが、Fusion Group/UnderlayはPhotoshop group compositing semanticsを自動では与えない。
- Blackmagic公式文書は純正Importerのlayer/Merge生成を確認する一方、group、clipping、mask、effects等の変換を説明していない。
- 現行hostでは製品editionを読み取りだけで確定していないため、Studio-only multilayer機能の適用可否もprobe metadataで確定する。
- Resolve 20.1.1、20.3.1、21.0.3でPSD import修正が続いており、Importer挙動はversion-pinned probeなしに設計前提へできない。
- PNG分解、PSD直参照、selective bakingを含むhybridは、それぞれ別の失敗モードを持つ。次の設計レビューで明示的に選ぶ必要がある。

## 調査していないこと

- 製品architectureの決定
- 製品コード、CLI/UI、package構成の作成
- 現在開いているResolve projectへのPSD importやnode追加
- Photoshop/Resolve間のpixel parity合否閾値の確定
- 外部実装からのコード移植
