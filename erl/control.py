"""Atomic body-and-face commands sharing one simulation clock."""
import math
from .client import ProtocolError
from .motor import validate_mapping as motor_mapping
from .face import validate_mapping as face_mapping


class ControlClient:
    def __init__(self, client):
        self.client = client
        state = client.request('control')
        if not state.get('ready'): raise ProtocolError('Combined control is not ready')
        self.motor = motor_mapping(state['motor']['mapping'])
        self.face = face_mapping(state['face']['mapping'])

    def reset(self, seed=42):
        return self.client.reset(seed)

    def step(self, motor_targets_deg, face_targets):
        c = self.client
        if c.episode is None or c.index is None or c.uncertain or c.done:
            raise ProtocolError('Reset required before combined commands')
        body = {x['name']: x['limit_deg'] for x in self.motor['channels']}
        face = {x['name'] for x in self.face['channels']}
        if not isinstance(motor_targets_deg, dict) or set(motor_targets_deg) != set(body):
            raise ValueError('Supply all body channels')
        if not isinstance(face_targets, dict) or set(face_targets) != face:
            raise ValueError('Supply all face channels')
        if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v)>body[k] for k,v in motor_targets_deg.items()):
            raise ValueError('Invalid body target')
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0<=v<=1 for v in face_targets.values()):
            raise ValueError('Invalid face target')
        result = c.request('control/step', dict(format='talos-control-command/1.0', episode_id=c.episode,
                           expected_step=c.index, motor_targets_deg=motor_targets_deg, face_targets=face_targets))
        try:
            c.validate_transition(result)
            if result['episode_id'] != c.episode or result['step_index'] != c.index+1:
                raise ProtocolError('Unexpected combined response ordering')
        except (ProtocolError, KeyError, ValueError):
            c.uncertain = True
            raise
        c.index = result['step_index']; c.done = result['terminated'] or result['truncated']
        return result
