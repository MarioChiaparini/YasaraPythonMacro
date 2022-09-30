from hypothesis import seed
from matplotlib.artist import setp
from yasara import *
from yasara_kernel import *
import params as par

class CavityStat:
    def __init__(self, selection, typeone):
        self.selection = selection
        self.typeone = typeone 
    #Get first atom or residue facing each cavity and the cavity volume
    #Get first atom or residue facing each surface and the surface area
    
    def SurfCav(self,selection, typeone):
        #The FirstCavi command locates cavities (empty space inside a macromolecule) and identifies the first, most important atom or residue (depending on the final selection unit) that faces each cavity. For each cavity, the atom or residue, as well as the cavity volume are returned.
        cav_list = FirstCaviAtom(selection1=f"{selection}")
        #The FirstSurf command allows to separate surfaces that are not connected 
        # with each other but belong to the same object. Every protein has one main 
        # outer surface, and possibly a number of smaller inner surfaces, that enclose cavities. 
        # For each of these surfaces, the FirstSurf command returns the number of the first 
        # atom or residue contributing to the surface as well as the area of the surface.
        surf_list = FirstSurfAtom(selection1=f"{selection}",Type=f"{typeone}")
        return surf_list, cav_list, ShowCaviAtom(selection1=f"{selection}")
    
    def CalcCav(self, typeone, selection, which):
        if which == "Atom":
            vol = CaviVolAtom(selection1=f"{selection}", Type=f"{typeone}")
            radius = RadiusAtom(selection1=f"{selection}", Type=f"{typeone}")
        elif which == "Mol":
            vol = CaviVolMol(selection1=f"{selection}", Type=f"{typeone}")
            radius = RadiusMol(selection1=f"{selection}", Type=f"{typeone}")
        elif which == "Obj":
            vol = CaviVolObj(selection1=f"{selection}", Type=f"{typeone}")
            radius = RadiusObj(selection1=f"{selection}", Type=f"{typeone}")
        elif which == "Res":
            vol = CaviVolRes(selection1=f"{selection}", Type=f"{typeone}")
            radius = RadiusRes(selection1=f"{selection}", Type=f"{typeone}")
        else:
            vol = CaviVolAll(selection1=f"{selection}", Type=f"{typeone}")
            radius = RadiusAll(selection1=f"{selection}", Type=f"{typeone}")
        return radius, vol, ShowCaviAll(selection="All")

    def EnvCalc(self, selection, typeone):
        while option == True:
            CalcEnv = AddEnvObj(selection1=f"{selection}")
            if selection == None and CalcEnv != 0:
                option = False 
        return CalcEnv, ShowSurfAll(selection1=f"{selection}", Type=f"{typeone}")