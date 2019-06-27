# coding: utf-8
# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import unittest
import os
import warnings

import pandas as pd

from monty.os.path import which

import pymatgen.command_line.vampire_caller as vampirecaller
from pymatgen.analysis.magnetism.heisenberg import HeisenbergMapper

from pymatgen import Structure

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        'test_files', 'magnetic_orderings')

@unittest.skipIf(not which('vampire-serial'), "vampire executable not present")
class VampireCallerTest(unittest.TestCase):
    """Todo:
        * Put json files of magnetic orderings and energies in
        pymatgen/test_files with variable number of unique magnetic
        sites, sublattices, FM, FiM, and AFM ground state, etc.
        * Compare Tc calcs to known Tc
    """

    @classmethod
    def setUpClass(cls):
        
        print('Testing with: ', which('vampire-serial'))

        cls.Mn3Al = pd.read_json(os.path.join(test_dir,
            'Mn3Al.json'))

        cls.compounds = [cls.Mn3Al]

        cls.structure_inputs = []
        cls.energy_inputs = []
        for c in cls.compounds:
            ordered_structures = list(c['structure'])
            ordered_structures = [Structure.from_dict(d) for d in ordered_structures]
            epa = list(c['energy_per_atom'])
            energies = [e*len(s) for (e, s) in zip(epa, ordered_structures)]

            cls.structure_inputs.append(ordered_structures)
            cls.energy_inputs.append(energies)

    def setUp(self):
        pass

    def tearDown(self):
        warnings.simplefilter('default')

    def test_vampire(self):
        for structs, energies in zip(self.structure_inputs, 
            self.energy_inputs):
            vc = vampirecaller.VampireCaller(structs, energies,
                equil_timesteps=100, mc_timesteps=100)
            print('Critical temp: ', vc.output.critical_temp, ' K')

if __name__ == '__main__':
    unittest.main()
