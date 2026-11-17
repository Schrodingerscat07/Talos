"""Rendered, scripted blink/jaw acceptance recording; no learning."""
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
from .face import FaceClient
from .manage import client_for
from .recorder import checked_png


def checks(client, face):
    zero = {c['name']: 0 for c in face.mapping['channels']}
    face.reset()
    base = dict(format='talos-face-command/1.0', episode_id=client.episode,
                expected_step=client.index, targets=zero)
    key = next(iter(zero))
    cases = []
    for label, value in [('boolean', True), ('range', 1.1), ('rate', 1)]:
        bad = deepcopy(base); bad['targets'][key] = value
        cases.append((label, bad, 400))
    bad = deepcopy(base); bad['targets']['unknown'] = 0
    cases.append(('unknown', bad, 400))
    bad = deepcopy(base); bad['expected_step'] = 1
    cases.append(('stale', bad, 409))
    results = {}
    for label, payload, code in cases:
        before = client.request('face')
        try:
            client.request('face/step', payload)
        except ProtocolError as exc:
            assert f'HTTP {code}:' in str(exc), str(exc)
        else:
            raise AssertionError('Invalid command accepted')
        assert before == client.request('face'), 'Rejected command changed state'
        results[label] = True
    face.reset()
    try:
        client.step(Action())
    except ProtocolError as exc:
        assert 'HTTP 409:' in str(exc)
    else:
        raise AssertionError('Navigation accepted during facial control')
    results['exclusive_control'] = True
    face.reset()
    targets = dict(zero); targets[key] = .2
    moved = face.step(targets)['privileged']['face']
    time.sleep(.4)
    assert moved == client.request('face'), 'Face state did not persist'
    results['persistence'] = True
    reset = face.reset()['privileged']['face']
    assert all(c['requested'] == 0 and abs(c['evaluated_curve']) < 1e-5 for c in reset['channels'])
    results['neutral_reset'] = True
    return results


def report(path, frames, sweep_all=False):
    data = json.dumps(frames).replace('<', '\\u003c')
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Talos · Facial control</title><style>body{margin:0;background:#f5f7fa;color:#25334a;font:16px system-ui}main{max-width:900px;margin:36px auto;padding:0 20px}section{background:white;border:1px solid #dfe6ef;border-radius:16px;padding:20px;margin:20px 0}img{display:block;width:100%;max-width:640px;margin:auto;border-radius:10px}input{width:100%;margin:20px 0}button{padding:10px 20px;border:0;border-radius:8px;background:#e6eefb;color:#244168}p{color:#5d6e84}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:10px;border-bottom:1px solid #edf0f5}</style>
<main><p>TALOS / FACIAL CONTROL / M2a</p><h1>Blinks & jaw movement</h1><p>Recorded Unreal frames from scripted commands. Human review pending.</p>
<section><img id="frame" alt="Bob facial close-up"><input id="scrub" aria-label="Recorded frame" type="range" min="0" value="0"><button id="play">Play</button> <select id="channel" aria-label="Jump to control"></select> <span id="caption"></span></section>
<section><table><thead><tr><th>Control</th><th>Requested</th><th>Evaluated curve</th></tr></thead><tbody id="values"></tbody></table><p>Normalized controls, 0–1. Curve readback is not a geometry measurement. Inspect each eye independently, jaw opening, and return to neutral. These expressions do not represent emotions or consciousness.</p></section></main>
<script>const frames=DATA, slider=document.querySelector('#scrub');slider.max=frames.length-1;function draw(){const f=frames[Number(slider.value)];document.querySelector('#frame').src=f.image;document.querySelector('#caption').textContent=f.label+' · step '+f.step;const rows=document.querySelector('#values');rows.replaceChildren();for(const c of f.channels){const tr=document.createElement('tr');for(const v of [c.name,c.requested.toFixed(2),c.evaluated_curve.toFixed(2)]){const td=document.createElement('td');td.textContent=v;tr.append(td)}rows.append(tr)}}const jump=document.querySelector('#channel'),seen=new Set();frames.forEach((f,i)=>{if(!seen.has(f.label)){seen.add(f.label);const option=document.createElement('option');option.value=i;option.textContent=f.label;jump.append(option)}});jump.onchange=()=>{slider.value=jump.value;draw()};let timer;slider.oninput=draw;document.querySelector('#play').onclick=()=>{if(timer){clearInterval(timer);timer=null;document.querySelector('#play').textContent='Play'}else{document.querySelector('#play').textContent='Pause';timer=setInterval(()=>{slider.value=(Number(slider.value)+1)%frames.length;draw()},180)}};draw();</script></html>'''
    if sweep_all:
        html = html.replace('M2a', 'M2b').replace('Blinks & jaw movement', 'Gaze, brows, lips & cheeks').replace('Inspect each eye independently, jaw opening, and return to neutral.', 'Inspect each isolated channel and neutral return. Gaze controls move the eyes, not the observation camera.')
    (path/'report.html').write_text(html.replace('DATA', data), encoding='utf-8')


def sequence(mapping, sweep_all=False):
    groups = [([c['name']], c['name'].replace('_', ' ').capitalize()) for c in mapping['channels']] if sweep_all else [(['blink_left'], 'Left blink'), (['blink_right'], 'Right blink'), (['blink_left','blink_right'], 'Both eyes'), (['jaw_open'], 'Jaw opening')]
    for names, label in groups:
        for value in [.2,.4,.6,.8,1,1,1,.8,.6,.4,.2,0,0]:
            yield {c['name']: value if c['name'] in names else 0 for c in mapping['channels']}, label


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance', default='bob-face')
    parser.add_argument('--runs', type=Path, default=Path('runs/face'))
    parser.add_argument('--sweep-all', action='store_true', help='Sweep each mapped facial channel independently')
    args = parser.parse_args()
    client = client_for(args.instance)
    spec = client.spec()
    if not spec.get('ready') or not spec.get('rgb_available'):
        raise RuntimeError('Ready rendered face instance required')
    face = FaceClient(client)
    if not args.sweep_all and {c['name'] for c in face.mapping['channels']} != {'blink_left', 'blink_right', 'jaw_open'}:
        raise ValueError('This sequence requires the basic blink/jaw mapping')
    commands = list(sequence(face.mapping, args.sweep_all))
    if spec['max_steps'] < len(commands):
        raise ValueError('Profile horizon is shorter than the diagnostic sequence')
    path = args.runs/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8])
    (path/'frames').mkdir(parents=True)
    provenance = runtime_provenance(args.instance)
    provenance.update(policy='scripted_face_acceptance_v1', learning=False,
                      assistance=['frozen supplied idle', 'CopyPoseFromMesh', 'MetaHuman post-process RigLogic', 'face LOD0'])
    provenance['sequence'] = 'isolated_all_channels_v1' if args.sweep_all else 'basic_blinks_jaw_v1'
    lighting = client.request('face').get('review_lighting')
    if lighting:
        provenance['assistance'].append(lighting)
    (path/'source.zip').write_bytes(Path(provenance['source_bundle']['path']).read_bytes())
    provenance['source_bundle']['path'] = 'source.zip'
    manifest = dict(format='talos-face-run/1.0', status='running', human_review='pending', spec=spec, provenance=provenance)
    frames = []
    def save():
        (path/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    save()
    try:
        manifest['checks'] = checks(client, face)
        (path/'rig.json').write_text(json.dumps(client.request('rig'), indent=2), encoding='utf-8')
        with (path/'transitions.jsonl').open('w', encoding='utf-8') as stream:
            def record(transition, targets, label):
                row = deepcopy(transition)
                for holder, key, prefix, size in [(row['observation'], 'rgb', 'ego', (160,120)), (row['privileged'], 'observer_rgb', 'face', (640,480))]:
                    png = checked_png(holder[key], size)
                    name = f"frames/{prefix}_{row['step_index']:04d}.png"
                    (path/name).write_bytes(png)
                    holder[key] = dict(path=name, sha256=hashlib.sha256(png).hexdigest())
                row.update(face_action=targets, label=label)
                stream.write(json.dumps(row, allow_nan=False)+'\n'); stream.flush()
                channels = row['privileged']['face']['channels']
                frames.append(dict(step=row['step_index'], image=row['privileged']['observer_rgb']['path'], label=label, channels=channels))
                assert all(abs(c['requested']-c['evaluated_curve']) < 1e-4 for c in channels), channels
            record(face.reset(), None, 'Neutral')
            for targets, label in commands:
                record(face.step(targets), targets, label)
        manifest['checks']['curve_readback_matches'] = True
        manifest['status'] = 'completed'
    except BaseException as exc:
        manifest.update(status='failed', error=str(exc)); raise
    finally:
        manifest['frames'] = len(frames)
        if frames: report(path, frames, args.sweep_all)
        manifest['files'] = {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(path.rglob('*')) if p.is_file() and p.name != 'manifest.json'}
        save()
    print(json.dumps(dict(run=str(path.resolve()), frames=len(frames), checks=manifest['checks']), indent=2))


if __name__ == '__main__':
    main()
