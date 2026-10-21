# Verification status — Talos 0.2.0

Reference implementation verified 2026-10-20; Talos GitHub source and MIT license prepared 2026-10-22. The configurability/reproducibility/documentation pass is implemented. Automated checks passed on the original Windows workstation. Human visual review and independent clean-machine reproduction remain pending. No learning, consciousness or interaction milestone is claimed. This source publication does not establish independent reproducibility.

The 17 Python tests were rerun successfully from the renamed Talos project location on 2026-10-22. Branding, license notices and repository metadata changed after the original native/rendered reference runs; historical run source snapshots remain unchanged.

## Delivered foundation

- Strict versioned portable profiles, separate private machine/content mappings, and resolved launch snapshots. Control rates, horizons, avatar fit, cameras, rendering and static scene selection are configurable.
- Actor Blueprint or direct Skeletal Mesh avatars; matching supplied clips, existing Blueprint animation, or no animation. Generic retarget recipes replace Bob-only preparation assumptions. Blender FBX import/fit/retarget workflow is documented, not universally automated.
- Room, home, explicit JSON primitive layout and authored Unreal map support. `configs/bob_home_edit.json` contains the actual 1,156 exported home pieces for editing without rebuilding C++. Profiles/maps require restart. Mutable map state needs its own reset adapter.
- Named processes with separate ports, tokens, snapshots, logs, UserDir/Saved state, guarded launch/stop and per-instance client selection. Bounded HTML preview memory; full streamed transitions/frames retained.
- Per-run source ZIP, resolved configuration, engine/binary/source/asset hashes, offline verification and a local source-only handoff archive. The inventory distinguishes primary assets from a full mounted-content scan; neither claims every engine/plugin dependency is captured.
- [Complete researcher manual](manual/README.md): installation, every configuration field, avatars/Blender, worlds, architecture/API, reproduction, scaling, operations/migration, testing and extension.

Detailed evidence paths below identify private original-workstation artifacts. They are excluded from this source repository; run the documented checks to generate your own evidence.

## Automated evidence

| Layer | Result and evidence |
| --- | --- |
| Python | **17 passed**; `local/python-tests-0.2.txt` |
| UE 5.8.3 build | Succeeded, 54.46 seconds; `local/build.log` |
| Editor preparation | Manny fixture-map/material generation and Bob retarget/material preparation completed without errors; latest `local/asset-preparation.json` |
| Rendered Bob home | **11 live checks**, 234 records, **468 images**; `runs/20261020T103037Z_992e6a9f/verification.json` |
| Rendered Manny layout | **7 contract checks**, 9 records, 18 images; `runs/20261020T095956Z_05ac669f/contract-check.json` |
| Authored Unreal map, Manny | **7 contract checks**, 9 records, NullRHI; `runs/20261020T101403Z_b6bf78bb/contract-check.json`; no rendered-map claim |
| Exported home reloaded with Manny | **7 contract checks**, 9 records, NullRHI; `runs/20261020T103819Z_c909dbad/contract-check.json` |
| Geometry and process isolation | All **1,156** exported primitive transforms/material/collision/shape records matched reload at 0.0001 comparison tolerance. Simultaneous rendered Bob and NullRHI Manny had independent step/reset state and distinct tokens/ports/configs; `local/export-and-isolation-check.json` |
| Offline integrity | Bob 234 records/468 images and exported-world 9 records verified; `local/verified-bob-0.2.json`, `local/verified-layout-0.2.json` |
| Actual Chrome replay | **5 checks**: image decode, desktop/mobile overflow, scrub, playback. Bob run `browser-check.json`, `viewer-desktop.png`, `viewer-mobile.png` |
| Source handoff | Per-file hashes, private/asset exclusions and repeated archive identity checked; `local/source-bundle-check.json` |

The Bob run also carries copies of the final build, Python-test, preparation and export/isolation/offline evidence files. Original run-time source.zip and provenance are preserved, not rewritten to pretend later documentation existed during the recording. Earlier Manny rendered evidence predates final nonvisual export/readiness additions; exact source/binary provenance is in each manifest.

Recorded 2026-10-20 reference adapter DLL SHA-256: `796d64d9b775770c49e76eed14b7feaa600a72aa94b35ddf896171cae2a2f9c9`.

Original Bob Blueprint SHA-256: `7bdbf5cf0efd0b6155b31af6912fdbb9e84e600065b6c4fa9d8c9c3b53a4ac2f`. It retained its 211019-byte size and 2026-10-12 modification date. Source avatar content was mounted for reading; generated saves were constrained to the isolated local plugin namespace.

## Current review artifact and limits

Open `runs/20261020T103037Z_992e6a9f/report.html`, or serve it with `scripts/view.ps1 -Run runs/20261020T103037Z_992e6a9f`. It is a privileged scripted tour, not a trained policy. Mean recorded step latency was 0.219 seconds, maximum 0.278 seconds on this Intel Arc 140V / approximately 16 GB host. Each action supplies 0.1 simulated seconds and captures two images. Startup remains multi-minute for cinematic MetaHuman assets; this is not a large-scale throughput benchmark.

Human appearance, animation, camera and realism acceptance remains **PENDING**; follow WORLD.md and manual/09-testing.md. Tests reduce risk but cannot guarantee future phases have no problems. Newly supplied Blender/nonhuman rigs, a second clean machine, large worker counts and distributed scheduling remain unverified. Avatar changes require fitting and compatible animation. Arbitrary live hot reload, full mutable-world reset, physics/pixel determinism, blending/balance learning, grasping, task rewards, ML training and consciousness measurement are not implemented.

Historical status notes and the append-only human decision record are retained locally and excluded from Git because they contain workstation-specific paths and evidence. The owner explicitly authorized this source-only GitHub push and MIT license on 2026-10-22. That does not supply a human visual PASS or authorize later training/interaction phases.
