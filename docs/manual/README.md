# Talos researcher manual

This manual describes the implemented **ERL 0.2.0** foundation. It covers configuration, operation, modification and verification. The protocol remains `erl/1.0`. Generated recordings use `erl-run/1.0` with additive preview/configuration metadata.

Start with [Installation and first run](01-installation.md), then [Configuration reference](02-configuration.md). To replace the character, follow [Avatar and Blender integration](03-avatars.md). To replace the scene, follow [World authoring](04-worlds.md).

For the new body, individual-finger and facial-control work, see the
[motor control implementation and verification plan](../MOTOR_CONTROL.md).
Its current delivered features are rig discovery and the opt-in two-channel
finger/wrist diagnostic. Rendered Bob checks passed; human acceptance and broader
body/facial controls remain pending.

| Guide | Purpose |
| --- | --- |
| [01 — Installation](01-installation.md) | Dependencies, a Bob-free first run, private machine setup, build/prepare/launch order |
| [02 — Configuration](02-configuration.md) | Every profile field, mount resolution, validation, examples and restart rules |
| [03 — Avatars](03-avatars.md) | Unreal Blueprints, Skeletal Meshes, Blender FBX, animation compatibility and rig limitations |
| [04 — Worlds](04-worlds.md) | Built-in scenes, editable JSON geometry, authored `.umap` levels and reset limits |
| [05 — Architecture and API](05-architecture.md) | Runtime responsibilities, source map, observations/actions and extension rules |
| [06 — Reproducibility](06-reproducibility.md) | What repeats, snapshots/hashes, asset inventory, offline verification and clean-machine reproduction |
| [07 — Scaling](07-scaling.md) | Isolated processes, multiple ports, headless/rendered modes, bounded recording and budgets |
| [08 — Operations](08-operations.md) | Commands, lifecycle, debugging, performance and migration from 0.1.0 |
| [09 — Testing and extension](09-testing.md) | Test layers, swap acceptance, contribution checklist and research claim boundaries |

## Current support boundary

| Capability | Implemented support | Qualification |
| --- | --- | --- |
| Replace Bob | Actor Blueprint or Unreal Skeletal Mesh selected by profile | Component, scale and animation compatibility must be checked |
| Blender character | Import as a Skeletal Mesh in Unreal, then use its asset path | A `.blend` file is not a runtime asset; arbitrary constraints are not automatically recreated |
| Different skeleton | Supply matching clips, retarget, or preserve an existing Animation Blueprint | Automated humanoid characterization may fail; nonhuman motor control needs a suitable adapter |
| Change world | `home`, `room`, JSON `layout`, or authored `map` | Profile/map changes require restart; live hot reload is deliberately not supplied |
| Reproduce kinematics | Seed/reset/action traces under fixed inputs | General physics, cloth, rendering and custom Blueprint behavior are not bit-deterministic |
| Scale experiments | Multiple isolated processes and bounded replay previews | A local process foundation, not a distributed training scheduler or proven large cluster |
| Learn intelligence | Model-independent observation/action client seam | No model training, task reward or consciousness result is implemented |

The profile validator and actual runtime are the source of truth. Examples ending `.example.json` are templates with placeholder paths. Do not describe template support as a tested import of a third-party character.
