"""Portable experiment profiles, separate machine paths, and strict validation.

No engine import, network access, or implicit shell evaluation. The resolved
profile is the exact engine input, persisted and hashed by the launcher.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

FORMAT='erl-experiment/1.0'
ROOT=Path(__file__).resolve().parents[1]
STATES=('idle','forward','backward','left','right')

class ConfigError(ValueError):
    pass

def read_json(path):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result: raise ConfigError(f'Duplicate JSON key: {key}')
            result[key]=value
        return result
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=unique,
                          parse_constant=lambda x: (_ for _ in ()).throw(ConfigError(f'Non-finite JSON: {x}')))
    except (OSError,json.JSONDecodeError) as exc:
        raise ConfigError(f'{path}: {exc}') from exc

def fields(value,required,optional=(),label='object'):
    if not isinstance(value,dict): raise ConfigError(f'{label} must be an object')
    missing=set(required)-value.keys(); unknown=value.keys()-set(required)-set(optional)
    if missing or unknown: raise ConfigError(f'{label}: missing {sorted(missing)}, unknown {sorted(unknown)}')

def number(value,lo,hi,label,integer=False):
    if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi or (integer and type(value) is not int):
        raise ConfigError(f'{label} must be {"an integer" if integer else "a number"} in [{lo}, {hi}]')
    return value

def vector(value,n,label,lo=-1e7,hi=1e7):
    if not isinstance(value,list) or len(value)!=n: raise ConfigError(f'{label} requires {n} numbers')
    for v in value: number(v,lo,hi,label)
    return value

def choice(value,values,label):
    if value not in values: raise ConfigError(f'{label} must be one of {values}')

def asset(value,label):
    if not isinstance(value,str) or not re.fullmatch(r'/[A-Za-z0-9_/]+(?:\.[A-Za-z0-9_]+)?',value):
        raise ConfigError(f'{label}: use a /Mount/Package.Object asset path without quotes')
    return value

def validate(profile,resolved=False):
    fields(profile,('format','id','mounts','world','avatar','control','render'),('retarget',),'profile')
    if profile['format']!=FORMAT: raise ConfigError('Unsupported profile format')
    if not isinstance(profile['id'],str) or not re.fullmatch('[a-z][a-z0-9_-]{0,63}',profile['id']): raise ConfigError('Invalid profile id')
    if not isinstance(profile['mounts'],list): raise ConfigError('mounts must be a list')
    seen=set()
    for mount in profile['mounts']:
        fields(mount,('virtual','directory' if resolved else 'source'),label='mount')
        if not isinstance(mount['virtual'],str) or not re.fullmatch('/[A-Za-z0-9_/]+/',mount['virtual']) or '..' in mount['virtual']:
            raise ConfigError('Mounts require a /Virtual/ prefix')
        if mount['virtual'] in seen or mount['virtual'].startswith(('/Engine/','/EmbodiedResearch/')): raise ConfigError('Duplicate or reserved mount')
        seen.add(mount['virtual'])
        key=mount['directory' if resolved else 'source']
        if not isinstance(key,str) or not key or any(x in key for x in ['"','\n','\r','\0']): raise ConfigError('Invalid mount source/directory')
    w=profile['world']
    fields(w,('kind','map','spawn_cm','heading_deg','bounds_cm','overview_cm','pieces'),label='world')
    choice(w['kind'],('home','room','layout','map'),'world.kind')
    asset(w['map'],'world.map')
    if '.' in w['map']: raise ConfigError('world.map must be a package path without .Object')
    vector(w['spawn_cm'],3,'spawn_cm');number(w['heading_deg'],-180,180,'heading_deg')
    vector(w['overview_cm'],3,'overview_cm');vector(w['bounds_cm'],4,'bounds_cm')
    if min(w['bounds_cm'][2:])<=0: raise ConfigError('Map bounds width/height must be positive')
    if not isinstance(w['pieces'],list) or len(w['pieces'])>10000: raise ConfigError('pieces must contain at most 10000 entries')
    if w['kind']!='layout' and w['pieces']: raise ConfigError('pieces only apply to a layout world')
    for p in w['pieces']:
        fields(p,('position_cm','size_cm','rotation_deg','shape','material','collision'),label='piece')
        vector(p['position_cm'],3,'position_cm');vector(p['size_cm'],3,'size_cm',.01,1e6)
        vector(p['rotation_deg'],3,'rotation_deg',-360,360)
        choice(p['shape'],('Cube','Cylinder','Sphere'),'shape')
        if p['material'] not in ('Plaster','Stone','Oak','Walnut','Linen','Cream','Metal','Steel','Terracotta','Leaves','Soil','Blue','Paper'):
            asset(p['material'],'material')
        if type(p['collision']) is not bool: raise ConfigError('collision must be Boolean')
    a=profile['avatar']
    fields(a,('kind','asset','body_component','offset_cm','yaw_deg','scale','capsule_radius_cm','capsule_half_height_cm','eye_offset_cm','animation'),label='avatar')
    choice(a['kind'],('blueprint','skeletal_mesh'),'avatar.kind');asset(a['asset'],'avatar.asset')
    if a['kind']=='blueprint' and not a['asset'].endswith('_C'): raise ConfigError('Blueprint avatar requires a generated class ending _C')
    if not isinstance(a['body_component'],str) or not a['body_component']: raise ConfigError('body_component must name the skeletal component')
    vector(a['offset_cm'],3,'offset_cm');vector(a['eye_offset_cm'],3,'eye_offset_cm');vector(a['scale'],3,'scale',.001,1000)
    number(a['yaw_deg'],-180,180,'yaw_deg');number(a['capsule_radius_cm'],1,1000,'capsule radius')
    number(a['capsule_half_height_cm'],a['capsule_radius_cm'],2000,'capsule half height')
    animation=a['animation'];fields(animation,('mode','clips','disable_groom_simulation'),label='animation')
    choice(animation['mode'],('clips','existing','none'),'animation.mode')
    if animation['mode']=='existing' and a['kind']!='blueprint': raise ConfigError('existing animation requires an Actor Blueprint containing its configured graph; direct meshes use clips or none')
    if type(animation['disable_groom_simulation']) is not bool: raise ConfigError('disable_groom_simulation must be Boolean')
    fields(animation['clips'],STATES if animation['mode']=='clips' else (),label='clips')
    for state,path in animation['clips'].items(): asset(path,f'clips.{state}')
    c=profile['control'];fields(c,('max_steps','speed_cm_s','turn_deg_s','look_deg_s'),label='control')
    number(c['max_steps'],1,10000000,'max_steps',True)
    for key in ('speed_cm_s','turn_deg_s','look_deg_s'): number(c[key],.01,10000,key)
    r=profile['render'];fields(r,('eye_exposure','observer_exposure','max_fps'),label='render')
    for key in ('eye_exposure','observer_exposure'): number(r[key],-8,8,key)
    number(r['max_fps'],1,120,'max_fps',True)
    if 'retarget' in profile:
        rt=profile['retarget'];fields(rt,('source_mesh','target_mesh','source_clips','output_folder','prefix'),label='retarget')
        asset(rt['source_mesh'],'source_mesh');asset(rt['target_mesh'],'target_mesh');fields(rt['source_clips'],STATES,label='source_clips')
        for key,value in rt['source_clips'].items(): asset(value,key)
        if not isinstance(rt['output_folder'],str) or not re.fullmatch('/EmbodiedResearch/[A-Za-z0-9_/]+',rt['output_folder']): raise ConfigError('Generated assets must stay under /EmbodiedResearch/')
        if not re.fullmatch('[A-Za-z][A-Za-z0-9_]*',rt['prefix']): raise ConfigError('Invalid generated animation prefix')
        expected={k:rt['output_folder']+'/'+rt['prefix']+v.split('/')[-1].split('.')[0] for k,v in rt['source_clips'].items()}
        if expected!=animation['clips']: raise ConfigError('Retarget output paths do not match animation clips')
    return profile

def resolve(profile_path,machine_path):
    p=deepcopy(validate(read_json(profile_path)))
    machine=read_json(machine_path)
    fields(machine,('format','engine_root','content_roots'),label='machine')
    if machine['format']!='erl-machine/1.0' or not isinstance(machine['content_roots'],dict): raise ConfigError('Invalid machine file')
    if not isinstance(machine['engine_root'],str) or not machine['engine_root']: raise ConfigError('engine_root must be a path string')
    engine=Path(machine['engine_root']).expanduser().resolve()
    for mount in p['mounts']:
        source=mount.pop('source')
        if source=='engine_templates': directory=engine/'Templates/TemplateResources/High/Characters/Content'
        else:
            if source not in machine['content_roots']: raise ConfigError(f'Missing machine content root: {source}')
            if not isinstance(machine['content_roots'][source],str): raise ConfigError('Content roots must be path strings')
            directory=Path(machine['content_roots'][source]).expanduser()
            if not directory.is_absolute(): directory=Path(machine_path).resolve().parent/directory
        directory=directory.resolve()
        if not directory.is_dir(): raise ConfigError(f'Mount directory missing: {directory}')
        mount['directory']=directory.as_posix()
    validate(p,resolved=True)
    if len(encoded(p))>8*1024*1024: raise ConfigError('Resolved profile exceeds 8 MiB engine limit')
    return p,engine

def encoded(profile):
    # Unreal's JSON numbers do not retain int-vs-whole-float spelling. Canonical
    # snapshots must treat 150 and 150.0 equally without rounding real fractions.
    def normalize(value):
        if isinstance(value,float) and math.isfinite(value) and value.is_integer(): return int(value)
        if isinstance(value,list): return [normalize(v) for v in value]
        if isinstance(value,dict): return {k:normalize(v) for k,v in value.items()}
        return value
    return (json.dumps(normalize(profile),sort_keys=True,indent=2,allow_nan=False)+'\n').encode()

def fingerprint(profile):
    return hashlib.sha256(encoded(profile)).hexdigest()

def package_file(asset_path,profile,extension='.uasset'):
    package=asset_path.split('.')[0]
    for mount in sorted(profile['mounts'],key=lambda x:-len(x['virtual'])):
        if package.startswith(mount['virtual']):
            return Path(mount['directory'])/(package[len(mount['virtual']):]+extension)
    if package.startswith('/EmbodiedResearch/'):
        return ROOT/'unreal/Plugins/EmbodiedResearch/Content'/(package[len('/EmbodiedResearch/'):]+extension)
    return None
