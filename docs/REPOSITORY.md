# Talos version control

Repository: [Schrodingerscat07/Talos](https://github.com/Schrodingerscat07/Talos). Default branch: `main`. Talos-authored source and documentation use the MIT License; see the root license and third-party notices.

## Clone and run

```powershell
git clone https://github.com/Schrodingerscat07/Talos.git C:\Researches\Talos
Set-Location C:\Researches\Talos
```

Follow [installation](manual/01-installation.md) to create private machine configuration, install dependencies, build, prepare assets and run a mannequin diagnostic. A clone contains source, example profiles and documentation. It intentionally contains no engine binaries, private character assets, generated retargeted assets, machine configuration or recorded images. Existing `erl` commands, protocol identifiers and Unreal module/package names are retained to preserve compatibility.

## Initial six commits

The existing implementation is imported in six functional groups. These are an organized source snapshot, not a reconstructed historical development timeline.

1. Project identity, MIT license, dependency notices and Git boundaries.
2. Unreal harness, runtime controller, sensors, configurable scenes and avatar adapter.
3. Experiment profiles, validation, process management and preparation/lifecycle scripts.
4. Observation/action client, recording, replay and source provenance archives.
5. Live diagnostics, offline verification and client/recorder/configuration tests.
6. Protocol, architecture, researcher manuals, verification summary and repository workflow.

## Future changes

Use a descriptive branch, make focused commits, run the relevant checks from [testing](manual/09-testing.md), inspect `git diff --cached`, and push the branch for review. Keep human research gate decisions separate from Git commits: committing or publishing source does not constitute visual or scientific approval.

Before a first commit, verify `git config user.name` and `git config user.email` match the intended human GitHub identity. Local repository configuration takes precedence over global settings. This repository's initial commits use the owner's configured identity, `schrodingerscat07`.

## Files that stay local

`.gitignore` excludes `local/`, `runs/`, tokens/secrets, Unreal Content/assets, engine build products, caches and historical private workstation notes. Keep sufficient permitted assets and experiment artifacts in a separate backed-up location; Git cannot restore files it never tracked. Source hashes and inventories identify artifacts but are not substitutes for preserving those artifacts.

Use `python -m erl.bundle` for a source-only ZIP with a per-file manifest and license notices. Do not use it as an archive of personal assets or completed experiments. Never force-add ignored private files to make a clone look complete.
