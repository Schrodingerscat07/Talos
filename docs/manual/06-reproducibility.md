# 06 — Reproducibility and provenance

## Three different promises

1. **Configuration reproduction:** same source, engine build, content inputs, resolved profile and control/model settings. Snapshots, hashes and recipes support this.
2. **Kinematic trace repeatability:** same reset seed and action sequence produce matching controller positions under fixed static conditions. The contract check tests this within a live process. Cross-machine reproduction is an additional gate.
3. **Complete world/pixel determinism:** not supplied. GPU rendering, animation graphs, physics, cloth, timers, shader warm-up and arbitrary custom maps can depend on wall time, hardware and engine state. A recording replay shows saved images; it does not re-execute the world.

Do not use a source hash or repeated capsule path as proof of brain equivalence, learning, physical realism or consciousness.

## Inputs to preserve

- Source snapshot/archive and its file manifest; package version and exact engine build/changelist.
- Original portable profile, resolved launch snapshot, private machine path mapping and launch mode/port/instance settings. Tokens are not scientific inputs and must remain private.
- Required source/derived character, Skeleton, animation, map, material and plugin content, subject to their licenses. Preserve export/import/retarget recipes and exporter versions too.
- Seed, action sequence, horizon, control rates, sensor/exposure settings and policy inputs.
- Any model architecture, weight/checkpoint hash, optimizer state, framework/CUDA versions, prompts, pretraining/motion data, demonstrations, task definitions and evaluation split. This foundation does not generate those ML records automatically because it does not train a model yet.
- Hardware/OS and resource/throughput measurements for comparisons. Do not compare NullRHI structural throughput against rendered visual-policy throughput.

The recorder stores the server's actual specification/configuration and launch provenance rather than relying only on a mutable profile filename. `configuration.json` is copied into each configured run. The canonical launch snapshot hash is compared with the engine's parsed configuration by the live contract check and offline verifier.

Managed diagnostics also copy a sanitized `source.zip` into the run and record its SHA-256. A hash alone would not let a later researcher recover overwritten source files; the archive preserves the actual permitted code/config/manual snapshot used for that diagnostic. The offline verifier checks its hash. Personal/derived content still needs its separate permitted archive/inventory.

## Asset inventories

```powershell
python -m erl.manage inventory --profile configs/bob_home.json --output local/bob-primary-assets.json
python -m erl.manage inventory --profile configs/bob_home.json --full --output local/bob-mounted-assets.json
```

Default scope is **primary assets only**, not a transitive dependency inventory. `--full` hashes asset/map/bulk/expansion files under all mounted content roots plus local generated plugin content. It may be slow for a large library. It does not inventory the entire engine installation, engine plugins or every external World Partition dependency type. Preserve the engine distribution/version and inspect world/plugin dependency packaging separately before claiming a fully portable release.

Inventories use virtual mount plus relative filename and file content hashes, enabling comparison across different physical directories. The resolved configuration hash intentionally changes if physical directories differ; compare portable profile content and logical asset inventories when assessing an equivalent installation elsewhere.

## Verify a recording offline

```powershell
python -m erl.verify runs/<run-id>
```

The verifier requires a completed manifest; checks the transition-file SHA-256; validates contiguous steps, one episode, action shape and transition fields; verifies image paths remain inside the run; checks image hashes, dimensions and PNG CRCs; and compares configuration provenance when available. It processes records one at a time. A successful check establishes integrity of the files it covers, not whether a renderer was truthful or the experimental design is valid.

The authoritative data are `transitions.jsonl`, PNG frames, specification/configuration and provenance. For long runs, HTML is a sampled preview. `manifest.replay_preview` records its stride and retained/full record counts. Full transitions and frames are still retained; never analyze only the sampled preview as if it contained every step.

## Clean-machine reproduction checklist

1. Unpack a reviewed source-only bundle; verify `SOURCE_MANIFEST.json` file hashes.
2. Install the declared engine/toolchain/Python versions and required plugins through their owners.
3. Obtain permitted content and recreate its package paths. Create a private machine mapping for this installation.
4. Validate the profile; build; prepare local derived content if needed; doctor required primary inputs. Compare logical asset inventory with the archived reference.
5. Launch one isolated instance; record the returned configuration/build/specification. Confirm requested animation and image availability, not only process startup.
6. Run the contract diagnostic and offline verifier. Compare seed/action kinematic traces with declared tolerance, excluding episode UUIDs, wall timestamps and rendered pixels.
7. Inspect appearance, motion, collision, camera and timing separately. Document differences and reopen affected gates.
8. For actual learning experiments, reproduce model/data/task/evaluation settings and multi-seed metrics separately. A successful environment setup is not a reproduced ML result.

This repository has local swap/isolation tests; it has not been installed by an independent researcher on a clean second machine. Generated Unreal binary assets and compiled binaries are not promised byte-identical across builds. Archive the exact permitted asset/binary inputs when strict provenance is needed.

## Local source handoff and rights

`python -m erl.bundle` creates a ZIP under `local/` containing an explicit source/config/manual/license allowlist and per-file hashes. It excludes `local`, `runs`, generated Content, binaries/caches and historical private status notes. It never uploads or publishes. Inspect the result before sharing. Talos project source is MIT licensed; the license does not grant rights to Unreal, likeness assets or third-party content. See the repository's `LICENSE` and `THIRD_PARTY_NOTICES.md`. Blender software licensing does not, by itself, establish rights to every imported model or motion dataset.
