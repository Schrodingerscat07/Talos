"""Finite synchronized pose diagnostic. Supplied poses, no learned controller."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import uuid
from .client import ProtocolError
from .cli import runtime_provenance
from .control import ControlClient
from .manage import client_for
from .recorder import checked_png


def checks(client, control):
    zero = {c['name']:0 for c in control.motor['channels']}
    neutral = {c['name']:0 for c in control.face['channels']}
    control.reset()
    base = dict(format='talos-control-command/1.0', episode_id=client.episode,
                expected_step=client.index, motor_targets_deg=zero, face_targets=neutral)
    body_key, face_key = next(iter(zero)), next(iter(neutral))
    results = {}
    def reject(label, payload, code=400, route='control/step'):
        before = client.request('control')
        try: client.request(route, payload)
        except ProtocolError as exc: assert f'HTTP {code}:' in str(exc), str(exc)
        else: raise AssertionError('Invalid command accepted: '+label)
        assert client.request('control') == before, 'Rejected command mutated pose/clock'
        results[label] = True
    bad = deepcopy(base); bad['motor_targets_deg'][body_key]=2; bad['face_targets'][face_key]=True
    reject('invalid_face_keeps_valid_body_unchanged', bad)
    bad = deepcopy(base); bad['motor_targets_deg'][body_key]=1000; bad['face_targets'][face_key]=.2
    reject('invalid_body_keeps_valid_face_unchanged', bad)
    bad = deepcopy(base); bad['face_targets'][face_key]=1
    reject('face_rate_limit', bad)
    bad = deepcopy(base); bad['motor_targets_deg'][body_key]=13
    reject('motor_rate_limit', bad)
    bad = deepcopy(base); del bad['face_targets'][face_key]
    reject('missing_channel', bad)
    bad = deepcopy(base); bad['face_targets']['unknown']=0
    reject('unknown_channel', bad)
    bad = deepcopy(base); bad['expected_step']=1
    reject('stale_step', bad, 409)
    bad = deepcopy(base); bad['episode_id']='old-episode'
    reject('old_episode', bad, 409)
    for route in ('motor/step','face/step','step'):
        reject('exclusive_'+route, {}, 409, route)
    control.reset()
    targets = dict(zero); targets[body_key]=2
    facial = dict(neutral); facial[face_key]=.2
    tr = control.step(targets, facial)
    assert tr['step_index']==1 and tr['sim_time_s']==.1
    results['single_clock_tick'] = True
    before = client.request('control'); time.sleep(.4)
    assert before == client.request('control')
    results['persistent_combined_pose'] = True
    tr = control.reset()
    assert all(abs(c['measured_axis_delta_deg'])<1 for c in tr['privileged']['motor']['channels'])
    assert all(abs(c['evaluated_curve'])<1e-5 for c in tr['privileged']['face']['channels'])
    results['neutral_reset'] = True
    return results


def sequence(control):
    body = {c['name']:0 for c in control.motor['channels']}
    face = {c['name']:0 for c in control.face['channels']}
    hands = {c['name'] for c in control.motor['channels'] if c['bone'].startswith(('thumb_','index_','middle_','ring_','pinky_','hand_'))}
    legs = {c['name'] for c in control.motor['channels'] if c['bone'].startswith(('thigh_','calf_','foot_','ball_','pelvis'))}
    upper = set(body)-hands-legs
    groups = [(hands,8,{'blink_left':.8,'blink_right':.8},'Both hands + blink'),
              (upper,4,{'jaw_open':.6},'Upper body + jaw'),
              (legs,2,{'brow_inner_raise_left':.8,'brow_inner_raise_right':.8},'Lower body + brows'),
              (set(body),2,{'lip_corner_pull_left':.6,'lip_corner_pull_right':.6},'Whole body + lip corners')]
    for names, amplitude, expressions, label in groups:
        for alpha in (.2,.4,.6,.8,1,1,1,.8,.6,.4,.2,0,0):
            yield ({k:amplitude*alpha if k in names else 0 for k in body},
                   {k:expressions.get(k,0)*alpha for k in face},label)


def report(path, frames):
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Talos · Combined control</title>
<style>body{margin:0;background:#f5f7fa;color:#25334a;font:16px system-ui}main{max-width:1150px;margin:32px auto;padding:0 20px}section{background:white;border:1px solid #dfe6ef;border-radius:16px;padding:20px;margin:20px 0}.views{display:grid;grid-template-columns:1fr 1fr;gap:16px}img{width:100%;border-radius:10px}figure{margin:0}figcaption,p{color:#607087}input{width:100%;margin:16px 0}button,select{padding:10px;border:0;border-radius:8px;background:#e6eefb;color:#244168}pre{white-space:pre-wrap;font-size:12px}@media(max-width:650px){.views{grid-template-columns:1fr}}</style>
<main><p>TALOS / SYNCHRONIZED CONTROL / M3a</p><h1>Body, hands & face</h1><p>One command, one simulation step. Scripted pose offsets over a frozen idle; no balance, grasping or learned movement. Human review pending.</p>
<section><div class="views"><figure><img id="body" alt="Full body"><figcaption>Full body</figcaption></figure><figure><img id="face" alt="Face close-up"><figcaption>Face</figcaption></figure><figure><img id="left" alt="Left hand close-up"><figcaption>Left hand</figcaption></figure><figure><img id="right" alt="Right hand close-up"><figcaption>Right hand</figcaption></figure></div><input id="scrub" aria-label="Recorded frame" type="range" min="0" value="0"><button id="play">Play</button> <select id="jump" aria-label="Jump to pose"></select> <span id="caption"></span></section><section><details><summary>Requested and evaluated controls</summary><pre id="values"></pre></details><p>Joint measurements are evaluated local-axis offsets. Facial curve readback is not a geometry measurement. The four review views are privileged diagnostics of the same frozen step.</p></section></main>
<script>const frames=DATA,s=document.querySelector('#scrub'),j=document.querySelector('#jump');s.max=frames.length-1;const seen=new Set();frames.forEach((f,i)=>{if(!seen.has(f.label)){seen.add(f.label);const o=document.createElement('option');o.value=i;o.textContent=f.label;j.append(o)}});function draw(){const f=frames[Number(s.value)];for(const key of ['body','face','left','right'])document.querySelector('#'+key).src=f[key];document.querySelector('#caption').textContent=f.label+' · step '+f.step;document.querySelector('#values').textContent=JSON.stringify({motor:f.motor,face:f.channels},null,2)}s.oninput=draw;j.onchange=()=>{s.value=j.value;draw()};let timer;document.querySelector('#play').onclick=()=>{if(timer){clearInterval(timer);timer=null;document.querySelector('#play').textContent='Play'}else{document.querySelector('#play').textContent='Pause';timer=setInterval(()=>{s.value=(Number(s.value)+1)%frames.length;draw()},220)}};draw();</script></html>'''
    (path/'report.html').write_text(html.replace('DATA',json.dumps(frames).replace('<','\\u003c')),encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--instance',default='bob-control');p.add_argument('--runs',type=Path,default=Path('runs/control'))
    args=p.parse_args();client=client_for(args.instance);control=ControlClient(client);spec=client.spec()
    if not spec.get('ready') or not spec.get('rgb_available'): raise RuntimeError('Rendered ready instance required')
    commands=list(sequence(control))
    if spec['max_steps']<len(commands):raise ValueError('Insufficient horizon')
    path=args.runs/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]);(path/'frames').mkdir(parents=True)
    provenance=runtime_provenance(args.instance);provenance.update(policy='scripted_combined_pose_acceptance_v1',learning=False,
        assistance=['frozen supplied idle','local single-axis joint offsets','MetaHuman RigLogic','LOD0',client.request('face').get('review_lighting')])
    (path/'source.zip').write_bytes(Path(provenance['source_bundle']['path']).read_bytes());provenance['source_bundle']['path']='source.zip'
    manifest=dict(format='talos-control-run/1.0',status='running',human_review='pending',spec=spec,provenance=provenance);frames=[]
    def save(): (path/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    save()
    try:
        manifest['checks']=checks(client,control)
        (path/'rig.json').write_text(json.dumps(client.request('rig'),indent=2),encoding='utf-8')
        with (path/'transitions.jsonl').open('w',encoding='utf-8') as stream:
            def record(tr,action,label):
                row=deepcopy(tr);row.update(control_action=action,label=label)
                for holder,key,prefix,size in [(row['observation'],'rgb','ego',(160,120))]+[(row['privileged'],key,prefix,(640,480)) for key,prefix in [('observer_rgb','body'),('face_rgb','face'),('left_hand_rgb','left'),('right_hand_rgb','right')]]:
                    png=checked_png(holder[key],size);name=f"frames/{prefix}_{row['step_index']:04d}.png";(path/name).write_bytes(png)
                    holder[key]=dict(path=name,sha256=hashlib.sha256(png).hexdigest())
                stream.write(json.dumps(row,allow_nan=False)+'\n');stream.flush()
                m=row['privileged']['motor']['channels'];f=row['privileged']['face']['channels']
                frames.append(dict(step=row['step_index'],label=label,motor=m,channels=f,**{prefix:row['privileged'][key]['path'] for key,prefix in [('observer_rgb','body'),('face_rgb','face'),('left_hand_rgb','left'),('right_hand_rgb','right')]}))
                assert all(abs(c['measured_axis_delta_deg']-c['requested_deg'])<1 for c in m), 'Body measurement mismatch'
                assert all(abs(c['evaluated_curve']-c['requested'])<1e-4 for c in f), 'Face curve mismatch'
                assert row['privileged']['motor']['step_index']==row['privileged']['face']['step_index']==row['step_index']
            record(control.reset(),None,'Neutral')
            for body,face,label in commands:
                record(control.step(body,face),dict(motor_targets_deg=body,face_targets=face),label)
        manifest['checks']['evaluated_pose_and_curves_match']=True;manifest['status']='completed'
    except BaseException as exc:
        manifest.update(status='failed',error=str(exc));raise
    finally:
        manifest['frames']=len(frames)
        if frames:report(path,frames)
        manifest['files']={p.relative_to(path).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file() and p.name!='manifest.json'};save()
    print(json.dumps(dict(run=str(path.resolve()),frames=len(frames),checks=manifest['checks']),indent=2))


if __name__=='__main__':main()
