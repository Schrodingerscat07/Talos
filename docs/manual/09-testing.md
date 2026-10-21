# 09 — Testing, extension and acceptance

## Separate evidence layers

| Layer | What it establishes | What it does not establish |
| --- | --- | --- |
| Python tests | Validation, unsafe inputs, recorder ordering/integrity, bounded previews and tampering detection | Engine/asset correctness |
| Unreal build | C++/reflection compatibility with the installed engine | Successful scene or avatar loading |
| Editor preparation | Material/retarget/map generation completed for that profile | Natural movement or all dependencies on another machine |
| NullRHI contract | Live API, profile/asset loading, seeded controller paths and ordering without images | Rendering, visual policy behavior or aesthetic quality |
| Rendered contract | Above plus valid sensor images and offline record verification | Universal rig compatibility, human realism or learning |
| Browser QA | Images/layout/scrubbing/playback in actual Chrome | Correct physics or scientific interpretation |
| Human review | Intended identity, motion, appearance, scale, usability and accepted limits | Guarantee of no future integration failures |
| Independent reproduction | Another installation followed the recipe and reproduced specified outputs | Arbitrary platform/version support |

## Commands

```powershell
New-Item -ItemType Directory -Force local/test-temp
$env:TEMP=(Resolve-Path local/test-temp).Path
$env:TMP=$env:TEMP
python -m unittest discover -s tests -v
python -m erl.contract_check --instance trial
python -m erl.verify runs/<run-id>
node tests/verify_report.cjs runs/<run-id>/report.html
node tests/browser_report.cjs runs/<run-id>
```

The Node DOM stub and real browser test are separate. The browser test requires a rendered run, Chrome, and Node with built-in fetch/WebSocket support. It uses its own profile and loopback debugging endpoint; it does not inspect the user's browser. Scrubbing adapts to the number of preview records, including short generic diagnostics.

The live contract compares engine vs launcher configuration, requested avatar/clip availability, idle body stability, repeated seed/action traces, old/stale request rejection and configured horizons up to 64 steps. Longer horizons are not exhaustively stepped by that fast check. The Bob/home diagnostic separately checks doorways, collision, invalid input, authentication and all five gait states. A general contract trace is supplied/privileged control, not an observation-only policy or training result.

## Adding a character/world

Start with one changed variable. Copy a known profile; fit/import/retarget assets; validate and doctor; run the generic rendered contract; verify the recording; inspect the result. For a world, check traversal/collision and correct static-vs-mutable reset scope. For a character, inspect all relevant poses, feet, camera, clothing/attachments and skeleton mapping. Repeat affected gates after changes.

## Adding a new research capability

1. State the concrete behavior and define observable acceptance criteria. Identify supplied assistance and privileged information.
2. Choose the proper source seam: controller for motor semantics; world/reset provider for mutable state; sensor adapter for observations; external policy for ML; recorder/analysis for evidence.
3. Preserve or explicitly version the wire/profile contracts. Update validator, runtime validation, examples and documentation together. Unknown fields should fail rather than silently ignoring a misspelled scientific condition.
4. Keep source avatar/world assets read-only. Save derived content only into a clearly owned local namespace; use new output prefixes for changed retarget recipes.
5. Run meaningful unit/integration checks appropriate to the change, followed by concrete human visual/behavior review. Do not convert AI inspection into a human PASS.
6. Archive source/configuration/content/model inputs and measured limits. An independent reproduction and licensing review are required before a public research release.

The user requested reproducibility/modifiability work after the world prototype. That authorizes this infrastructure/documentation pass; it does not imply a completed human visual gate, authorize publication, or complete task/reward/learning phases. Object interactions, generalized dynamic reset, evaluation splits and trained policies remain later research work.
