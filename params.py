from argparse import _StoreFalseAction
from msilib.schema import ListBox
from typing import List
from unittest import result
from yasara import *
from yasara_kernel import *


def BondAtoms(atom1,atom2):
    AddBond(selection1=f"{atom1}", selection2=f"{atom2}", Update="Yes")
    list_bounds = ListBond(selection1=f"{atom1}",selection2=f"{atom2}", results=4)
    Coun_bonds = CountBond(selection=f"{atom1}",_selection2=f"{atom2}", Type="All")
    return list_bounds, Coun_bonds

def HydroAtoms(atom1, numb, ph, pka=None):
    #add the missing ones
    print(f"Adding Hydrogens: {atom1}")
    AddHydroAtom(selection=f"{atom1}", number=numb)
    
    #setting ph
    print(f"Setting PH: {ph}")
    pH(value=ph)

    # setting pKa
    print(f"Setting the Pka: {pka}")
    pKaRes(selection1=f"{atom1}", value=pka)
    
    return  CountAtom(selection=f"{atom1}")
