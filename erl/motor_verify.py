"""Offline integrity/ordering checks for motor runs, not human acceptance."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(path):
    path = Path(path).resolve()
    manifest = json.loads((path/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 'talos-motor-run/1.0' or manifest.get('status') != 'completed':
        raise ValueError('Expected a completed motor run')
    for name, expected in manifest['files'].items():
        file = (path/name).resolve()
        if not file.is_relative_to(path) or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            raise ValueError(f'File integrity failure: {name}')
    count=0; episode=None; images=0
    with (path/'transitions.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            if row['step_index'] != count or (episode and row['episode_id'] != episode):
                raise ValueError('Discontinuous motor episode')
            episode=row['episode_id']
            if (row['motor_action'] is None) != (count == 0):
                raise ValueError('Incorrect reset/action association')
            for image in (row['observation']['rgb'],row['privileged']['observer_rgb']):
                if manifest['files'].get(image['path']) != image['sha256']:
                    raise ValueError('Image missing from integrity manifest')
                images += 1
            channels=row['privileged']['motor']['channels']
            if count and row['motor_action'] != {c['name']:c['requested_deg'] for c in channels}:
                raise ValueError('Requested target differs from recorded action')
            count+=1
    if count != manifest['frames'] or count<2:
        raise ValueError('Frame count mismatch')
    return {'status':'passed','frames':count,'images':images,'human_review':'pending'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path)
    print(json.dumps(verify(parser.parse_args().run),indent=2))
