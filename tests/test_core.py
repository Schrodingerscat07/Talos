import base64
import json
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from erl.client import Action, Client, ProtocolError
from erl.recorder import Recorder, checked_png


def png():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 160,120,8,2,0,0,0))
    data += chunk(b'IDAT', zlib.compress((b'\0' + b'\x55\xaa\x33' * 160) * 120)) + chunk(b'IEND',b'')
    return {'encoding':'png_base64','width':160,'height':120,'data':base64.b64encode(data).decode()}


def transition(step=0, episode='test-episode'):
    return {'protocol':'erl/1.0','episode_id':episode,'step_index':step,'sim_time_s':step*0.1,
            'reward':0,'terminated':False,'truncated':False,
            'observation':{'rgb':png(),'proprioception':{'heading_deg':0,'look_pitch_deg':0,'local_velocity_cm_s':[0,0,0]},'contacts':{'blocked':False}},
            'privileged':{'position_cm':[0,0,88],'obstacle_position_cm':[220,10,60],'seed':42}}


class CoreTests(unittest.TestCase):
    def test_invalid_action_is_rejected_before_network(self):
        client = Client('test')
        client.episode, client.index = 'episode', 0
        for value in [float('nan'), float('inf'), True, 1.01, '1']:
            with patch.object(client,'request') as request:
                with self.assertRaises(ValueError):
                    client.step(Action(forward=value))
                request.assert_not_called()

    def test_order_conflict_requires_reset(self):
        client = Client('test')
        client.episode, client.index = 'episode', 0
        with patch.object(client,'request',return_value=transition(2,'episode')):
            with self.assertRaises(ProtocolError): client.step(Action())
        self.assertTrue(client.uncertain)
        with self.assertRaises(ProtocolError): client.step(Action())

    def test_invalid_reset_response_blocks_old_episode(self):
        client = Client('test')
        client.episode,client.index='old-episode',5
        with patch.object(client,'request',return_value=transition(1,'new-episode')):
            with self.assertRaises(ProtocolError): client.reset(42)
        with self.assertRaises(ProtocolError): client.step(Action())

    def test_read_only_protocol_failure_does_not_clear_uncertainty(self):
        client = Client('test')
        client.uncertain = True
        with patch.object(client.opener,'open',return_value=io.BytesIO(b'{"protocol":"unknown"}')):
            with self.assertRaises(ProtocolError): client.spec()
        self.assertTrue(client.uncertain)

    def test_recording_preserves_images_and_separates_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = Recorder(Path(directory),{'rgb_available':True},42)
            data = transition()
            recorder.append(data)
            recorder.append(transition(1),Action(forward=1))
            recorder.close()
            manifest = json.loads((recorder.path/'manifest.json').read_text())
            self.assertEqual(manifest['status'],'completed')
            self.assertEqual(manifest['human_verification'],'pending')
            rows = [json.loads(line) for line in (recorder.path/'transitions.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),2)
            self.assertNotIn('privileged',rows[0]['observation'])
            self.assertEqual((recorder.path/rows[0]['observation']['rgb']['path']).read_bytes(),checked_png(data['observation']['rgb']))
            self.assertTrue((recorder.path/'report.html').exists())
            self.assertIn('data',data['observation']['rgb'])  # caller-owned response was not mutated

    def test_corrupt_image_cannot_be_recorded_as_success(self):
        rgb=png()
        raw=bytearray(base64.b64decode(rgb['data']))
        raw[30] ^= 1
        rgb['data']=base64.b64encode(raw).decode()
        with self.assertRaises(ProtocolError): checked_png(rgb)

    def test_recorder_rejects_dropped_step_and_marks_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder=Recorder(Path(directory),{'rgb_available':True},42)
            recorder.append(transition())
            with self.assertRaises(ProtocolError): recorder.append(transition(2),Action())
            recorder.close('missing transition')
            self.assertEqual(json.loads((recorder.path/'manifest.json').read_text())['status'],'failed')

    def test_privileged_field_cannot_leak_into_observation_contract(self):
        data=transition()
        data['observation']['hidden_target_position']=[1,2,3]
        with self.assertRaises(ProtocolError): Client.validate_transition(data)


if __name__ == '__main__': unittest.main()
