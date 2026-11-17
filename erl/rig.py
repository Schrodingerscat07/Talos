"""Read-only live rig audit. Discovery does not establish motor control."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .manage import client_for


def validate_inventory(value: dict) -> None:
    if value.get('format') != 'talos-rig-inventory/1.0' or not value.get('avatar_loaded'):
        raise ValueError('A loaded avatar and supported rig inventory are required')
    components = value.get('components')
    if not isinstance(components, list) or not components:
        raise ValueError('No skeletal mesh components found')
    names = set()
    for component in components:
        name = component['component']
        if name in names:
            raise ValueError('Ambiguous component name')
        names.add(name)
        bones = component['bones']
        bone_names = set()
        for index, bone in enumerate(bones):
            if bone['index'] != index or not -1 <= bone['parent_index'] < index:
                raise ValueError('Invalid parent hierarchy')
            if bone['name'] in bone_names:
                raise ValueError('Duplicate bone name')
            bone_names.add(bone['name'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance', default='bob-brain')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    client = client_for(args.instance)
    spec = client.spec()
    if not spec.get('ready'):
        raise RuntimeError('Instance is not ready; wait for asset initialization')
    inventory = client.request('rig')
    validate_inventory(inventory)
    canonical = json.dumps(inventory, sort_keys=True, separators=(',', ':')).encode()
    result = {'inventory': inventory, 'inventory_sha256': hashlib.sha256(canonical).hexdigest(),
              'engine_version': spec['engine_version'], 'profile_id': spec['profile_id'],
              'motor_control_verified': False, 'human_review': 'pending'}
    from .cli import source_fingerprint, ROOT
    result['source_sha256'] = source_fingerprint()
    binary = ROOT / 'unreal/ResearchHarness/Binaries/Win64/UnrealEditor-EmbodiedResearch.dll'
    result['adapter_binary_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Avoid accidentally replacing evidence from an earlier build.
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({'output': str(args.output), 'components': [
        {'name': item['component'], 'bones': len(item['bones']),
         'morph_targets': len(item['morph_targets'])} for item in inventory['components']],
        'motor_control_verified': False}, indent=2))


if __name__ == '__main__':
    main()
