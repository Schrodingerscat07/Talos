# 07 — Scaling and resource control

## Isolation model

One Unreal process hosts one controlled avatar/environment. Each process has its own loopback API port and token, immutable configuration snapshot, state/log files and Unreal `-UserDir`. The installed engine and read-only content may be shared. Shader/DDC stores can also be shared through Unreal's own cache mechanisms; they are not private experimental state.

```text
local/instances/worker-a/
  state.json
  session.token
  profile-<sha256>.json
  unreal-<launch-id>.log
  user/Saved/...
  user/Intermediate/...
```

Instance names are validated path components; traversal and Windows device names are rejected. The launcher serializes launch bookkeeping, checks recorded live instance/port reservations, and probes the requested port. Stop verifies the recorded PID's actual Unreal command line and snapshot ownership before termination. It does not kill unrelated editor processes by name alone.

## Two local workers

```powershell
python -m erl.manage launch --profile configs/manny_layout.json --instance worker-a --port 8775 --offscreen
python -m erl.manage launch --profile configs/manny_map.json --instance worker-b --port 8776 --headless
python -m erl.cli wait --instance worker-a --wait-seconds 420
python -m erl.cli wait --instance worker-b --wait-seconds 420
python -m erl.contract_check --instance worker-a
python -m erl.contract_check --instance worker-b --allow-no-rgb
python -m erl.manage stop --instance worker-a
python -m erl.manage stop --instance worker-b
```

The local validation exercised two simultaneous processes with distinct ports/tokens/snapshots and confirmed stepping one does not advance the other. This establishes basic isolation, not linear scaling, distributed training, fault-tolerant orchestration or a safe arbitrary worker count.

Use one independent client/control loop per instance. A training manager can collect from multiple processes and batch model inference externally, but ERL does not yet supply a vector-environment wrapper, cluster scheduler, shared-model inference service or checkpoint orchestration. It also does not host multiple independently controlled avatars inside one Unreal process.

## Rendering modes

| Mode | Images | Appropriate use |
| --- | --- | --- |
| Normal launch | Yes, game window | Human inspection and interactive development |
| `--offscreen` | Yes, rendering remains active | Visual-policy diagnostics without a visible game window |
| `--headless` / NullRHI | No | Structural API/kinematic integration tests |

Offscreen is not GPU-free. NullRHI is not a substitute for the visual environment used by an RGB policy. Record the mode in every benchmark and reject missing images when the specification advertises RGB.

## Recorder scaling

Transition/image files stream to disk. The recorder retains counters rather than the whole episode in memory. Closing reads transitions sequentially and builds a preview capped by `preview_frames` (default 2,000, minimum 2), retaining the first and final transition. The HTML/browser loads only that preview. `manifest.replay_preview` tells you if it was sampled.

```python
recorder = Recorder(run_root, spec, seed, provenance, preview_frames=500)
```

Disk remains proportional to all saved frames and transitions; streaming does not make storage free. Plan from measured PNG sizes and steps/episode × episodes. Hash/inventory work and HTML preview generation also take time. Large-scale use may need chunked/remote storage, asynchronous capture/compression and a separate analysis service; those are future adapters, not current capabilities.

## Capacity planning

Start with one lightweight avatar and short episodes. Measure startup time, working/committed memory, VRAM, median/tail step latency, disk rate and complete episode throughput. Increase worker count gradually while keeping task/model/render conditions fixed. GPU readback and two PNG captures per step can dominate runtime; a cinematic MetaHuman's grooms/textures can dominate memory and startup.

The reference Intel Arc 140V / approximately 16 GB host is not a large-training server. Multiple Bob processes are not validated as a recommended load. The successful two-worker check used a mannequin and one NullRHI instance. Maximum-FPS is a rendering cap, not a guarantee of action throughput or physics timing. Engine compilation and shader warm-up should not be mixed into steady-state model comparison without reporting them.

## Failure handling

Do not retry ambiguous mutations. Mark the episode failed, preserve its logs/manifest, reset or restart that worker deliberately, and record a new episode. A stale `local/launch.lock` can remain if the launcher itself crashes; verify no launch is in progress before removing that one file. Failed workers do not automatically resume trajectories or policy/checkpoint state. Loopback binding and local tokens are not a multi-user network authentication/deployment solution.
