# 01 — Installation and first run

## Requirements

- Windows with Unreal Engine **5.8.3** installed. The doctor rejects other versions until they are ported and verified. Engine build changelist is recorded; the current reference is 58210709.
- Visual Studio 2022 C++ build tools and a Windows SDK supported by that engine. This machine used MSVC 14.44 and SDK 10.0.22621.0.
- Python 3.11 or newer. ERL's runtime client/recorder has no third-party Python dependencies. The reference host uses Python 3.13.6. Unreal editor Python is a separate embedded interpreter.
- Sufficient disk/RAM for your chosen assets. Bob's cinematic MetaHuman is much more expensive than the geometric world. A small mannequin run is the recommended installation check.
- Optional Chrome and Node.js for the supplied real-browser test; they are not required for simulation or recording. Its Chrome executable path is in `tests/browser_report.cjs` and can be adjusted for your installation.

Unreal is not vendored or automatically downloaded. Obtain it and character/world content through their owners' supported channels. Source files alone do not grant rights to distribute Epic or personal avatar assets.

## Private machine configuration

Use a short checkout directory without spaces for the reference Windows workflow, such as `C:\Researches\Talos`. Checkout paths containing spaces have not been validated against Unreal's command-line parsing. Engine installations and external Content roots may contain spaces; those are resolved separately.

Work from the repository root. Copy `configs/machine.example.json` to `local/machine.json`, then edit it. The `local` directory is ignored and excluded from source handoffs.

```powershell
New-Item -ItemType Directory -Force local
Copy-Item configs/machine.example.json local/machine.json
```

```json
{
  "format": "erl-machine/1.0",
  "engine_root": "C:/Program Files/Epic Games/UE_5.8",
  "content_roots": {
    "avatar": "D:/MyMetaHumanProject/Content",
    "research_content": "D:/MyResearchProject/Content"
  }
}
```

`engine_root` is the installation directory above `Engine`. Content roots point at `Content`, not a `.uproject` file. Relative content paths are resolved against the machine file's directory. Do not put API keys or tokens here. The `engine_templates` source is resolved automatically from the engine installation.

For mannequin-only profiles, unused entries can be removed: `content_roots: {}` is valid. This makes the first test independent of Bob and his private project.

## Build and prepare

```powershell
python -m erl.manage validate --profile configs/manny_map.json
.\scripts\build.ps1 -EngineRoot 'C:\Program Files\Epic Games\UE_5.8'
.\scripts\prepare-assets.ps1 -Profile configs/manny_map.json
python -m erl.manage doctor --profile configs/manny_map.json
```

Build before opening any process that loads the DLL. Asset preparation creates only local `/EmbodiedResearch` materials and, for this example, `/EmbodiedResearch/Worlds/FixtureLab`. It uses installed Epic mannequin content; it does not generate or save Bob. Python pip installation at editor startup is disabled in the harness configuration.

`validate` checks profile structure and resolves mounts; it does not load engine assets. `doctor` also checks the installed engine version and required primary asset files. Skeleton compatibility is checked in the live engine, not inferred from file names.

## First Bob-free simulation

```powershell
.\scripts\launch.ps1 -Profile configs/manny_layout.json -Instance trial -Port 8775 -Offscreen
python -m erl.cli wait --instance trial --wait-seconds 420
python -m erl.cli spec --instance trial
python -m erl.contract_check --instance trial
.\scripts\stop.ps1 -Instance trial
```

Wait for a responsive specification, not just a ready log line. Material, texture and pipeline preparation can continue after the HTTP routes are created. The contract check prints a recording directory. Open its `report.html`, or serve that directory with `scripts/view.ps1 -Run <run-directory>`.

`manny_layout.json` uses a 24-step horizon for fast validation. It is an example, not a training benchmark. For a longer episode, copy the profile and increase `control.max_steps` before launching.

## Return to Bob

Supply the `avatar` content root in the machine file, keeping the entire original MetaHuman dependency layout intact.

```powershell
.\scripts\prepare-assets.ps1 -Profile configs/bob_home.json
python -m erl.manage doctor --profile configs/bob_home.json
.\scripts\launch.ps1 -Profile configs/bob_home.json -Instance default -Port 8765 -Offscreen
python -m erl.cli wait --instance default --wait-seconds 420
python -m erl.home_check
```

`home_check` remains a Bob/home-specific visual tour. Use `contract_check` for a replacement avatar/world. Switching profile requires stopping the old instance first. Existing replay files remain usable after the engine is stopped.

## A fresh-machine handoff

Create a local source archive with `python -m erl.bundle`. Give a researcher that archive separately from any licensed/private assets they are entitled to use. They must install the engine/toolchain, create their own machine file, build, prepare and run the mannequin checks above. A clean-machine reproduction is a separate validation gate; success on the original workstation does not establish it.
