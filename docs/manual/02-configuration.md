# 02 — Configuration reference

An experiment profile is portable JSON with `format: erl-experiment/1.0`. Machine-specific directories live in `erl-machine/1.0`. The launcher resolves them into an immutable, content-hashed snapshot under `local/instances/<name>/profile-<sha256>.json`. That snapshot is passed to Unreal using `-ERLConfig`; the engine reports the parsed configuration in `/v1/spec`.

The [portable profile JSON Schema](../../configs/profile.schema.json) supports editor tooling. `erl.config.validate` additionally enforces cross-field relationships and is the normative validator. The [machine example](../../configs/machine.example.json) is intentionally a template, not an actual installation mapping.

Copy an example rather than editing a profile used by a recorded experiment. Use a new `id` for a meaningful new experimental condition. JSON duplicate keys, unknown fields, nonfinite numbers and invalid dimensions are rejected by the Python validator. C++ repeats critical runtime validation. Always launch through the validated path.

## Root and mounts

Asset/package path validation currently accepts ASCII letters, digits, `_`, `/` and an optional `.Object` suffix. It does not restrict skeleton bone names to that convention. Use compatible Unreal package names in an authoring copy when importing content with other naming conventions.

| Field | Meaning |
| --- | --- |
| `format` | Exactly `erl-experiment/1.0` |
| `id` | Lowercase letter followed by up to 63 lowercase letters, numbers, `_` or `-` |
| `mounts` | List of `{"virtual":"/Game/","source":"avatar"}` entries |
| `world`, `avatar`, `control`, `render` | Required objects described below |
| `retarget` | Optional editor-preparation recipe |

`source` names a key in machine `content_roots`, or the built-in `engine_templates`. A resolved snapshot replaces it with `directory`. Package paths use forward slashes and virtual mounts; filesystem paths belong in the machine file. Keep `/Engine/` and `/EmbodiedResearch/` reserved. Duplicate virtual mount prefixes are rejected. A narrower mount such as `/Game/Characters/` takes precedence over `/Game/`.

Mount the original project's `Content` tree without flattening or renaming its packages. Assets may reference other packages, plugin content, virtual textures or external world-partition data. A primary asset file existing is not proof that all dependencies are available.

## World

| Field | Type / interpretation |
| --- | --- |
| `kind` | `home`, `room`, `layout`, or `map` |
| `map` | Unreal package path without `.Object`; authored map for `map`, otherwise `/Engine/Maps/Entry` |
| `spawn_cm` | Three numbers: capsule center at reset, in world centimeters |
| `heading_deg` | Initial yaw in [-180,180] |
| `bounds_cm` | `[svg_x, svg_y, width, height]` for the privileged top-down map; SVG y is negative world y |
| `overview_cm` | Position of the privileged overview camera; it looks toward the center of the map bounds |
| `pieces` | Empty for other kinds; JSON geometry entries for `layout` |

A layout piece requires `position_cm`, positive `size_cm`, `rotation_deg` as `[pitch,yaw,roll]`, `shape`, `material`, and Boolean `collision`. Shapes are `Cube`, `Cylinder`, `Sphere`, each nominally 100 cm before size scaling. Material aliases are `Plaster`, `Stone`, `Oak`, `Walnut`, `Linen`, `Cream`, `Metal`, `Steel`, `Terracotta`, `Leaves`, `Soil`, `Blue`, `Paper`; alternatively use a full material asset path. Custom materials need Unreal's **Used with Instanced Static Meshes** usage enabled and saved in the authoring project. At most 10,000 explicit pieces are accepted.

## Avatar

| Field | Meaning |
| --- | --- |
| `kind` | `blueprint` or `skeletal_mesh` |
| `asset` | Generated Blueprint class path ending `_C`, or Skeletal Mesh asset path |
| `body_component` | Skeletal component name to animate; for direct meshes ERL creates it with this name |
| `offset_cm` | Visual actor location relative to capsule center; e.g. feet-at-origin mesh with half-height 88 uses `[0,0,-88]` |
| `yaw_deg` | Visual facing correction relative to the controller |
| `scale` | Positive `[x,y,z]` visual scale; uniform scaling is preferable for a skeleton |
| `capsule_radius_cm`, `capsule_half_height_cm` | Collision capsule dimensions; half-height must be at least the radius |
| `eye_offset_cm` | Ego camera location relative to capsule center |
| `animation` | Object containing `mode`, `clips`, `disable_groom_simulation` |

The capsule supplies locomotion collision; the visual actor's collisions and autonomous movement components are disabled. Changing visual scale does not automatically resize the capsule or move the camera. Fit and test all three deliberately. The ego camera currently hides the whole visual actor.

Animation modes:

- `clips`: exactly five paths named `idle`, `forward`, `backward`, `left`, `right`. Each must be an AnimSequence using the selected body's exact Skeleton asset. ERL chooses and samples it at command time. It does not infer joint controls from bone names.
- `existing`: `clips: {}` and `avatar.kind: blueprint`. Keep the Blueprint's configured animation graph. A direct Skeletal Mesh does not contain that actor's graph configuration. Its own code must be passive with respect to world translation; any desired movement inputs need a custom animation adapter. Its animation may evolve with wall time.
- `none`: `clips: {}`. Use a reference pose for structural integration tests. This is not successful walking animation.

`disable_groom_simulation` is Boolean. The Bob reference uses true to prevent cosmetic physics/capture lag. Attached face/groom components receive an engine tick before reset/step response capture.

## Control and rendering

`control.max_steps` is an integer in [1,10,000,000]. `speed_cm_s`, `turn_deg_s`, and `look_deg_s` are positive rates in [.01,10000]. Actions remain four normalized numbers and each accepted action still advances 0.1 simulated seconds. A rate change changes the environment condition and is reported in the specification; do not mix it into an existing baseline silently.

`render.eye_exposure` and `observer_exposure` are fixed manual compensation values in [-8,8]. `max_fps` is an integer in [1,120]. Agent RGB remains 160×120 and observer RGB remains 640×480 for protocol compatibility. Runtime flags lower GI/reflection/shadow/texture cost. Exposure and appearance must be visually rechecked when changing content.

## Optional retarget recipe

Required keys: `source_mesh`, `target_mesh`, `source_clips` with the same five state keys, `output_folder` beneath `/EmbodiedResearch/`, and an alphanumeric/underscore `prefix`. Each destination animation path must equal `output_folder/prefix + source_sequence_name` and match `avatar.animation.clips`.

The preparation script auto-characterizes source and target with Unreal IK rigs, builds the retargeter and saves derived sequences locally. Existing five matching-skeleton outputs are preserved. If you change retarget settings, first archive the old generated outputs and intentionally generate to a new output folder/prefix. Existing files are not evidence that a changed recipe was rerun. Invalid/nonstandard characterization requires a manually authored retargeter or compatible clips.

## Change discipline

Stop the instance, edit/copy the profile or authored map, validate/prepare/doctor as appropriate, and launch again. Record a new experiment. **No live hot reload** is provided: changing layout, avatar or collision dimensions during a recorded episode would invalidate its declared initial condition. Policies can still change their actions on every step through the existing API.
