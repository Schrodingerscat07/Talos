"""Offline recording verification. No simulator or third-party packages needed."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
from .client import Action,Client,ProtocolError
from .config import read_json,fingerprint
from .recorder import checked_png

def verify(directory):
    directory=Path(directory).resolve();manifest=read_json(directory/'manifest.json')
    if manifest['status']!='completed': raise ProtocolError('Recording did not complete successfully')
    with (directory/'transitions.jsonl').open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=manifest['transitions_sha256']: raise ProtocolError('Transition checksum mismatch')
    count=0;images=0;episode=None
    with (directory/'transitions.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line,parse_constant=lambda x: (_ for _ in ()).throw(ProtocolError('Non-finite JSON')))
            Client.validate_transition(row)
            spec=manifest['environment_spec']
            if spec.get('rgb_available') and row['observation']['rgb'] is None: raise ProtocolError('Advertised agent image is missing')
            if spec.get('rgb_available') and spec.get('observer_width') and row.get('privileged',{}).get('observer_rgb') is None:
                raise ProtocolError('Advertised observer image is missing')
            if row['step_index']!=count or (episode and row['episode_id']!=episode): raise ProtocolError('Dropped/reordered step or mixed episode')
            if count==0:
                if row['action'] is not None: raise ProtocolError('Reset has an action')
            else: Action(**row['action']).payload()
            for rgb,size in [(row['observation']['rgb'],(160,120)),(row.get('privileged',{}).get('observer_rgb'),(640,480))]:
                if rgb is None: continue
                file=(directory/rgb['path']).resolve()
                if not file.is_relative_to(directory) or file.suffix!='.png': raise ProtocolError('Image reference escapes recording directory')
                raw=file.read_bytes()
                if hashlib.sha256(raw).hexdigest()!=rgb['sha256']: raise ProtocolError('Image checksum mismatch')
                checked_png({'encoding':'png_base64','width':rgb['width'],'height':rgb['height'],'data':base64.b64encode(raw).decode()},size)
                images+=1
            episode=row['episode_id'];count+=1
    if count!=manifest['transitions']: raise ProtocolError('Manifest count mismatch')
    provenance=manifest.get('provenance',{})
    bundle=provenance.get('source_bundle')
    if bundle:
        file=(directory/bundle['path']).resolve()
        if not file.is_relative_to(directory) or hashlib.sha256(file.read_bytes()).hexdigest()!=bundle['sha256']:
            raise ProtocolError('Source snapshot checksum/path mismatch')
    config=manifest['environment_spec'].get('configuration')
    if config and provenance.get('configuration_sha256') and fingerprint(config)!=provenance['configuration_sha256']:
        raise ProtocolError('Engine configuration differs from launch snapshot')
    return {'status':'passed','transitions':count,'images':images,'scope':'record integrity; not physics, learning or human visual approval'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path)
    print(json.dumps(verify(parser.parse_args().run),indent=2))
