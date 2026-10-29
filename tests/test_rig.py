import copy
import unittest

from erl.rig import validate_inventory


class RigInventoryTests(unittest.TestCase):
    def setUp(self):
        self.inventory = {'format': 'talos-rig-inventory/1.0', 'avatar_loaded': True,
                          'components': [{'component': 'Body', 'bones': [
                              {'name': 'root', 'index': 0, 'parent_index': -1},
                              {'name': 'finger', 'index': 1, 'parent_index': 0}]}]}

    def test_valid_hierarchy(self):
        validate_inventory(self.inventory)

    def test_unloaded_avatar(self):
        self.inventory['avatar_loaded'] = False
        with self.assertRaises(ValueError):
            validate_inventory(self.inventory)

    def test_parent_cycle(self):
        self.inventory['components'][0]['bones'][1]['parent_index'] = 1
        with self.assertRaises(ValueError):
            validate_inventory(self.inventory)

    def test_ambiguous_component(self):
        self.inventory['components'].append(copy.deepcopy(self.inventory['components'][0]))
        with self.assertRaises(ValueError):
            validate_inventory(self.inventory)


if __name__ == '__main__':
    unittest.main()
