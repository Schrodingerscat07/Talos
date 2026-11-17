import json
from pathlib import Path
import unittest
from unittest.mock import Mock
from erl.client import ProtocolError
from erl.control import ControlClient
from erl.control_demo import sequence


class ControlTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'configs'
        motor=json.loads((root/'motor_metahuman_combined_v1.json').read_text())
        face=json.loads((root/'face_metahuman_combined_v1.json').read_text())
        self.client=Mock(episode='episode',index=0,uncertain=False,done=False)
        self.client.request.return_value=dict(ready=True,motor=dict(mapping=motor),face=dict(mapping=face))
        self.control=ControlClient(self.client);self.client.request.reset_mock()
        self.body={c['name']:0 for c in motor['channels']};self.face={c['name']:0 for c in face['channels']}

    def test_mapping_and_sequence(self):
        self.assertEqual(len(self.body),55);self.assertEqual(len(self.face),19)
        prior_body=self.body;prior_face=self.face;activated=set()
        for body,face,label in sequence(self.control):
            self.assertEqual(set(body),set(self.body));self.assertEqual(set(face),set(self.face))
            for k,v in body.items():
                self.assertLessEqual(abs(v-prior_body[k]),12.00001)
                if v:activated.add(k)
            for k,v in face.items():self.assertLessEqual(abs(v-prior_face[k]),.20001)
            prior_body,prior_face=body,face
        self.assertEqual(activated,set(self.body))
        self.assertTrue(all(v==0 for v in prior_body.values()))
        self.assertTrue(all(v==0 for v in prior_face.values()))

    def test_invalid_targets_never_sent(self):
        for v in (True,float('nan'),float('inf'),-1,1.1):
            with self.subTest(value=v),self.assertRaises(ValueError):self.control.step(self.body,dict(self.face,blink_left=v))
        with self.assertRaises(ValueError):self.control.step({},self.face)
        self.client.request.assert_not_called()

    def test_one_request_and_one_tick(self):
        self.client.request.return_value=dict(episode_id='episode',step_index=1,terminated=False,truncated=False)
        self.control.step(self.body,self.face)
        self.client.request.assert_called_once();self.assertEqual(self.client.index,1)
        route,payload=self.client.request.call_args.args
        self.assertEqual(route,'control/step');self.assertEqual(payload['expected_step'],0)
        self.assertEqual(payload['motor_targets_deg'],self.body);self.assertEqual(payload['face_targets'],self.face)

    def test_order_conflict_blocks_further_actions(self):
        self.client.request.return_value=dict(episode_id='episode',step_index=2)
        with self.assertRaises(ProtocolError):self.control.step(self.body,self.face)
        self.assertTrue(self.client.uncertain);self.client.request.reset_mock()
        with self.assertRaises(ProtocolError):self.control.step(self.body,self.face)
        self.client.request.assert_not_called()


if __name__=='__main__':unittest.main()
