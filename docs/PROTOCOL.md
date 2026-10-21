# ERL protocol 1.0 — implementation 0.2.0

JSON over HTTP on loopback, one environment per port and one controlling client per instance. Every route requires `X-ERL-Token`. Tokens remain private and are excluded from recorded provenance/source handoffs. The managed launcher supplies a validated resolved profile. See [Architecture](manual/05-architecture.md) and [Configuration](manual/02-configuration.md).

The isolated harness mounts external Content for loading and saves generated content only under its local `/EmbodiedResearch` namespace. Do not save original mounted assets in the harness editor.

## Routes

| Method/path | Request | Result |
| --- | --- | --- |
| GET /v1/health | none | Protocol, readiness and environment specification |
| GET /v1/spec | none | Current configuration, sensor/control availability and reset scope |
| POST /v1/reset | `{"seed":42}` | Initial observation; fresh episode UUID and step index 0 |
| GET /v1/observe | none | Current observation without a body action or step advance |
| GET /v1/overview | none | Privileged 640×480 world overview; no step advance |
| GET /v1/layout | none | Privileged primitive snapshot of native home/layout; no step advance; unsupported for room/authored map |
| POST /v1/step | `{"episode_id":"...","expected_step":0,"action":{"forward":1,"strafe":0,"turn":0,"look":0}}` | One accepted kinematic update followed by its observation |

Poll health/spec until `ready` is true. A spawned process or listening port does not establish asset/animation readiness. Missing configured avatar/body/clip compatibility prevents usable reset/step operations.

## Actions, timing and reset

Seeds are integers in `[0,2147483647]`. Actions have exactly four finite JSON numbers in `[-1,1]`; booleans are invalid. Forward/strafe use local axes and the combined translation vector is clamped to unit magnitude. Positive turn increases Unreal yaw; positive look increases pitch. Pitch is clamped to `[-70,70]` degrees.

Each accepted step supplies **0.1 seconds** of kinematic motion. Translation/turn/look rates and episode horizon come from the profile and are reported by spec. Bob's reference defaults are 150 cm/s, 90 degrees/s, 60 degrees/s and 500 steps; those values are not universal protocol constants. Gravity locomotion, joint torques, balance, grasp, jump and learned motor control are not supplied.

Only accepted commands advance the controller's step index and simulated control time. Engine rendering, animation, lighting, physics and custom Blueprint clocks may continue independently. The engine is not physics-lockstepped and pixels are not promised bit-identical.

Reference room/home reset also repositions the supplied seeded obstacle. JSON layouts and authored maps reset the avatar only; authored mutable state needs a separate reset adapter. Read `reset_scope` before comparing episodes. An exported home converts its reference obstacle into a static piece at the exported position.

Reset/step captures defer until the following engine tick to synchronize attached visuals. During that pending response, other observation/mutation calls return 503 `pose_capture_pending`; health/spec remain readable. Wait for each response before issuing another request. This serialization does not create physics lockstep.

## Response and errors

The transition envelope contains `protocol`, `episode_id`, `step_index`, `sim_time_s`, `reward`, `terminated`, `truncated`, `observation` and `privileged`. Reward is currently always zero; terminated is false. Truncated becomes true at the configured horizon, and further steps require reset. See [transition.schema.json](transition.schema.json).

Invalid input returns 400; stale/wrong episode, expected step or exhausted horizon returns 409; unauthorized access returns 401. Unavailable avatar/animation or a pending capture can return 503. Validation precedes controller mutation. Never blindly retry a timed-out mutation: it may have executed. Reset to recover from an uncertain outcome.

## Policy observations and privileged data

Policy observations contain 160×120 RGB PNG, heading, look pitch, displacement-derived local velocity over the last accepted interval (cm/s), and a blocked-contact flag. Heading is a supplied ideal sensor, not a learned visual estimate. `Policy.act` receives only this observation dictionary.

Privileged diagnostics contain world position, seed, obstacle position (nullable when absent), last blocking actor, supplied animation state/gait phase, and a 640×480 third-person image in rendered mode. Overview/layout routes are privileged authoring/testing tools. Their contents are never automatic policy inputs. UUIDs, timestamps and reward/truncation are control metadata.

NullRHI returns no RGB and cannot meet a visual-policy or visual-review gate. A rendered recorder rejects missing/corrupt advertised images. Ego capture hides the avatar to avoid self-occlusion; observer capture displays it. Eye/observer exposure is configurable and reported. Built-in lighting is supplied assistance; authored maps supply their own lighting. Animation modes select configured matching-skeleton clips, preserve an existing Blueprint graph, or supply no animation. None establishes learned motion.

## Recording and replay

Each episode directory contains `manifest.json`, `transitions.jsonl`, `frames/*.png`, `report.html`, and configured-run `configuration.json`. Managed diagnostics also preserve a sanitized `source.zip` snapshot. Row 0 is reset with action null; later rows pair each action with its resulting observation. PNG references include checksums. The manifest begins running and closes completed/failed with the transition checksum and provenance.

Recording is streamed; HTML previews are bounded/sampled for long episodes, while full transition/image data remain available. The manifest states preview stride/counts. Replay displays recorded data; it does not re-execute the engine. `python -m erl.verify <run>` checks covered file/record integrity, not scientific validity, learning or human acceptance. See [Reproducibility](manual/06-reproducibility.md).

## Extension rules

Keep policy, task/reward, recorder, sensor and engine controller responsibilities separate. Adding a body visual or static world must not silently change action units or leak privileged state into observations. Version incompatible motor/sensor/task semantics and rerun affected gates. Profiles/maps are selected at launch; changes require restart. Arbitrary mutable-world reset, interactions, task rewards and ML training remain later work.
