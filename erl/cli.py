from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

from .client import Action, Client, ProtocolError
from .recorder import Recorder

ROOT = Path(__file__).resolve().parents[1]


def source_fingerprint() -> str:
    import hashlib
    digest = hashlib.sha256()
    for directory in (ROOT / "erl", ROOT / "unreal" / "Plugins" / "EmbodiedResearch",
                      ROOT / "unreal" / "ResearchHarness" / "Source", ROOT / "unreal" / "ResearchHarness" / "Config", ROOT / "scripts",ROOT/'configs'):
        for file in sorted(directory.rglob("*")):
            if file.suffix in {".py", ".ps1", ".cpp", ".h", ".cs", ".ini", ".uplugin",'.json'}:
                digest.update(file.relative_to(ROOT).as_posix().encode())
                digest.update(file.read_bytes())
    digest.update((ROOT / "unreal/ResearchHarness/ResearchHarness.uproject").read_bytes())
    return digest.hexdigest()


def demo_actions():
    # Hand-authored hardware/interface diagnostic. This is not an ML policy.
    return ([Action(forward=1)] * 45 + [Action(forward=-1)] * 20 +
            [Action(turn=1)] * 10 + [Action(strafe=1)] * 12 +
            [Action(look=1)] * 5 + [Action(look=-1)] * 5 + [Action()] * 3)


def runtime_provenance(instance: str = 'default') -> dict:
    import hashlib
    provenance = {"source_sha256": source_fingerprint(), "policy": "scripted_interface_diagnostic_v1", "learning": False}
    from .bundle import build
    import uuid
    source_dir=ROOT/'local/sources';source_dir.mkdir(parents=True,exist_ok=True)
    temporary=source_dir/(uuid.uuid4().hex+'.zip')
    archive=build(temporary)
    permanent=source_dir/(archive['sha256']+'.zip')
    if permanent.exists(): temporary.unlink()
    else: temporary.replace(permanent)
    provenance['source_bundle']={'path':str(permanent),'sha256':archive['sha256'],'files':archive['files']}
    binary = ROOT / "unreal/ResearchHarness/Binaries/Win64/UnrealEditor-EmbodiedResearch.dll"
    if binary.exists():
        provenance["adapter_binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
    launch = ROOT / "local" / "launch.json"
    managed=ROOT/'local/instances'/instance/'state.json'
    if managed.exists(): launch=managed
    if launch.exists():
        provenance["launch"] = {k:v for k,v in json.loads(launch.read_text(encoding="utf-8-sig")).items() if k not in ('token_file','command')}
        snapshot=provenance['launch'].get('config_snapshot')
        if snapshot:
            contents=Path(snapshot).read_bytes()
            provenance['resolved_configuration']=json.loads(contents)
            provenance['configuration_sha256']=hashlib.sha256(contents).hexdigest()
            from .manage import inventory
            provenance['primary_asset_inventory']=inventory(provenance['resolved_configuration'],Path(provenance['launch']['engine_root']))
    generated=ROOT/'unreal/Plugins/EmbodiedResearch/Content'
    if generated.exists():
        digest=hashlib.sha256()
        files=sorted(p for p in generated.rglob('*') if p.is_file() and p.suffix in ('.uasset','.umap','.ubulk','.uexp'))
        for file in files:
            digest.update(file.relative_to(generated).as_posix().encode())
            with file.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''): digest.update(chunk)
        provenance['generated_assets']={'sha256':digest.hexdigest(),'files':len(files),
                                        'source':'entire local generated plugin asset store; may include unused avatars; primary inventory identifies selected inputs'}
    return provenance


def main():
    parser = argparse.ArgumentParser(description="Talos research simulation")
    parser.add_argument("command", choices=["wait", "spec", "demo", "smoke"])
    parser.add_argument("--token-file", type=Path, default=ROOT / "local" / "session.token")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument('--instance',help='Use an isolated managed instance; overrides token-file and port')
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--wait-seconds", type=int, default=300)
    parser.add_argument("--runs", type=Path, default=ROOT / "runs")
    parser.add_argument("--allow-no-rgb", action="store_true", help="Structural headless check only; cannot pass the visual gate")
    args = parser.parse_args()
    if args.instance:
        from .manage import client_for
        client=client_for(args.instance)
    else: client = Client(args.token_file.read_text(encoding="utf-8-sig"), args.port)
    if args.command == "wait":
        client.timeout = 25
        deadline = time.monotonic() + args.wait_seconds
        while time.monotonic() < deadline:
            try:
                ready=client.spec()
                print(json.dumps({k:ready.get(k) for k in ('ready','profile_id','avatar_loaded','animation_loaded','rgb_available','engine_version')},indent=2))
                return
            except ProtocolError:
                time.sleep(2)
        raise TimeoutError("Harness did not become responsive; inspect the latest Unreal log")
    spec = client.spec()
    if args.command == "spec":
        print(json.dumps(spec, indent=2))
        return
    if not spec.get("avatar_loaded"):
        raise RuntimeError("Avatar did not load. See Unreal log before collecting results.")
    if not spec.get("rgb_available") and not args.allow_no_rgb:
        raise RuntimeError("RGB is unavailable; a visual run requires the renderer.")
    if args.command == "smoke":
        from .smoke import check_live
        print(json.dumps(check_live(client, args.seed, args.allow_no_rgb), indent=2))
        return
    recorder = Recorder(args.runs, spec, args.seed, runtime_provenance(args.instance or 'default'))
    try:
        recorder.append(client.reset(args.seed))
        for action in demo_actions():
            recorder.append(client.step(action), action)
    except BaseException as exc:
        recorder.close(str(exc))
        raise
    else:
        recorder.close()
    print(str(recorder.path / "report.html"))


if __name__ == "__main__":
    main()
