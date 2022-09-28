from lib2to3.pgen2.token import OP
from threading import local
from typing import Type
from yasara import *
from yasara_kernel import *
import params as par


#Sum atom displacement to calculate cross-validation coefficients 
def DccM(atom, number):
    AddDispMol(selection1=f"{atom} Mol A {number}")
    return DCCM()

# Root Mean Square Fluctuation
def RmsF(atom, number):
    print("Adding the atom position into a table")
    AddPosAtom(selection1=f"{atom} Mol A {number}")
    print("Setting the average postion of the atom")
    AveragePosAtom(selection1=f"{atom} Mol A {number}")
    print("Calculation the RMSF...")
    return RMSFAtom(selection1=f"{atom} Mol A {number}")
