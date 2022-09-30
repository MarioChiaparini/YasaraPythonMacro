from lib2to3.pgen2.token import OP
from threading import local
from typing import Type

from matplotlib.artist import setp
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

# 
def RsmD(atom,number):
    return None 

#Define the force fields
def ForceF(ff, method, parset):
    #AMBER94 (ff94), AMBER96 (ff96), AMBER99 (ff99), AMBER03 (ff03.r1), AMBER10 (ff10), AMBER11 (ff99sb*-ILDN), AMBER12 (ff12SB), AMBER14 (ff14SB), AMBER14IPQ (ff14ipq), NOVA, YAMBER, YAMBER2 and YAMBER3
    return ForceField(name=f"{ff}", method=f"{method}", setpar=f"{parset}")
def SimulState(cont, femto, path):
    #	Control = Init | On | Pause | Continue | Off
    #	in = femtoseconds till pause
    return Sim(control=f"{cont}", In=f"{femto}"), SaveSim(filename=f"{path}"), LoadSim(filename=f"{path}")
 