# Detailed avatar control: implementation and verification plan

2026-11-11: the owner accepted M3a synchronized control with "pass" for run
`20261111T151237Z_e13cab57`. See [COMBINED_CONTROL.md](COMBINED_CONTROL.md)
for its API, evidence, accepted scope and remaining M3 work.

Status: M1a, M1b, M1c, M1d, M2a and M2b accepted by the owner. M2a covers independent
blinks and jaw opening in the recorded diagnostic. M3a integrated body/face
pose control is also accepted; multi-axis joints, broader facial coverage and
the remaining M3 features are still pending.

M2b covers 16 additional isolated facial bindings. The owner replied "pass"
on 2026-11-05 to the improved-lighting replay `20261104T185232Z_04caa652`.
This is partial facial coverage, not complete control.

Human decision 2026-11-04: "pass" accepts M1d lower-body replay
`20261104T062514Z_75733614` within its diagnostic pose-control limits.

### M2b expression extension — implementation 2026-11-05

Lighting revision requested by the owner on 2026-11-05 (not a human PASS):
face-enabled instances now add two unshadowed directional front fills at
pitch -10 degrees, yaw agent+155/+205 degrees, intensities 3.0/1.5. They
follow the agent/review-camera heading (not the imported mesh yaw offset)
and are runtime-only; original MetaHuman assets are not
saved. These lights affect the whole instance, including policy captures, and
are explicitly listed in `/v1/face.review_lighting` and run assistance metadata.
They are supplied diagnostic lighting, not learned behavior. Non-face instances
do not create them. Existing recordings remain unchanged. Native rebuild passed
after the lighting change; all five facial Python tests passed after the recorder update.

Final camera-aligned light build: 15.09 seconds. Fresh rendered evidence:
`runs/face_lighting/20261104T185232Z_04caa652` (209 frames, 418 images).
All nine live checks and offline recording integrity passed. Agent inspected
neutral, horizontal-gaze and brow frames: facial shading is brighter with
more visible detail; some eye-socket shadow remains. This improves inspection
but does not establish calibrated gaze angles. Engine stopped after recording.
The previous M2b replay remains intact. The owner subsequently accepted this
improved-lighting replay on 2026-11-05. Capture-time manifests and reports keep
their historical pending status; this dated decision records human acceptance.

`configs/face_metahuman_expression_v1.json` supplies 16 independent normalized
channels: up/down/left/right for each eye, inner-brow raise and brow lowering
per side, lip-corner pull per side, and cheek puff per side. These are input
curve names found in Bob's face skeleton, not an exhaustive facial-action set.
The existing native adapter and protocol are reused without a binary change.
Only one channel is activated at a time in this diagnostic; arbitrary opposing
eye commands are not a coordinated gaze controller or an anatomical constraint.
Gaze does not steer the first-person observation camera.

Use the existing launch command with
`-FaceMap configs/face_metahuman_expression_v1.json`, then run
`python -m erl.face_demo --instance bob-expression --sweep-all`.
Set the profile horizon to at least 208 commanded steps. Each channel receives
a rate-limited 0-to-1-to-0 sweep with a brief peak hold, yielding 209 frames.
The report's control selector jumps to each isolated sweep. Neutral is step 0;
channel number N (zero-based in the mapping) peaks at steps 13*N+5 through
13*N+7 and returns to neutral at 13*N+12. The private review profile copies
the prior Bob profile and raises observer exposure from -2 to -0.5; policy-eye
exposure is unchanged. Both exposures remain in recorded provenance.

Readiness, rendered evidence and human acceptance must be checked separately.
Five facial unit tests pass, including isolation, full channel coverage,
rate limits and neutral return for the extended sequence. No additional brain
training or integrated body/face controller is part of this increment.

2026-11-05 evidence (local date; directory timestamps are UTC):
`runs/face_expression/20261104T183311Z_d6e96d81` completed all nine live checks,
209 frames and 418 PNGs. Offline integrity/order/action association passed.
No native changes were made; the previously compiled M2a adapter was reused
and its hash is recorded in the manifest. Browser image decoding, control
selection, frame seeking and playback were checked. The engine was stopped.

Agent inspection covered neutral, all 16 peak frames and final neutral. Brow,
lip-corner, cheek and vertical-eye deformation is visible. Horizontal gaze
remains difficult to assess in the shadowed eyes, despite the exposure-profile
change; stronger fill lighting and a frontal view would improve verification.
Curve agreement does not prove anatomical gaze direction or angle, nor does
it independently measure geometry. No side view, alternate LOD, second avatar,
combined expression or integrated body/face claim is made. M2b human PASS is
pending. Use the replay's control selector and inspect neutral return before
accepting; report uncertain gaze or visible defects instead of inferring PASS.

### M2a recorded evidence — 2026-11-04

The native facial adapter compiled against UE 5.8.3 (1290.05 seconds).
Rendered run `runs/face/20261104T135916Z_8185e4fc` contains 53 frames and
106 PNGs. Nine live checks passed: boolean/range/rate/unknown/stale rejection,
exclusive control, persistence, neutral reset and evaluated curve agreement.
Offline hashes, ordering and action/image associations passed. All 50 Python
tests passed, including four new facial-client tests; brain tests use mock
fixtures and do not establish live learning. The agent inspected neutral,
independent left/right blink and jaw-open images: visible deformation is present.
This is visual inspection, not a quantitative facial geometry measurement.
Lighting is dark around the eyes. No side view or alternate LOD is verified.
The engine instance was stopped after capture. The owner replied "pass" on
2026-11-04, accepting this M2a replay. Historical run files retain their original
capture-time pending status; this dated decision records subsequent acceptance.

`configs/face_metahuman_basic_v1.json` maps three semantic controls to the
MetaHuman input curves `CTRL_expressions_eyeBlinkL`,
`CTRL_expressions_eyeBlinkR` and `CTRL_expressions_jawOpen`. A native
CopyPoseFromMesh animation instance copies the attached body pose and writes
these curves before the existing MetaHuman face post-process/RigLogic stack.
The post-process class is preserved and recorded. Face LOD0 is forced; the
supplied body idle clip is frozen. Original avatar assets are not saved.

GET `/v1/face` returns version `talos-face-state/1.0`, readiness, mapping,
requested/evaluated curves and the post-process class. These are privileged
diagnostics. POST `/v1/face/step` takes exactly `format`, `episode_id`,
`expected_step` and `targets`; format is `talos-face-command/1.0` and targets
must contain every mapped channel. Values are finite numbers in [0,1].
Maximum change is 2 units/second (0.2 per 0.1-second step). Updates are atomic;
reset immediately zeros all targets. Stale/conflicting commands fail, and
transport uncertainty requires reset rather than mutation retries. Curve
readback is not a measurement of eyelid position or jaw angle.

At the original M2a checkpoint, face and body maps required separate instances. M3a adds combined control when both maps are supplied. Normal navigation
commands are rejected in a face-controlled instance. `erl.face.FaceClient`
uses the same authenticated instance connection and episode clock. The
launcher snapshots/hashes the face map alongside the resolved profile.

Reproduce from the repository root, using your own configured avatar profile:

```powershell
.\scripts\build.ps1
.\scripts\launch.ps1 -Profile local/bob_brain_two.json -Instance bob-face -Port 8774 -FaceMap configs/face_metahuman_basic_v1.json -Offscreen
python -m erl.cli wait --instance bob-face --wait-seconds 420
python -m erl.face_demo --instance bob-face
python -m erl.face_verify runs/face/<printed-run-id>
python -m erl.manage stop --instance bob-face
.\scripts\view.ps1 -Run runs/face/<printed-run-id>
```

The example local profile and Bob assets are private and excluded from Git.
Future MetaHumans need a matching component, a body attachment, supported
curves, existing post-process and compatible body clips; readiness checks fail
when these prerequisites are absent. Re-test each avatar. Generic Blender rigs
require their own expression adapter; this map does not make them compatible.

Human review: inspect steps 5–7 for left blink, 18–20 for right blink,
31–33 for both eyes, 44–46 for jaw opening, and 52 for neutral return.
Left/right refer to Bob's anatomy. Confirm independent motion, neutral return,
and absence of stuck eyelids or obvious deformation defects. Reply PASS or
describe the defect before the next facial increment. Gaze, brows, lips,
cheeks, speech and integrated body/face control remain unverified/unimplemented.

Human decision 2026-11-04: "pass move to other details" accepts the M1b left
and right hand recordings and authorizes the next upper-body control increment.
This does not pre-approve new movements, other avatars or facial control.

Human decision 2026-11-04: "ok proceed pass" accepts the M1c upper-body replay
`20261104T060427Z_d4c5cd80` and authorizes the lower-body increment.

### M1d lower-body extension

2026-11-04 evidence: native build passed in 19.10 seconds; six motor-map tests
passed and nine bindings matched the live rig inventory. Run
`runs/motor_lower/20261104T062514Z_75733614` completed 80 commanded steps,
81 frames and 162 images. All nine live checks and offline integrity passed.
The agent inspected neutral, knee and pelvis images; full body/feet are visible.
This establishes commanded local-axis offsets, not anatomically calibrated knee
hinges or contact-preserving motion. Instance stopped; owner subsequently passed
this gate on 2026-11-04 (decision above).

Review frames 1/9/17/25 for left hip/knee/ankle/toes, 33/41/49/57 for the
right side, 65 for pelvis and 73 for the combined pose. Neutral returns occur
throughout. Ground intersection or lifted feet are possible because no contact
or balance solver is supplied. See M2a above for the subsequent facial increment.

`motor_metahuman_lower_body_v1.json` exposes one local axis on each thigh,
calf, foot, toe-ball and pelvis: nine channels. Each receives isolated signed
10-degree offsets, neutral returns and a 2-degree combined diagnostic. These
are pose offsets over a supplied standing clip, without joint physics, ground
constraints, balance, inverse kinematics or gait generation. Feet can penetrate
or leave the ground; those outcomes must not be mistaken for stable locomotion.
Axes/ranges are diagnostic bindings requiring later anatomical calibration.

The pelvis is last in this map to select the full-body diagnostic camera.
Run `python -m erl.motor_demo --instance bob-lower --sweep-all --combined-deg 2`
after launching with this motor map. Source MetaHuman assets remain unmodified.
The owner requested this work on 2026-10-29, before further brain work.
This work reopens avatar/control verification. Earlier demonstrations do not
constitute acceptance of these new motor capabilities. No training is involved.

### Human decision, 2026-10-30

After viewing the M1a replay, the owner explicitly replied "pass". This is the
human acceptance of run `20261029T201927Z_77f6e55f` and its two tested channels,
and authorization to proceed to the next hand-control increment. Subsequent
channels and avatars require fresh verification; this does not approve them.

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

### M1c upper-body extension

Evidence 2026-11-04: native build passed in 50.98 seconds; six motor-map tests
passed and all 14 bindings matched Bob's inventory. Rendered run
`runs/motor_upper/20261104T060427Z_d4c5cd80` completed all nine live checks:
121 frames, 242 images, independent recording integrity passed. The agent
inspected neutral, spine, upper-arm and head frames. Three-quarter view partly
occludes the far arm; this is not exhaustive visual verification of all joints.
The instance was stopped. Human M1c acceptance remains pending.

Review frame 1 for spine, 49 for left upper arm, 57 for left elbow, 73/81 for
right arm/elbow, 89/97 for neck, 105 for head and 113 for combined movement.

`configs/motor_metahuman_upper_body_v1.json` binds five spine joints, both
clavicles, both upper arms and elbows, two neck joints and the head: 14 local
axis controls. Names and axes remain avatar-map data. The test uses signed
10-degree isolated sweeps and 2-degree combined offsets over the supplied idle
pose. Limits are diagnostic limits, not anatomical calibration. No balance,
physical joint torques, foot placement or contact constraints are provided.

Launch with the new map and run:
`python -m erl.motor_demo --instance bob-upper --sweep-all --combined-deg 2`.
Non-hand maps use an avatar overview camera. Hand maps retain their close-up.
Inspect shoulder/clothing deformation, face/neck alignment, unintended movement
and neutral return. The body API still supports one axis per configured bone.

### M1b evidence and scope

Rendered evidence on 2026-10-30: both 16-channel sweeps completed, each with
137 frames and 274 images. All nine live checks passed per run; independent
file-integrity checks passed for both recordings. The six motor-map unit tests
passed and the native build succeeded in 21.94 seconds. Agent inspected both
combined-hand close-ups. Human M1b visual acceptance remains pending.

- Left: `runs/motor_hands/20261029T202833Z_6c06bc69`
- Right: `runs/motor_hands/20261029T203035Z_cf824a9f`
- Review hub: `runs/motor_hands/report.html`

Both test instances were stopped after recording. These changes are local and
uncommitted after the previous GitHub checkpoint `9009ed6`.


Two portable maps, `motor_metahuman_left_hand_v1.json` and
`motor_metahuman_right_hand_v1.json`, each bind three joints per finger/thumb
and one wrist, totaling 16 channels per hand. Maps contain no Bob asset paths.
All 32 bone bindings were checked against Bob's live inventory. They expose
one local axis per bone; finger spreading, thumb opposition and full three-axis
wrist control are not implemented by these maps. Signed local Z offsets on
finger bones require human inspection and later anatomical calibration.

`python -m erl.motor_demo --instance <name> --sweep-all` tests each channel at
+10 and -10 degrees with neutral returns, then combines finger commands. Each
hand runs in its own instance and close-up; simultaneous two-hand operation is
not established by these separate runs. Diagnostic cameras choose the right
side for the `_r` bone convention and left otherwise. Other naming conventions
may need a future explicit camera configuration.

Launch using `-MotorMap configs/motor_metahuman_left_hand_v1.json` or the right
hand equivalent. Build the updated harness before running the right-hand view.
The M1a two-channel template and its original demo remain supported.

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
