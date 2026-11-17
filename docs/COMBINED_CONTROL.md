# Synchronized avatar control — M3a

Started 2026-11-11 after the owner's M2b PASS and "pass next". This combines
supplied pose controls, not learned movement, balance, grasping or consciousness.
The owner accepted the combined demonstration with "pass" on 2026-11-11:
run `20261111T151237Z_e13cab57`. This accepts the recorded M3a scope only.

## Configuration and ownership

Launch with both a motor map and face map to opt into combined control.
Motor-only and face-only instances retain their existing interfaces. A combined
instance rejects `/v1/motor/step`, `/v1/face/step` and `/v1/step` with HTTP409;
only `/v1/control/step` owns its action clock. Reset zeros both target sets.
Individual read-only diagnostics remain available.

`motor_metahuman_combined_v1.json` merges the accepted maps: 55 unique,
single-axis bone bindings (32 hand/wrist, 14 upper body, nine lower body).
`face_metahuman_combined_v1.json` merges 19 curves (blinks/jaw plus 16 facial
bindings). Facial maps now allow up to 32 channels; old maps remain valid.
Every configured target must be supplied on each command. There is no partial
update or coordinated gaze solver. The body evaluates offsets over the supplied
frozen idle; the face copies its pose and applies curves before MetaHuman
post-processing. Both use LOD0. Existing front review lights affect all captures
and are recorded in assistance metadata. Source avatar assets stay unchanged.

## Atomic command protocol

Authenticated GET `/v1/control` returns `talos-control-state/1.0`, readiness,
episode ID, step index, and nested motor/face states with their mappings.
POST `/v1/control/step` takes exactly five fields:

```json
{
  "format": "talos-control-command/1.0",
  "episode_id": "<reset episode>",
  "expected_step": 0,
  "motor_targets_deg": {"<every configured body channel>": 0},
  "face_targets": {"<every configured facial channel>": 0}
}
```

Both native validators run without mutation first. They check finite numbers
(not booleans), exact keys, bounds, rate limits, episode/step and horizon.
Only when both pass are targets committed, the clock advanced once by 0.1s,
and animation evaluated. Invalid facial targets cannot partially apply a valid
body pose. Combined request limit is 32KiB; old endpoints retain 4KiB limits.
The existing next-tick capture guard serializes requests while rendering.
Transport uncertainty requires reset, not retrying a possibly applied command.

`erl.control.ControlClient` validates targets locally, sends one request and
validates episode/step ordering. An ordering conflict marks the client uncertain.
The base transition protocol and policy observation schema remain unchanged.

## Recording and views

Privileged fields contain motor and face diagnostics plus four 640x480 PNGs:
`observer_rgb` (full body), `face_rgb`, `left_hand_rgb`, `right_hand_rgb`.
They are sequential captures of the same frozen simulated step, not physically
simultaneous sensors. The normal 160x120 policy image is also recorded. These
extra views add rendering cost; throughput has not been benchmarked.
Evaluated motor rotations are measurements; facial curves are not measured
geometry. The combined map ends with pelvis to select the full-body camera.
Close-ups follow the evaluated head/hand bones. Alternate rigs need their
camera anchors, mappings, base clips and post-process verified separately.

The scripted test runs hands + blink, upper body + jaw, lower body + brows,
and a small whole-body pose + lip corners. It commands all 55 body bindings
and selected facial combinations: 52 commands, 53 frames, 265 images.
Source ZIP, binary/asset hashes, launch snapshots, rig inventory, input targets,
evaluated diagnostics and JSONL transitions are preserved. Offline verification
checks file hashes, step/episode ordering, action association and synchronization.
Neither automated checks nor the replay imply human acceptance.

## Reproduce and review

From the repository root, using your private configured avatar profile:

```powershell
.\scripts\build.ps1
.\scripts\launch.ps1 -Profile local/bob_face_expression_review.json -Instance bob-control -Port 8775 -Offscreen -MotorMap configs/motor_metahuman_combined_v1.json -FaceMap configs/face_metahuman_combined_v1.json
python -m erl.cli wait --instance bob-control --wait-seconds 420
python -m erl.control_demo --instance bob-control
python -m erl.control_verify runs/control/<run-id>
python -m erl.manage stop --instance bob-control
.\scripts\view.ps1 -Run runs/control/<run-id>
```

The local profile and Bob assets are private and excluded from Git. Native
build passed in 143.28s. 36 Python tests passed: four combined, five facial,
six motor, eight core, nine profile and four rig tests. The profile path test
was corrected to resolve its expected Windows path before string comparison;
the app sandbox changed path capitalization. No production path behavior changed.
Live results and human decisions must be recorded separately below.

### Rendered evidence — 2026-11-11

Final run: `runs/control/20261111T151237Z_e13cab57`, 53 frames and 265 PNGs.
All 15 live checks passed: atomic rejection with either target set invalid,
both rate limits, missing/unknown channels, stale step/old episode, rejection
of three competing command routes, one clock tick, persistence, neutral reset,
and evaluated motor/face agreement. Offline hashes, action association and
body/face episode synchronization passed. Final hand-camera rebuild passed in
32.08s. The earlier run `20261111T150812Z_c732cea5` is preserved but its hand
close-ups cropped fingertips; the final run uses wider, lower-centered views.

Agent inspection covered body/face combinations, both hands, lower body and
neutral return. Fingertips fit the final hand frames; normal self-occlusion
still hides some fingers. Eye shadows, uncalibrated single-axis joint offsets
and lack of ground contact constraints remain. Browser pose selection,
playback, seeking, all four image decodes and no horizontal overflow were
verified. Bob's source Blueprint SHA256 still matches the original reference
`7bdbf5cf0efd0b6155b31af6912fdbb9e84e600065b6c4fa9d8c9c3b53a4ac2f`.
The native instance was stopped after recording; the local replay remains
available. The owner subsequently supplied M3a PASS on 2026-11-11. Historical
reports/manifests retain their capture-time pending status; this document and
PHASES.md record the later decision. No training or publication was performed.
The standalone modes were not re-run live in this increment; their validation
code is shared and their Python checks passed. Clean-machine reproduction and
other avatars remain unverified.

In the replay inspect body, face and both hands together. Peaks are steps
5–7, 18–20, 31–33 and 44–46; final neutral is step52. Check attachments,
fingers, clothing, facial response and neutral return. Feet may lift/intersect
the floor because this has no balance/contact solver. Reply PASS or describe
defects. This M3a increment does not complete all M3 requirements: interactive
manual control/emergency release, extra policy sensors, moving gait integration
and an AI motor policy remain later work.
