# `a.psd` PSD -> semantic IR -> Fusion graph audit

Status: diagnosis only; converter code was not changed.

## Scope and source

- PSD: `D:\Downloads\a.psd`
- SHA-256: `574d8a6511b2aabe744835d81ed76c8fc8ffd0c9c5678f3359e8eda10f9174db`
- Parser: `psd-tools 1.18.0`
- Canvas: `2304 x 1296`, RGB, 8-bit
- Repository HEAD: `fada240cf0448bffa4502ab92232e6cda4db96d6`
- Resolve/Fusion runtime: DaVinci Resolve Studio `21.0.3.7`

Sibling indexes below are the parser/compiler's canonical bottom-to-top order.
Photoshop's Layers panel top-to-bottom order is the reverse within each parent.

## Result

| Boundary | Result | Evidence |
| --- | --- | --- |
| PSD tree -> semantic IR fields and order | PASS | 136/136 objects matched; 34 groups, 102 pixel layers |
| PSD clipping flags/chains -> semantic IR | PASS | 23/23 chains and 59/59 members matched, in order |
| Semantic groups -> Fusion GroupOperator | PASS | 34/34 isolated groups; direct membership and group output matched |
| Semantic clipping relation -> intended generated wiring | PASS | 59/59 have base Loader -> ClipIn BG, member Loader -> ClipIn FG, `Operator=In`, then ClipIn -> member Merge |
| `.comp` -> Resolve runtime objects | PASS | 363 tools; all 59 clipping connections and all GroupOperator children survived `LoadComp` |
| Generated graph -> Photoshop clipping evaluation | **FAIL (classification E)** | graph applies every clipped member to the already-composited outer stream instead of evaluating one base+clipped subtree |

No pixel/vector masks, fill-opacity overrides, unsupported kinds, blend fallbacks,
or pass-through groups occur in this PSD. All 34 groups are `Normal` isolated
groups. Two leaves are hidden. One clipped layer (`root/1/0/3/3`) has opacity
`97/255 = 0.380392`. Clipped-member modes are Normal 43, Multiply 12,
Linear Dodge 3, and Overlay 1. Seventeen clipping bases contain fractional
alpha pixels. These facts make the FIRST_USABLE clipping approximation material
for this PSD rather than theoretical.

`root/2/0/0/1` (`レイヤー 83`, `4022139ff7aa7fa2`) is structurally present but
its generated asset alpha is all zero. Raw PSD transparency/R/G/B channel
readback is also all zero, so this is a blank source layer, not converter loss.

## Compact PSD tree

Top-level bottom-to-top order is:

```text
root/0 用紙
root/1 背景 (isolated)
  root/1/0 室外 (isolated)
    hidden: 葉（選択用影, 草（フィルターオン）
    visible: 草
    Group added by GIMP: clipping chain 1
  root/1/1 室内 (isolated)
    壁: clipping chains 2-4
    カーテン仮: chain 5
    小物: chains 6-7
    椅子＆テーブル: chains 8-10
    レコード: chains 11-13; normal layer レイヤー 109
  root/1/2 室内　線: chain 14
root/2 キャラ (isolated)
  root/2/0 色: chains 15-21 plus normal layers
  root/2/1 キャラ線: 8 normal layers
  root/2/2 カップ: chains 22-23 plus normal layers
```

The exhaustive 136-object tree, including name, bbox, visibility, opacity,
blend, raw/visual sibling indexes, stable IDs and clip arrows, is in the audit
packet at `D:\Temp\psd2fusion-a-audit-20260901-1403\audit_report.md` and
`audit_raw_psd_tree.json`.

## All clipping chains and members

Every member below has structural result `PASS`; every chain has Photoshop
group-scope result `FAIL (E)` because the compiler does not create the required
collective clipped subtree. The member node triplet is deterministic:
`Loader<scope>_<member-id[:10]> -> ClipIn<scope>_<member-id[:10]> -> Merge<scope>_<member-id[:10]>`.
The ClipIn BG is the base Loader, FG is the member Loader, and the result Merge
FG is the ClipIn output.

| # | Base PSD path | Clipped members, bottom-to-top |
| ---: | --- | --- |
| 1 | `root/1/0/3/0 ソラ` | `root/1/0/3/1 レイヤー 43`; `/2 レイヤー 44`; `/3 レイヤー 46` |
| 2 | `root/1/1/0/0/0 レイヤー 16` | `/1 レイヤー 58`; `/2 レイヤー 57`; `/3 レイヤー 59`; `/4 レイヤー 72` |
| 3 | `root/1/1/0/1/0 レイヤー 17` | `/1 レイヤー 67 のコピー`; `/2 レイヤー 74` |
| 4 | `root/1/1/0/2/0 レイヤー 17 のコピー` | `/1 レイヤー 63`; `/2 レイヤー 66`; `/3 レイヤー 67` |
| 5 | `root/1/1/1/0 レイヤー 79` | `root/1/1/1/1 レイヤー 82` |
| 6 | `root/1/1/2/0/0 レイヤー 22` | `/1 スクリーンショット 2026-08-14 013323 のコピー`; `/2 ... のコピー 4`; `/3 レイヤー 73` |
| 7 | `root/1/1/2/1/0 レイヤー 20` | `/1 スクリーンショット 2026-08-14 013323 のコピー 2`; `/2 レイヤー 106` |
| 8 | `root/1/1/3/0/0 レイヤー 15` | `/1 レイヤー 68`; `/2 レイヤー 69`; `/3 レイヤー 70` |
| 9 | `root/1/1/3/1/0 レイヤー 12` | `/1 レイヤー 53`; `/2 レイヤー 55`; `/3 レイヤー 54`; `/4 レイヤー 62`; `/5 レイヤー 61` |
| 10 | `root/1/1/3/2/0 レイヤー 14` | `/1 レイヤー 47`; `/2 レイヤー 50`; `/3 レイヤー 49`; `/4 レイヤー 51`; `/5 レイヤー 60`; `/6 レイヤー 52` |
| 11 | `root/1/1/4/0/0 レイヤー 23` | `/1 p0498_l`; `/2 色相・彩度・明度 1 2` |
| 12 | `root/1/1/4/1/0 レイヤー 64` | `/1 スクリーンショット 2026-08-13 172808 のコピー 6` |
| 13 | `root/1/1/4/2/0 レイヤー 42` | `/1 スクリーンショット 2026-08-13 172808 のコピー 3` |
| 14 | `root/1/2/0 レイヤー 4` | `root/1/2/1 レイヤー 78 のコピー` |
| 15 | `root/2/0/0/0 レイヤー 26` | `/1 レイヤー 83` (blank source); `/2 レイヤー 81` |
| 16 | `root/2/0/2/0 レイヤー 35` | `/1 レイヤー 94`; `/2 レイヤー 93` |
| 17 | `root/2/0/3/0 レイヤー 33` | `/1 レイヤー 98`; `/2 レイヤー 92`; `/3 レイヤー 96`; `/4 レイヤー 97` |
| 18 | `root/2/0/4/0 レイヤー 34` | `/1 レイヤー 95` |
| 19 | `root/2/0/6/0 レイヤー 32` | `/1 レイヤー 90 のコピー`; `/2 レイヤー 90 のコピー 2`; `/3 レイヤー 90`; `/4 レイヤー 91` |
| 20 | `root/2/0/7/0 レイヤー 32 のコピー` | `/1 レイヤー 86` |
| 21 | `root/2/0/8/0 レイヤー 36` | `/1 レイヤー 85`; `/2 レイヤー 89`; `/3 レイヤー 84`; `/4 レイヤー 87` |
| 22 | `root/2/2/0/0 皿` | `/1 レイヤー 101`; `/2 レイヤー 102` |
| 23 | `root/2/2/2/0 レイヤー 40` | `/1 レイヤー 99`; `/2 レイヤー 100` |

The audit packet's `audit_correspondence.json` contains one row per member with
the exact semantic IDs, GroupOperator, Loader, ClipIn BG/FG, downstream Merge,
ApplyMode/Blend, and final-output reachability.

## Confirmed first divergence and root cause

The base/member relationship itself is not lost at parse or serialization.
The semantic IR nevertheless has no field for `Blend Clipped Layers As Group`
or its default provenance. This PSD contains no explicit `clbl` tagged block;
Photoshop's documented default is selected/true.

The first observable graph divergence is in the clipping compiler. Current
runtime-preserved wiring is:

```text
outer current + base Loader -> base Merge
base Loader + member Loader -> ClipIn (Operator=In)
already-composited current + ClipIn -> per-member Merge
repeat per member
```

Photoshop default semantics require the base and successive clipped layers to
be evaluated as one clipping group, with the base layer's blend scope applied
to the collective result. The generated graph never constructs that collective
subtree. This is the documented FIRST_USABLE approximation, classification E,
not a missing clipping flag (A), serializer wiring bug (B), misunderstood
Fusion `In` operator (C), or Loader/canvas/position failure (D).

## Minimum fix proposal (implemented after this audit)

1. Add a clipping-chain semantic object with ordered members,
   `blend_clipped_as_group`, and provenance (`explicit clbl` or Photoshop
   default true).
2. For the default/true case, compile base plus all clipped members inside one
   isolated chain subtree. Use the base alpha as the fixed matte and preserve
   that alpha on the completed subtree.
3. Apply each member's blend/opacity inside the subtree, then merge the
   completed subtree onto the outer backdrop once using the base blend/opacity.
4. Keep the existing per-member form only as an explicitly named approximation
   or for a separately proven `clbl=false` path.
5. Validate with one Resolve host fixture containing a partial-alpha base,
   multiple clipped members, at least one non-Normal member, and a Photoshop
   reference image.

## Runtime scope

Runtime evidence used non-destructive `fusion:LoadComp` and inspected actual
tool/input objects via `GetConnectedOutput`, `GetConnectedInputs`, and
`GroupOperator:GetChildrenList`. Pasting into the unknown current composition
was not performed because it would mutate an unrelated active graph. No render,
fix, commit, push, or converter code change was performed.

## 2026-09-01 clipping-boundary fix verification

The bounded fix adds an ordered semantic `ClippingChain` with base, members,
`blend_clipped_as_group`, and explicit-`clbl` versus default-true provenance.
For true/default chains, the compiler now finishes every member inside a
`ClipStack` subtree with a fixed base matte and `ProcessAlpha=0`, then performs
one outer Merge using the base blend/opacity. The ordinary-layer and
GroupOperator paths were not redesigned.

The native-Fusion micro-oracle contains a partial-alpha base, two ordered
members, Normal at 75% opacity, and Multiply at 50% opacity. Resolve 21 built
both the former and corrected topologies in the current composition and showed
their differing pixel results side-by-side in the Viewers without using
`Composition:Render`; the corrected side retains the base-alpha group boundary
before the single outer merge.

Regeneration and chain-aware validation of `D:\Downloads\a.psd` passed:

- 23/23 clipping chains use the completed-subtree-before-outer structure;
- 59/59 clipped members remain in canonical order;
- 34/34 semantic groups remain 34/34 runtime GroupOperators;
- Resolve `LoadComp` recognized 363 tools and current-comp Paste added all 363
  while preserving the identity and count of all pre-existing tools;
- no converter warning was emitted.

The saved Photoshop composite was not used as a pixel oracle because the local
Photoshop instance required interactive sign-in. The host micro-oracle is the
visual evidence for this failure class; full Photoshop pixel parity and the
explicit `clbl=false` path remain out of scope.
