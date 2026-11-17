import copy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from erl.client import ProtocolError
from erl.face import FaceClient, validate_mapping
from erl.face_demo import sequence


class FaceTests(unittest.TestCase):
    def setUp(self):
        self.mapping = json.loads((Path(__file__).resolve().parents[1]/'configs/face_metahuman_basic_v1.json').read_text())
        self.client = Mock(episode='episode', index=0, uncertain=False, done=False)
        self.client.request.return_value = dict(ready=True, mapping=self.mapping)
        self.face = FaceClient(self.client)
        self.client.request.reset_mock()

    def test_invalid_mapping(self):
        for field in ('name', 'curve'):
            bad = copy.deepcopy(self.mapping)
            bad['channels'][1][field] = bad['channels'][0][field].upper()
            with self.assertRaises(ValueError): validate_mapping(bad)
        bad = copy.deepcopy(self.mapping); bad['channels'][0]['extra'] = 1
        with self.assertRaises(ValueError): validate_mapping(bad)

    def test_invalid_targets_never_sent(self):
        for value in (True, -1, 1.1, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.face.step(dict(blink_left=value, blink_right=0, jaw_open=0))
        with self.assertRaises(ValueError): self.face.step(dict(blink_left=0))
        self.client.request.assert_not_called()

    def test_ordering_failure_requires_reset(self):
        self.client.request.return_value = dict(episode_id='wrong', step_index=1)
        with self.assertRaises(ProtocolError):
            self.face.step(dict(blink_left=.2, blink_right=0, jaw_open=0))
        self.assertTrue(self.client.uncertain)
        self.client.request.reset_mock()
        with self.assertRaises(ProtocolError):
            self.face.step(dict(blink_left=.2, blink_right=0, jaw_open=0))
        self.client.request.assert_not_called()

    def test_success_updates_clock(self):
        self.client.request.return_value = dict(episode_id='episode', step_index=1, terminated=False, truncated=False)
        self.face.step(dict(blink_left=.2, blink_right=0, jaw_open=0))
        self.assertEqual(self.client.index, 1)
        self.assertEqual(self.client.request.call_args.args[1]['expected_step'], 0)

    def test_expression_sweep_is_isolated_rate_limited_and_returns_neutral(self):
        mapping = json.loads((Path(__file__).resolve().parents[1]/'configs/face_metahuman_expression_v1.json').read_text())
        validate_mapping(mapping)
        previous = {c['name']: 0 for c in mapping['channels']}
        activated = set()
        steps = list(sequence(mapping, True))
        self.assertEqual(len(steps), 208)
        for targets, label in steps:
            self.assertEqual(set(targets), set(previous))
            self.assertLessEqual(sum(v > 0 for v in targets.values()), 1)
            for name, value in targets.items():
                self.assertLessEqual(abs(value-previous[name]), .200001)
                if value == 1: activated.add(name)
            previous = targets
        self.assertEqual(activated, set(previous))
        self.assertTrue(all(v == 0 for v in previous.values()))


if __name__ == '__main__': unittest.main()
