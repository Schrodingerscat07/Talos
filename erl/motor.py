"""Versioned, opt-in joint pose diagnostic; independent of learned policies."""
from __future__ import annotations

import math
import re

from .client import Client, ProtocolError


def validate_mapping(value):
    if not isinstance(value, dict) or set(value) != {'format', 'body_component', 'channels'}:
        raise ValueError('Motor map must contain format, body_component and channels')
    if value['format'] != 'talos-motor-map/1.0' or not isinstance(value['body_component'], str) or not value['body_component']:
        raise ValueError('Unsupported motor map or empty component')
    channels = value['channels']
    if not isinstance(channels, list) or not 1 <= len(channels) <= 64:
        raise ValueError('Expected 1..64 motor channels')
    names, bones = set(), set()
    for c in channels:
        if not isinstance(c, dict) or set(c) != {'name', 'bone', 'axis', 'limit_deg', 'rate_deg_s'}:
            raise ValueError('Invalid motor channel fields')
        for key, seen in [('name', names), ('bone', bones)]:
            if not isinstance(c[key], str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,95}', c[key]) or c[key].lower() in seen:
                raise ValueError(f'Invalid or duplicate {key}')
            seen.add(c[key].lower())
        axis = c['axis']
        if not isinstance(axis, list) or len(axis) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) for x in axis):
            raise ValueError('Axis must contain three finite numbers')
        if not math.isclose(sum(x*x for x in axis), 1, rel_tol=0, abs_tol=0.0001):
            raise ValueError('Axis must have unit length')
        for key, maximum in [('limit_deg', 90), ('rate_deg_s', 360)]:
            if type(c[key]) not in (int, float) or not math.isfinite(c[key]) or not 0 < c[key] <= maximum:
                raise ValueError(f'Invalid {key}')
    return value


class MotorClient:
    """Shares the existing episode clock; never retries uncertain mutations."""
    def __init__(self, client: Client):
        self.client = client
        state = client.request('motor')
        if not state.get('ready'):
            raise ProtocolError(f"Motor unavailable: {state.get('error')}")
        self.mapping = validate_mapping(state['mapping'])

    def reset(self, seed=42):
        return self.client.reset(seed)

    def step(self, targets_deg):
        c = self.client
        if c.episode is None or c.index is None or c.uncertain or c.done:
            raise ProtocolError('Reset required before motor commands')
        channels = {item['name']: item for item in self.mapping['channels']}
        if not isinstance(targets_deg, dict) or set(targets_deg) != set(channels):
            raise ValueError('Supply exactly every configured channel')
        for name, value in targets_deg.items():
            if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > channels[name]['limit_deg']:
                raise ValueError('Motor target outside configured range')
        result = c.request('motor/step', {'format': 'talos-motor-command/1.0',
                                        'episode_id': c.episode, 'expected_step': c.index,
                                        'targets_deg': targets_deg})
        try:
            c.validate_transition(result)
            if result['episode_id'] != c.episode or result['step_index'] != c.index + 1:
                raise ProtocolError('Unexpected motor response ordering')
        except (ValueError, KeyError, ProtocolError):
            c.uncertain = True
            raise
        c.index = result['step_index']
        c.done = result['terminated'] or result['truncated']
        return result
