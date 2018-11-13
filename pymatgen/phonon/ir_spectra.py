# coding: utf-8
# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

from __future__ import unicode_literals

import collections
import numpy as np

from pymatgen.core.structure import Structure
from pymatgen.core.lattice import Lattice
from pymatgen.core.spectrum import Spectrum
from pymatgen.electronic_structure.bandstructure import Kpoint
from pymatgen.util.plotting import pretty_plot, add_fig_kwargs, get_ax_fig_plt
from monty.json import MSONable

"""
This module provides classes to handle the calculation of the IR spectra
This implementation is adapted from Abipy
https://github.com/abinit/abipy
where it was originally done by Guido Petretto and Matteo Giantomassi
"""

__author__ = "Henrique Miranda, Guido Pettreto, Matteo Giantomassi"
__copyright__ = "Copyright 2018, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Henrique Miranda"
__email__ = "miranda.henrique@gmail.com"
__date__ = "Oct 31, 2018"

class IRDielectricTensorGenerator(MSONable):
    """
    Class to handle the Ionic Dielectric Tensor
    The implementation is adapted from Abipy
    See the definitions Eq.(53-54) in :cite:`Gonze1997` PRB55, 10355 (1997).
    """

    def __init__(self, oscillator_strength, phfreqs_gamma, epsinf, structure):
        self.structure = structure
        self.oscillator_strength = np.array(oscillator_strength).real
        self.phfreqs_gamma = np.array(phfreqs_gamma)
        self.epsinf = np.array(epsinf)

    @classmethod
    def from_dict(cls, d):
        """
        Returns IRDielectricTensor from dict representation
        """
        structure = Structure.from_dict(d['structure'])
        oscillator_strength = d['oscillator_strength']
        phfreqs_gamma = d['phfreqs_gamma']
        epsinf = d['epsinf']
        return cls(oscillator_strength, phfreqs_gamma, epsinf, structure)
 
    @property
    def max_phfreq(self): return max(self.phfreqs_gamma)
    @property
    def nphfreqs(self): return len(self.phfreqs_gamma)

    def as_dict(self):
        """
        Json-serializable dict representation of IRDielectricTensor.
        """
        return {"@module": self.__class__.__module__,
                "@class": self.__class__.__name__,
                "oscillator_strength": self.oscillator_strength.tolist(),
                "phfreqs_gamma": self.phfreqs_gamma.tolist(),
                "structure": self.structure.as_dict(),
                "epsinf": self.epsinf.tolist()}

    def write_json(self,filename):
        """
        Save a json file with this data
        """
        import json
        with open(filename,'w') as f:
            json.dump(self.as_dict(),f)

    def get_ir_spectra(self,broad=0.00005,emin=0,emax=None,divs=500):
        """
        The IR spectra is obtained for the different directions

        Args:
            broad: a list of broadenings or a single broadening for the phonon peaks
            emin, emax: minimum and maximum energy in which to obtain the spectra
            ndivs: number of frequency samples between emin and emax
        """
        if isinstance(broad,float): broad = [broad]*self.nphfreqs 
        if isinstance(broad,list) and len(broad) != self.nphfreqs:
            raise ValueError('The number of elements in the broad_list is not the same as the number of frequencies')
 
        if emax is None: emax = self.max_phfreq + max(broad)*20 
        w = np.linspace(emin,emax,divs)
           
        na = np.newaxis
        t = np.zeros((divs, 3, 3),dtype=complex)
        for i in range(3, len(self.phfreqs_gamma)):
            g =  broad[i] * self.phfreqs_gamma[i]
            t += (self.oscillator_strength[i,:,:] / (self.phfreqs_gamma[i]**2 - w[:,na,na]**2 - 1j*g))
        t += self.epsinf[na,:,:]

        return IRSpectra(w,t,self)

class IRSpectra():
    """
    Class containing an IR Spectra
    """
    def __init__(self,frequencies,ir_spectra_tensor,ir_spectra_generator):
        self.frequencies = frequencies
        self.ir_spectra_tensor = ir_spectra_tensor
        self.ir_spectra_generator = ir_spectra_generator
 
    @add_fig_kwargs
    def plot(self,ax=None,components=('xx',),reim="reim",vertical_lines=True,**kwargs):
        """
        Return an instance of the spectra and plot it using matplotlib
        """
        ax,fig,plt = get_ax_fig_plt(ax=ax)
        directions_map = {'x':0,'y':1,'z':2}
        functions_map = {'re': lambda x: x.real, 'im': lambda x: x.imag}
        reim_label = {'re':'Re','im':'Im'}
        for component in components:
            i,j = [directions_map[direction] for direction in component]
            for fstr in functions_map:
                if fstr in reim:
                    f = functions_map[fstr]
                    label = "%s{$\epsilon_{%s}$}"%(reim_label[fstr],component)
                    ax.plot(self.frequencies*1000,f(self.ir_spectra_tensor[:,i,j]),label=label,**kwargs)

        if vertical_lines:
            phfreqs_gamma = self.ir_spectra_generator.phfreqs_gamma[3:]
            ax.scatter(phfreqs_gamma*1000,np.zeros_like(phfreqs_gamma))
        ax.set_xlabel('$\epsilon(\omega)$')
        ax.set_xlabel('Frequency (meV)')
        ax.legend()
        return fig

