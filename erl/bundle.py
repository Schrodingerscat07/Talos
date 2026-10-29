"""Create a local source-only handoff. Never uploads or publishes anything."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from .config import ROOT

def build(output):
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'local'): raise ValueError('Write handoff archives under local/')
    files=[ROOT/'README.md',ROOT/'LICENSE',ROOT/'THIRD_PARTY_NOTICES.md',ROOT/'pyproject.toml',ROOT/'.gitignore',ROOT/'unreal/ResearchHarness/ResearchHarness.uproject']
    directories=['erl','scripts','tests','configs','docs/manual','unreal/ResearchHarness/Source','unreal/ResearchHarness/Config','unreal/Plugins/EmbodiedResearch/Source']
    suffixes={'.py','.ps1','.cjs','.json','.md','.h','.cpp','.cs','.ini'}
    for name in directories:
        files.extend(p for p in (ROOT/name).rglob('*') if p.is_file() and p.suffix in suffixes and '__pycache__' not in p.parts)
    files+=[ROOT/'unreal/Plugins/EmbodiedResearch/EmbodiedResearch.uplugin',ROOT/'docs/PROTOCOL.md',ROOT/'docs/transition.schema.json',ROOT/'docs/WORLD.md',ROOT/'docs/PHASES.md',ROOT/'docs/MOTOR_CONTROL.md']
    entries=[];output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(set(files)):
            if file.is_symlink(): raise ValueError(f'Symlinks are not allowed in a source bundle: {file}')
            name=file.relative_to(ROOT).as_posix();data=file.read_bytes()
            entries.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
            item=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(item,data)
        item=zipfile.ZipInfo('SOURCE_MANIFEST.json',date_time=(2026,1,1,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED
        archive.writestr(item,json.dumps({'format':'erl-source/1.0','license':'MIT for project source; third-party assets excluded','files':entries},indent=2))
    return {'archive':str(output),'files':len(entries),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'excluded':['personal/generated assets','machine paths/configuration','tokens','recordings','engine binaries/caches','historical private status notes']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'local/erl-source-0.2.0.zip')
    print(json.dumps(build(p.parse_args().output),indent=2))
