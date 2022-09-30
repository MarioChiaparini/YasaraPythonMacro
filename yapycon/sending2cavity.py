from lib2to3.pgen2.token import OP
from threading import local
from typing import Type
from yasara import *
from yasara_kernel import *

print(ListObj("All"))
objects = JoinObj(2,1)

#Moving the ligand to the receptor
def Mol2Rec(objects, atomref):
    center1 = GroupCenter(f"{objects[0]} 1 Mol A", coordsys="global", Type="Geometric")
    center2 = GroupCenter(f"{objects[1]} 2 Mol A", coordsys="global", Type="Geometric")
    localone = PosAtom(selection1=f"{objects[0]} Mol A {atomref}", coordsys="local")
    globalone = PosAtom(selection1=f"{objects[0]} Mol A {atomref}", coordsys="global")

    return MoveObj(selection1=f"{objects[1]}", x=localone[0], y=localone[1], z=localone[2])

#get cavities 
def CaviScene(PATH):
    pdb_file = LoadPDB(f"{PATH}")
    #show the cavitiers 
    return ShowCaviAll(Type="Molecular")

#Docking simulation
def DockingExec():
    None
