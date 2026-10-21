# Talos

**A modular research platform for brain-inspired intelligence.**

Version **0.2.0** provides the simulation and experiment infrastructure. Brain-inspired learning architectures are planned research; this release does not replicate a human brain or establish consciousness.

A configurable Unreal foundation for embodied AI/ML research: interchangeable visual avatars and static worlds, a versioned observation/action API, isolated local simulator processes, and auditable recordings. Movement and animation are supplied; task learning and object manipulation are later work.

**[Read the complete researcher manual](docs/manual/README.md).** It documents every implemented configuration field, installation, Blender/Unreal character integration, world authoring, reproducibility, scaling, API, operations, testing and limitations.

## Start without Bob

Install Unreal Engine 5.8.3, its supported Windows C++ toolchain, and Python 3.11+. Create `local/machine.json` from `configs/machine.example.json` and set your engine path. Mannequin profiles need no private avatar Content root.

```powershell
.\scripts\build.ps1 -EngineRoot 'C:\Program Files\Epic Games\UE_5.8'
.\scripts\prepare-assets.ps1 -Profile configs/manny_map.json
python -m erl.manage doctor --profile configs/manny_layout.json
.\scripts\launch.ps1 -Profile configs/manny_layout.json -Instance trial -Port 8775 -Offscreen
python -m erl.cli wait --instance trial --wait-seconds 420
python -m erl.contract_check --instance trial
.\scripts\stop.ps1 -Instance trial
```

Use `configs/bob_home.json` with your private MetaHuman content root for the original scene. Copy profiles to change parameters or select an Actor Blueprint, Skeletal Mesh, JSON geometry layout or authored Unreal map. Arbitrary rigs still require correct import, dimensions and compatible animation/retargeting; there is no universal automatic biomechanics conversion or live profile hot reload.

The [editable exported home](configs/bob_home_edit.json) contains all 1,156 primitive pieces as data. Copy it and change geometry/materials without rebuilding the plugin, or author an Unreal map for visual scene editing.

## Reproduce and modify

- [Installation and clean-machine procedure](docs/manual/01-installation.md)
- [Full profile and machine configuration reference](docs/manual/02-configuration.md)
- [Replace the avatar, including Blender imports](docs/manual/03-avatars.md)
- [Replace or author the world](docs/manual/04-worlds.md)
- [Architecture, source extension points and policy integration](docs/manual/05-architecture.md)
- [Snapshots, hashes, asset inventory and record verification](docs/manual/06-reproducibility.md)
- [Multiple processes and recording/resource limits](docs/manual/07-scaling.md)
- [Commands, troubleshooting and 0.1.0 migration](docs/manual/08-operations.md)
- [Automated/human acceptance and contribution workflow](docs/manual/09-testing.md)

The wire contract remains [erl/1.0](docs/PROTOCOL.md). Existing `erl` Python commands and `EmbodiedResearch` Unreal module/package paths are retained for compatibility. Machine-specific paths/tokens, generated personal/third-party content and recordings stay outside Git and source handoffs. `python -m erl.bundle` creates a local source-only archive; it does not upload anything.

Read the [verification status](docs/STATUS.md) for tested capabilities and limits. Detailed local recordings and human-gate history are retained privately. Current coverage is local Windows/UE5.8.3; clean-machine, other-platform and large-cluster claims require separate evidence.

See [repository workflow](docs/REPOSITORY.md) for the six-commit source import, cloning and future version-control practices.

## License

Talos project source is released under the [MIT License](LICENSE), copyright 2026 Schrodingerscat07. Unreal Engine, Epic mannequin/MetaHuman content and third-party models or animations are separate dependencies with their own terms; they are not included or relicensed. See [third-party notices](THIRD_PARTY_NOTICES.md).
