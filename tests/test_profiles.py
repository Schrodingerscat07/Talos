from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from erl.config import ROOT,ConfigError,read_json,validate,resolve,fingerprint,encoded,package_file
from erl.manage import instance_dir,inventory
from erl.recorder import Recorder
from erl.verify import verify
from erl.client import Action,ProtocolError
from test_core import transition

class ProfileTests(unittest.TestCase):
    def setUp(self): self.profile=read_json(ROOT/'configs/manny_layout.json')

    def test_portable_examples_validate_without_personal_machine_paths(self):
        for file in (ROOT/'configs').glob('*.json'):
            data=read_json(file)
            if data.get('format')=='erl-experiment/1.0': validate(data)
            self.assertNotIn('Users\\Shiva',file.read_text())

    def test_invalid_semantics_are_rejected(self):
        cases=[('control','max_steps',True),('control','speed_cm_s',float('nan')),('avatar','capsule_half_height_cm',1),('world','kind','typo')]
        for section,key,value in cases:
            p=deepcopy(self.profile);p[section][key]=value
            with self.assertRaises(ConfigError):validate(p)
        self.profile['avatar']['animation']['clips'].pop('left')
        with self.assertRaises(ConfigError):validate(self.profile)

    def test_unknown_fields_and_reserved_mounts_fail(self):
        self.profile['control']['speed_typo']=10
        with self.assertRaises(ConfigError):validate(self.profile)
        p=deepcopy(read_json(ROOT/'configs/manny_room.json'));p['mounts'][0]['virtual']='/Engine/'
        with self.assertRaises(ConfigError):validate(p)

    def test_config_hash_matches_engine_numeric_roundtrip(self):
        p=deepcopy(self.profile)
        p['control']['speed_cm_s']=150.0;p['avatar']['scale']=[1.0,1.0,1.0]
        self.assertEqual(fingerprint(p),fingerprint(self.profile))
        p['control']['speed_cm_s']=150.01
        self.assertNotEqual(fingerprint(p),fingerprint(self.profile))

    def test_duplicate_json_and_instance_path_traversal_fail(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'duplicate.json';file.write_text('{"id":1,"id":2}')
            with self.assertRaises(ConfigError):read_json(file)
        for name in ('../other','a/b','a\\b','C:\\elsewhere',''):
            with self.assertRaises(ConfigError):instance_dir(name)

    def test_resolved_profiles_are_stable_and_machine_paths_are_separate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'content').mkdir();(root/'engine').mkdir()
            p=deepcopy(self.profile);p['mounts']=[{'virtual':'/Game/','source':'custom'}]
            file=root/'profile.json';file.write_text(json.dumps(p))
            machine=root/'machine.json';machine.write_text(json.dumps({'format':'erl-machine/1.0','engine_root':str(root/'engine'),'content_roots':{'custom':'content'}}))
            first,_=resolve(file,machine);second,_=resolve(file,machine)
            self.assertEqual(encoded(first),encoded(second));self.assertEqual(fingerprint(first),fingerprint(second))
            self.assertNotIn('directory',p['mounts'][0]);self.assertEqual(first['mounts'][0]['directory'],(root/'content').as_posix())
            self.assertEqual(package_file('/Game/Robot/SK_Robot.SK_Robot',first),root/'content/Robot/SK_Robot.uasset')

    def test_long_recording_has_bounded_preview_and_complete_verifiable_log(self):
        with tempfile.TemporaryDirectory() as d:
            recorder=Recorder(Path(d),{'rgb_available':False},42,preview_frames=5)
            for index in range(31):
                row=transition(index);row['observation']['rgb']=None
                recorder.append(row,None if index==0 else Action())
            recorder.close()
            manifest=read_json(recorder.path/'manifest.json')
            self.assertEqual(manifest['transitions'],31);self.assertLessEqual(manifest['replay_preview']['records'],5)
            self.assertTrue(manifest['replay_preview']['sampled']);self.assertEqual(verify(recorder.path)['transitions'],31)
            html=(recorder.path/'report.html').read_text();payload=html.split('id="records">')[1].split('</script>')[0]
            self.assertEqual(json.loads(payload)[-1]['step_index'],30)

    def test_offline_verifier_detects_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            recorder=Recorder(Path(d),{'rgb_available':True},42)
            recorder.append(transition());recorder.close();self.assertEqual(verify(recorder.path)['images'],1)
            image=recorder.path/'frames/000000.png';image.write_bytes(image.read_bytes()[:-1]+b'x')
            with self.assertRaisesRegex(ProtocolError,'checksum'):verify(recorder.path)

    def test_missing_advertised_observer_cannot_be_recorded_as_success(self):
        with tempfile.TemporaryDirectory() as d:
            recorder=Recorder(Path(d),{'rgb_available':True,'observer_width':640},42)
            with self.assertRaisesRegex(ProtocolError,'Observer camera'):recorder.append(transition())
            recorder.close('missing observer')
            with self.assertRaisesRegex(ProtocolError,'did not complete'):verify(recorder.path)

if __name__=='__main__':unittest.main()
