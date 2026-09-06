# DaVinci Resolve integration

The integration is a thin Fusion Comp script.  It does not copy or reimplement
the PSD parser/compiler.

## Install or remove

From the repository root, run:

    pwsh -NoProfile -File .\scripts\install_resolve.ps1

The installer checks the installed Resolve scripting documentation and Python
bridge, then writes the launcher to the current user's Resolve script folder.
Running the same command again reinstalls it (the operation is idempotent).
To remove only this launcher:

    pwsh -NoProfile -File .\scripts\install_resolve.ps1 -Uninstall

-Force is only needed when an unrelated file already occupies the target name
and has been checked by the user.

## Use

1. Open the Fusion page in DaVinci Resolve.
2. Choose Workspace > Scripts > Comp > PSD2Fusion (Resolve may expose the
   same Comp script from the Fusion page's Script menu).
3. Select a .psd in the file picker.

The launcher writes to <PSD folder>\<PSD stem>_fusion by default.  If that
folder already contains a PSD2Fusion composition or manifest, a confirmation
dialog is required before --force is passed for that run.  On success it
reads the generated `.comp` settings and pastes that tool set into the Fusion
Composition that was current when the script started.  The generated `.comp`,
assets, and manifest remain available as recovery/debug artifacts.

### Running-state UX

After the PSD is selected and any overwrite confirmation has passed, PSD2Fusion
should display a small visible running-state window before noticeable blocking
work begins.  The v1 contract is intentionally coarse and truthful:

```text
PSD2Fusion

処理しています…
PSDを変換しています…
```

After bridge conversion/artifact verification and before current-graph
insertion, the status may change to:

```text
処理しています…
Fusionグラフを挿入しています…
```

The launcher must not invent a percentage or ETA.  Its current Python bridge is
one blocking process call from Lua, so finer-grained progress is not observable
unless the bridge later exposes structured progress.  The running-state UI is
informational only in v1: there is no mid-run Cancel until cooperative bridge
cancellation plus complete host/artifact rollback are independently proven.

Success closes the running-state UI only after the existing host readback and
identity/invariant checks have passed, then shows the normal completion dialog.
Failure closes the running-state UI after any required rollback, then shows the
existing detailed failure dialog.  The progress layer must not move Resolve
mutation/Paste onto an unsafe background thread merely to keep the window
responsive.

Full implementation/acceptance contract: `docs/RESOLVE_PROGRESS_UX.md`.

This differs from `LoadComp` and `TimelineItem.ImportFusionComp(path)`, which
load or add a separate composition instead of inserting tools into the graph
currently shown in Resolve's integrated Fusion page.  The launcher verifies
the current Composition identity before and after insertion, preserves every
pre-existing tool object, and wraps the paste in one undo operation.  It does
not replace the Composition, delete nodes, or save the project/timeline.  If
insertion fails after changing the graph, it attempts and verifies an undo.

The launcher writes a short-lived UTF-8 JSON request for the bridge.  Only the
installed Python/bridge paths and the temporary request/log paths are passed
through the Windows shell; the selected PSD and output paths stay in the JSON
payload.  This keeps spaces and Japanese Windows paths out of command-line
codepage parsing.  A failure dialog identifies the phase, input/output,
bridge exit code, stderr/exception summary, artifact state, and the resolved
current Fusion Composition (including the `fu:GetCurrentComp()` comparison).

The launcher uses the Python executable found by the installer and a small
repository bridge; it does not require a PowerShell command from the user.
The repository's normal python -m pip install -e . dependencies remain the
source of truth for conversion.

## Validation on this machine

On 2026-09-01 with DaVinci Resolve Studio 21.0.3.0007, an installed-docs and
runtime probe established `fu:GetCurrentComp()`, `bmd.readfile`, and the
Composition `Paste`/undo APIs as the shortest current-graph insertion path.
The Workspace > Scripts > Comp > PSD2Fusion flow then passed with both an ASCII
PSD path and a Japanese/space PSD path in a new unsaved validation project.
Each run inserted 12 tools into the same selected Composition: one
`GroupOperator`, three `Loader`, five `Merge` (including the clipping input),
two `Background`, and one generated `MediaOut`.  The original `MediaOut` and
all tools from the first run remained the same runtime objects after the
second run; the generated final Merge-to-MediaOut connection was visible and
Resolve remained responsive.  Existing Group/clipping behavior and the
pre-existing no-current-Composition guard were unchanged.

The progress-UX feature is a later presentation layer and requires its own real
host acceptance before being called FIRST_USABLE.  The prior insertion evidence
does not by itself prove UIManager/Dispatcher rendering or repaint behavior.

## Known limitations

- This is a Windows, per-user Resolve 21 integration.  Re-run the installer
  after moving the repository or changing the Python installation.
- The default output is deliberately fail-closed for an existing result unless
  the overwrite checkbox is explicitly enabled.
- The inserted graph retains the generated `MediaOut` as a recovery-complete
  tool set; it does not reconnect or remove a pre-existing `MediaOut`.
- Unsupported Photoshop features retain the existing FIRST_USABLE core's
  warnings/fallbacks; this integration does not add masks, text, smart objects,
  adjustment layers, or render automation.
