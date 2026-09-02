# PSD2Fusion parity validation contract

This file defines the evidence needed to promote any Photoshop-compositing claim.

## Environment and evidence packet

Every host/reference run records exact Git HEAD; Windows, Python, psd-tools and Pillow versions; Photoshop version; Resolve/Fusion version and edition; PSD mode/depth/profile; project color settings; Loader alpha settings; output format; input SHA-256 values; commands and exit codes.

Commit only safe summaries at `.control/evidence/<task-id>/<run-id>/summary.json`. Full-resolution/private files stay in ignored local directories.

## Reference qualification

For `D:\Downloads\a.psd` and `D:\Downloads\20260812.png`, establish before comparison:

- existence and unchanged before/after hashes;
- dimensions, channels, bit depth, profile and alpha;
- whether the PNG is exact-canvas, cropped, scaled, rotated, color-transformed or otherwise normalized;
- PSD stored composite as a separate origin from recomposition;
- hard failure for unexplained dimensions/channels;
- no hidden resize, crop, grade, alpha discard or threshold tuning to the candidate.

Known historical `a.psd` structure, to re-measure after hashing: 136 objects, 34 groups, 23 clipping chains and 59 clipped members.

## Comparator

At minimum report:

- dimensions and channel presence;
- RGBA max, mean and p99 absolute error;
- threshold-exceeding pixel count and ratio;
- alpha max and mean error;
- edge-band, opaque-region, transparent-region and transparent-RGB error;
- difference bounding box;
- absolute, signed and alpha difference artifacts.

SSIM or Delta E may supplement but never replace alpha, position and outlier checks. Measure repeated export/render noise before setting thresholds. Never choose thresholds from the current candidate error.

Synthetic tests must prove the comparator fails on: one-pixel translation, wrong crop/scale, RGB-only match with wrong alpha, hidden profile conversion, premultiply fringe, large local outlier masked by a low mean and threshold relaxation.

## Asset and alpha checks

- opacity, blend and clipping are not double-baked into layer assets;
- intended transparency channel is preserved;
- negative/out-of-canvas placement is exact;
- ICC transforms are named;
- transparent RGB is inspectable;
- straight/premult state is explicit;
- no edge fringe;
- unexplained dimension/channel mismatch fails closed.

## Blend fixture axes

For every promoted mode, cover:

```text
Backdrop: transparent, black, white, gray, saturated color, partial alpha, gradient
Source alpha: 0, .25, .5, .75, 1, antialiased edge
Opacity: 0, .25, .5, .75, 1
```

Include partial backdrop alpha, clamp/range behavior, source-alpha versus opacity and transparent RGB.

## Opacity fixtures

Cover ordinary opacity, source alpha × opacity, member opacity, base opacity, isolated-group opacity, nested group opacity, Fill versus Overall when effects exist, opacity-zero base and hidden layers. Tests must prove each stage applies once at the verified boundary.

## Clipping fixtures

Required cases:

1. hard opaque base plus oversized member;
2. fractional base alpha `0, .25, .5, .75, 1`;
3. antialiased and transparent-RGB base edge;
4. base opacity `1, .5, 0`;
5. member opacity `1, .5, 0`;
6. two/four ordered Normal members;
7. mixed Normal/Multiply/Linear Dodge/Overlay;
8. reversed member order;
9. non-Normal base;
10. black/white/color/transparent outer backdrops;
11. intermediate alpha after every member;
12. zero-alpha base;
13. hidden member;
14. interrupted and orphan chain;
15. parent/group boundary;
16. clipping in isolated group;
17. clipping in Pass Through group;
18. group as base or member;
19. absent versus explicit true `clbl`;
20. true versus false `clbl`;
21. `clbl=false` plus non-Normal base;
22. masks on base when supported;
23. reduced real-world chain from `a.psd`.

Metamorphic invariants: transparent/opacity-zero member is a no-op; changing member RGB outside base coverage cannot affect output; local span alpha remains base coverage; base-only span equals ordinary base; cross-parent membership is impossible; `clbl=true` local span has no outer-backdrop input.

## Host checks

- `.comp` loads in the recorded Resolve version;
- paths including Japanese survive;
- ApplyMode, Blend, Operator, ProcessAlpha and PostMultiply survive reload;
- GroupOperator connections survive;
- the same commit renders deterministically;
- existing composition/tools are preserved;
- partial failure cleanup/recovery is actionable;
- evidence names the exact candidate commit.

## Promotion gates

1. Source contract: raw/asset RGB-alpha, profile and premultiplication are explicit.
2. Normal plus opacity: ordinary, partial-alpha and isolated-group cases pass.
3. Core blend: Multiply, Linear Dodge and Overlay pass.
4. Grouped clipping: fixed coverage, ordering, opacity, mixed blends and fractional edges pass.
5. Group interaction: isolated, Pass Through and nested cases pass.
6. `clbl`: absent/true are verified; false is either verified or explicitly baked/rejected.
7. Real PSD: all chains have structural evidence, full output is compared with the supplied PNG and material failures are reduced to fixtures.
8. Fresh verifier: clean checkout reproduction and false-PASS audit pass.
