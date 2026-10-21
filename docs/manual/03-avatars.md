# 03 — Avatar and Blender integration

## What “replaceable” means

ERL controls a collision capsule independently of its visible character. A profile can attach an Actor Blueprint or create an actor around any loadable Unreal `USkeletalMesh`. Camera placement, collision dimensions, visual offset, scale, facing and animation paths are data. No Python policy rewrite is needed to swap these inputs.

This does not reconstruct arbitrary anatomy, muscle control or an Animation Blueprint's custom gameplay logic. A robot, quadruped or unusual rig can be displayed and moved by the capsule, but natural locomotion needs clips/logic made for that rig and, for different actuator semantics, a new controller adapter/protocol. Successful loading is a structural check; natural motion and rig quality require inspection.

## Option A: an existing Unreal Blueprint

1. Keep it in its authoring project with its dependencies. Add that project's Content directory to the private machine file.
2. Copy `configs/custom_character.example.json` to a new profile. Set its mount to that content root.
3. Set `avatar.kind` to `blueprint`. Use the generated class path, e.g. `/Game/Characters/Robot/BP_Robot.BP_Robot_C`, not the editor's quoted `/Script/Engine.Blueprint'...'` wrapper.
4. Find the body Skeletal Mesh Component's actual object name in the Blueprint. Set `body_component` to that name, often `Body` or `Mesh`. A visible label is not necessarily the object name.
5. Treat the Blueprint as a passive visual shell. ERL disables the actor tick, its world collisions and movement-component ticks. Timers, AI controllers, physics and other custom components may still contain behavior; remove or adapt code that competes for world transforms or changes research state unexpectedly.
6. Choose animation mode and paths. Configure scale, yaw, offset, capsule and eye separately.
7. Validate, doctor, launch, run the contract check, then inspect feet, clothing, camera direction and motion. A different Blueprint may need additional engine plugins; update the isolated harness descriptor and rebuild, not the original avatar project.

The source Blueprint is never saved by the runtime. ERL changes only its spawned instance.

## Option B: a Skeletal Mesh asset

Use `kind: skeletal_mesh` and a path such as `/Game/Characters/Robot/SK_Robot.SK_Robot`. ERL creates a Skeletal Mesh Component named by `body_component` and attaches the actor to the capsule. This is the smallest route for standard rigs that do not need a custom character Blueprint.

Copy `configs/manny_layout.json` for a working example. It uses installed Epic mannequin content and avoids Bob entirely. Set `animation.mode: none` with empty `clips` for an initial reference-pose fit check; then add compatible animation.

## Fit the body

The root origin, actual geometry height, mesh import scale and controller dimensions are different quantities. A feet-at-origin mesh with an 88 cm capsule half-height typically uses `offset_cm: [0,0,-88]`; this is an example, not a universal rule. Spawn the capsule with its bottom slightly above the floor. A camera offset of `[10,0,77]` relative to a center at z=89 gives an eye around z=166.

Check facing using one forward command. Correct visual facing through `yaw_deg`; changing this does not rotate the policy's local action axes. Fit the capsule so doorways are traversable and the mesh does not visually pass through walls. Recheck eye height and observer camera framing for tall/short characters. Do not compensate for a 100× import-unit error with a hidden arbitrary capsule change.

## Animation routes

The `clips` adapter requires five AnimSequences bound to the body's **exact Skeleton asset**. This is a conservative ERL check; it does not claim that all of Unreal requires identical skeleton objects. If clips come from another skeleton, retarget them first. Unreal's Skeleton and IK retargeting systems support authoring this conversion. [Epic Skeleton documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/skeletons-in-unreal-engine)

For a conventional humanoid, copy Bob's `retarget` recipe and change the target mesh, output folder and prefix. Point the five runtime clips at those outputs. Run preparation and inspect its log. Automatic chain characterization is an initial tool, not proof of correct shoulders, spine, fingers or foot contact. If it fails or looks wrong, author source/target IK rigs and an IK Retargeter in Unreal, export target sequences, then reference those sequences directly. [Epic IK retargeting](https://dev.epicgames.com/documentation/unreal-engine/ik-rig-animation-retargeting-in-unreal-engine)

Use a unique output folder for each avatar/skeleton and recipe revision. Existing compatible generated clips are reused rather than overwritten. Record which motion data and retarget assistance were supplied. Clips are selected without blending, turn-in-place or foot-placement IK; these remain explicit limitations.

At a full movement command, the supplied clip adapter advances at its nominal clip rate. Changing maximum translation speed or visual body scale does not automatically calibrate stride length/foot contact. Validate motion again and supply an appropriate motion-rate/stride adapter if required; the capsule's travel rate alone is not biomechanics.

`existing` mode keeps a preconfigured Animation Blueprint, but ERL does not automatically drive its project-specific variables such as Speed, Direction or gait state. An existing graph that only idles will continue to idle. Implement a tested adapter for its parameters or use the five-clip interface.

## Blender → Unreal → ERL

The supported runtime boundary is an Unreal asset, not a `.blend` file. Blender's FBX exporter carries mesh/armature/animation data, while Unreal imports a skinned FBX as Skeletal Mesh/Skeleton assets. Epic documents FBX 2020.2 as its import-pipeline version; exporter differences need inspection rather than an assumed universal preset. [Blender FBX manual](https://docs.blender.org/manual/en/latest/files/import_export/fbx.html), [Epic skeletal FBX pipeline](https://dev.epicgames.com/documentation/unreal-engine/fbx-skeletal-mesh-pipeline-in-unreal-engine?lang=en-US)

1. Save a source backup. Verify skin weights, a clear root, the intended rest pose and a consistent unit/axis convention. Check expected real dimensions: a 1.7 m person should become approximately 170 cm in Unreal.
2. Select the mesh and intended export armature. Export FBX with only the intended object types/selection. Avoid exporting cameras, lights and control widgets accidentally.
3. Preserve the deformation hierarchy, including a required root/connector bone. “Only Deform Bones” may remove controls you want excluded, but check that it preserves needed hierarchy and root motion. Extra leaf/end bones are usually unnecessary for this adapter; keep the choice consistent across mesh and animation exports.
4. Blender constraints, drivers and control-rig widgets are not an ERL runtime controller. Bake animation to exportable deform-bone transforms. Export the intended action/range deliberately; do not accidentally concatenate unrelated NLA/actions. Keep the mesh and animations on a compatible rest skeleton.
5. Import into a separate Unreal authoring project. Create a Skeleton on the first mesh import; choose it for compatible animation imports. Inspect the Skeletal Mesh/Skeleton editors for scale, orientation, bone hierarchy, normals and deformation before involving ERL.
6. Import/rebuild materials through Unreal. Blender shader graphs do not become the same Unreal material graph automatically. Check texture color-space/normal-map settings and reduce excessive texture, groom and cloth costs.
7. Create or retarget your five movement sequences, or choose `existing`/`none` explicitly. Save all required assets in the authoring project.
8. Mount its Content directory, create the ERL profile and run the same validation/visual gate as for an Unreal-native character.

Blender exporter options and importers change between versions; record the actual Blender version, export settings, FBX file hash and Unreal import settings with your experiment. This project documents the workflow but does not claim to have tested every Blender version or a third-party character that has not been supplied.

## Acceptance before research use

Confirm the intended identity; mesh and Skeleton compatibility; clothing/attachments; head/hair alignment; forward/back/left/right motion; foot placement; camera alignment; collision clearance; and idle stability. Repeat seeded action traces after the swap. Keep source assets and motion data out of a public source bundle unless you have distribution rights.
