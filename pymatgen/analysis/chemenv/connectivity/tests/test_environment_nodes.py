#!/usr/bin/env python


__author__ = 'waroquiers'

import networkx as nx
import os
import shutil
from pymatgen.analysis.chemenv.connectivity.environment_nodes import get_environment_node, EnvironmentNode
from pymatgen.util.testing import PymatgenTest
import bson

json_files_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..",
                              'test_files', "chemenv", "json_test_files")


class EnvironmentNodesTest(PymatgenTest):

    def test_equal(self):
        s = PymatgenTest.get_structure('SiO2')
        en = EnvironmentNode(central_site=s[0], i_central_site=0, ce_symbol='T:4')

        en1 = EnvironmentNode(central_site=s[2], i_central_site=0, ce_symbol='T:4')
        self.assertTrue(en == en1)
        self.assertFalse(en.everything_equal(en1))

        en2 = EnvironmentNode(central_site=s[0], i_central_site=3, ce_symbol='T:4')
        self.assertFalse(en == en2)
        self.assertFalse(en.everything_equal(en2))

        en3 = EnvironmentNode(central_site=s[0], i_central_site=0, ce_symbol='O:6')
        self.assertTrue(en == en3)
        self.assertFalse(en.everything_equal(en3))

    def test_as_dict(self):
        s = PymatgenTest.get_structure('SiO2')
        en = EnvironmentNode(central_site=s[2], i_central_site=3, ce_symbol='T:4')

        en_from_dict = EnvironmentNode.from_dict(en.as_dict())
        self.assertTrue(en.everything_equal(en_from_dict))

        bson_data = bson.BSON.encode(en.as_dict())
        en_from_bson = bson_data.decode()
        self.assertTrue(en.everything_equal(en_from_bson))


if __name__ == "__main__":
    import unittest
    unittest.main()
