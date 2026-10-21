# 08 — Commands, operation and migration

All examples run from the repository root. `--machine` defaults to `local/machine.json`; a different private file can be supplied. Commands accept profile paths; shell snippets never execute JSON contents as code.

| Command | Purpose |
| --- | --- |
| `python -m erl.manage validate --profile <file>` | Strict validation and mount resolution |
| `python -m erl.manage doctor --profile <file>` | Engine build and primary file checks |
| `scripts/build.ps1 -EngineRoot <directory>` | Compile the isolated Editor target/plugin |
| `scripts/prepare-assets.ps1 -Profile <file>` | Editor-only local material/optional retarget/map preparation |
| `scripts/launch.ps1 -Profile <file> -Instance <name> -Port <port> -Offscreen` | Validated isolated launch |
| `python -m erl.manage status --instance <name>` | Recorded metadata and current process presence |
| `python -m erl.cli wait --instance <name> --wait-seconds 420` | Wait for responsive specification |
| `python -m erl.cli spec --instance <name>` | Read declared live conditions |
| `python -m erl.contract_check --instance <name>` | General profile-independent diagnostic |
| `python -m erl.manage inventory --profile <file> --full --output local/assets.json` | Explicit mounted-content inventory |
| `python -m erl.manage export-layout --instance <name> --profile <base-profile> --output configs/<new-name>.json` | Export the running home/layout as editable portable static geometry |
| `python -m erl.verify <run-directory>` | Offline integrity verification |
| `scripts/view.ps1 -Run <run-directory>` | Serve just one replay directory at localhost:8870 |
| `scripts/stop.ps1 -Instance <name>` | Verify ownership and stop only that instance |
| `python -m erl.bundle` | Local source-only handoff ZIP; no publishing |

For `erl.cli`, specifying `--instance` selects its token and port and overrides `--token-file`/`--port`. The default instance maintains the old local token/PID/log aliases for the Bob-specific scripts. The instance directory remains authoritative for managed processes.

## Lifecycle

Stop → change profile/content → validate → prepare if needed → doctor → launch → wait → check/record → inspect. Stop all processes that load the DLL before rebuilding it. You can keep using a replay after the engine stops. Do not overwrite the source avatar project with assets from the harness.

Build output is in `local/build.log`. Managed launch state points to its exact unique Unreal log. A ready log line can precede renderer completion. The startup waiter uses bounded read requests, but abandoned reads can still produce socket-send warnings while the game thread is busy; examine completed integration results and actual errors separately.

## Troubleshooting

| Symptom | Check / response |
| --- | --- |
| Missing machine file/root | Copy the example; use `Content` directories and valid engine root; relative roots are relative to the machine file |
| `doctor` missing asset | Correct virtual mount/package path and obtain dependencies; run preparation for generated plugin outputs |
| Blueprint load failure | Use generated class `.BP_Name_C`; ensure it derives from Actor and required plugins are enabled |
| `missing_body_or_mesh` / `ready: false` | Correct component object name and assign a Skeletal Mesh |
| Skeleton mismatch | Retarget onto the selected body's Skeleton; compatible-looking bone names are insufficient |
| Existing Animation Blueprint only idles | Its custom speed/direction variables are not automatically driven; supply clips or a tested graph adapter |
| Reference pose | `none` mode is intentional or animation failed; do not mark it successful gait |
| Wrong scale, facing or feet | Check import units/rest pose, profile scale/yaw/offset/capsule/eye independently |
| Default/checker materials | Enable and save instanced-mesh material usage in authoring content; check material/shader logs |
| Very dark/bright images | Let shader/texture warm-up finish; check actual lighting and fixed exposure; compare both cameras |
| Hair/head separation | Bob mode disables cosmetic groom physics and defers capture; inspect custom attachments and nonpassive graph/component logic |
| Doorway collision | Capsule dimensions may exceed opening clearance; scenery is solid and contains no automatic navigation/door-opening logic |
| Map never becomes ready | Inspect map package/dependencies/plugins and travel log; Entry is only staging for external maps |
| World does not reset | Custom-map reset is avatar-only; implement and verify a mutable-world reset provider before reproducibility claims |
| HTTP 401 | Match the correct instance token; never paste it into reports |
| HTTP 409 | Stale episode/order/horizon; synchronize the client or reset |
| HTTP 503 pending capture | Use one control client and wait for responses; do not send overlapping actions |
| Transport timeout | Outcome may be unknown; reset, never blindly retry the same step |
| Port/name already used | Inspect recorded worker state; use a distinct port/name or safely stop the old worker |
| Compiler cannot replace DLL | Stop instances/editor commandlets first |
| Memory/shader stalls | Reduce avatar/content cost and worker count; leave time for warm-up; benchmark after it settles |
| Sandbox temporary test failure | Set `TEMP`/`TMP` to an existing writable workspace test directory before Python tests |

## Migration from 0.1.0

- Wire `erl/1.0`, normalized action keys, 0.1-second kinematic interval and sensor dimensions are preserved. Specification/diagnostics add profile and readiness metadata. Consumers should tolerate additive diagnostic fields.
- PowerShell launch parameters changed: use `-Profile`/`-Machine`/`-Instance` rather than legacy `-Avatar`, `-AvatarYaw`, `-ContentRoot`, `-World` and exposure flags. Move those values into the profile/machine file. This is an explicit launcher change in 0.2.0.
- C++ retains legacy direct engine flags for old launches, but the documented supported path is the validated profile launcher.
- Asset preparation now requires a profile and machine mapping; no private Bob filesystem path is embedded in the script.
- `Recorder.entries` is removed to avoid episode-sized memory growth. Use `count`/`last_index`; read full transitions from JSONL. Short replays remain complete; long replays may be sampled.
- The generic replay no longer labels every avatar as Bob or every scene as the home. Existing old HTML files are preserved historical artifacts, not silently rewritten.

Record new verification evidence after migration rather than attaching old binary/launch results to the new build.
