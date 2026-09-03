# PARITY-004 GroupOperator lowering decision

Status: implementation-ready semantic decision from focused actual-Fusion probes.

## Failure

The first broken boundary is a parent Merge consuming `GroupOperator.MainOutput1`. The internal terminal renders correctly, but actual-Fusion readback reports the parent Merge input connection as nil. The same failure repeats across nested groups; bypassing the GroupOperator restores pixels.

## Fusion canonical topology

`GroupOperator` is an editable Flow/container and InstanceInput/InstanceOutput proxy boundary. It is not the runtime render source that parent consumers should reference.

Wrong:

```text
internal terminal
  -> GroupOperator.MainOutput1
  -> parent Merge.Foreground
```

Correct:

```text
internal terminal -----------------> parent Merge.Foreground / sibling / MediaOut
       \
        -> Group InstanceOutput     # UI/proxy only
```

Fusion save/readback normalizes direct Group output wiring to the internal terminal source.

## Isolated group lowering

```text
transparent GroupCanvas
  -> internal child sequence
  -> internal terminal ------------> parent Merge.Foreground
          \
           -> Group InstanceOutput
```

The parent Merge owns group blend and opacity exactly once.

Implementation contract:

- keep `_group_operator(...)` and InstanceOutput for editability/readability;
- `_ItemResult.output` and matte must return `nested.output`, not `_Source(group_name, "MainOutput1")`;
- ordinary parent/sibling/MediaOut render inputs must never consume a GroupOperator output.

## Pass Through group lowering

```text
parent current --------------------> first internal consumer Background
                                     -> child sequence
internal terminal -----------------> next parent consumer / MediaOut

Group InstanceInput  -> display proxy for the first internal consumer
Group InstanceOutput -> display proxy for the terminal
```

Implementation contract:

- pass the actual parent `backdrop` into the internal sequence instead of `_Source("", "Output")`;
- retain lowering-only metadata identifying the first internal backdrop consumer for InstanceInput proxy declaration;
- return `nested.output` as the actual output;
- preserve `consumed_backdrop=True`;
- do not add a parent Normal Merge that double-composites the pass-through result.

## Scope

No Semantic IR change is expected. Existing `children`, `pass_through`, `isolated`, and parent relationships are sufficient.

Do not change:

- straight/opaque clipping island;
- fixed ClipIn matte;
- clipping member order;
- `Operator=In` coverage;
- final local `ClipStack = Normal / member opacity / ProcessAlpha=0`;
- PARITY-005/006.

## Required regression proof

- no ordinary render `Input { SourceOp=... }` references a GroupOperator;
- nested isolated parent Merge Foreground references the internal terminal;
- Pass Through internal entry Background directly references the actual parent stream;
- GroupOperator and exposed proxy ports still exist;
- actual-Fusion readback inputs are non-nil;
- minimal nested isolated render PASS;
- minimal Pass Through render PASS;
- existing clipping micro gate remains within its proven quantization tolerance;
- real `a.psd` P4-09 is regenerated and rerendered after the group boundary fix.

If corrected group wiring still leaves multiple plausible group semantic models, stop and escalate to Sol. Mechanical wiring/test failures remain Luna work.
