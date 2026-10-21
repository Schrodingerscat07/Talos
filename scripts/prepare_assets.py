"""Run inside Unreal Editor Python; creates only local /EmbodiedResearch assets.

Source MetaHuman and Epic template assets are mounted read-only by convention;
all save operations below are constrained to the plugin destination.
"""
import json
import math
from pathlib import Path
import random
import struct
import zlib
import os
import sys
import unreal as u

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from erl.config import read_json,validate,fingerprint,STATES
PROFILE=validate(read_json(os.environ['ERL_PREPARATION_PROFILE']),resolved=True)
DEST = '/EmbodiedResearch'
tools = u.AssetToolsHelpers.get_asset_tools()

def save(asset):
    assert asset.get_path_name().startswith(DEST + '/'), asset.get_path_name()
    if not u.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError('Save failed: ' + asset.get_path_name())

def create(name, folder, cls, factory):
    path = f'{DEST}/{folder}/{name}'
    return u.load_asset(path) or tools.create_asset(name, f'{DEST}/{folder}', cls, factory)

def mount(root, directory):
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    u.SystemLibrary.execute_console_command(world, f'PackageName.RegisterMountPoint {root} "{directory.as_posix()}/"')

def texture_file(name, kind):
    directory = ROOT / 'local' / 'generated_textures'
    directory.mkdir(parents=True, exist_ok=True)
    rng = random.Random(310)
    raw = bytearray()
    for y in range(256):
        raw.append(0)
        for x in range(256):
            value = 0.85 + rng.uniform(-0.045, 0.045)
            if kind == 'wood':
                value = 0.76 + 0.1*math.sin(x*0.24+math.sin(y*0.025)*1.4) + 0.045*math.sin(x*1.6+math.sin(y*.03)) + rng.uniform(-.025,.025)
            elif kind == 'fabric':
                value += .08*((x % 3 == 0) + (y % 3 == 0))
            raw.extend([int(max(0,min(1,value))*255)]*3)
    def chunk(k, data):
        return struct.pack('>I',len(data))+k+data+struct.pack('>I',zlib.crc32(k+data)&0xffffffff)
    data = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',256,256,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
    path = directory / (name+'.png')
    path.write_bytes(data)
    return path

def make_material(name, color, rough=.7, metal=0., texture=None, sky=False):
    existing = u.load_asset(f'{DEST}/Materials/M_{name}')
    if existing:
        existing.set_editor_property('used_with_instanced_static_meshes',True)
        u.MaterialEditingLibrary.recompile_material(existing)
        save(existing)
        return existing
    mat = create('M_'+name,'Materials',u.Material,u.MaterialFactoryNew())
    mat.set_editor_property('used_with_instanced_static_meshes',True)
    lib = u.MaterialEditingLibrary
    tint = lib.create_material_expression(mat,u.MaterialExpressionConstant3Vector,-500,0)
    tint.set_editor_property('constant',u.LinearColor(*color))
    output = tint
    if texture:
        task=u.AssetImportTask()
        task.set_editor_property('filename',str(texture_file(name,texture)))
        task.set_editor_property('destination_path',DEST+'/Textures')
        task.set_editor_property('automated',True)
        task.set_editor_property('save',True)
        tools.import_asset_tasks([task])
        tex=u.load_asset(task.get_editor_property('imported_object_paths')[0])
        sample=lib.create_material_expression(mat,u.MaterialExpressionTextureSample,-500,160)
        sample.set_editor_property('texture',tex)
        mult=lib.create_material_expression(mat,u.MaterialExpressionMultiply,-200,0)
        lib.connect_material_expressions(tint,'',mult,'A')
        lib.connect_material_expressions(sample,'RGB',mult,'B')
        output=mult
    lib.connect_material_property(output,'',u.MaterialProperty.MP_EMISSIVE_COLOR if sky else u.MaterialProperty.MP_BASE_COLOR)
    for value,prop in [(rough,u.MaterialProperty.MP_ROUGHNESS),(metal,u.MaterialProperty.MP_METALLIC)]:
        node=lib.create_material_expression(mat,u.MaterialExpressionConstant,-200,250)
        node.set_editor_property('r',value)
        lib.connect_material_property(node,'',prop)
    if sky:
        mat.set_editor_property('two_sided',True)
        mat.set_editor_property('shading_model',u.MaterialShadingModel.MSM_UNLIT)
    lib.recompile_material(mat)
    save(mat)
    return mat

def build_materials():
    for name,color,rough,metal,tex in [
        ('Plaster',(.76,.72,.64),.91,0,'stone'), ('Stone',(.43,.45,.43),.87,0,'stone'),
        ('Oak',(.45,.26,.115),.58,0,'wood'), ('Walnut',(.17,.085,.038),.54,0,'wood'),
        ('Linen',(.63,.67,.62),.96,0,'fabric'), ('Cream',(.86,.81,.68),.88,0,'fabric'),
        ('Metal',(.09,.105,.11),.32,.8,None), ('Steel',(.48,.52,.53),.23,.85,None),
        ('Terracotta',(.42,.17,.085),.9,0,'stone'), ('Leaves',(.085,.19,.065),.85,0,None),
        ('Soil',(.075,.052,.027),1,0,'stone'), ('Blue',(.065,.20,.26),.55,0,None),
        ('Paper',(.9,.88,.80),.9,0,None), ('Sky',(.40,.60,.78),1,0,None)]:
        make_material(name,color,rough,metal,tex,sky=name=='Sky')

def retarget():
    for entry in PROFILE['mounts']: mount(entry['virtual'],Path(entry['directory']))
    if 'retarget' not in PROFILE:
        return list(PROFILE['avatar']['animation']['clips'].values())
    settings=PROFILE['retarget']
    folder=settings['output_folder']
    source = u.load_asset(settings['source_mesh'])
    target = u.load_asset(settings['target_mesh'])
    assert source and target, 'Source/target skeletal mesh missing'
    source_paths=[settings['source_clips'][key] for key in STATES]
    existing=[u.load_asset(PROFILE['avatar']['animation']['clips'][key]) for key in STATES]
    if all(existing):
        for asset in existing:
            assert asset.get_editor_property('skeleton')==target.get_editor_property('skeleton'), 'Existing animation belongs to another avatar'
        u.log('ERL: reusing matching-skeleton animations; existing generated files preserved')
        return [asset.get_path_name() for asset in existing]
    rigs=[]
    for name,mesh in [('IK_Source',source),('IK_Target',target)]:
        rig=create(settings['prefix']+name,folder[len(DEST)+1:],u.IKRigDefinition,u.IKRigDefinitionFactory())
        ctl=u.IKRigController.get_controller(rig)
        assert ctl.set_skeletal_mesh(mesh)
        assert ctl.apply_auto_generated_retarget_definition(), 'Auto characterization failed '+name
        save(rig)
        rigs.append(rig)
    rtg=create(settings['prefix']+'RTG',folder[len(DEST)+1:],u.IKRetargeter,u.IKRetargetFactory())
    ctl=u.IKRetargeterController.get_controller(rtg)
    ctl.set_ik_rig(u.RetargetSourceOrTarget.SOURCE,rigs[0])
    ctl.set_ik_rig(u.RetargetSourceOrTarget.TARGET,rigs[1])
    ctl.remove_all_ops()
    ctl.add_default_ops()
    ctl.auto_map_chains(u.AutoMapChainType.EXACT,True)
    ctl.auto_align_all_bones(u.RetargetSourceOrTarget.TARGET)
    save(rtg)
    assets=[]
    for path,old in zip(source_paths,existing):
        if old:
            continue
        asset=u.load_asset(path)
        assert asset, path
        assets.append(u.AssetRegistryHelpers.create_asset_data(asset))
    inputs=u.IKRetargetBatchOperationInputs()
    for key,value in dict(assets_to_retarget=assets,source_mesh=source,target_mesh=target,ik_retarget_asset=rtg,
                          target_path=folder,prefix=settings['prefix'],include_referenced_assets=False,
                          overwrite_existing_files=True).items():
        inputs.set_editor_property(key,value)
    results=u.IKRetargetBatchOperation.run_batch_retarget(inputs)
    assert len(results)==len(assets), 'Retarget did not produce all missing animations'
    outputs=[asset.get_path_name() for asset in existing if asset]
    for data in results:
        asset=data.get_asset()
        save(asset)
        outputs.append(asset.get_path_name())
    return outputs

def prepare_fixture_map():
    path=DEST+'/Worlds/FixtureLab'
    if PROFILE['world']['map']!=path or u.EditorAssetLibrary.does_asset_exist(path):
        return
    levels=u.get_editor_subsystem(u.LevelEditorSubsystem)
    assert levels.new_level(path), 'Could not create local fixture map'
    world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    assert world.get_path_name().startswith(path+'.'), 'Refusing to save a source world'
    actors=u.get_editor_subsystem(u.EditorActorSubsystem)
    for pos,size in [((0,0,-15),(1400,1400,30)),((700,0,150),(20,1400,300)),((-700,0,150),(20,1400,300)),((0,700,150),(1400,20,300)),((0,-700,150),(1400,20,300))]:
        actor=actors.spawn_actor_from_class(u.StaticMeshActor,u.Vector(*pos))
        mesh=actor.get_component_by_class(u.StaticMeshComponent)
        mesh.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
        mesh.set_world_scale3d(u.Vector(*(v/100 for v in size)))
        mesh.set_material(0,u.load_asset(DEST+'/Materials/M_Plaster'))
    for yaw in (45,135,225,315):
        light=actors.spawn_actor_from_class(u.DirectionalLight,u.Vector(0,0,500),u.Rotator(-45,yaw,0))
        component=light.get_component_by_class(u.DirectionalLightComponent)
        component.set_intensity(.75)
        component.set_cast_shadows(False)
    assert levels.save_current_level(), 'Could not save local fixture map'

try:
    build_materials()
    outputs=retarget()
    prepare_fixture_map()
    (ROOT/'local'/'asset-preparation.json').write_text(json.dumps({'status':'completed','profile_id':PROFILE['id'],'profile_sha256':fingerprint(PROFILE),'animations':outputs,'source':'configured supplied animation; not learned','distribution':'researcher must provide asset permissions'},indent=2))
    u.log('ERL_ASSETS_READY')
except Exception as exc:
    (ROOT/'local'/'asset-preparation.json').write_text(json.dumps({'status':'failed','error':str(exc)},indent=2))
    raise
