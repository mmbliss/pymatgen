# coding: utf-8
# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

import warnings

import os
import unittest
import pandas as pd

from monty.serialization import loadfn

import pymatgen.analysis.magnetism.heisenberg as heisenberg
from pymatgen import Structure

test_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..",
                        'test_files', 'magnetic_orderings')

formulas = ['CoS2', 'MnNi2Sn', 'MnSi', 'LiMnPO4', 'Ta2CoO6', 'Ni(SbO3)2']

class HeisenbergMapperTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.df = pd.read_json(os.path.join(test_dir, 'mag_orderings_test_cases.json'))

        cls.CoS2 = cls.df[cls.df['formula_pretty']=='CoS2']
        cls.MnNi2Sn = cls.df[cls.df['formula_pretty']=='MnNi2Sn']
        cls.MnSi = cls.df[cls.df['formula_pretty']=='MnSi']
        cls.LiMnPO4 = cls.df[cls.df['formula_pretty']=='LiMnPO4']
        cls.Ta2CoO6 = cls.df[cls.df['formula_pretty']=='Ta2CoO6']
        cls.Ni_SbO3_2 = cls.df[cls.df['formula_pretty']=='Ni(SbO3)2']

        # cls.compounds = [cls.CoS2, cls.MnNi2Sn, cls.MnSi,
        # cls.LiMnPO4, cls.Ta2CoO6, cls.Ni_SbO3_2]
        cls.compounds = [cls.MnSi]

        cls.hms = []
        for c in cls.compounds:
            ordered_structures = list(c['structure'])
            ordered_structures = [Structure.from_dict(d) for d in ordered_structures]
            epa = list(c['energy_per_atom'])
            energies = [e*len(s) for (e, s) in zip(epa, ordered_structures)]

            hm = heisenberg.HeisenbergMapper(ordered_structures, energies)
            cls.hms.append(hm)

    def setUp(self):
        pass

    def tearDown(self):
        warnings.simplefilter('default')

    def test_graphs(self):
        for hm in self.hms:
            sgraphs = hm.sgraphs
            print('Num of graphs: %d' % (len(sgraphs)))
        pass

    def test_sites(self):
        for hm in self.hms:
            unique_site_ids = hm.unique_site_ids
            print('Unique sites: ' + str(unique_site_ids))

    def test_nn_interactions(self):
        for hm in self.hms:
            nn_interactions = hm.nn_interactions
            print('NN interactions: ' + str(nn_interactions))

    def test_exchange_matrix(self):
        for hm in self.hms:
            ex_mat = hm.ex_mat
            print('Ex mat: ')
            print(ex_mat.values)

    def test_exchange_params(self):
        for hm in self.hms:
            ex_params = hm.get_exchange()
            print('Ex params: ' + str(ex_params))

    def test_mean_field(self):
        for hm in self.hms:
            j_avg = hm.estimate_exchange()
            print('<J> ' + str(j_avg))
            mft_t = hm.get_mft_temperature(j_avg)
            print('MFT T: ' + str(mft_t))

if __name__ == '__main__':
    unittest.main()