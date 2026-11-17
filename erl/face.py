"""Normalized facial curve interface; deformation must be verified separately."""
import math
import re
from .client import ProtocolError


def validate_mapping(m):
    if not isinstance(m,dict) or set(m)!={'format','component','channels'} or m['format']!='talos-face-map/1.0':
        raise ValueError('Invalid face mapping')
    if not isinstance(m['component'],str) or not m['component']:raise ValueError('Missing face component')
    if not isinstance(m['channels'],list) or not 1<=len(m['channels'])<=32:raise ValueError('Expected 1..32 face channels')
    names=set();curves=set()
    for c in m['channels']:
        if not isinstance(c,dict) or set(c)!={'name','curve'}:raise ValueError('Invalid face channel')
        for key,seen in [('name',names),('curve',curves)]:
            if not isinstance(c[key],str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,95}',c[key]) or c[key].lower() in seen:raise ValueError('Invalid or duplicate face binding')
            seen.add(c[key].lower())
    return m


class FaceClient:
    def __init__(self,client):
        self.client=client
        state=client.request('face')
        if not state.get('ready'):raise ProtocolError(f"Face unavailable: {state.get('error')}")
        self.mapping=validate_mapping(state['mapping'])

    def reset(self,seed=42):return self.client.reset(seed)

    def step(self,targets):
        c=self.client
        if c.episode is None or c.index is None or c.uncertain or c.done:raise ProtocolError('Reset required')
        if not isinstance(targets,dict) or set(targets)!={x['name'] for x in self.mapping['channels']}:raise ValueError('Supply all face channels')
        if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in targets.values()):raise ValueError('Face targets must be finite numbers in [0,1]')
        result=c.request('face/step',{'format':'talos-face-command/1.0','episode_id':c.episode,'expected_step':c.index,'targets':targets})
        try:
            c.validate_transition(result)
            if result['episode_id']!=c.episode or result['step_index']!=c.index+1:raise ProtocolError('Unexpected face ordering')
        except (ProtocolError,KeyError,ValueError):
            c.uncertain=True;raise
        c.index=result['step_index'];c.done=result['terminated'] or result['truncated']
        return result
