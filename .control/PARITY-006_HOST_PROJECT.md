# PARITY-006 dedicated Resolve host project

Status: ACTIVE task-branch host execution contract for PARITY-006.

## Dedicated host project

All PARITY-006 Resolve/Fusion host work must run in the dedicated Resolve project named exactly:

`PSD2Fusion`

This project was created by the operator specifically for PSD2Fusion validation. Do not use the historical `PSD2Fusion P4-08 20260902` project or any unrelated user project for PARITY-006 host work.

## Safety boundary

- Treat every existing Fusion Composition/timeline item in `PSD2Fusion` as test-only host workspace, but still avoid destructive edits to unrelated items.
- Never paste the full generated graph into another project or a pre-existing non-PSD2Fusion production comp.
- Prefer a disposable Fusion Composition or disposable loaded comp inside the `PSD2Fusion` project for each host experiment.
- Do not save over unrelated projects.
- If the test project must be saved for stability/relaunch recovery, save only `PSD2Fusion` and record that save in evidence.
- Do not delete the project.
- Do not modify or commit the real PSD/reference inputs.

## Host recovery after the 2026-09-05 P6-02 incident

The previous P6-02 qualified paste/Saver attempt in `PSD2Fusion P4-08 20260902` rendered for about 125 seconds, returned nil, produced no artifact, then Resolve exited before cleanup. That historical project is no longer an allowed PARITY-006 target.

On resume:

1. Confirm Resolve Studio 21.0.3.7 is running and scripting endpoints respond.
2. Resolve/open the project by exact name `PSD2Fusion`; do not assume the current project is correct.
3. Record project name, Resolve PID/version, timeline/comp identifier, tool count, and endpoint health before mutation.
4. Use a disposable comp inside `PSD2Fusion`.
5. Run a trivial host sanity render first.
6. Run a representative single-chain smoke render second.
7. Only after both pass, attempt the full latest generated graph.

## Full-render retry rule

Do not repeat an unchanged full 1109-tool route after a second crash/nil/no-artifact/process-exit event. If it fails again, raise `S-HOST` and split the cause into graph size/tool count, specific tool/node, Saver route, memory/resource exhaustion, or host lifecycle.

## Evidence requirements

Every host run records:
- exact Git candidate HEAD;
- project name (`PSD2Fusion`);
- Resolve Studio version and PID before/after;
- disposable comp/timeline identity;
- tool count before render;
- Saver settings including `PreDivide=1` where applicable;
- artifact path/hash or explicit no-artifact result;
- render return value/timing/polls;
- endpoint health before/after;
- cleanup/isolation result;
- whether the project was saved.

A successful run in any other Resolve project is not PARITY-006 closure evidence unless the operator explicitly changes this contract.
