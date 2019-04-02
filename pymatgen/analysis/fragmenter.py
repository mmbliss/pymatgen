# coding: utf-8
# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.


import logging
import copy
import numpy as np
from monty.json import MSONable
from pymatgen.analysis.graphs import MoleculeGraph, MolGraphSplitError, isomorphic
from pymatgen.analysis.local_env import OpenBabelNN
from pymatgen.io.babel import BabelMolAdaptor


__author__ = "Samuel Blau"
__copyright__ = "Copyright 2018, The Materials Project"
__version__ = "1.0"
__maintainer__ = "Samuel Blau"
__email__ = "samblau1@gmail.com"
__status__ = "Alpha"
__date__ = "9/7/18"


logger = logging.getLogger(__name__)


class Fragmenter(MSONable):

    def __init__(self, molecule, edges=None, depth=1, open_rings=True, opt_steps=10000, use_igraph=False, prev_unique_frag_dict=None):
        """
        Standard constructor for molecule fragmentation

        Args:
            molecule (Molecule): The molecule to fragment
            edges (list): List of index pairs that define graph edges, aka molecule bonds. If not
                          set, edges will be determined with OpenBabel.
            depth (int): The number of levels of iterative fragmentation to perform, where each
                         level will include fragments obtained by breaking one bond of a fragment
                         one level up. Defaults to 1. However, if set to 0, instead all possible
                         fragments are generated using an alternative, non-iterative scheme.
            open_rings (bool): Whether or not to open any rings encountered during fragmentation.
                               Defaults to False. If true, any bond that fails to yield disconnected
                               graphs when broken is instead removed and the entire structure is
                               optimized with OpenBabel in order to obtain a good initial guess for
                               an opened geometry that can then be put back into QChem to be
                               optimized without the ring just reforming.
            opt_steps (int): Number of optimization steps when opening rings. Defaults to 1000.

        """
        self.assume_previous_thoroughness = True
        self.open_rings = open_rings
        self.opt_steps = opt_steps
        self.use_igraph = use_igraph

        if edges is None:
            self.mol_graph = MoleculeGraph.with_local_env_strategy(molecule, OpenBabelNN(),
                                                                   reorder=False,
                                                                   extend_structure=False)
        else:
            edges = {(e[0], e[1]): None for e in edges}
            self.mol_graph = MoleculeGraph.with_edges(molecule, edges)

        if "Li" in molecule.composition or "Mg" in molecule.composition:
            print("Extending lithium and magnesium edges to ensure that we capture coordination to nearby oxygens or nitrogens.")
            if self.open_rings:
                print("WARNING: Metal edge extension while opening rings can yeild unphysical fragments!")
            self._metal_edge_extender()

        self.prev_unique_frag_dict = prev_unique_frag_dict or {}
        self.new_unique_frag_dict = {}

        if depth == 0: # Non-iterative, find all possible fragments:

            # Find all unique fragments besides those involving ring opening
            self.unique_fragments = self.mol_graph.build_unique_fragments(self.use_igraph)

            # Then, if self.open_rings is True, open all rings present in self.unique_fragments
            # in order to capture all unique fragments that require ring opening.
            if self.open_rings:
                self._open_all_rings()

            for fragment in self.unique_fragments:
                frag_key = str(fragment.molecule.composition.alphabetical_formula)+" E"+str(len(fragment.graph.edges()))
                add_frag = False
                if frag_key not in self.prev_unique_frag_dict:
                    add_frag = True
                else:
                    found = False
                    for prev_frag in self.prev_unique_frag_dict[frag_key]:
                        if isomorphic(fragment.graph,prev_frag.graph,self.use_igraph):
                            found = True
                            break
                    add_frag = not found
                if add_frag:
                    if frag_key not in self.new_unique_frag_dict:
                        self.new_unique_frag_dict[frag_key] = [fragment]
                    else:
                        self.new_unique_frag_dict[frag_key].append(fragment)
                            
        else: # Iterative fragment generation:
            self.level_unique_frag_dict = {}
            self.fragments_by_level = {}

            # Loop through the number of levels,
            for level in range(depth):
                # If on the first level, perform one level of fragmentation on the principle molecule graph:
                if level == 0:
                    print("Level",level)
                    self.fragments_by_level["0"] = self._fragment_one_level({str(self.mol_graph.molecule.composition.alphabetical_formula)+" E"+str(len(self.mol_graph.graph.edges())): [self.mol_graph]})
                else:
                    num_frags_prev_level = 0
                    for key in self.fragments_by_level[str(level-1)]:
                        num_frags_prev_level += len(self.fragments_by_level[str(level-1)][key])
                    print(num_frags_prev_level,"unique fragments on level",level-1)
                    print("Level",level)
                    if num_frags_prev_level == 0:
                        # Nothing left to fragment, so exit the loop:
                        break
                    else: # If not on the first level, and there are fragments present in the previous level, then
                          # perform one level of fragmentation on all fragments present in the previous level:
                        self.fragments_by_level[str(level)] = self._fragment_one_level(self.fragments_by_level[str(level-1)])
            if self.prev_unique_frag_dict == {}:
                self.new_unique_frag_dict = copy.deepcopy(self.level_unique_frag_dict)
            else:
                for frag_key in self.level_unique_frag_dict:
                    if frag_key not in self.prev_unique_frag_dict:
                        self.new_unique_frag_dict[frag_key] = copy.deepcopy(self.level_unique_frag_dict[frag_key])
                    else:
                        for fragment in self.level_unique_frag_dict[frag_key]:
                            found = False
                            for prev_frag in self.prev_unique_frag_dict[frag_key]:
                                if isomorphic(fragment.graph,prev_frag.graph,self.use_igraph):
                                    found = True
                            if not found:
                                if frag_key not in self.new_unique_frag_dict:
                                    self.new_unique_frag_dict[frag_key] = [fragment]
                                else:
                                    self.new_unique_frag_dict[frag_key].append(fragment)

        self.new_unique_fragments = 0
        for frag_key in self.new_unique_frag_dict:
            self.new_unique_fragments += len(self.new_unique_frag_dict[frag_key])

        if self.prev_unique_frag_dict == {}:
            self.unique_frag_dict = self.new_unique_frag_dict
            self.total_unique_fragments = self.new_unique_fragments
        else:
            self.unique_frag_dict = copy.deepcopy(self.prev_unique_frag_dict)
            for frag_key in self.new_unique_frag_dict:
                if frag_key in self.unique_frag_dict:
                    for new_frag in self.new_unique_frag_dict[frag_key]:
                        self.unique_frag_dict[frag_key].append(new_frag)
                else:
                    self.unique_frag_dict[frag_key] = copy.deepcopy(self.new_unique_frag_dict[frag_key])

            self.total_unique_fragments = 0
            for frag_key in self.unique_frag_dict:
                self.total_unique_fragments += len(self.unique_frag_dict[frag_key])

    def _metal_edge_extender(self):
        metal_sites = {"Li": {}, "Mg": {}}
        num_new_edges = 0
        for idx in self.mol_graph.graph.nodes():
            if self.mol_graph.graph.nodes()[idx]["specie"] in metal_sites:
                metal_sites[self.mol_graph.graph.nodes()[idx]["specie"]][idx] = [site[2] for site in self.mol_graph.get_connected_sites(idx)]
        for metal in metal_sites:
            for idx in metal_sites[metal]:
                for ii,site in enumerate(self.mol_graph.molecule):
                    if ii != idx and ii not in metal_sites[metal][idx]:
                        if str(site.specie) == "O" or str(site.specie) == "N":
                            if site.distance(self.mol_graph.molecule[idx]) < 2.5:
                                self.mol_graph.add_edge(idx,ii)
                                num_new_edges += 1
                                metal_sites[metal][idx].append(ii)
        total_metal_edges = 0
        for metal in metal_sites:
            for idx in metal_sites[metal]:
                total_metal_edges += len(metal_sites[metal][idx])
        if total_metal_edges == 0:
            for metal in metal_sites:
                for idx in metal_sites[metal]:
                    for ii,site in enumerate(self.mol_graph.molecule):
                        if ii != idx and ii not in metal_sites[metal][idx]:
                            if str(site.specie) == "O" or str(site.specie) == "N":
                                if site.distance(self.mol_graph.molecule[idx]) < 3.5:
                                    self.mol_graph.add_edge(idx,ii)
                                    num_new_edges += 1
                                    metal_sites[metal][idx].append(ii)
        total_metal_edges = 0
        for metal in metal_sites:
            for idx in metal_sites[metal]:
                total_metal_edges += len(metal_sites[metal][idx])
        print("Metal edge extension added", num_new_edges, "new edges.")
        print("Total of", total_metal_edges, "metal edges.")

    def _fragment_one_level(self, old_frag_dict):
        """
        Perform one step of iterative fragmentation on a list of molecule graphs. Loop through the graphs,
        then loop through each graph's edges and attempt to remove that edge in order to obtain two
        disconnected subgraphs, aka two new fragments. If successful, check to see if the new fragments
        are already present in self.unique_fragments, and append them if not. If unsucessful, we know
        that edge belongs to a ring. If we are opening rings, do so with that bond, and then again
        check if the resulting fragment is present in self.unique_fragments and add it if it is not.
        """
        new_frag_dict = {}
        for old_frag_key in old_frag_dict:
            for old_frag in old_frag_dict[old_frag_key]:
                for edge in old_frag.graph.edges:
                    bond = [(edge[0],edge[1])]
                    try:
                        fragments = old_frag.split_molecule_subgraphs(bond, allow_reverse=True)
                        for fragment in fragments:
                            new_frag_key = str(fragment.molecule.composition.alphabetical_formula)+" E"+str(len(fragment.graph.edges()))
                            proceed = True
                            if self.assume_previous_thoroughness and self.prev_unique_frag_dict != {}:
                                if new_frag_key in self.prev_unique_frag_dict:
                                    for unique_fragment in self.prev_unique_frag_dict[new_frag_key]:
                                        if isomorphic(unique_fragment.graph,fragment.graph,self.use_igraph):
                                            proceed = False
                                            break
                            if proceed:
                                if new_frag_key not in self.level_unique_frag_dict:
                                    self.level_unique_frag_dict[new_frag_key] = [fragment]
                                    new_frag_dict[new_frag_key] = [fragment]
                                else:
                                    found = False
                                    for unique_fragment in self.level_unique_frag_dict[new_frag_key]:
                                        if isomorphic(unique_fragment.graph,fragment.graph,self.use_igraph):
                                            found = True
                                            break
                                    if not found:
                                        self.level_unique_frag_dict[new_frag_key].append(fragment)
                                        if new_frag_key in new_frag_dict:
                                            new_frag_dict[new_frag_key].append(fragment)
                                        else:
                                            new_frag_dict[new_frag_key] = [fragment]
                    except MolGraphSplitError:
                        if self.open_rings:
                            fragment = open_ring(old_frag, bond, self.opt_steps)
                            new_frag_key = str(fragment.molecule.composition.alphabetical_formula)+" E"+str(len(fragment.graph.edges()))
                            proceed = True
                            if self.assume_previous_thoroughness and self.prev_unique_frag_dict != {}:
                                if new_frag_key in self.prev_unique_frag_dict:
                                    for unique_fragment in self.prev_unique_frag_dict[new_frag_key]:
                                        if isomorphic(unique_fragment.graph,fragment.graph,self.use_igraph):
                                            proceed = False
                                            break
                            if proceed:
                                if new_frag_key not in self.level_unique_frag_dict:
                                    self.level_unique_frag_dict[new_frag_key] = [fragment]
                                    new_frag_dict[new_frag_key] = [fragment]
                                else:
                                    found = False
                                    for unique_fragment in self.level_unique_frag_dict[new_frag_key]:
                                        if isomorphic(unique_fragment.graph,fragment.graph,self.use_igraph):
                                            found = True
                                            break
                                    if not found:
                                        self.level_unique_frag_dict[new_frag_key].append(fragment)
                                        if new_frag_key in new_frag_dict:
                                            new_frag_dict[new_frag_key].append(fragment)
                                        else:
                                            new_frag_dict[new_frag_key] = [fragment]
        return new_frag_dict

    def _open_all_rings(self):
        """
        Having already generated all unique fragments that did not require ring opening,
        now we want to also obtain fragments that do require opening. We achieve this by
        looping through all unique fragments and opening each bond present in any ring
        we find. We also temporarily add the principle molecule graph to self.unique_fragments
        so that its rings are opened as well.
        """
        self.unique_fragments.insert(0, self.mol_graph)
        for fragment in self.unique_fragments:
            ring_edges = fragment.find_rings()
            if ring_edges != []:
                for bond in ring_edges[0]:
                    new_fragment = open_ring(fragment, [bond], self.opt_steps)
                    found = False
                    for unique_fragment in self.unique_fragments:
                        if isomorphic(unique_fragment.graph,new_fragment.graph,self.use_igraph):
                            found = True
                            break
                    if not found:
                        # self.unique_fragments_from_ring_openings.append(new_fragment)
                        self.unique_fragments.append(new_fragment)
        # Finally, remove the principle molecule graph:
        self.unique_fragments.pop(0)

def open_ring(mol_graph, bond, opt_steps):
    """
    Function to actually open a ring using OpenBabel's local opt. Given a molecule
    graph and a bond, convert the molecule graph into an OpenBabel molecule, remove
    the given bond, perform the local opt with the number of steps determined by
    self.steps, and then convert the resulting structure back into a molecule graph
    to be returned.
    """
    obmol = BabelMolAdaptor.from_molecule_graph(mol_graph)
    obmol.remove_bond(bond[0][0]+1, bond[0][1]+1)
    obmol.localopt(steps=opt_steps,forcefield='uff')
    return MoleculeGraph.with_local_env_strategy(obmol.pymatgen_mol, OpenBabelNN(), reorder=False, extend_structure=False)
