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
calls Fusion's LoadComp and reports whether MediaOut1 was recognized.  If
automatic loading is unavailable, the dialog shows the .comp path and its
neighboring assets directory for manual opening.

The launcher uses the Python executable found by the installer and a small
repository bridge; it does not require a PowerShell command from the user.
The repository's normal python -m pip install -e . dependencies remain the
source of truth for conversion.

## Validation on this machine

On 2026-09-01 with DaVinci Resolve Studio 21.0.3.0007, the menu entry was
visible in the Fusion page.  Selecting `D:\Documents\PSD2Fusion\clipfixture.psd`
from the picker generated `clipfixture_fusion\PSD2Fusion.comp` and its
`assets` directory.  The launcher then loaded the composition through Fusion's
`LoadComp`; the returned composition contained `MediaOut1`.  The smoke used a
new empty Resolve project and did not edit or save an existing project.

## Known limitations

- This is a Windows, per-user Resolve 21 integration.  Re-run the installer
  after moving the repository or changing the Python installation.
- The default output is deliberately fail-closed for an existing result unless
  the overwrite checkbox is explicitly enabled.
- `LoadComp` is a non-destructive Fusion load.  Resolve may keep the current
  timeline composition visible in its page UI; the completion dialog always
  shows the exact `.comp` and `assets` paths for manual opening if the loaded
  tab is not surfaced by that Resolve layout.
- Unsupported Photoshop features retain the existing FIRST_USABLE core's
  warnings/fallbacks; this integration does not add masks, text, smart objects,
  adjustment layers, or render automation.
