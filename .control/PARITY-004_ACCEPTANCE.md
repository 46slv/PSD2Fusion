# PARITY-004 production acceptance override

Status: ACTIVE operator policy for PARITY-004 production acceptance.
Updated: 2026-09-04.

This file changes acceptance policy only. It does not invalidate existing strict fixtures, deterministic oracles, comparator evidence, semantic contracts, structural evidence, or previously recorded failures.

For PARITY-004, this policy supersedes conflicting acceptance language in older Goal/evidence/docs where that language would require byte-exact Photoshop-style 8-bit intermediate quantization from the production Fusion graph.

## Production target

Keep the Fusion production graph on its 32-bit float processing path. Do not add quantization, rounding, depth-reduction, or equivalent nodes solely to reproduce Photoshop's 8-bit intermediate rounding behavior.

`strict RGBA threshold=0` remains required diagnostic/regression evidence. A strict failure is not automatically a production blocker when the residual is only quantization-scale and all structural/semantic requirements remain satisfied.

## Acceptance classification

### Non-material quantization residual

A residual may be accepted as non-blocking when all of the following hold:

- maximum channel delta is approximately one 8-bit LSB (normally `max_delta <= 1`);
- alpha behavior is correct for the tested boundary;
- dimensions, placement, group scope, clipping scope/order, blend semantics and opacity semantics are correct;
- no localized visible anomaly or coherent high-difference region is present;
- the residual is consistent with host/export/quantization behavior rather than a graph-semantic defect.

Do not repair this class merely to obtain byte identity.

### Material visual/semantic difference

The following remain blockers until localized and resolved or explicitly rejected by the capability policy:

- alpha/coverage mismatch;
- group, isolation, Pass Through, clipping, ordering or backdrop-scope mismatch;
- wrong blend semantics or opacity placement;
- large pixel deltas or coherent localized outliers;
- visually observable divergence in the real reference case;
- unexplained profile/color-space, crop, placement, canvas or asset-materialization errors.

Threshold relaxation must never hide a material region. Record strict metrics even when the acceptance verdict treats a 1-LSB residual as non-blocking.

## PARITY-004 execution after current micro work

Do not interrupt the currently running micro-matrix/diagnostic work. Complete it and retain its strict threshold-zero evidence.

After that work completes:

1. fresh-read the latest PARITY-004 candidate and repository state;
2. regenerate the real read-only `D:\Downloads\a.psd` from that candidate;
3. render it in actual Fusion using the qualified production path;
4. compare the fresh render directly with qualified `D:\Downloads\20260812.png`;
5. report strict metrics, but partition residuals into non-material quantization versus material visual/semantic differences;
6. prioritize localization of large/coherent differences, especially the Linear Dodge region and any other real-image outliers;
7. do not enter a production repair loop whose only purpose is to close +/-1 LSB differences.

## Float-pipeline rule

Production lowering should preserve the established float32 materialization/compositing path unless evidence shows a semantic defect that requires a different verified boundary. An 8-bit deterministic oracle may model source/reference semantics and stage behavior for diagnosis, but it does not by itself authorize inserting an 8-bit quantization stage into the production graph.

## Linear Dodge repair authority

A temp-only actual-Fusion investigation has now produced evidence strong enough to authorize a bounded production implementation attempt for clipped `Linear Dodge` members, provided the implementation preserves the float32 path and is generalized by blend semantics rather than by the real-case L52 layer identity.

The candidate behavior to implement is the smallest native-only float boundary that reproduces the verified temp host variant: member RGB contribution is attenuated by member alpha and opacity before the additive/saturating blend boundary, the fixed base coverage remains the clipping-span alpha, and the existing ClipIn / ClipStack / outer / group structure remains intact. Do not introduce uint8 quantization or per-pixel fitting.

This is implementation authority, not completion evidence. After implementation, focused host fixtures and a fresh full `a.psd` Fusion render/reference comparison are still required. A fresh verifier must classify the remaining real-image residuals under this acceptance policy before PARITY-004 can close.

## State transition

PARITY-004 remains `in_progress` until the required host/render/reference evidence is complete and a fresh verifier confirms that remaining differences are either:

- non-material quantization residuals under this policy; or
- explicitly classified unsupported/rejected behavior allowed by the program contract.

PARITY-005 and PARITY-006 remain blocked until that verification/state transition occurs.
