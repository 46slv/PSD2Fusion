# PARITY-007 independent closeout runbook
Status: ACTIVE on branch codex/parity-007 from canonical main 4032e0e.
Parent contract: .control/PROGRAM_CLOSEOUT_RUNBOOK.md Phase B, queue items C06-C15.

## Objective
Independently re-verify the P1-P6 proof chain from a clean environment: state/evidence integrity, full offline regression, fresh real-PSD regen, final fresh actual Fusion proof in project PSD2Fusion, strict threshold-0 reference compare, semantic/capability audit, false-PASS/privacy audit, then a fresh independent verdict. PASS is required before program terminal state.

## Operating model
Muse lanes COORD/A_AUDIT/B_HOST/C_REFEREE/V_FRESH per parent runbook. Coordinator serializes state transitions, production edits, commits touching the same file, verifier verdict and any correction. Parallel groups: P7_STATIC_A (P7-01 audit + P7-02 offline regression after clean env), P7_DYNAMIC_B (P7-04 host render + P7-06 semantic audit after fresh regen). Verifier lane uses a fresh context and never repairs its own candidate.

## Stage order
P7-00 clean env -> P7-01/P7-02 static audits -> P7-03 fresh regen -> P7-04/P7-06 dynamic proofs -> P7-05 compare -> P7-07 false-PASS/privacy -> P7-08 fresh verdict -> P7-09 conditional correction -> P7-10 terminal publish.

## Hard rules
No threshold relaxation, no reference fitting, no 1LSB-only repair, float32 preserved, real inputs read-only, no private artifacts committed, host work only in Resolve project PSD2Fusion with disposable comps, unchanged retry max once, fresh result wins over stale evidence.

