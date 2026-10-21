"""Profile-independent live checks and a recorded supplied-controller diagnostic."""
import argparse
import json
import math
from pathlib import Path
from .client import Action,ProtocolError
from .manage import client_for,state
from .config import ROOT,fingerprint
from .cli import runtime_provenance
from .recorder import Recorder,checked_png
from .verify import verify

def check(instance='default',seed=42,allow_no_rgb=False):
    client=client_for(instance,180);spec=client.spec()
    assert spec.get('ready') and spec['avatar_loaded'],spec
    if spec.get('animation_mode')=='clips': assert spec['animation_loaded'],spec
    if not allow_no_rgb: assert spec['rgb_available'],'Rendered mode required'
    launch=state(instance)
    assert fingerprint(spec['configuration'])==launch['profile_sha256'],'Engine/launcher profile mismatch'
    tests=['profile_snapshot_matches_engine','avatar_and_requested_animation_loaded']
    actions=[Action(forward=1)]*4+[Action(turn=1),Action(strafe=1),Action(forward=-1),Action()]
    paths=[]
    for _ in range(2):
        reset=client.reset(seed)
        before=reset['privileged']['position_cm']
        assert client.observe()['privileged']['position_cm']==before
        trace=[]
        for action in actions:
            row=client.step(action)
            trace.append(row['privileged']['position_cm'])
        paths.append(trace)
        assert math.dist(before,trace[0])>0 or row['observation']['contacts']['blocked'],'No movement or contact'
    assert all(math.dist(a,b)<1e-5 for a,b in zip(*paths)),paths
    tests+=['no_idle_body_drift','seed_action_kinematic_repeatability']
    old=client.episode
    reset=client.reset(seed)
    for envelope in [dict(episode_id=old,expected_step=0,action=Action().payload()),dict(episode_id=reset['episode_id'],expected_step=1,action=Action().payload())]:
        try: client.request('step',envelope)
        except ProtocolError as exc: assert '409' in str(exc)
        else: raise AssertionError('Conflict accepted')
    assert client.observe()['step_index']==0
    tests+=['old_episode_rejected','stale_step_rejected']
    if spec['max_steps']<=64:
        client.reset(seed)
        for _ in range(spec['max_steps']): last=client.step(Action())
        assert last['truncated']
        try: client.request('step',{'episode_id':last['episode_id'],'expected_step':last['step_index'],'action':Action().payload()})
        except ProtocolError as exc: assert '409' in str(exc)
        else: raise AssertionError('Server accepted a step after the horizon')
        try: client.step(Action())
        except ProtocolError: pass
        else: raise AssertionError('Horizon ignored')
        tests.append('configured_episode_horizon')
    provenance={**runtime_provenance(instance),'policy':'privileged_contract_diagnostic_v2','learning':False}
    recorder=Recorder(ROOT/'runs',spec,seed,provenance)
    try:
        recorder.append(client.reset(seed))
        if spec['rgb_available']:
            (recorder.path/'overview.png').write_bytes(checked_png(client.request('overview')['rgb'],(640,480)))
        for action in actions: recorder.append(client.step(action),action)
    except BaseException as exc:
        recorder.close(str(exc));raise
    recorder.close()
    evidence={'status':'passed','instance':instance,'profile':spec['profile_id'],'checks':tests,'count':len(tests),
              'rgb_available':spec['rgb_available'],'human_review':'pending','run':str(recorder.path),'integrity':verify(recorder.path)}
    (recorder.path/'contract-check.json').write_text(json.dumps(evidence,indent=2))
    (ROOT/'local'/f'latest-contract-{instance}.txt').write_text(str(recorder.path))
    return evidence

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--instance',default='default');parser.add_argument('--seed',type=int,default=42);parser.add_argument('--allow-no-rgb',action='store_true')
    args=parser.parse_args();print(json.dumps(check(args.instance,args.seed,args.allow_no_rgb),indent=2))
