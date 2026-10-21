# Home, courtyard and workshop — Phase 2A

This increment adds a 26 × 23 m enclosed plot with a furnished home, an open courtyard with pergola and planters, and a furnished workshop. Dimensions are in centimeters. ResearchHome.cpp generates repeated pieces grouped into instanced mesh batches. Materials and 256-pixel textures are generated locally by Unreal editor Python. No external asset downloads are needed.

Bob uses Epic's installed Manny idle and four directional walking sequences, retargeted with Unreal IK rigs onto his body skeleton. The original Bob project remains external and is loaded for reading. Generated animations reference his private skeleton and must not be redistributed with a public source release.

## Run and inspect

Run scripts/prepare-assets.ps1 once, then scripts/build.ps1 and scripts/launch.ps1 -Offscreen. Wait for startup, then run `python -m erl.home_check`. Its output identifies the recording directory containing report.html, overview.png, verification.json and lossless frames. This diagnostic deliberately uses privileged positions and a hand-authored route; it is not an ML evaluation.

Use scripts/view.ps1 with that run directory to serve its replay. Close the previous viewer before changing its served run. The token remains outside the served directory. Scrubbing and playback update images, state and the diagnostic map. Agent observations exclude the map.

In 0.2.0, select the original room with `scripts/launch.ps1 -Profile configs/bob_room.json`. Its existing `erl.cli smoke` and `erl.cli demo` commands assume that layout; use the home-specific check for the new world. See manual/README.md for the current profile-driven workflow.

## Control and supplied assistance

- Existing erl/1.0 actions remain forward, strafe, turn and look. A kinematic collision capsule supplies 150 cm/s travel independently of a learned policy.
- Pose selection and animation time follow command steps. Captures are deferred to the next engine tick so attached face/hair components can consume the new pose; one response is outstanding at a time. Cosmetic groom simulation is disabled. There is no learned locomotion, balance, muscle simulation, joint control, animation blending or turn-in-place animation.
- Furniture, tools, cupboards, planters and work surfaces are scenery. Doorways are open portals. Picking up tools, opening hinged doors, sitting, cooking and arbitrary object use are subsequent work.
- A native Unreal sky atmosphere, fixed daylight ambient cubemap, sun and unshadowed fill lights approximate daylight cheaply. Diffuse GI and ray traced effects are disabled at runtime. This is an architectural research prototype, not calibrated photometric rendering or a photorealistic scanned home.
- Each action supplies 0.1 simulated seconds of kinematic state. Full engine physics, rendering and face animation are not lockstepped. Pixel-identical replay is not promised.
- Reward remains zero and the episode limit remains 500 steps. No training, task rewards, internal drives or consciousness measurement are implemented here.

## Human visual review

Inspect the report and overview, then report PASS or the visible defects:

1. Bob is the intended avatar; clothing follows his body and feet are acceptably placed.
2. Forward, backward and both lateral walks change pose in the appropriate direction. Check for foot sliding, clipping and abrupt changes.
3. The home, courtyard and workshop are recognizable. Check brightness, materials, scale, doorway clearance and camera obstruction.
4. Scrubbing and playback update both images, step information and the map correctly. Readability should hold on a narrow browser window too.
5. Accept the supplied controls and current interaction limits before object-interaction research.

Automated trajectory tests cannot approve appearance, biomechanics or realism. A passed human review reduces risk; later features can reopen affected checks.
