"""Offline face recording integrity, not visual or human acceptance."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from .client import Client


def verify(path):
    path = Path(path).resolve()
    manifest = json.loads((path/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 'talos-face-run/1.0' or manifest.get('status') != 'completed':
        raise ValueError('Expected completed facial run')
    for name, digest in manifest['files'].items():
        file = (path/name).resolve()
        if not file.is_relative_to(path) or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            raise ValueError(f'File integrity failure: {name}')
    count = 0; episode = None
    with (path/'transitions.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            Client.validate_transition(row)
            if row['step_index'] != count or (episode and row['episode_id'] != episode):
                raise ValueError('Discontinuous facial episode')
            episode = row['episode_id']
            action = row['face_action']
            if (action is None) != (count == 0): raise ValueError('Invalid action association')
            channels = row['privileged']['face']['channels']
            if count:
                requested = {c['name']: c['requested'] for c in channels}
                if set(action) != set(requested) or any(not math.isclose(action[k], requested[k], abs_tol=1e-5) for k in action):
                    raise ValueError('Recorded action does not match targets')
            for image in (row['observation']['rgb'], row['privileged']['observer_rgb']):
                if manifest['files'].get(image['path']) != image['sha256']:
                    raise ValueError('Image missing from manifest')
            count += 1
    if count < 2 or count != manifest['frames']: raise ValueError('Frame count mismatch')
    return dict(status='passed', frames=count, images=count*2, human_review='pending')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('run', type=Path)
    print(json.dumps(verify(parser.parse_args().run), indent=2))
