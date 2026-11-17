"""Finite rendered actuator acceptance test. Does not train or run a brain."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import uuid

from .client import Action, ProtocolError
from .cli import runtime_provenance
from .manage import client_for
from .motor import MotorClient
from .recorder import checked_png


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checks(client, motor):
    zero = {c['name']: 0 for c in motor.mapping['channels']}
    motor.reset()
    def rejected(payload, code):
        before = client.request('motor')
        try:
            client.request('motor/step', payload)
        except ProtocolError as exc:
            assert f'HTTP {code}:' in str(exc), str(exc)
        else:
            raise AssertionError('Invalid motor command was accepted')
        after = client.request('motor')
        assert before == after, 'Rejected command changed state'
    base = {'format': 'talos-motor-command/1.0', 'episode_id': client.episode,
            'expected_step': client.index, 'targets_deg': zero}
    key = next(iter(zero))
    for value in (True, 1000):
        bad = deepcopy(base); bad['targets_deg'][key] = value
        rejected(bad, 400)
    bad = deepcopy(base); bad['targets_deg']['unknown'] = 0; rejected(bad, 400)
    bad = deepcopy(base); bad['expected_step'] = 1; rejected(bad, 409)
    motor.reset()
    base.update(episode_id=client.episode, expected_step=client.index)
    bad = deepcopy(base); bad['targets_deg'][key] = motor.mapping['channels'][0]['limit_deg']; rejected(bad, 400)
    try:
        client.step(Action())
    except ProtocolError as exc:
        assert 'HTTP 409:' in str(exc)
    else:
        raise AssertionError('Navigation and motor both own the clock')
    motor.reset()
    targets = dict(zero); targets[key] = 10
    moved = motor.step(targets)['privileged']['motor']
    time.sleep(0.4)
    held = client.request('motor')
    assert moved == held, 'Pose did not persist between engine ticks'
    reset = motor.reset()['privileged']['motor']
    assert all(abs(c['measured_axis_delta_deg']) < 1 for c in reset['channels']), reset
    return {'invalid_boolean': True, 'invalid_range': True, 'unknown_channel': True,
            'stale_step': True, 'rate_limit': True, 'exclusive_control': True,
            'persistence': True, 'neutral_reset': True}


def write_report(path, frames):
    data = json.dumps(frames).replace('<', '\\u003c')
    template = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Talos · Hand control</title><style>
body{margin:0;background:#f6f8fb;color:#233148;font:16px system-ui,sans-serif}
main{max-width:1000px;margin:40px auto;padding:0 22px}h1{font-size:32px;margin:8px 0}
.muted{color:#607087}section{background:white;border:1px solid #dde4ee;border-radius:16px;padding:20px;margin:20px 0}
img{width:100%;max-width:640px;display:block;margin:auto;border-radius:10px}
button{background:#e7eefb;color:#244168;border:0;border-radius:8px;padding:10px 18px;cursor:pointer}
input{width:100%;margin:20px 0}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:10px 5px;border-bottom:1px solid #edf0f5}
@media(max-width:600px){main{margin:20px auto}table{font-size:13px}section{padding:12px}}
</style><main><span class="muted">TALOS / MOTOR INTERFACE / M1a</span>
<h1>Finger & wrist control</h1><p class="muted">Recorded Unreal movement. Scripted commands, fixed idle pose, no learning or grasp physics. Human review pending.</p>
<section><img id="frame" alt="Unreal close-up of the controlled hand"><input aria-label="Recorded frame" id="scrub" type="range" min="0" step="1" value="0">
<button id="play">Play</button> <span id="caption"></span></section>
<section><table><thead><tr><th>Channel</th><th>Requested</th><th>Measured</th></tr></thead><tbody id="values"></tbody></table>
<p class="muted">Degrees relative to the captured neutral pose. Inspect finger direction, wrist deformation and neutral reset. Counts of bones do not imply verified controls.</p></section></main>
<script>const frames=DATA;const slider=document.querySelector('#scrub');slider.max=frames.length-1;
function draw(){const f=frames[Number(slider.value)];document.querySelector('#frame').src=f.image;document.querySelector('#caption').textContent=`${f.label} · frame ${f.step}`;
const rows=document.querySelector('#values');rows.replaceChildren();for(const c of f.channels){const tr=document.createElement('tr');for(const v of [c.name,c.requested_deg.toFixed(1)+'°',c.measured_axis_delta_deg.toFixed(1)+'°']){const td=document.createElement('td');td.textContent=v;tr.append(td)}rows.append(tr)}}
let timer;slider.oninput=draw;document.querySelector('#play').onclick=()=>{if(timer){clearInterval(timer);timer=null;document.querySelector('#play').textContent='Play'}else{document.querySelector('#play').textContent='Pause';timer=setInterval(()=>{slider.value=(Number(slider.value)+1)%frames.length;draw()},180)}};draw();</script></html>'''
    upper=frames and any(c['bone']=='head' for c in frames[0]['channels'])
    lower=frames and any(c['bone']=='pelvis' for c in frames[0]['channels'])
    stage='M1d' if lower else ('M1c' if upper else ('M1b' if frames and len(frames[0]['channels'])>2 else 'M1a'))
    if lower: template=template.replace('Finger & wrist control','Lower-body joint control').replace('Hand control','Lower-body control').replace('Unreal close-up of the controlled hand','Unreal full-body pose diagnostic').replace('Inspect finger direction, wrist deformation and neutral reset.', 'Inspect hips, knees, ankles, toes and neutral return. Foot contact and balance are not constrained in this pose test.')
    if upper: template=template.replace('Finger & wrist control','Upper-body joint control').replace('Hand control','Upper-body control').replace('Unreal close-up of the controlled hand','Unreal view of the controlled avatar').replace('Inspect finger direction, wrist deformation and neutral reset.', 'Inspect shoulders, elbows, spine, neck, head and neutral reset.')
    (path/'report.html').write_text(template.replace('M1a',stage).replace('DATA', data), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance', default='bob-motor')
    parser.add_argument('--runs', type=Path, default=Path('runs/motor'))
    parser.add_argument('--sweep-all', action='store_true', help='Isolate every configured channel then combine finger joints')
    parser.add_argument('--combined-deg', type=float, default=10, help='Magnitude of the final combined pose sweep')
    args = parser.parse_args()
    client = client_for(args.instance)
    spec = client.spec()
    if not spec.get('ready') or not spec.get('rgb_available'):
        raise RuntimeError('A ready rendered motor instance is required')
    motor = MotorClient(client)
    if not args.sweep_all and [c['name'] for c in motor.mapping['channels']] != ['left_index_proximal', 'left_wrist']:
        raise RuntimeError('This finite acceptance sequence requires the two-channel hand template')
    path = args.runs/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8])
    (path/'frames').mkdir(parents=True)
    provenance = runtime_provenance(args.instance)
    provenance.update(policy='scripted_motor_acceptance_v1', learning=False,
                      assistance=['frozen supplied idle pose', 'local joint offsets', 'avatar post-process', 'LOD0'])
    source = Path(provenance['source_bundle']['path'])
    (path/'source.zip').write_bytes(source.read_bytes())
    provenance['source_bundle']['path'] = 'source.zip'
    manifest = {'format': 'talos-motor-run/1.0', 'status': 'running', 'human_review': 'pending',
                'spec': spec, 'provenance': provenance}
    def save_manifest():
        (path/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    save_manifest()
    frames=[]
    try:
        manifest['checks'] = checks(client, motor)
        (path/'rig.json').write_text(json.dumps(client.request('rig'), indent=2))
        with (path/'transitions.jsonl').open('w', encoding='utf-8') as stream:
            def record(transition, targets, label):
                row=deepcopy(transition)
                for holder, key, prefix, size in [(row['observation'],'rgb','ego',(160,120)),
                                                  (row['privileged'],'observer_rgb','hand',(640,480))]:
                    png=checked_png(holder[key],size)
                    name=f"frames/{prefix}_{row['step_index']:04d}.png"
                    (path/name).write_bytes(png)
                    holder[key]={'path':name,'sha256':hashlib.sha256(png).hexdigest()}
                row['motor_action']=targets; row['label']=label
                stream.write(json.dumps(row,allow_nan=False)+'\n'); stream.flush()
                channels=row['privileged']['motor']['channels']
                frames.append({'step':row['step_index'],'image':row['privileged']['observer_rgb']['path'],
                               'label':label,'channels':channels})
                for c in channels:
                    if abs(c['measured_axis_delta_deg']-c['requested_deg'])>1:
                        raise AssertionError(f"Pose mismatch: {c}")
            record(motor.reset(),None,'Neutral')
            if args.sweep_all:
                zero={c['name']:0 for c in motor.mapping['channels']}
                for name in zero:
                    for value in (10,0,-10,0):
                        targets=dict(zero); targets[name]=value
                        for _ in range(2): record(motor.step(targets),targets,name)
                for value in (args.combined_deg,0,-args.combined_deg,0):
                    targets={name:(0 if name.endswith('_wrist') else value) for name in zero}
                    for _ in range(2): record(motor.step(targets),targets,'Combined configured joints')
            sequence=[]
            for v in [10,20,30,20,10,0,-10,-20,-30,-20,-10,0]:
                sequence.extend([(v,0,'Index finger')]*3)
            for v in [10,20,25,15,5,0,-10,-20,-25,-15,-5,0]:
                sequence.extend([(0,v,'Wrist')]*3)
            for v in [10,20,10,0]:
                sequence.extend([(v,v,'Combined')]*3)
            for finger,wrist,label in ([] if args.sweep_all else sequence):
                targets={'left_index_proximal':finger,'left_wrist':wrist}
                record(motor.step(targets),targets,label)
        manifest['status']='completed'
        manifest['checks']['evaluated_pose_matches_targets']=True
    except BaseException as exc:
        manifest.update(status='failed',error=str(exc))
        raise
    finally:
        manifest['frames']=len(frames)
        write_report(path,frames) if frames else None
        manifest['files']={p.relative_to(path).as_posix():digest(p) for p in sorted(path.rglob('*')) if p.is_file() and p.name != 'manifest.json'}
        save_manifest()
    print(json.dumps({'run':str(path.resolve()),'frames':len(frames),'checks':manifest['checks']},indent=2))


if __name__ == '__main__':
    main()
