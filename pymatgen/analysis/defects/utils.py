#!/usr/bin/env python

__author__ = "Danny Broberg, Shyam Dwaraknath, Bharat Medasani, Nils Zimmermann, Geoffroy Hautier"
__copyright__ = "Copyright 2014, The Materials Project"
__version__ = "1.0"
__maintainer__ = "Danny Broberg, Shyam Dwaraknath"
__email__ = "dbroberg@berkeley.edu, shyamd@lbl.gov"
__status__ = "Development"
__date__ = "January 11, 2018"

import math

from monty.json import MSONable

import numpy as np
norm = np.linalg.norm

hart_to_ev = 27.2114
ang_to_bohr = 1.8897
invang_to_ev = 3.80986
kb = 8.6173324e-5  #eV / K


class QModel(MSONable):
    """
    Model for the defect charge distribution.
    A combination of exponential tail and gaussian distribution is used
    (see Freysoldt (2011), DOI: 10.1002/pssb.201046289 )
    q_model(r) = q [x exp(-r/gamma) + (1-x) exp(-r^2/beta^2)]
            without normalization constants
    By default, gaussian distribution with 1 Bohr width is assumed.
    If defect charge is more delocalized, exponential tail is suggested.
    """

    def __init__(self, beta=1.0, expnorm=0.0, gamma=1.0):
        """
        Args:
            beta: Gaussian decay constant. Default value is 1 Bohr.
                  When delocalized (eg. diamond), 2 Bohr is more appropriate.
            expnorm: Weight for the exponential tail in the range of [0-1].
                     Default is 0.0 indicating no tail .
                     For delocalized charges ideal value is around 0.54-0.6.
            gamma: Exponential decay constant
        """
        self.beta = beta
        self.expnorm = expnorm
        self.gamma = gamma

        self.beta2 = beta * beta
        self.gamma2 = gamma * gamma
        if expnorm and not gamma:
            raise ValueError("Please supply exponential decay constant.")

    def rho_rec(self, g2):
        """
        Reciprocal space model charge value
        for input squared reciprocal vector.
        Args:
            g2: Square of reciprocal vector

        Returns:
            Charge density at the reciprocal vector magnitude
        """
        return (self.expnorm / np.sqrt(1 + self.gamma2 * g2) + (1 - self.expnorm) * np.exp(-0.25 * self.beta2 * g2))

    @property
    def rho_rec_limit0(self):
        """
        Reciprocal space model charge value
        close to reciprocal vector 0 .
        rho_rec(g->0) -> 1 + rho_rec_limit0 * g^2
        """
        return -2 * self.gamma2 * self.expnorm - 0.25 * self.beta2 * (1 - self.expnorm)


def eV_to_k(energy):
    """
    Convert energy to reciprocal vector magnitude k via hbar*k^2/2m
    Args:
        a: Energy in eV.

    Returns:
        (double) Reciprocal vector magnitude (units of 1/Bohr).
    """
    return math.sqrt(energy / invang_to_ev) * ang_to_bohr


def genrecip(a1, a2, a3, encut):
    """
    Args:
        a1, a2, a3: lattice vectors in bohr
        encut: energy cut off in eV
    Returns:
        reciprocal lattice vectors with energy less than encut
    """
    vol = np.dot(a1, np.cross(a2, a3))  # 1/bohr^3
    b1 = (2 * np.pi / vol) * np.cross(a2, a3)  # units 1/bohr
    b2 = (2 * np.pi / vol) * np.cross(a3, a1)
    b3 = (2 * np.pi / vol) * np.cross(a1, a2)

    # create list of recip space vectors that satisfy |i*b1+j*b2+k*b3|<=encut
    gcut = eV_to_k(encut)
    imax = int(math.ceil(gcut/min(map(norm, [b1, b2, b3]))))

    for i in range(-imax, imax + 1):
        for j in range(-imax, imax + 1):
            for k in range(-imax, imax + 1):
                vec = i*b1 + j*b2 + k*b3
                en = invang_to_ev * (((1.0/ang_to_bohr) * norm(vec))**2)
                if (en <= encut and en != 0):
                    yield vec


def generate_reciprocal_vectors_squared(a1, a2, a3, encut):
    """
    Generate reciprocal vector magnitudes within the cutoff along the specied
    lattice vectors.
    Args:
        a1: Lattice vector a (in Bohrs)
        a2: Lattice vector b (in Bohrs)
        a3: Lattice vector c (in Bohrs)
        encut: Reciprocal vector energy cutoff

    Returns:
        [[g1^2], [g2^2], ...] Square of reciprocal vectors (1/Bohr)^2
        determined by a1, a2, a3 and whose magntidue is less than gcut^2.
    """
    vol = np.dot(a1, np.cross(a2, a3))
    b1 = (2 * np.pi / vol) * np.cross(a2, a3)
    b2 = (2 * np.pi / vol) * np.cross(a3, a1)
    b3 = (2 * np.pi / vol) * np.cross(a1, a2)

    # Max (i,j,k) that doesn't upset the condition |i*b1+j*b2+k*b3|<=gcut
    gcut = eV_to_k(encut)
    imax = int(math.ceil(gcut / min(norm(b1), norm(b2), norm(b3))))
    gcut2 = gcut * gcut

    for i in range(-imax, imax + 1):
        for j in range(-imax, imax + 1):
            for k in range(-imax, imax + 1):
                vec = i * b1 + j * b2 + k * b3
                vec2 = np.dot(vec, vec)
                if (vec2 <= gcut2 and vec2 != 0.0):
                    yield vec2


def closestsites(struct_blk, struct_def, pos):
    """
    Returns closest site to the input position
    for both bulk and defect structures
    Args:
        struct_blk: Bulk structure
        struct_def: Defect structure
        pos: Position
    Return: (site object, dist, index)
    """
    blk_close_sites = struct_blk.get_sites_in_sphere(pos, 5, include_index=True)
    blk_close_sites.sort(key=lambda x: x[1])
    def_close_sites = struct_def.get_sites_in_sphere(pos, 5, include_index=True)
    def_close_sites.sort(key=lambda x: x[1])

    return blk_close_sites[0], def_close_sites[0]

