# Detailed avatar control: implementation and verification plan

Status: M1a finger/wrist actuator implemented and rendered checks passed;
human visual acceptance pending. Full-hand, full-body and facial control remain
future increments.
The owner requested this work on 2026-10-29, before further brain work.
This work reopens avatar/control verification. Earlier demonstrations do not
constitute acceptance of these new motor capabilities. No training is involved.

### Human decision, 2026-10-30

The owner replied "go ahead" to the M0 plan review and requested compatibility
with a future scanned-face MetaHuman. This accepts proceeding with M1a; it does
not count as a human visual PASS for any actuator demonstration.

### M1a evidence, 2026-10-30 (Asia/Calcutta)

- UE 5.8.3 native build succeeded (103.21 seconds).
- 27 Python tests passed: 8 core, 9 profile, 4 inventory and 6 motor mapping.
- Rendered Bob run: `runs/motor/20261029T201927Z_77f6e55f` (directory uses UTC).
  85 frames, 84 commanded steps, 170 PNG images. Offline integrity verified.
- Measured local-axis deltas agreed with requested targets to below 0.001
  degrees in this run. This is supplied kinematic pose control, not physical
  joint accuracy or biomechanical validation.
- Nine live checks passed: rejected boolean, range, unknown channel, stale step
  and rate-limit violations; exclusive action ownership; between-tick persistence;
  neutral reset; and evaluated pose/target agreement.
- Agent inspected neutral, positive/negative index and wrist images. Browser
  image display, slider values and playback were checked. Human visual acceptance
  is still pending; no other MetaHuman or scanned avatar has been tested.
- Separate live headless Manny regression confirmed normal navigation without
  a motor map and rejection of disabled motor commands without step changes.
  Evidence: `local/motor-nav-regression-20261030.json`.

Human M1a walkthrough: open the run's `report.html`, press Play, inspect the
isolated finger sweep, wrist sweep and combined movement; check neutral return,
clipping and visible deformation. Report PASS or describe the defect before
expanding the actuator set. This accepts only these two channels and this avatar.

Verify saved motor runs with `python -m erl.motor_verify <run-directory>`.
The verifier checks file hashes, episode ordering and action/image association;
it cannot establish human acceptance or realism.

### M1a implementation

`configs/motor_metahuman_hand_v1.json` supplies two named bindings: left index
proximal joint (local Z offset) and left wrist (local X offset). These are
signed local-axis rotations, not calibrated anatomical flexion measurements.
The sample ranges are conservative diagnostic limits, not medical joint limits.
The mapping has no Bob asset path. Different bindings are supported through a
separate versioned JSON file. Duplicate bones, missing bones and invalid axes
are rejected. A bone can currently have only one configured axis channel.

Opt in at launch:

```powershell
.\scripts\launch.ps1 -Profile local/bob_brain_two.json -Instance bob-motor -Port 8768 -MotorMap configs/motor_metahuman_hand_v1.json
python -m erl.cli wait --instance bob-motor --wait-seconds 420
python -m erl.motor_demo --instance bob-motor
```

Check `ready: true`, not merely a process ID. The finite demo writes its path
under `runs/motor`; open that run's `report.html`. This is a separate
`talos-motor-run/1.0` artifact, not the navigation recorder format. It preserves
input commands, evaluated transforms, image hashes, rig inventory, engine/spec,
source archive and binary provenance. Human visual acceptance remains explicit.

The adapter derives from Unreal's single-node animation instance, evaluates the
supplied idle clip at time zero, adds bone-local quaternion offsets during pose
evaluation, then leaves the existing post-process pipeline in place. Targets
are copied to the animation proxy before evaluation. Source avatar assets are
never saved. Motor mode requires the existing compatible five-clip profile;
arbitrary existing Animation Blueprints are not yet supported by this adapter.

Body LOD0 is forced for this diagnostic; other LODs require their own tests. The
observer image uses a close-up of the last mapped bone, with a fixed camera offset
in avatar heading space. It is a diagnostic camera, not an AI observation.
Different body sizes and opposite hands may need camera adjustments in a later
viewer increment. The normal live game camera remains the existing overview.

`GET /v1/motor` returns readiness, mapping, requested angles, evaluated local
quaternions and measured axis deltas relative to the captured neutral pose.
These diagnostic measurements are not silently added to policy sensors.

`POST /v1/motor/step` accepts exactly `format`, `episode_id`, `expected_step`,
and `targets_deg`; format is `talos-motor-command/1.0`. Supply every mapped
channel. Values are degrees, not normalized actions. The whole command is
validated before mutation, including maximum per-command change
`rate_deg_s * 0.1`. Excess changes are rejected, not interpolated or clipped.
The pose updates at each accepted command; smooth continuous interpolation is
not implemented. Every accepted command advances the shared step by one.
Reset immediately clears all motor offsets and restores the frozen idle pose.

Motor mode exclusively owns an instance's action clock: the existing navigation
step returns 409. Non-motor instances retain their old navigation behavior.
`MotorClient` requires reset after a stale/uncertain mutation; it never blindly
retries a command. Joint quaternions are evaluated values, not target echoes.

### Replacing Bob with a future MetaHuman

1. Assemble/import the new MetaHuman into your Unreal content project. A face
   scan must first be converted into a working MetaHuman with body and facial
   rigs; a raw scan mesh alone is not sufficient.
2. Copy the portable avatar/world profile and choose the new Blueprint, body
   component and mounted content root. Keep machine paths in private machine
   configuration. Supply/retarget clips compatible with the new body skeleton.
3. Run rig inventory on the new avatar and verify its component/bone hierarchy.
   Reuse the hand map only if its bone names, axes and pose behavior match.
   Otherwise copy the map and change bindings; the public channel names can stay
   the same, so the controller does not need avatar-specific names.
4. Launch a dedicated motor instance with that map. Missing bindings fail
   readiness rather than silently omitting movement. A successful load alone
   does not verify axis direction, limits, clothing or facial deformation.
5. Repeat neutral, isolated positive/negative sweeps, persistence and visual
   review. Calibrate range/direction for that avatar and record a new evidence
   run. The future face adapter will require its own acceptance checks even if
   the body map passes. No universal future Unreal-version compatibility is
   claimed; the current build is UE 5.8.3.

### Initial Bob audit, 2026-10-29

The native extension built successfully against installed UE 5.8. The 17 existing
core/configuration tests and 4 new inventory validation tests passed. A live
NullRHI Bob instance reported:

| Component | Reference bones | Morph targets | Active animation instance |
| --- | ---: | ---: | --- |
| Body | 342 | 0 | AnimSingleNodeInstance |
| Face | 875 | 858 | MetaHuman ABP_Face |
| SkeletalMesh | 342 | 0 | None reported |

The extra component's role is not inferred from its generic name. Bone counts
include corrective/deformation helpers and must not be treated as independent
action counts. Facial morph presence does not establish writable expression
controls through the currently active animation pipeline.

Live checks passed for repeatable inventory, unchanged episode/step/control time
after inventory requests, and HTTP 401 for an invalid token. Evidence is stored
locally in `local/bob-rig-inventory-20261029.json` and
`local/bob-rig-checks-20261029.json`. The inventory contains source and adapter
binary hashes. This was a structural headless audit, with no rendered motion test.
Human acceptance and all motor-actuator demonstrations remain pending.

## What complete control means

The target is programmatic access to the avatar's supported voluntary pose and
expression controls: torso, neck, arms, legs, wrists, individual finger joints,
eyes, eyelids, jaw, lips, brows and cheeks. Not every deforming bone is an
independent action. Corrective, twist and facial deformation bones should remain
owned by the rig's solvers. Counts and supported ranges must come from each
avatar adapter, not from assumed universal bone names.

Pose control is separate from physical motor control. A hand closing visually
does not establish a grasp; a posed leg does not establish balance. Contact,
forces, friction, object manipulation and learned locomotion require later
physics work and separate evidence.

## Architecture

Policy -> versioned motor command -> validation and ownership -> avatar adapter
-> Unreal animation/rig evaluation -> measured pose -> observation and recorder.

Keep the four-action erl/1.0 navigation API compatible. The existing trained
navigation models retain their four outputs; they cannot control new channels
without a new controller. Introduce a separately versioned motor action contract
only after the actual actuator mapping has been verified.

Each avatar adapter declares semantic channel, actual rig binding, units,
coordinate frame, neutral value, limits, maximum change per second, supported
LOD, and whether control is direct or supplied through IK/animation assistance.
Unsupported channels must be rejected, never silently ignored. Blender avatars
need their own mappings and facial shapes/rigs; an arbitrary skeleton does not
automatically have expressions or fingers.

Use Unreal for animation evaluation, body/hand IK, rig deformation, rendering,
collision and later physics. Use the external Python layer for policies,
experiments, recordings and analysis. MetaHuman facial deformation must use its
compatible facial animation pipeline; arbitrary bone rotations or generic morph
names must not be presented as verified MetaHuman expressions.

## M0: inventory and mapping design (current)

Implemented GET /v1/rig is authenticated, read-only and privileged. It lists
skeletal mesh components on the spawned avatar, asset paths, selected locomotion
body, active animation instance class, reference bone hierarchy and morph target
names. It does not advance the episode or change assets. It does not enumerate
Control Rig controls, facial curve names, child-actor meshes or per-LOD active
bones. A missing morph target is not evidence that the face cannot be animated.

Capture with:

```powershell
python -m erl.rig --instance bob-brain --output local/bob-rig-inventory.json
```

The output contains a stable inventory hash and explicit unverified motor status.
Run against a newly built and launched harness. Older binaries return 404.
Output is private because it includes avatar asset paths. The command refuses
to overwrite existing evidence. Rig discovery is structural evidence only.

Gate: review the actual body/face hierarchy and proposed control scope with the
human. Do not label the inventory as working finger or expression control.

## M1: body and independent fingers

Implement a pose layer after the supplied base animation, with explicit ownership
for each controlled chain. Avoid directly setting skeletal component transforms
that the animation graph overwrites on the following tick. Verify corrective
deformation and clothing follow the final body pose.

Start with one index finger and one wrist. Then add all available finger joints
on both hands, wrist/arm pose, head/neck, torso, legs and feet. Thumb axes and
coupled joints need rig-specific calibration. Separate convenient hand presets
from independent joint commands. IK targets must advertise solver assistance.

Commands must be atomic: validate the entire command before changing any target.
Require episode ID and expected step; reject stale, unsupported, nonfinite and
out-of-range requests without changing state. Specify partial-update semantics,
neutral reset, interpolation, velocity limits and exclusive controller ownership.
No simultaneous independent navigation and motor writers.

Gate: record isolated positive/negative joint sweeps, neutral resets, simultaneous
finger poses, wrist/arm movement and gait-plus-hand control. Measure requested
versus evaluated transforms. Human inspects both hands, clothing and deformation.

## M2: face and eyes

Inspect Bob's facial animation class, post-process stack and available curve/rig
inputs. Preserve required MetaHuman deformation processing. Bind semantically
named controls only after verifying visible effects and neutral values.

Verify left/right blink separately, gaze yaw/pitch, jaw opening, lip movement,
brows and cheeks, then combined expressions. Smile/frown presets are convenience
combinations, not internal emotions. Independent gaze must be distinguished from
the camera's current look action. Neither camera direction nor facial pose proves
attention, affect or subjective experience.

Gate: facial close-up and side view; verify no double transforms, stuck face,
cross-talk, eye clipping or disappearance at supported LODs. Record each actuator
binding and any channels that remain unavailable.

## M3: integrated control, sensors and replay

Capture target values, evaluated local joint rotations, expression channel values,
timestamps, control mode, active LOD and solver/animation assistance. Separate
privileged diagnostic world coordinates from policy observations. Sensor joint
angles are measured evaluated poses, not merely copies of requested commands.
Record unsupported or saturated commands explicitly.

Provide a light inspection UI with channel search, neutral reset, joint/face
close-ups, requested-versus-measured values and recorded timeline. Manual control
and AI control use the same validation path. A UI emergency release returns to
the documented neutral/base-animation mode; it must not race another writer.

Regression tests: invalid commands cause no state changes; stale commands cannot
apply; reset clears previous targets; lost-response handling avoids double action;
old navigation clients still work; commanded poses survive capture and subsequent
ticks; all advertised channels visibly work at supported LODs. Measure latency
and memory on this workstation before increasing camera sizes or physics detail.

Gate: human verifies a combined body/hands/face demonstration and replay. Only
then connect an AI motor policy. No new training or intelligence claim follows
from a scripted actuator sweep.

## M4: physical interaction (later, separately accepted)

Add hand/object contact sensing, collision geometry, grasp definitions, force or
constraint models, object reset and task metrics. Clearly label scripted attach
grasp assistance if used. Joint pose control alone cannot guarantee physically
valid grasping, self-collision avoidance, balance or locomotion.

## Evidence and reproducibility

For each gate preserve source and binary hashes, engine version, rig inventory,
adapter mapping version, asset hashes, input sequence, actual observed poses,
images, results and the human decision. Source assets stay unchanged. Store
generated rig assets under the isolated harness namespace. Reopen affected gates
after changing avatar, rig mappings, animation pipeline, LOD, engine or timing.
