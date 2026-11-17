"""Offline combined recording integrity; not visual acceptance."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from .client import Client


def verify(path):
    path=Path(path).resolve();m=json.loads((path/'manifest.json').read_text(encoding='utf-8'))
    if m.get('format')!='talos-control-run/1.0' or m.get('status')!='completed':raise ValueError('Expected completed control recording')
    for name,digest in m['files'].items():
        p=(path/name).resolve()
        if not p.is_relative_to(path) or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise ValueError('File integrity failure: '+name)
    count=0;episode=None
    for line in (path/'transitions.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line);Client.validate_transition(row)
        if row['step_index']!=count or (episode and row['episode_id']!=episode):raise ValueError('Discontinuous episode')
        episode=row['episode_id'];action=row['control_action'];priv=row['privileged']
        if (action is None)!=(count==0):raise ValueError('Invalid action association')
        for name in ('motor','face'):
            if priv[name]['step_index']!=count or priv[name]['episode_id']!=episode:raise ValueError('Unsynchronized diagnostics')
        if action:
            for name,key,field in [('motor','motor_targets_deg','requested_deg'),('face','face_targets','requested')]:
                targets={c['name']:c[field] for c in priv[name]['channels']}
                if set(targets)!=set(action[key]) or any(not math.isclose(targets[k],action[key][k],abs_tol=1e-5) for k in targets):raise ValueError('Action/target mismatch')
        for image in [row['observation']['rgb']]+[priv[k] for k in ('observer_rgb','face_rgb','left_hand_rgb','right_hand_rgb')]:
            if m['files'].get(image['path'])!=image['sha256']:raise ValueError('Image missing from manifest')
        count+=1
    if count<2 or count!=m['frames']:raise ValueError('Incorrect frame count')
    return dict(status='passed',frames=count,images=count*5,human_review='pending')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path)
    print(json.dumps(verify(p.parse_args().run),indent=2))
