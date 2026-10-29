import copy
import json
from pathlib import Path
import unittest

from erl.motor import validate_mapping


class MotorMappingTests(unittest.TestCase):
    def setUp(self):
        self.mapping = json.loads((Path(__file__).resolve().parents[1] / 'configs/motor_metahuman_hand_v1.json').read_text())

    def test_template(self):
        validate_mapping(self.mapping)

    def test_invalid_axis(self):
        for axis in ([0, 0, 0], [0, True, 0], [0, float('nan'), 1], [0, 0, 2]):
            with self.subTest(axis=axis), self.assertRaises(ValueError):
                m = copy.deepcopy(self.mapping)
                m['channels'][0]['axis'] = axis
                validate_mapping(m)

    def test_duplicate_binding(self):
        self.mapping['channels'][1]['bone'] = self.mapping['channels'][0]['bone'].upper()
        with self.assertRaises(ValueError):
            validate_mapping(self.mapping)

    def test_extra_fields(self):
        self.mapping['channels'][0]['unknown'] = 1
        with self.assertRaises(ValueError):
            validate_mapping(self.mapping)

    def test_invalid_limits(self):
        for value in (-1, True, 91, float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m = copy.deepcopy(self.mapping)
                m['channels'][0]['limit_deg'] = value
                validate_mapping(m)

    def test_alternate_avatar_component(self):
        self.mapping['body_component'] = 'MyBody'
        self.mapping['channels'][0]['bone'] = 'my_index_joint'
        validate_mapping(self.mapping)


if __name__ == '__main__':
    unittest.main()
