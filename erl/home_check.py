"""Live, layout-specific diagnostic. Uses privileged positions deliberately.

This hand-authored tour is not an observation-only policy or a learned behavior.
It checks traversability and supplied pose selection rather than approving beauty.
"""
import json
import math
from pathlib import Path
import time

from .client import Action, Client, ProtocolError
from .cli import ROOT, runtime_provenance
from .recorder import Recorder, checked_png


def main():
    client=Client((ROOT/'local/session.token').read_text(),timeout=180)
    spec=client.spec()
    assert spec['environment']=='unreal_home_courtyard_workshop_v1'
    assert spec['avatar_loaded'] and spec['animation_loaded'] and spec['rgb_available'], spec
    checks=[]
    initial=client.reset(42)
    position=initial['privileged']['position_cm']
    time.sleep(.4)
    assert client.observe()['privileged']['position_cm']==position
    checks.append('no_idle_body_drift')
    # Collision against the uninterrupted west wall from the clear front aisle.
    travelled=0
    previous=position
    for _ in range(50):
        result=client.step(Action(forward=-1))
        p=result['privileged']['position_cm']
        travelled+=math.dist(previous,p)
        previous=p
    assert travelled>350 and result['observation']['contacts']['blocked']
    assert -1070<p[0]<-1000,p
    checks.append('solid_house_wall_stops_translation_after_real_travel')
    again=client.reset(42)
    assert again['privileged']['position_cm']==position
    assert again['privileged']['obstacle_position_cm']==initial['privileged']['obstacle_position_cm']
    checks.append('seeded_reset')
    episode=again['episode_id']
    try:
        client.request('step',{'episode_id':episode,'expected_step':1,'action':Action().payload()})
    except ProtocolError as error:
        assert '409' in str(error)
    else:
        raise AssertionError('Stale step accepted')
    assert client.observe()['step_index']==0
    checks.append('stale_step_rejected_without_advance')
    bad=Action().payload()
    bad['forward']=True
    try:
        client.request('step',{'episode_id':episode,'expected_step':0,'action':bad})
    except ProtocolError as error:
        assert '400' in str(error)
    else:
        raise AssertionError('Boolean accepted as a numeric action')
    assert client.observe()['step_index']==0
    checks.append('invalid_action_rejected_without_advance')
    fresh=client.reset(42)
    try:
        client.request('step',{'episode_id':episode,'expected_step':0,'action':Action().payload()})
    except ProtocolError as error:
        assert '409' in str(error)
    else:
        raise AssertionError('Old episode accepted')
    assert client.observe()['episode_id']==fresh['episode_id'] and client.observe()['step_index']==0
    checks.append('old_episode_rejected_without_advance')
    try:
        Client('incorrect-token').spec()
    except ProtocolError as error:
        assert '401' in str(error)
    else:
        raise AssertionError('Unauthenticated access accepted')
    checks.append('authentication_required')
    recorder=Recorder(ROOT/'runs',spec,42,{**runtime_provenance(),'policy':'privileged_scripted_home_tour_v1','learning':False,
                                         'purpose':'phase_2A_traversability_and_supplied_animation_diagnostic'})
    states=set()
    timings=[]
    try:
        recorder.append(client.reset(42))
        overview=client.request('overview')
        (recorder.path/'overview.png').write_bytes(checked_png(overview['rgb'],(640,480)))
        def segment(count,action,target=None):
            for _ in range(count):
                start=time.perf_counter()
                result=client.step(action)
                timings.append(time.perf_counter()-start)
                recorder.append(result,action)
                states.add(result['privileged']['animation_state'])
                if action.forward or action.strafe:
                    assert not result['observation']['contacts']['blocked'],result['privileged']
            if target:
                p=result['privileged']['position_cm']
                assert math.dist(p[:2],target)<8,(p,target)
            return result
        segment(5,Action())
        segment(23,Action(forward=1),(-255,-130))
        segment(10,Action(turn=1))
        segment(30,Action(forward=1),(-255,320))
        checks.append('home_doorway_to_courtyard')
        segment(10,Action(turn=-1))
        segment(60,Action(forward=1),(645,320))
        segment(10,Action(turn=-1))
        segment(34,Action(forward=1),(645,-190))
        checks.append('courtyard_to_workshop_doorway')
        segment(16,Action(forward=1),(645,-430))
        segment(5,Action(strafe=-1),(570,-430))
        segment(5,Action(strafe=1),(645,-430))
        segment(10,Action(forward=-1),(645,-280))
        segment(5,Action())
        segment(5,Action(look=-1))
        segment(5,Action(look=1))
        assert states=={'idle','walk_forward','walk_backward','walk_left','walk_right'},states
        checks.append('all_five_supplied_animation_states_selected')
        assert client.observe()['step_index']==recorder.last_index
        checks.append('observe_does_not_advance_step')
    except BaseException as error:
        recorder.close(str(error))
        raise
    recorder.close()
    evidence={'status':'passed','checks':checks,'count':len(checks),'human_review':'pending',
              'animation_scope':'live state selection; visual pose quality is separately reviewed',
              'step_latency_seconds':{'mean':sum(timings)/len(timings),'max':max(timings)},
              'run':str(recorder.path),'source_provenance':recorder.manifest['provenance']}
    (recorder.path/'verification.json').write_text(json.dumps(evidence,indent=2))
    (ROOT/'local/latest-home-run.txt').write_text(str(recorder.path))
    print(json.dumps(evidence,indent=2))


if __name__=='__main__':
    main()
