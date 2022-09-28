from lib2to3.pgen2.token import OP
from typing import Type
from yasara import *
from yasara_kernel import *

print(ListObj("All"))
objects = JoinObj(2,1)

#Moving the ligand to the receptor
def Mol2Rec(objects):
    center1 = GroupCenter(f"{objects[0]} 1 Mol A", coordsys="global", Type="Geometric")
    center2 = GroupCenter(f"{objects[1]} 2 Mol A", coordsys="global", Type="Geometric")
    cavity = [2.2001, 28.61056, -0.45295]
    return MoveObj(selection1=f"{objects[1]}", x=cavity[0], y=cavity[1], z=cavity[2])

#get cavities 
def DockingScene(PATH):
    pdb_file = LoadPDB(PATH)
    #show the cavitiers 
    ShowCaviAll(Type="Molecular")
    
