# PSD2Fusion Resolve progress UX

Status: implementation contract
Updated: 2026-09-06 JST

## Goal

PSD2Fusion must never look idle after the user has committed to a conversion.

The existing Resolve/Fusion launcher already has a good safety model:

- explicit PSD picker;
- overwrite confirmation;
- bridge conversion evidence;
- generated-artifact verification;
- exact current-comp checks;
- bounded `Paste` with Undo/rollback verification;
- visible final success/failure dialogs.

This contract adds a **visible running state** between user confirmation and the final result. It must not weaken any existing rollback/identity invariant.

## User flow

```text
Workspace -> Scripts -> Comp -> PSD2Fusion
        |
        v
select PSD
        |
        +-- cancel -> zero conversion / zero graph mutation
        |
        v
optional overwrite confirmation
        |
        +-- cancel/refuse -> zero new conversion / zero graph mutation
        |
        v
+--------------------------------------+
| PSD2Fusion                           |
|                                      |
| 処理しています…                     |
| PSDを変換しています…                |
|                                      |
+--------------------------------------+
        |
        v
bridge conversion / artifact check
        |
        v
+--------------------------------------+
| PSD2Fusion                           |
|                                      |
| 処理しています…                     |
| Fusionグラフを挿入しています…       |
|                                      |
+--------------------------------------+
        |
        v
readback / invariant verification
        |
        +-- success -> running UI closes -> existing success dialog
        |
        +-- failure -> rollback if needed -> running UI closes -> existing failure dialog
```

The exact styling is secondary. The required behavior is that valid work has a visible busy/running state.

## Phase mapping

Only display phases that correspond to observable boundaries in the current implementation.

### Before bridge launch

Display:

```text
処理しています…
PSDを変換しています…
```

This covers the blocking Python bridge call. Do not claim finer-grained internal parser/export/compiler phases unless the bridge later emits structured progress that the launcher can actually observe.

### After successful bridge/artifact verification, before Fusion insertion

Display:

```text
処理しています…
Fusionグラフを挿入しています…
```

This covers reading the generated `.comp`, `Paste`, and initial post-Paste tool snapshot.

### Final host verification

When the implementation can safely repaint/update the status before final verification, use:

```text
処理しています…
結果を確認しています…
```

If the host UI cannot reliably repaint between the blocking Paste and verification without changing execution semantics, keeping the previous truthful insertion text is acceptable for v1. Do not fake a phase transition merely for appearance.

## No fake percentage

v1 does not show `%`, a progress bar with invented completion, ETA, layer counters, or other synthetic progress.

The current bridge is one blocking process invocation from the Lua launcher. Until it exposes machine-readable incremental progress, the launcher knows only phase boundaries, not completion percentage.

## Running window semantics

Preferred implementation surface: Resolve/Fusion `UIManager` + `bmd.UIDispatcher`, using the host's native scripting UI.

The running window is informational:

- show before the first noticeable blocking conversion work;
- status text may update at real phase boundaries;
- keep it small;
- do not require user interaction;
- close deterministically on success and failure;
- do not install a new desktop automation layer.

### Repaint/event handling

A visible window that never paints is not accepted.

If the implementation needs a short host-safe event pump/yield after `Show()` or a status update, use only a measured Fusion-safe mechanism. Do not move Resolve/Fusion mutation or `Paste` onto an arbitrary background thread merely to keep the UI responsive.

The first host canary must explicitly prove that the running window is visibly rendered before the blocking bridge operation begins.

## Cancel policy

There are two different cancel concepts.

### Pre-run cancel

Existing picker and overwrite-dialog cancellation remain valid and must perform zero new conversion / zero graph mutation.

### Mid-run cancel

v1 has **no mid-run Cancel button**.

Reason:

- bridge cancellation/temporary artifact cleanup is not yet an explicit transactional contract;
- Fusion `Paste` is protected by Undo/rollback, but interrupting it asynchronously has not been proven safe;
- a button that only hides the window would falsely imply cancellation.

A future mid-run Cancel may be added only after cooperative bridge cancellation, artifact cleanup, host mutation cancellation, and complete rollback are independently proven.

## Error/refusal UX

No expected refusal/error after conversion has started should be Console-only.

On failure:

1. preserve/perform the existing rollback semantics;
2. close/hide the running window;
3. show the existing `PSD2Fusion failed` dialog with the current `phase`, bridge exit/artifact state, comp identity, and rollback/insertion information;
4. retain Console/log detail as supplemental evidence, not the only user-visible signal.

If the progress UI itself cannot be created, PSD2Fusion should fail soft to the current conversion behavior rather than breaking conversion. However, FIRST_USABLE acceptance for this feature remains open until the progress UI is host-proven.

## Success UX

Success ordering:

1. bridge returned success;
2. generated artifacts exist;
3. generated graph inserted;
4. current comp / original tool preservation checks pass;
5. running window closes;
6. existing success dialog appears.

Do not close the running state before host verification merely to make the operation look faster.

## Existing state machine integration

The current launcher already tracks `state.phase`. Preserve that model.

Relevant existing phases include:

- `picker`
- `selected_path`
- `overwrite_guard`
- `bridge_launch`
- `converter_complete`
- `artifact_check`
- `converter_failed`
- `graph_insertion`
- `success_dialog`

The progress UI should be a presentation layer over these boundaries, not a second conversion state machine.

Suggested helpers:

```text
create_progress_ui(fusion_app)
progress:show(status)
progress:update(status)
progress:close()
```

or equivalent Lua functions. A no-op fallback object is acceptable for defensive compatibility, while host acceptance still requires the real UI path.

## Safety invariants

Adding progress UX must not change:

- selected/current Fusion composition resolution;
- PSD input/output paths;
- overwrite/`--force` semantics;
- Python bridge command or exit interpretation;
- generated artifact contract;
- connection/tool semantics of the generated graph;
- `Lock` / `StartUndo` / `EndUndo` / `Undo` behavior;
- existing-tool preservation checks;
- project save state;
- whether Resolve saves/closes/switches projects.

Progress UI is presentation-only.

## Host acceptance

A real Resolve/Fusion run must prove all of the following.

### P1 — pre-run cancellation

- run PSD2Fusion;
- cancel the PSD picker;
- no running window remains;
- no graph mutation.

### P2 — progress visibility before conversion

- select a valid PSD with no overwrite ambiguity;
- the running window visibly renders before bridge conversion completes;
- text is truthful (`PSDを変換しています…` or equivalent);
- no fake percentage.

### P3 — insertion transition

- after bridge success, progress UI remains present;
- it changes to `Fusionグラフを挿入しています…` where host repaint permits;
- insertion safety/invariants remain unchanged.

### P4 — success closeout

- after final readback, progress UI closes;
- existing success dialog appears;
- generated graph is present;
- original tools remain preserved;
- no project save was introduced.

### P5 — failure closeout

Using a disposable/fault-injected safe case:

- failure does not leave the progress window stranded;
- rollback behavior remains correct;
- visible failure dialog appears after progress UI closes;
- failure phase/evidence remains accurate.

### P6 — no regression

- repository test/check suite passes;
- launcher install/reinstall still works;
- existing host/reference claims are unchanged;
- progress-only changes do not touch the parity/compositing math.

## FIRST_USABLE condition

This feature is first-usable when a user can:

1. open Fusion;
2. run `PSD2Fusion` from Comp Scripts;
3. choose a PSD;
4. see a visible running state while conversion/insertion occurs;
5. receive the existing success dialog when complete;
6. receive a visible failure dialog, with no stranded busy window, on a safe tested failure path.

Code existence or offline UI tests alone are not sufficient.
