"""Append-only transitions, lossless image files, provenance, and a visual report."""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import platform
import struct
import uuid
import zlib

from . import __version__
from .client import Action, Client, ProtocolError


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def checked_png(rgb: dict, expected: tuple[int, int] = (160,120)) -> bytes:
    if not isinstance(rgb, dict) or rgb.get("encoding") != "png_base64":
        raise ProtocolError("Unsupported RGB encoding")
    try:
        data = base64.b64decode(rgb["data"], validate=True)
    except (KeyError, ValueError, TypeError) as exc:
        raise ProtocolError("Invalid base64 image") from exc
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ProtocolError("Invalid PNG signature")
    offset, ended, dimensions = 8, False, None
    while offset + 12 <= len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise ProtocolError("Truncated PNG")
        chunk = data[offset + 8:offset + 8 + length]
        crc = struct.unpack_from(">I", data, end - 4)[0]
        if zlib.crc32(kind + chunk) & 0xffffffff != crc:
            raise ProtocolError("PNG checksum failure")
        if kind == b"IHDR":
            if dimensions is not None or length != 13:
                raise ProtocolError("Invalid PNG header")
            dimensions = struct.unpack_from(">II", chunk)
        if kind == b"IEND":
            ended = True
            if end != len(data):
                raise ProtocolError("Trailing PNG content")
            break
        offset = end
    if not ended or dimensions != (rgb.get("width"), rgb.get("height")) or dimensions != expected:
        raise ProtocolError("Missing PNG end or unexpected dimensions")
    return data


class Recorder:
    def __init__(self, root: Path, spec: dict, seed: int, provenance: dict | None = None, preview_frames: int = 2000):
        if type(preview_frames) is not int or preview_frames<2: raise ValueError('preview_frames must be an integer >= 2')
        self.path = root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8])
        (self.path / "frames").mkdir(parents=True, exist_ok=False)
        self.manifest = {"format": "erl-run/1.0", "status": "running", "created_utc": utc_now(),
                         "erl_version": __version__, "python": platform.python_version(),
                         "seed": seed, "environment_spec": spec, "provenance": provenance or {},
                         "human_verification": "pending", "transitions": 0}
        self.preview_frames=preview_frames
        self.count=0
        source_bundle=self.manifest['provenance'].get('source_bundle')
        if source_bundle:
            source=Path(source_bundle['path']).read_bytes()
            if hashlib.sha256(source).hexdigest()!=source_bundle['sha256']: raise ProtocolError('Source snapshot checksum mismatch')
            (self.path/'source.zip').write_bytes(source)
            self.manifest['provenance']['source_bundle']={**source_bundle,'path':'source.zip'}
        self._episode = None
        self._index = -1
        self._write_manifest()
        self.stream = (self.path / "transitions.jsonl").open("x", encoding="utf-8")

    def _write_manifest(self):
        temporary = self.path / "manifest.tmp"
        temporary.write_text(json.dumps(self.manifest, indent=2, allow_nan=False), encoding="utf-8")
        temporary.replace(self.path / "manifest.json")

    def append(self, transition: dict, action: Action | None = None):
        Client.validate_transition(transition)
        if transition["step_index"] != self._index + 1:
            raise ProtocolError("Recorder requires contiguous steps beginning with reset")
        if self._episode is not None and transition["episode_id"] != self._episode:
            raise ProtocolError("Use a new recorder for a new episode")
        if (action is None) != (transition["step_index"] == 0):
            raise ProtocolError("Only reset may have no action")
        entry = deepcopy(transition)
        rgb = entry["observation"]["rgb"]
        if rgb is not None:
            raw = checked_png(rgb)
            relative = f"frames/{entry['step_index']:06d}.png"
            (self.path / relative).write_bytes(raw)
            entry["observation"]["rgb"] = {"path": relative, "sha256": hashlib.sha256(raw).hexdigest(),
                                            "width": rgb["width"], "height": rgb["height"]}
        elif self.manifest["environment_spec"].get("rgb_available"):
            raise ProtocolError("Camera advertised but capture missing; recording aborted")
        observer = entry.get("privileged", {}).get("observer_rgb")
        if observer is None and self.manifest['environment_spec'].get('rgb_available') and self.manifest['environment_spec'].get('observer_width'):
            raise ProtocolError('Observer camera advertised but capture missing; recording aborted')
        if observer is not None:
            raw = checked_png(observer, (640,480))
            relative = f"frames/observer_{entry['step_index']:06d}.png"
            (self.path / relative).write_bytes(raw)
            entry["privileged"]["observer_rgb"] = {"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "width":640, "height":480}
        entry["action"] = None if action is None else action.payload()
        entry["recorded_utc"] = utc_now()
        self.stream.write(json.dumps(entry, allow_nan=False, separators=(",", ":")) + "\n")
        self.stream.flush()
        self.count+=1
        self._episode, self._index = transition["episode_id"], transition["step_index"]

    def close(self, error: str | None = None):
        self.stream.close()
        self.manifest.update(status="failed" if error else "completed", finished_utc=utc_now(),
                             transitions=self.count, error=error)
        with (self.path/'transitions.jsonl').open('rb') as stream:
            self.manifest['transitions_sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
        stride=max(1,(max(0,self.count-1)+self.preview_frames-2)//(self.preview_frames-1))
        preview=[];last=None
        with (self.path/'transitions.jsonl').open(encoding='utf-8') as stream:
            for i,line in enumerate(stream):
                last=json.loads(line)
                if i%stride==0: preview.append(last)
        if last and (not preview or preview[-1]['step_index']!=last['step_index']): preview.append(last)
        self.manifest['replay_preview']={'records':len(preview),'stride':stride,'full_records':self.count,'sampled':stride>1}
        self._write_manifest()
        if 'configuration' in self.manifest['environment_spec']:
            (self.path/'configuration.json').write_text(json.dumps(self.manifest['environment_spec']['configuration'],indent=2,allow_nan=False),encoding='utf-8')
        build_report(self.path, self.manifest, preview)

    @property
    def last_index(self):
        return self._index


def build_report(path: Path, manifest: dict, entries: list[dict]):
    # Escape '<' so an arbitrary experiment label can never terminate this script element.
    payload = json.dumps(entries, allow_nan=False).replace("<", "\\u003c")
    spec = manifest["environment_spec"]
    home = spec.get("diagnostic_map", {}).get("layout") == "home"
    layout=spec.get('diagnostic_map',{}).get('layout','room')
    bounds = spec.get("diagnostic_map", {}).get("bounds_cm", [-650,-650,1300,1300])
    map_art = '''<rect x="-1300" y="-1150" width="2600" height="2300" rx="18" fill="#f0f2eb" stroke="#9ba69e" stroke-width="12"/>
<rect x="-1100" y="0" width="1200" height="810" fill="#eee4d6" stroke="#a79b88" stroke-width="10"/>
<rect x="350" y="0" width="750" height="810" fill="#e3e8e8" stroke="#96a2a2" stroke-width="10"/>
<path d="M-320 0h140M580 0h140" stroke="#f0f2eb" stroke-width="30"/>
<text x="-510" y="460" text-anchor="middle">HOME</text><text x="725" y="460" text-anchor="middle">WORKSHOP</text>
<text x="0" y="-550" text-anchor="middle">COURTYARD</text>''' if home else '<rect x="-600" y="-600" width="1200" height="1200" fill="none" stroke="#9ba69e" stroke-width="15"/>'
    if layout not in ('home','room'):
        map_art=f'<rect x="{bounds[0]}" y="{bounds[1]}" width="{bounds[2]}" height="{bounds[3]}" fill="#f0f2eb" stroke="#9ba69e" stroke-width="10"/>'
    content = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ERL experiment viewer</title>
<style>*{box-sizing:border-box}body{background:#f5f6f3;color:#263c38;font:15px/1.5 system-ui;margin:0 auto;padding:36px 28px;max-width:1360px}
h1{font-size:30px;font-weight:550;letter-spacing:-1px;margin:4px 0}h2{font-size:15px;font-weight:600;margin:0 0 14px}.eyebrow{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#70817a}
.muted{color:#718079;font-size:13px}.grid{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(280px,1fr);gap:22px;align-items:start}
section{background:#fff;border:1px solid #e2e7df;border-radius:18px;padding:22px;min-width:0}.grid>div{min-width:0}img{display:block;width:100%;max-width:100%;border-radius:10px;background:#e7ebe3}p{overflow-wrap:anywhere}
#eye{max-width:320px;image-rendering:auto}input{width:100%;accent-color:#4b7967;cursor:pointer}pre{white-space:pre-wrap;font:12px/1.7 ui-monospace,monospace;color:#65756e}
button{padding:10px 18px;border-radius:24px;border:1px solid #cfdcd3;background:#edf3ec;color:#305846;cursor:pointer;font:inherit}button:hover{background:#dfeadd}
svg{width:100%;border-radius:12px;background:#fafbf8}svg text{fill:#859087;font:70px system-ui;letter-spacing:3px}.badge{display:inline-block;color:#7b7148;background:#f0eddf;padding:5px 12px;border-radius:20px;font-size:12px}
.row{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:12px;margin:14px 0}.small{font-size:12px;color:#7b8980}details{border-top:1px solid #edf0e8;margin-top:20px;padding-top:14px}summary{cursor:pointer;color:#65756e;font-size:13px}
header{margin-bottom:26px}footer{margin-top:22px}@media(max-width:800px){body{padding:22px 14px}.grid{grid-template-columns:minmax(0,1fr)}h1{font-size:25px}}</style>
<header><div class="eyebrow">Talos</div><h1>WORLD_TITLE</h1>
<p class="muted">Recorded Unreal simulation · supplied movement and animation · human review pending</p>
<span class="badge">PHASE_LABEL · visual verification</span><p class="small">STATUS_DESCRIPTION</p></header>
<div class="grid"><section><h2>Observer camera</h2><img id="observer" alt="Recorded third-person diagnostic view">
<div class="row"><span id="frame" class="small"></span><button id="play" aria-label="Play or pause the recorded simulation">Play / pause</button></div>
<input id="slider" aria-label="Recorded simulation frame" type="range" min="0" value="0" max="0">
<details><summary>Action and movement data</summary><pre id="action"></pre><pre id="state"></pre></details></section>
<div><section><h2>Agent camera</h2><img id="eye" alt="Recorded first-person observation"><p class="muted">The visual input available to the agent.</p></section>
<section style="margin-top:22px"><h2>Movement through the world</h2>
<svg role="img" aria-label="Top-down diagnostic map and recorded trajectory" viewBox="MAP_BOUNDS">MAP_ART
<polyline id="trail" fill="none" stroke="#4b7967" stroke-width="10"/><rect id="obstacle" width="100" height="100" rx="8" fill="#c19c67"/>
<circle id="agent" r="24" fill="#376754" stroke="#fff" stroke-width="8"/></svg>
<p class="muted">Research view · positions in centimeters. This map is excluded from agent input.</p></section></div></div>
OVERVIEW_PANEL
<footer class="muted">Captured observations from a scripted diagnostic. Replay is not a deterministic re-simulation. No learning or consciousness result is claimed.</footer>
<script type="application/json" id="records">PAYLOAD</script><script>
const data=JSON.parse(document.getElementById('records').textContent), slider=document.getElementById('slider');
slider.max=Math.max(0,data.length-1);let playing=false;
function draw(){if(!data.length)return;const i=Number(slider.value),r=data[i],p=r.privileged?.position_cm;
const rgb=r.observation.rgb,eye=document.getElementById('eye');eye.hidden=!rgb;if(rgb)eye.src=rgb.path;
const observer=r.privileged?.observer_rgb,third=document.getElementById('observer');third.hidden=!observer;if(observer)third.src=observer.path;
document.getElementById('frame').textContent=`Step ${r.step_index} · ${r.sim_time_s.toFixed(1)} s · contact ${r.observation.contacts.blocked} · ${r.privileged?.animation_state||'pose'}`;
document.getElementById('action').textContent=JSON.stringify(r.action,null,2);
document.getElementById('state').textContent=JSON.stringify(r.observation.proprioception,null,2);
document.getElementById('trail').setAttribute('points',data.slice(0,i+1).map(x=>x.privileged?.position_cm).filter(Boolean).map(x=>`${x[0]},${-x[1]}`).join(' '));
if(p){document.getElementById('agent').setAttribute('cx',p[0]);document.getElementById('agent').setAttribute('cy',-p[1]);}
const o=r.privileged?.obstacle_position_cm;document.getElementById('obstacle').setAttribute('visibility',o?'visible':'hidden');if(o){document.getElementById('obstacle').setAttribute('x',o[0]-50);document.getElementById('obstacle').setAttribute('y',-o[1]-50);}}
slider.oninput=draw;document.getElementById('play').onclick=()=>playing=!playing;
setInterval(()=>{if(playing){slider.value=(Number(slider.value)+1)%data.length;draw();}},100);draw();
</script></html>"""
    description = html.escape(f"Run {path.name} | {manifest['status']} | Avatar loaded: {spec.get('avatar_loaded')} | RGB: {spec.get('rgb_available')} | Replay: {len(entries)} / {manifest.get('transitions',len(entries))} records")
    title=spec.get('profile_id') or ('Home & courtyard' if home else 'Research room')
    replacements = {"STATUS_DESCRIPTION":description,"PAYLOAD":payload,"MAP_BOUNDS":" ".join(map(str,bounds)),"MAP_ART":map_art,
                    "WORLD_TITLE":html.escape(title),"PHASE_LABEL":"Research interface",
                    "OVERVIEW_PANEL":'<details><summary>World overview · research camera</summary><img src="overview.png" alt="Rendered world overview" style="max-width:640px;margin-top:16px"></details>' if (path/'overview.png').exists() else ''}
    for key,value in replacements.items():
        content=content.replace(key,value)
    (path / "report.html").write_text(content, encoding="utf-8")
