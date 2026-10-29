# Phases and human verification gates

## Current motor-control increment

On 2026-10-29 the owner requested detailed body, individual-finger and facial
control before further brain development. The implementation sequence and
acceptance checks are in [MOTOR_CONTROL.md](MOTOR_CONTROL.md). Initial live rig
discovery is verified structurally; this does not pass an actuator or visual
gate. Body/hand, facial and integrated-control demonstrations each need human
review before advancing to the next motor milestone. Earlier phase acceptance
is not inferred from this new work request.

2026-10-30: the owner explicitly authorized proceeding from M0 with a reusable
mapping for future MetaHumans. M1a (left index proximal joint and wrist) now has
rendered automated evidence and a recorded human walkthrough. Its human visual
PASS remains pending; full hands/body/face have not been verified.

Each phase produces runnable artifacts, automated evidence, known limitations, a human walkthrough, and an explicit pass/fail decision. Automated checks alone never approve a phase. Later features must not begin until the human accepts the preceding gate. Passing a gate reduces risk; it does not guarantee that later integration cannot expose problems. New failures reopen affected gates.

## Phase 1 — Simulation and research interfaces

Deliver: isolated Unreal harness; configurable avatar; bounded movement and look actions; collision; first-person RGB/proprioception/contact observations; reset/step/observe/spec; seeded room variation; ordered experiment records; image integrity checks; portable visual report.

Automated gate:
- C++ module compiles against the installed engine.
- Bob's generated Blueprint class loads and spawns in the live engine.
- Reset returns a fresh episode and zero step; repeated seed/action sequences repeat the supplied kinematic trajectory.
- No input means no kinematic body drift. Collisions stop translation.
- Invalid actions, stale steps, and old episode IDs cannot advance the environment.
- Episode horizon is enforced. Transport uncertainty requires a reset.
- Rendered mode returns valid 160x120 PNGs. NullRHI checks are explicitly structural only.
- Records contain matching actions/observations, seed, protocol, source fingerprint, timestamps, specification, checksums, and completion/failure status.
- Privileged diagnostic positions are kept outside the policy observation.

Human walkthrough:
1. View Bob in the research room; confirm it is the intended avatar and inspect geometry, feet placement, clothing, and rig appearance.
2. Run the scripted diagnostic. Confirm forward/backward/turn/strafe/look behavior and wall contact visually.
3. Inspect report.html: scrub frames, compare the first-person view with the trajectory, and check action/contact changes.
4. Confirm that movement is supplied kinematic control; learned locomotion and interaction are not claimed.
5. Report pass or fail with observed defects. Ask the human explicitly; never infer approval from silence.

Phase status: AUTOMATED CHECKS COMPLETE; READY FOR HUMAN VERIFICATION. Human approval: PENDING. See STATUS.md for the exact run and evidence.

## Phase 2 — Research tasks and extensibility

The human requested a world/animation increment before the remaining task-system work. Current subphase **2A** is the small home, courtyard and workshop, supplied idle/directional gait, a rendered tour and light replay interface. Its human visual gate is in WORLD.md. Continuation authorization and the uncompleted detailed Phase 1 human checklist are recorded in GATE_DECISIONS.md. Passing 2A does not complete Phase 2 or authorize training.

Subphase **2B**, after human acceptance of 2A, adds actual interaction, configurable tasks/rewards, evaluation splits and the extensibility checks below.

Deliver: configurable task/reset/reward/termination providers; physical or explicitly assisted object interaction; multiple tasks; train/validation/test layouts; avatar replacement example; versioned configuration; observation/action compatibility tests. Publish clear supplied-control boundaries.

Human gate: swap an avatar or task without rewriting the client; inspect an interaction and reward trace; confirm no hidden engine state enters observations. Approve the tasks and evaluation split before training.

## Phase 3 — Learning baseline

Deliver: recurrent model-free RL baseline; observation-only policy interface; checkpoints; resumable training; fixed and adaptive evaluation modes; multi-seed metrics; random and scripted baselines. Record any pretraining and demonstrations.

Human gate: inspect unseen-layout trials and learning curves; compare trained, untrained, and scripted behavior; confirm training/evaluation separation and budget reporting.

## Phase 4 — Episodic memory experiment

Deliver: bounded memory and retrieval interface; baseline-matched capacity/interaction comparisons; delayed-observation tasks; retrieval visualizations; memory ablations.

Human gate: inspect remembered events and counterexamples; confirm gains require useful memory rather than extra information or a larger budget.

## Phase 5 — Predictive learning experiment

Deliver: action-conditioned latent world model; uncertainty/calibration diagnostics; planning or imagined-policy-training experiment; predictive-model ablations; unexpected-world-change tests.

Human gate: compare predictions against actual outcomes and inspect failures. Accept the experimental design before interpreting gains as a contribution.

## Phase 6 — Continual learning and contribution

Deliver: sequential task learning; replay/consolidation ablations; forgetting/transfer measures; repeated runs and uncertainty; one clearly isolated candidate contribution; negative results and compute costs.

Human gate: review retention and transfer on held-out tasks, confounds, and baseline fairness. Claims must follow evidence.

## Phase 7 — Reusable research release

Deliver: clean-machine installation test; pinned supported engine/runtime versions; example policy/task/avatar adapters; API/version migration rules; benchmark configurations; reproducibility report; dependency/license inventory; contribution guide; sanitized example run.

Human gate: have another researcher follow the guide and reproduce a reference result. Explicitly approve any publication or external release. Bob's MetaHuman content and personal likeness are not included in a source-only release; asset permissions must be assessed separately.

## Gate decision record

Record the phase, exact build/source fingerprint, artifact/run path, automated results, reviewer, review date, PASS/FAIL, limitations accepted, and requested fixes. A reviewer must be human for human-verification fields. Keep decisions append-only. Reopen a passed phase when interface, physics, sensor, or dependency changes invalidate its evidence.
