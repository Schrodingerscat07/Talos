"""Local Windows process isolation and reproducible, resolved launch inputs."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import uuid

from .config import ROOT,ConfigError,encoded,fingerprint,read_json,resolve,package_file
from .client import Client

def instance_dir(name):
    if not re.fullmatch('[a-z][a-z0-9_-]{0,47}',name): raise ConfigError('Invalid instance name')
    if name in {'con','prn','aux','nul',*[f'com{i}' for i in range(1,10)],*[f'lpt{i}' for i in range(1,10)]}: raise ConfigError('Reserved Windows device name')
    return ROOT/'local/instances'/name

def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8');temp.replace(path)

def process_alive(pid):
    if type(pid) is not int or pid<=0: return False
    if os.name!='nt': raise ConfigError('Process management is currently Windows-only')
    result=subprocess.run(['tasklist','/FI',f'PID eq {pid}','/FO','CSV','/NH'],capture_output=True,text=True,creationflags=0x08000000)
    return any(len(row)>1 and row[1]==str(pid) and row[0].lower()=='unrealeditor.exe' for row in csv.reader(io.StringIO(result.stdout)))

def state(name='default'):
    return read_json(instance_dir(name)/'state.json')

def client_for(name='default',timeout=120):
    s=state(name)
    return Client(Path(s['token_file']).read_text(encoding='utf-8-sig'),s['port'],timeout)

def inspect_inputs(profile,engine,allow_unprepared=False):
    version_file=engine/'Engine/Build/Build.version'
    version=read_json(version_file)
    if [version.get(k) for k in ('MajorVersion','MinorVersion','PatchVersion')]!=[5,8,3]:
        raise ConfigError('Only UE 5.8.3 is validated. Port/build/verify against another engine before using it.')
    exe=engine/'Engine/Binaries/Win64/UnrealEditor.exe'
    if not exe.is_file(): raise ConfigError(f'Engine executable missing: {exe}')
    assets=[profile['avatar']['asset']]
    if profile['world']['kind']=='map': assets.append(profile['world']['map'])
    if not allow_unprepared: assets.extend(profile['avatar']['animation']['clips'].values())
    for asset in assets:
        extension='.umap' if asset==profile['world']['map'] and profile['world']['kind']=='map' else '.uasset'
        file=package_file(asset,profile,extension)
        if asset.startswith('/Engine/'): file=engine/'Engine/Content'/(asset[len('/Engine/'):].split('.')[0]+extension)
        if file is None or not file.is_file(): raise ConfigError(f'Asset file missing/unmounted: {asset} ({file})')
    return version

def launch(profile_path,machine_path,name='default',port=8765,headless=False,offscreen=False):
    if os.name!='nt': raise ConfigError('Launcher is Windows-only; source portability has not been validated')
    if type(port) is not int or not 1024<=port<=65535: raise ConfigError('Port must be 1024..65535')
    profile,engine=resolve(profile_path,machine_path)
    inspect_inputs(profile,engine)
    binary=ROOT/'unreal/ResearchHarness/Binaries/Win64/UnrealEditor-EmbodiedResearch.dll'
    if not binary.is_file(): raise ConfigError('Build scripts/build.ps1 first')
    directory=instance_dir(name);directory.mkdir(parents=True,exist_ok=True)
    lock=ROOT/'local/launch.lock'
    try: lease=lock.open('x')
    except FileExistsError as exc: raise ConfigError('Another launcher holds local/launch.lock; verify it is stale before removing it') from exc
    try:
        for file in (ROOT/'local/instances').glob('*/state.json'):
            prior=read_json(file)
            if process_alive(prior.get('pid')) and (file.parent==directory or prior['port']==port):
                raise ConfigError('Instance name or port is already in use by a recorded live engine')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',port))
        snapshot=directory/('profile-'+fingerprint(profile)+'.json')
        snapshot.write_bytes(encoded(profile))
        token_file=directory/'session.token'
        if not token_file.exists(): token_file.write_text(secrets.token_hex(32),encoding='ascii')
        log=directory/('unreal-'+uuid.uuid4().hex[:8]+'.log')
        exe=engine/'Engine/Binaries/Win64/UnrealEditor.exe'
        args=[str(exe),str(ROOT/'unreal/ResearchHarness/ResearchHarness.uproject'),'/Engine/Maps/Entry','-game','-ERL',
              f'-ERLConfig={snapshot}',f'-ERLPort={port}',f'-ERLTokenFile={token_file}',f'-UserDir={(directory/"user").as_posix()}/',
              '-windowed','-ResX=960','-ResY=640','-NoSplash','-Unattended','-NoSound','-NoVSync','-DisablePython','-NoScreenMessages',
              '-ExecCmds=sg.ViewDistanceQuality 1,sg.ShadowQuality 1,sg.PostProcessQuality 0,sg.TextureQuality 1,r.RayTracing.ForceAllRayTracingEffects 0,r.DynamicGlobalIlluminationMethod 0,r.ReflectionMethod 0,t.MaxFPS '+str(profile['render']['max_fps']),f'-abslog={log}']
        if headless: args.append('-NullRHI')
        if offscreen: args.append('-RenderOffscreen')
        process=subprocess.Popen(args,cwd=ROOT,creationflags=0x08000000,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        info={'format':'erl-instance/1.0','name':name,'pid':process.pid,'port':port,'token_file':str(token_file),
              'profile_id':profile['id'],'profile_sha256':fingerprint(profile),'config_snapshot':str(snapshot),
              'engine_root':str(engine),'log':str(log),'headless':headless,'offscreen':offscreen,
              'started_utc':datetime.now(timezone.utc).isoformat(),'command':args}
        try: write_json(directory/'state.json',info)
        except BaseException:
            process.terminate();raise
        if name=='default':
            (ROOT/'local/unreal.pid').write_text(str(process.pid))
            (ROOT/'local/session.token').write_text(token_file.read_text())
            (ROOT/'local/latest-unreal-log.txt').write_text(str(log))
            write_json(ROOT/'local/launch.json',{k:v for k,v in info.items() if k!='command'})
        return {k:v for k,v in info.items() if k not in ('command','token_file')}
    finally:
        lease.close();lock.unlink()

def stop(name='default'):
    s=state(name);pid=s['pid']
    if not process_alive(pid): return {'status':'already_stopped','name':name}
    snapshot=Path(s['config_snapshot']).resolve()
    if not snapshot.is_relative_to(instance_dir(name).resolve()): raise ConfigError('Instance snapshot is outside its directory')
    quoted="'"+str(snapshot).replace("'","''")+"'"
    # Verify exact instance ownership, including PID reuse, before terminating.
    script=f"""$taskInfo=Get-CimInstance Win32_Process -Filter 'ProcessId = {int(pid)}'
if(!$taskInfo -or $taskInfo.Name -ne 'UnrealEditor.exe' -or !$taskInfo.CommandLine.Contains({quoted})) {{throw 'PID does not belong to this instance'}}
$taskWorkers=Get-CimInstance Win32_Process -Filter 'ParentProcessId = {int(pid)} AND Name = "ShaderCompileWorker.exe"'
foreach($taskWorker in $taskWorkers) {{if($taskWorker.ExecutablePath -and (Split-Path -Parent $taskWorker.ExecutablePath) -eq (Split-Path -Parent $taskInfo.ExecutablePath)) {{Stop-Process -Id $taskWorker.ProcessId -ErrorAction SilentlyContinue}}}}
Stop-Process -Id {int(pid)}
Wait-Process -Id {int(pid)} -Timeout 10 -ErrorAction SilentlyContinue
"""
    import base64
    command=base64.b64encode(script.encode('utf-16le')).decode()
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',command],check=True,creationflags=0x08000000)
    return {'status':'stopped','name':name,'pid':pid}

def inventory(profile,engine,full=False):
    records=[]
    sources=list(profile['mounts'])+[
        {'virtual':'/EmbodiedResearch/','directory':str(ROOT/'unreal/Plugins/EmbodiedResearch/Content')}]
    requested={profile['avatar']['asset'],*profile['avatar']['animation']['clips'].values()}
    if 'retarget' in profile:
        requested.update([profile['retarget']['source_mesh'],profile['retarget']['target_mesh'],*profile['retarget']['source_clips'].values()])
    if profile['world']['kind']=='map': requested.add(profile['world']['map'])
    for mount in sources:
        directory=Path(mount['directory'])
        files=sorted(p for p in directory.rglob('*') if p.is_file() and p.suffix in ('.uasset','.umap','.ubulk','.uexp')) if full else []
        if not full:
            files=[package_file(a,profile,'.umap' if a==profile['world']['map'] else '.uasset') for a in sorted(requested)
                   if a.startswith(mount['virtual']) and next(m['virtual'] for m in sorted(sources,key=lambda x:-len(x['virtual'])) if a.startswith(m['virtual']))==mount['virtual']]
        for file in sorted(set(files)):
            if file is None or not file.is_file(): raise ConfigError(f'Inventory input missing: {file}')
            with file.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
            records.append({'mount':mount['virtual'],'relative':file.relative_to(directory).as_posix(),'bytes':file.stat().st_size,'sha256':digest})
    body=json.dumps(records,sort_keys=True,separators=(',',':')).encode()
    return {'format':'erl-assets/1.0','scope':'all_mounted_content' if full else 'primary_assets_only_not_transitive',
            'sha256':hashlib.sha256(body).hexdigest(),'files':records,'engine_build':read_json(engine/'Engine/Build/Build.version')}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['validate','doctor','launch','status','stop','inventory','export-layout'])
    p.add_argument('--profile',type=Path,default=ROOT/'configs/bob_home.json')
    p.add_argument('--machine',type=Path,default=ROOT/'local/machine.json')
    p.add_argument('--instance',default='default');p.add_argument('--port',type=int,default=8765)
    p.add_argument('--headless',action='store_true');p.add_argument('--offscreen',action='store_true')
    p.add_argument('--full',action='store_true');p.add_argument('--output',type=Path)
    args=p.parse_args()
    if args.command=='stop': result=stop(args.instance)
    elif args.command=='status':
        s=state(args.instance);result={k:v for k,v in s.items() if k not in ('command','token_file')};result['process_alive']=process_alive(s['pid'])
    elif args.command=='launch': result=launch(args.profile,args.machine,args.instance,args.port,args.headless,args.offscreen)
    elif args.command=='export-layout':
        from copy import deepcopy
        from .config import validate
        if not args.output or args.output.resolve().is_relative_to(ROOT/'local/instances'): raise ConfigError('Choose an output profile outside active instance state')
        resolved,_=resolve(args.profile,args.machine)
        client=client_for(args.instance)
        spec=client.spec()
        if fingerprint(spec['configuration'])!=fingerprint(resolved): raise ConfigError('Base portable profile differs from the running configuration')
        result=deepcopy(read_json(args.profile));result['id']=result['id'][:59]+'_edit'
        result['world']['kind']='layout';result['world']['map']='/Engine/Maps/Entry';result['world']['pieces']=client.request('layout')['pieces']
        validate(result)
        if args.output.exists(): raise ConfigError('Refusing to overwrite an existing profile; choose a new output filename')
    else:
        profile,engine=resolve(args.profile,args.machine)
        result={'status':'valid','profile':profile['id'],'profile_sha256':fingerprint(profile)}
        if args.command=='doctor': result['engine_build']=inspect_inputs(profile,engine)
        elif args.command=='inventory': result=inventory(profile,engine,args.full)
    if args.output: write_json(args.output,result)
    else: print(json.dumps(result,indent=2))

if __name__=='__main__':
    try: main()
    except (ConfigError,OSError,subprocess.CalledProcessError) as exc:
        print(str(exc),file=sys.stderr);sys.exit(1)
