"""
YASARA functionality available to YaPyCon.

**Notes:**

    * This module is largely based on the original `yasara.py` module by Elmar Krieger, that can be found in a typical
      YASARA installation.

    * ``yasara_kernel.py`` is *almost* identical to ``yasara.py``.

    * The key differences are:

      1. ``yasara_kernel`` *excludes* certain YASARA functions that could bring YASARA and / or YaPyCon in an
         indeterminate state (for example: ``StopPlugin(), Exit()``).
      2. ``yasara_kernel.py`` *includes* certain convenience functions that reformat the output of certain YASARA commands
         (such as: ``ListAtom(), ListBond()``). Any additional functions provided by YaPyCon are prefixed with
         ``yapycon_`` and are very easy to browse through.
      3. ``yasara_kernel.py`` *includes* typical docstrings in the
         `Sphinx docstring format <https://sphinx-rtd-tutorial.readthedocs.io/en/latest/docstrings.html>`_, for:

          * *All* of its own functions (i.e. the plugin code and ``yapycon_`` prefixed functions from
            ``yasara_kernel.py``)
          * *All* of the ``yasara.py`` functions that have been modified (e.g. ``SavePNG()``).
          * *Selected* ``yasara.py`` functions to demonstrate the usefulness of this feature more generally.

      4. ``yasara_kernel.py`` *skips* all of the initialisation that ``yasara.py`` carries out typically when it is
         loaded. Instead, it re-uses the RPC proxied objects to initialise its own global variables such as:
         ``plugin, request, opsys, version, serialnumber, stage, owner, permissions, workdir, selection, com``.

      5. ``yasara_kernel.py`` is more up to date with Python3 (to the extent that this is possible and practical).
     
:author: Athanasios Anastasiou
:date: Nov 2021
"""

import sys
import os
import socket
import struct
import pickle

import rpyc

try:
    from matplotlib import pyplot as plt
    MATPLOTLIB_AVAILABLE=True
except ImportError:
    MATPLOTLIB_AVAILABLE=False




#  ======================================================================
#           Y A S A R A   C O M M U N I C A T I O N   C L A S S
#  ======================================================================

def binary(text):
    return (text.encode("latin-1"))


def text(binary):
    return (binary.decode("latin-1"))


def byte(value):
    return (value)


class yasara_communicator:

    # INITIALIZE COMMUNICATION WITH YASARA
    # ====================================
    def __init__(self):
        # THE MESSAGE IDs AND OTHER PREDEFINED VALUES
        self.RESULT = 0  # Result of a YASARA command
        self.ERROR = 1  # Error raised by YASARA
        self.broken = "Socket connection broken"
        port = socket.IPPORT_USERRESERVED
        while (1):
            self.srvsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # FIND AND BLOCK A FREE PORT.
            # NOTE: AT LEAST WINDOWS ME WITH PYTHON 2.5 HAS A BUG WHERE SETTING SO_REUSEADDR
            # ALLOWS TO BIND TO PORT 5000, WHICH IS HOWEVER USED BY ANOTHER PROGRAM (ssdpsrv.exe).
            # (INSTEAD, SO_REUSEADDR SHOULD ONLY ALLOW TO BIND PORTS THAT ARE IN TIME_WAIT STATE
            # AFTER A PREVIOUS CONNECTION HAS ENDED, WAITING FOR LEFTOVER TCP PACKETS). AS A
            # RESULT, YASARA SENDS THE RESULTS TO WHOEVER OWNS PORT 5000, AND THE SCRIPT HANGS FOREVER.
            # self.srvsock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            try:
                # SOCKET IS ONLY VISIBLE ON THE LOCAL MACHINE
                self.srvsock.bind(("", port))
                break
            except:
                port += 1
        self.srvsock.listen(1)
        self.sock = None
        self.port = port

    # ACCEPT A CONNECTION FROM YASARA
    # ===============================
    def accept(self):
        if (self.sock != None): raise RuntimeError("Connection has already been accepted")
        (self.sock, ip) = self.srvsock.accept()

    # RECEIVE DATA FROM YASARA
    # ========================
    def receive(self, size):
        data = binary("")
        while (len(data) < size):
            # IF THE CONNECTION BREAKS, THIS RETURNS 0 IN LINUX,
            # BUT RAISES AN EXCEPTION (WHICH ONE??) IN SOME WINDOWS VERSIONS
            try:
                chunk = self.sock.recv(size - len(data))
            except KeyboardInterrupt:
                raise
            except:
                raise RuntimeError(self.broken)
            if (len(chunk) == 0): raise RuntimeError(self.broken)
            data += chunk
        return (data)

    # RECEIVE A MESSAGE FROM YASARA
    # =============================
    def receivemessage(self, expectedtype=None):
        (messagetype, datasize) = struct.unpack('ii', self.receive(8))
        data = self.receive(datasize)
        messagedata = pickle.loads(data)
        if (messagetype == self.ERROR):
            raise RuntimeError("YASARA raised error %d: %s" % (messagedata[0], messagedata[1]))
        if (expectedtype != None and messagetype != expectedtype):
            raise RuntimeError("Unexpected message type received")
        if (expectedtype == None):
            return ((messagetype, messagedata))
        else:
            return (messagedata)


#  ======================================================================
#                 P L U G I N   F U N C T I O N   G R O U P
#  ======================================================================

# RUN A YASARA COMMAND, POTENTIALLY RETURNING RESULTS
# ===================================================
def runretval(command, retvalused):
    global com, std_relay_service

    # NOTE: This will never execute in the case of yapycon because the "checking" stage is skipped
    # if (request=="CheckIfDisabled"):
    #   raise RuntimeError("You cannot run YASARA commands during the startup phase, when your plugin checks if it can be activated or should be disabled")
    if not retvalused:
        # NO RETURN VALUE NEEDED, RETURN IMMEDIATELY
        std_relay_service.root.stdout_relay('Exec: ' + command + '\n')
        return None
    else:
        # THE CALLER WANTS A RETURN VALUE, WAIT FOR YASARA RESULTS
        if com is None:
            # BIND A SOCKET TO RECEIVE RESULTS FROM YASARA
            com = yasara_communicator()
            # SEND COMMAND AND REPLY PORT
            std_relay_service.root.stdout_relay('ExecRV%d: ' % com.port + command + '\n')
            # ACCEPT CONNECTION
            com.accept()
        else:
            # SEND COMMAND ONLY
            std_relay_service.root.stdout_relay('ExecRV: ' + command + '\n')
        return com.receivemessage(com.RESULT)


# CONVERT VERSION STRING TO INTEGER
# =================================
def versionint(ver_str):
    ver_str_components_int = list(map(lambda x: int, ver_str.strip().split('.')))
    return ver_str_components_int[0] * 10000 + ver_str_components_int[1] * 100 + ver_str_components_int[2]


# TODO: HIGH, Revise the accessibility of these functions.
# # RUN A YASARA COMMAND
# # ====================
# def run(command):
#   return(runretval(command, True))

# # WRITE DEBUGGING INFO TO CONSOLE
# # ===============================
# def write(info):
#   print(info)
#   sys.stdout.flush()

# CLEAN STRING
# ============
def cstr(text, quoted=False):
    text_inst = str(text)
    text_inst = text_inst.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    if quoted or text_inst.find(',') != -1:
        for quote in ['"', "'"]:
            if text_inst.find(quote) == -1:
                break
        else:
            quote = '"'
            text_inst = text_inst.replace(quote, "'")
        text_inst = f"{quote}{text_inst}{quote}"
    return text_inst


# CONVERT SELECTION TO STRING
# ===========================
def selstr(selection):
    # TODO: HIGH, Review this function
    if (type(selection) in [type(""), type(u""), type(1), type(1.)]):
        selstr = cstr(selection)
    else:
        if (type(selection) != type([])):
            selection = list(selection)
        selstr = ""
        for i in range(len(selection)):
            if (i > 0 and type(selection[i]) == type("") and type(selection[i - 1]) == type("") and
                    ((selection[i][:9] == "Res Atom " and selection[i - 1][:9] == "Res Atom ") or
                     (selection[i][:9] == "Mol Atom " and selection[i - 1][:9] == "Mol Atom "))):
                # WE CAN COMPRESS THE UNIQUE RESIDUE/MOLECULE IDs (SEE DOCS OF List COMMAND)
                selstr += cstr(selection[i][9:] + " ")
            else:
                selstr += cstr(selection[i]) + " "
    selstr = selstr.strip()
    if (selstr == ""): selstr = "none"
    return (selstr)


# TODO: HIGH, review whether to include these two functions
# # CHECK FOR YASARA VERSION
# # ========================
# # THIS IS A REPLACEMENT FOR YASARA'S RequireVersion COMMAND
# def RequireVersion(reqversion):
#   # GET CURRENT VERSION
#   curversionsplit=version.split(".")
#   reqversionsplit=reqversion.split(".")
#   for i in range(3):
#     if (int(curversionsplit[i])>int(reqversionsplit[i])):
#         break
#     if (int(curversionsplit[i])<int(reqversionsplit[i])):
#       plugin.end(f"This plugin reqires at least YASARA Version {reqversion}, "
#                  f"but currently only version {version} is installed")

# # SAVE PERSISTENT STORAGE FOR NEXT TIME
# # =====================================
# def SaveStorage():
#   if (storage!=None):
#     # USER ADDED PERSISTENT data, SEND TO YASARA (WHICH WILL DELETE THE FILE)
#     filename=disk.tmpfilename("data")
#     pickle.dump(storage,open(filename,"wb"))
#     runretval("SaveStorage %s"%filename,0)

# WAIT FOR YASARA TO FINISH EXECUTION
# ===================================
def Finish():
    # USE THE RETURN VALUE OF A DUMMY COMMAND TO FORCE THE SYNCHRONIZATION
    result = CountObj("all")


# TODO: HIGH, Review whether to allow for Exit() to be used from the kernel
# # EXIT YASARA
# # ===========
# # WE CANNOT WAIT FOR A RESULT
# def Exit():
#   runretval("Exit",0)


#  ======================================================================
#                Y A S A R A   F U N C T I O N   G R O U P
#  ======================================================================

# SET/GET ACCELERATION OF ATOMS (ALL OR SELECTED)
# ===============================================
def Accel(x=None, y=None, z=None):
    command = 'Accel '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET ACCELERATION OF ATOMS (ALL)
# ===================================
def AccelAll(x=None, y=None, z=None):
    command = 'AccelAll '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET ACCELERATION OF ATOMS (OBJECT)
# ======================================
def AccelObj(selection1, x=None, y=None, z=None):
    command = 'AccelObj '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET ACCELERATION OF ATOMS (MOLECULE)
# ========================================
def AccelMol(selection1, x=None, y=None, z=None):
    command = 'AccelMol '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET ACCELERATION OF ATOMS (RESIDUE)
# =======================================
def AccelRes(selection1, x=None, y=None, z=None):
    command = 'AccelRes '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET ACCELERATION OF ATOMS (ATOM)
# ====================================
def AccelAtom(selection1, x=None, y=None, z=None):
    command = 'AccelAtom '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# ADD ANGLE TO FORCE FIELD
# ========================
def AddAngle(selection1, selection2, selection3, Min=None, bfc=None):
    command = 'AddAngle '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += selstr(selection3) + ','
    if (Min != None): command += 'Min=' + cstr(Min) + ','
    if (bfc != None): command += 'BFC=' + cstr(bfc) + ','
    return (runretval(command[:-1], True))


# ADD COVALENT BONDS
# ==================
def AddBond(selection1, selection2, order=None, update=None, lenmax=None):
    command = 'AddBond '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (order != None): command += 'Order=' + cstr(order) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    if (lenmax != None): command += 'LenMax=' + cstr(lenmax) + ','
    return (runretval(command[:-1], True))


# ADD N/C-TERMINAL CAPPING GROUPS (ALL OR SELECTED)
# =================================================
def AddCap(Type=None, location=None):
    command = 'AddCap '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (location != None): command += 'Location=' + cstr(location) + ','
    return (runretval(command[:-1], True))


# ADD N/C-TERMINAL CAPPING GROUPS (ALL)
# =====================================
def AddCapAll(Type=None, location=None):
    command = 'AddCapAll '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (location != None): command += 'Location=' + cstr(location) + ','
    return (runretval(command[:-1], True))


# ADD N/C-TERMINAL CAPPING GROUPS (OBJECT)
# ========================================
def AddCapObj(selection1, Type=None, location=None):
    command = 'AddCapObj '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (location != None): command += 'Location=' + cstr(location) + ','
    return (runretval(command[:-1], True))


# ADD DIHEDRAL TO FORCE FIELD
# ===========================
def AddDihedral(selection1, selection2, selection3, selection4, barrier=None, period=None, phase=None):
    command = 'AddDihedral '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += selstr(selection3) + ','
    command += selstr(selection4) + ','
    if (barrier != None): command += 'Barrier=' + cstr(barrier) + ','
    if (period != None): command += 'Period=' + cstr(period) + ','
    if (phase != None): command += 'Phase=' + cstr(phase) + ','
    return (runretval(command[:-1], True))


# SUM ATOM DISPLACEMENTS TO CALCULATE CROSS-CORRELATION COEFFICIENTS (MOLECULE)
# =============================================================================
def AddDispMol(selection1, selection2):
    command = 'AddDispMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    return (runretval(command[:-1], True))


# SUM ATOM DISPLACEMENTS TO CALCULATE CROSS-CORRELATION COEFFICIENTS (RESIDUE)
# ============================================================================
def AddDispRes(selection1, selection2):
    command = 'AddDispRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    return (runretval(command[:-1], True))


# SUM ATOM DISPLACEMENTS TO CALCULATE CROSS-CORRELATION COEFFICIENTS (ATOM)
# =========================================================================
def AddDispAtom(selection1, selection2):
    command = 'AddDispAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    return (runretval(command[:-1], True))


# ADD TO ENVIRONMENT FOR SURFACE CALCULATIONS (ALL OR SELECTED)
# =============================================================
def AddEnv():
    command = 'AddEnv '
    return (runretval(command[:-1], True))


# ADD TO ENVIRONMENT FOR SURFACE CALCULATIONS (ALL)
# =================================================
def AddEnvAll():
    command = 'AddEnvAll '
    return (runretval(command[:-1], True))


# ADD TO ENVIRONMENT FOR SURFACE CALCULATIONS (OBJECT)
# ====================================================
def AddEnvObj(selection1):
    command = 'AddEnvObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# ADD TO ENVIRONMENT FOR SURFACE CALCULATIONS (MOLECULE)
# ======================================================
def AddEnvMol(selection1):
    command = 'AddEnvMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# ADD TO ENVIRONMENT FOR SURFACE CALCULATIONS (RESIDUE)
# =====================================================
def AddEnvRes(selection1):
    command = 'AddEnvRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# ADD TO ENVIRONMENT FOR SURFACE CALCULATIONS (ATOM)
# ==================================================
def AddEnvAtom(selection1):
    command = 'AddEnvAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# ADD ELECTROSTATIC FIELD
# =======================
def AddESF(x=None, y=None, z=None):
    command = 'AddESF '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# ADD MISSING HYDROGENS (ALL OR SELECTED)
# =======================================
def AddHyd(number=None, update=None):
    command = 'AddHyd '
    if (number != None): command += 'Number=' + cstr(number) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    return (runretval(command[:-1], True))


# ADD MISSING HYDROGENS (ALL)
# ===========================
def AddHydAll(number=None, update=None):
    command = 'AddHydAll '
    if (number != None): command += 'Number=' + cstr(number) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    return (runretval(command[:-1], True))


# ADD MISSING HYDROGENS (OBJECT)
# ==============================
def AddHydObj(selection1, number=None, update=None):
    command = 'AddHydObj '
    command += selstr(selection1) + ','
    if (number != None): command += 'Number=' + cstr(number) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    return (runretval(command[:-1], True))


# ADD MISSING HYDROGENS (MOLECULE)
# ================================
def AddHydMol(selection1, number=None, update=None):
    command = 'AddHydMol '
    command += selstr(selection1) + ','
    if (number != None): command += 'Number=' + cstr(number) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    return (runretval(command[:-1], True))


# ADD MISSING HYDROGENS (RESIDUE)
# ===============================
def AddHydRes(selection1, number=None, update=None):
    command = 'AddHydRes '
    command += selstr(selection1) + ','
    if (number != None): command += 'Number=' + cstr(number) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    return (runretval(command[:-1], True))


# ADD MISSING HYDROGENS (ATOM)
# ============================
def AddHydAtom(selection1, number=None, update=None):
    command = 'AddHydAtom '
    command += selstr(selection1) + ','
    if (number != None): command += 'Number=' + cstr(number) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    return (runretval(command[:-1], True))


# SUM ATOM POSITIONS TO CALCULATE AVERAGE AND STANDARD DEVIATION (MOLECULE)
# =========================================================================
def AddPosMol(selection1):
    command = 'AddPosMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SUM ATOM POSITIONS TO CALCULATE AVERAGE AND STANDARD DEVIATION (RESIDUE)
# ========================================================================
def AddPosRes(selection1):
    command = 'AddPosRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SUM ATOM POSITIONS TO CALCULATE AVERAGE AND STANDARD DEVIATION (ATOM)
# =====================================================================
def AddPosAtom(selection1):
    command = 'AddPosAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# ADD TERMINAL RESIDUE
# ====================
def AddRes(name, selection1, omega=None, phi=None, psi=None, tau=None, end=None, isomer=None):
    command = 'AddRes '
    command += 'Name=' + cstr(name) + ','
    command += selstr(selection1) + ','
    if (omega != None): command += 'Omega=' + cstr(omega) + ','
    if (phi != None): command += 'Phi=' + cstr(phi) + ','
    if (psi != None): command += 'Psi=' + cstr(psi) + ','
    if (tau != None): command += 'Tau=' + cstr(tau) + ','
    if (end != None): command += 'End=' + cstr(end) + ','
    if (isomer != None): command += 'Isomer=' + cstr(isomer) + ','
    return (runretval(command[:-1], True))


# ADD TERMINAL RESIDUE
# ====================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def AddRes2(name, selection1, epsilon=None, zeta=None, alpha=None, beta=None, gamma=None, end=None):
    command = 'AddRes '
    command += 'Name=' + cstr(name) + ','
    command += selstr(selection1) + ','
    if (epsilon != None): command += 'Epsilon=' + cstr(epsilon) + ','
    if (zeta != None): command += 'Zeta=' + cstr(zeta) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (beta != None): command += 'Beta=' + cstr(beta) + ','
    if (gamma != None): command += 'Gamma=' + cstr(gamma) + ','
    if (end != None): command += 'End=' + cstr(end) + ','
    return (runretval(command[:-1], True))


# ADD BOND OR POSITION RESTRAINT TO FORCE FIELD
# =============================================
def AddSpring(selection1, selection2, len=None, sfc=None):
    command = 'AddSpring '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (len != None): command += 'Len=' + cstr(len) + ','
    if (sfc != None): command += 'SFC=' + cstr(sfc) + ','
    return (runretval(command[:-1], True))


# ADD CELLS TO TABLE
# ==================
def Tabulate(value):
    command = 'Tabulate '
    command += 'Value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# ADD C-TERMINAL OXYGENS (ALL OR SELECTED)
# ========================================
def AddTer():
    command = 'AddTer '
    return (runretval(command[:-1], True))


# ADD C-TERMINAL OXYGENS (ALL)
# ============================
def AddTerAll():
    command = 'AddTerAll '
    return (runretval(command[:-1], True))


# ADD C-TERMINAL OXYGENS (OBJECT)
# ===============================
def AddTerObj(selection1):
    command = 'AddTerObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# ADD OBJECTS TO THE SOUP (ALL OR SELECTED)
# =========================================
def Add():
    command = 'Add '
    return (runretval(command[:-1], True))


# ADD OBJECTS TO THE SOUP (ALL)
# =============================
def AddAll():
    command = 'AddAll '
    return (runretval(command[:-1], True))


# ADD OBJECTS TO THE SOUP (OBJECT)
# ================================
def AddObj(selection1):
    command = 'AddObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# ALIGN MULTIPLE OBJECTS (ALL OR SELECTED)
# ========================================
def AlignMulti(parameter=None):
    command = 'AlignMulti '
    if (parameter != None): command += 'Parameter=' + cstr(parameter) + ','
    return (runretval(command[:-1], True))


# ALIGN MULTIPLE OBJECTS (ALL)
# ============================
def AlignMultiAll(parameter=None):
    command = 'AlignMultiAll '
    if (parameter != None): command += 'Parameter=' + cstr(parameter) + ','
    return (runretval(command[:-1], True))


# ALIGN MULTIPLE OBJECTS (OBJECT)
# ===============================
def AlignMultiObj(selection1, parameter=None):
    command = 'AlignMultiObj '
    command += selstr(selection1) + ','
    if (parameter != None): command += 'Parameter=' + cstr(parameter) + ','
    return (runretval(command[:-1], True))


# SET/GET ALIGNMENT PARAMETERS
# ============================
def AlignPar(dismax=None, anglemax=None, lenmin=None, gapopen=None, gapextend=None, overhang=None):
    command = 'AlignPar '
    if (dismax != None): command += 'DisMax=' + cstr(dismax) + ','
    if (anglemax != None): command += 'AngleMax=' + cstr(anglemax) + ','
    if (lenmin != None): command += 'LenMin=' + cstr(lenmin) + ','
    if (gapopen != None): command += 'GapOpen=' + cstr(gapopen) + ','
    if (gapextend != None): command += 'GapExtend=' + cstr(gapextend) + ','
    if (overhang != None): command += 'Overhang=' + cstr(overhang) + ','
    return (runretval(command[:-1], True))


# ALIGN SIMILAR PROTEINS FROM THE PDB
# ===================================
def AlignPDBMol(selection1, method=None, structures=None, coverage=None, seqidmax=None, filename=None, format=None):
    command = 'AlignPDBMol '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (structures != None): command += 'Structures=' + cstr(structures) + ','
    if (coverage != None): command += 'Coverage=' + cstr(coverage) + ','
    if (seqidmax != None): command += 'SeqIdMax=' + cstr(seqidmax) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    return (runretval(command[:-1], True))


# ALIGN ATOMS
# ===========
def AlignAtom(selection1, selection2, method=None, matchelement=None, matchname=None, matchbonds=None,
              matchbondorders=None, matchsecstr=None, dismax=None):
    command = 'AlignAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (matchelement != None): command += 'MatchElement=' + cstr(matchelement) + ','
    if (matchname != None): command += 'MatchName=' + cstr(matchname) + ','
    if (matchbonds != None): command += 'MatchBonds=' + cstr(matchbonds) + ','
    if (matchbondorders != None): command += 'MatchBondOrders=' + cstr(matchbondorders) + ','
    if (matchsecstr != None): command += 'MatchSecStr=' + cstr(matchsecstr) + ','
    if (dismax != None): command += 'DisMax=' + cstr(dismax) + ','
    return (runretval(command[:-1], True))


# ALIGN OBJECTS AND MOLECULES (OBJECT)
# ====================================
def AlignObj(selection1, selection2, method=None, parameter=None, results=None, copyresnum=None):
    command = 'AlignObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (parameter != None): command += 'Parameter=' + cstr(parameter) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    if (copyresnum != None): command += 'CopyResNum=' + cstr(copyresnum) + ','
    return (runretval(command[:-1], True))


# ALIGN OBJECTS AND MOLECULES (MOLECULE)
# ======================================
def AlignMol(selection1, selection2, method=None, parameter=None, results=None, copyresnum=None):
    command = 'AlignMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (parameter != None): command += 'Parameter=' + cstr(parameter) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    if (copyresnum != None): command += 'CopyResNum=' + cstr(copyresnum) + ','
    return (runretval(command[:-1], True))


# SET/GET ANGLE BETWEEN ATOMS
# ===========================
def Angle(selection1, selection2, selection3, bound=None, set=None):
    command = 'Angle '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += selstr(selection3) + ','
    if (bound != None): command += 'bound=' + cstr(bound) + ','
    if (set != None): command += 'set=' + cstr(set) + ','
    return (runretval(command[:-1], True))


# GET ANGLE BETWEEN TWO VECTORS
# =============================
def AngleVec(x1=None, y1=None, z1=None, x2=None, y2=None, z2=None):
    command = 'AngleVec '
    if (x1 != None): command += 'X1=' + cstr(x1) + ','
    if (y1 != None): command += 'Y1=' + cstr(y1) + ','
    if (z1 != None): command += 'Z1=' + cstr(z1) + ','
    if (x2 != None): command += 'X2=' + cstr(x2) + ','
    if (y2 != None): command += 'Y2=' + cstr(y2) + ','
    if (z2 != None): command += 'Z2=' + cstr(z2) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# ANIMATE APPEARANCE AND DISAPPEARANCE OF IMAGES
# ==============================================
def AnimateImage(selection1, enter=None, rest=None, leave=None, steps=None):
    command = 'AnimateImage '
    command += selstr(selection1) + ','
    if (enter != None): command += 'Enter=' + cstr(enter) + ','
    if (rest != None): command += 'Rest=' + cstr(rest) + ','
    if (leave != None): command += 'Leave=' + cstr(leave) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    return (runretval(command[:-1], True))


# ANIMATE WINDOWS
# ===============
def AnimateWin(Type):
    command = 'AnimateWin '
    command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# SET SIMULATED ANNEALING STEPS
# =============================
def AnnealSteps(number):
    command = 'AnnealSteps '
    command += 'Number=' + cstr(number) + ','
    return (runretval(command[:-1], True))


# SWITCH ANTIALIASING ON/OFF
# ==========================
def Antialias(level):
    command = 'Antialias '
    command += 'Level=' + cstr(level) + ','
    return (runretval(command[:-1], True))


# APPLY MACRO TO MULTIPLE TARGETS OR FILES
# ========================================
def ApplyMacro(filename, targets, remove=None, newextension=None):
    command = 'ApplyMacro '
    command += 'Filename=' + cstr(filename) + ','
    command += 'Targets=' + cstr(targets) + ','
    if (remove != None): command += 'Remove=' + cstr(remove) + ','
    if (newextension != None): command += 'NewExtension=' + cstr(newextension) + ','
    return (runretval(command[:-1], True))


# SWITCH PLASMA INSIDE ATOMS ON/OFF
# =================================
def AtomPlasma(flag):
    command = 'AtomPlasma '
    command += 'Flag=' + cstr(flag) + ','
    return (runretval(command[:-1], True))


# SET SIZE OF ATOMS
# =================
def AtomSize(radius):
    command = 'AtomSize '
    command += 'Radius=' + cstr(radius) + ','
    return (runretval(command[:-1], True))


# SWITCH ELEMENT SYMBOL INSIDE ATOMS ON/OFF
# =========================================
def AtomSymbol(flag):
    command = 'AtomSymbol '
    command += 'Flag=' + cstr(flag) + ','
    return (runretval(command[:-1], True))


# SET TEXTURE STYLE OF ATOMS
# ==========================
def AtomTexture(Type):
    command = 'AtomTexture '
    command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# MOVE IMAGES AUTOMATICALLY
# =========================
def AutoMoveImage(selection1, x=None, y=None, width=None, height=None, alpha=None, steps=None, cycle=None, zoom3d=None):
    command = 'AutoMoveImage '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (width != None): command += 'Width=' + cstr(width) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (cycle != None): command += 'Cycle=' + cstr(cycle) + ','
    if (zoom3d != None): command += 'Zoom3D=' + cstr(zoom3d) + ','
    return (runretval(command[:-1], True))


# POSITION AND ORIENT OBJECTS OR SCENE AUTOMATICALLY IN A GIVEN NUMBER OF STEPS (ALL OR SELECTED)
# ===============================================================================================
def AutoPosOri(x, y, z, alpha, beta, gamma, steps=None, wait=None):
    command = 'AutoPosOri '
    command += 'X=' + cstr(x) + ','
    command += 'Y=' + cstr(y) + ','
    command += 'Z=' + cstr(z) + ','
    command += 'Alpha=' + cstr(alpha) + ','
    command += 'Beta=' + cstr(beta) + ','
    command += 'Gamma=' + cstr(gamma) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# POSITION AND ORIENT OBJECTS OR SCENE AUTOMATICALLY IN A GIVEN NUMBER OF STEPS (ALL)
# ===================================================================================
def AutoPosOriAll(x, y, z, alpha, beta, gamma, steps=None, wait=None):
    command = 'AutoPosOriAll '
    command += 'X=' + cstr(x) + ','
    command += 'Y=' + cstr(y) + ','
    command += 'Z=' + cstr(z) + ','
    command += 'Alpha=' + cstr(alpha) + ','
    command += 'Beta=' + cstr(beta) + ','
    command += 'Gamma=' + cstr(gamma) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# POSITION AND ORIENT OBJECTS OR SCENE AUTOMATICALLY IN A GIVEN NUMBER OF STEPS (OBJECT)
# ======================================================================================
def AutoPosOriObj(selection1, x, y, z, alpha, beta, gamma, steps=None, wait=None):
    command = 'AutoPosOriObj '
    command += selstr(selection1) + ','
    command += 'X=' + cstr(x) + ','
    command += 'Y=' + cstr(y) + ','
    command += 'Z=' + cstr(z) + ','
    command += 'Alpha=' + cstr(alpha) + ','
    command += 'Beta=' + cstr(beta) + ','
    command += 'Gamma=' + cstr(gamma) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# POSITION OBJECTS OR SCENE AUTOMATICALLY IN A GIVEN NUMBER OF STEPS (ALL OR SELECTED)
# ====================================================================================
def AutoPos(x=None, y=None, z=None, steps=None, wait=None):
    command = 'AutoPos '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# POSITION OBJECTS OR SCENE AUTOMATICALLY IN A GIVEN NUMBER OF STEPS (ALL)
# ========================================================================
def AutoPosAll(x=None, y=None, z=None, steps=None, wait=None):
    command = 'AutoPosAll '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# POSITION OBJECTS OR SCENE AUTOMATICALLY IN A GIVEN NUMBER OF STEPS (OBJECT)
# ===========================================================================
def AutoPosObj(selection1, x=None, y=None, z=None, steps=None, wait=None):
    command = 'AutoPosObj '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# MOVE OBJECTS OR SCENE AUTOMATICALLY (ALL OR SELECTED)
# =====================================================
def AutoMove(x=None, y=None, z=None):
    command = 'AutoMove '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# MOVE OBJECTS OR SCENE AUTOMATICALLY (ALL)
# =========================================
def AutoMoveAll(x=None, y=None, z=None):
    command = 'AutoMoveAll '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# MOVE OBJECTS OR SCENE AUTOMATICALLY (OBJECT)
# ============================================
def AutoMoveObj(selection1, x=None, y=None, z=None):
    command = 'AutoMoveObj '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# ORIENT OBJECTS OR SCENE AUTOMATICALLY IN A GIVEN NUMBER OF STEPS (ALL OR SELECTED)
# ==================================================================================
def AutoOri(alpha, beta, gamma, steps=None, wait=None):
    command = 'AutoOri '
    command += 'Alpha=' + cstr(alpha) + ','
    command += 'Beta=' + cstr(beta) + ','
    command += 'Gamma=' + cstr(gamma) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# ORIENT OBJECTS OR SCENE AUTOMATICALLY IN A GIVEN NUMBER OF STEPS (ALL)
# ======================================================================
def AutoOriAll(alpha, beta, gamma, steps=None, wait=None):
    command = 'AutoOriAll '
    command += 'Alpha=' + cstr(alpha) + ','
    command += 'Beta=' + cstr(beta) + ','
    command += 'Gamma=' + cstr(gamma) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# ORIENT OBJECTS OR SCENE AUTOMATICALLY IN A GIVEN NUMBER OF STEPS (OBJECT)
# =========================================================================
def AutoOriObj(selection1, alpha, beta, gamma, steps=None, wait=None):
    command = 'AutoOriObj '
    command += selstr(selection1) + ','
    command += 'Alpha=' + cstr(alpha) + ','
    command += 'Beta=' + cstr(beta) + ','
    command += 'Gamma=' + cstr(gamma) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# ROTATE OBJECTS OR SCENE AUTOMATICALLY (ALL OR SELECTED)
# =======================================================
def AutoRotate(x=None, y=None, z=None):
    command = 'AutoRotate '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# ROTATE OBJECTS OR SCENE AUTOMATICALLY (ALL)
# ===========================================
def AutoRotateAll(x=None, y=None, z=None):
    command = 'AutoRotateAll '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# ROTATE OBJECTS OR SCENE AUTOMATICALLY (OBJECT)
# ==============================================
def AutoRotateObj(selection1, x=None, y=None, z=None):
    command = 'AutoRotateObj '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# AVERAGE ATOM POSITIONS (MOLECULE)
# =================================
def AveragePosMol(selection1):
    command = 'AveragePosMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# AVERAGE ATOM POSITIONS (RESIDUE)
# ================================
def AveragePosRes(selection1):
    command = 'AveragePosRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# AVERAGE ATOM POSITIONS (ATOM)
# =============================
def AveragePosAtom(selection1):
    command = 'AveragePosAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SET BALL AND STICK RADII IN BALLS&STICKS
# ========================================
def BallStickRadius(ball=None, stick=None):
    command = 'BallStickRadius '
    if (ball != None): command += 'Ball=' + cstr(ball) + ','
    if (stick != None): command += 'Stick=' + cstr(stick) + ','
    return (runretval(command[:-1], True))


# STYLE ATOMS AS BALLS&STICKS (ALL OR SELECTED)
# =============================================
def BallStick():
    command = 'BallStick '
    return (runretval(command[:-1], True))


# STYLE ATOMS AS BALLS&STICKS (ALL)
# =================================
def BallStickAll():
    command = 'BallStickAll '
    return (runretval(command[:-1], True))


# STYLE ATOMS AS BALLS&STICKS (OBJECT)
# ====================================
def BallStickObj(selection1):
    command = 'BallStickObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# STYLE ATOMS AS BALLS&STICKS (MOLECULE)
# ======================================
def BallStickMol(selection1):
    command = 'BallStickMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# STYLE ATOMS AS BALLS&STICKS (RESIDUE)
# =====================================
def BallStickRes(selection1):
    command = 'BallStickRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# STYLE ATOMS AS BALLS&STICKS (ATOM)
# ==================================
def BallStickAtom(selection1):
    command = 'BallStickAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# STYLE ATOMS AS BALLS (ALL OR SELECTED)
# ======================================
def Ball():
    command = 'Ball '
    return (runretval(command[:-1], True))


# STYLE ATOMS AS BALLS (ALL)
# ==========================
def BallAll():
    command = 'BallAll '
    return (runretval(command[:-1], True))


# STYLE ATOMS AS BALLS (OBJECT)
# =============================
def BallObj(selection1):
    command = 'BallObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# STYLE ATOMS AS BALLS (MOLECULE)
# ===============================
def BallMol(selection1):
    command = 'BallMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# STYLE ATOMS AS BALLS (RESIDUE)
# ==============================
def BallRes(selection1):
    command = 'BallRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# STYLE ATOMS AS BALLS (ATOM)
# ===========================
def BallAtom(selection1):
    command = 'BallAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# CALCULATE BINDING ENERGIES
# ==========================
def BindEnergyObj(selection1):
    command = 'BindEnergyObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SET/GET THE B-FACTOR (ALL OR SELECTED)
# ======================================
def BFactor(value=None):
    command = 'BFactor '
    if (value != None): command += 'value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE B-FACTOR (ALL)
# ==========================
def BFactorAll(value=None):
    command = 'BFactorAll '
    if (value != None): command += 'value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE B-FACTOR (OBJECT)
# =============================
def BFactorObj(selection1, value=None):
    command = 'BFactorObj '
    command += selstr(selection1) + ','
    if (value != None): command += 'value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE B-FACTOR (MOLECULE)
# ===============================
def BFactorMol(selection1, value=None):
    command = 'BFactorMol '
    command += selstr(selection1) + ','
    if (value != None): command += 'value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE B-FACTOR (RESIDUE)
# ==============================
def BFactorRes(selection1, value=None):
    command = 'BFactorRes '
    command += selstr(selection1) + ','
    if (value != None): command += 'value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE B-FACTOR (ATOM)
# ===========================
def BFactorAtom(selection1, value=None):
    command = 'BFactorAtom '
    command += selstr(selection1) + ','
    if (value != None): command += 'value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SORT DISTANCES INTO BINS TO CALCULATE THE RADIAL DISTRIBUTION FUNCTION
# ======================================================================
def BinDistance(selection1, selection2, bins=None, binwidth=None):
    command = 'BinDistance '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (bins != None): command += 'Bins=' + cstr(bins) + ','
    if (binwidth != None): command += 'BinWidth=' + cstr(binwidth) + ','
    return (runretval(command[:-1], True))


# BLAST PROTEIN SEQUENCE (ALL OR SELECTED)
# ========================================
def BLAST(database=None, passes=None, evalue=None, hits=None, order=None, filename=None, format=None):
    command = 'BLAST '
    if (database != None): command += 'Database=' + cstr(database) + ','
    if (passes != None): command += 'Passes=' + cstr(passes) + ','
    if (evalue != None): command += 'EValue=' + cstr(evalue) + ','
    if (hits != None): command += 'Hits=' + cstr(hits) + ','
    if (order != None): command += 'Order=' + cstr(order) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    return (runretval(command[:-1], True))


# BLAST PROTEIN SEQUENCE (ALL)
# ============================
def BLASTAll(database=None, passes=None, evalue=None, hits=None, order=None, filename=None, format=None):
    command = 'BLASTAll '
    if (database != None): command += 'Database=' + cstr(database) + ','
    if (passes != None): command += 'Passes=' + cstr(passes) + ','
    if (evalue != None): command += 'EValue=' + cstr(evalue) + ','
    if (hits != None): command += 'Hits=' + cstr(hits) + ','
    if (order != None): command += 'Order=' + cstr(order) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    return (runretval(command[:-1], True))


# BLAST PROTEIN SEQUENCE (OBJECT)
# ===============================
def BLASTObj(selection1, database=None, passes=None, evalue=None, hits=None, order=None, filename=None, format=None):
    command = 'BLASTObj '
    command += selstr(selection1) + ','
    if (database != None): command += 'Database=' + cstr(database) + ','
    if (passes != None): command += 'Passes=' + cstr(passes) + ','
    if (evalue != None): command += 'EValue=' + cstr(evalue) + ','
    if (hits != None): command += 'Hits=' + cstr(hits) + ','
    if (order != None): command += 'Order=' + cstr(order) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    return (runretval(command[:-1], True))


# BLAST PROTEIN SEQUENCE (MOLECULE)
# =================================
def BLASTMol(selection1, database=None, passes=None, evalue=None, hits=None, order=None, filename=None, format=None):
    command = 'BLASTMol '
    command += selstr(selection1) + ','
    if (database != None): command += 'Database=' + cstr(database) + ','
    if (passes != None): command += 'Passes=' + cstr(passes) + ','
    if (evalue != None): command += 'EValue=' + cstr(evalue) + ','
    if (hits != None): command += 'Hits=' + cstr(hits) + ','
    if (order != None): command += 'Order=' + cstr(order) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    return (runretval(command[:-1], True))


# BLAST PROTEIN SEQUENCE (RESIDUE)
# ================================
def BLASTRes(selection1, database=None, passes=None, evalue=None, hits=None, order=None, filename=None, format=None):
    command = 'BLASTRes '
    command += selstr(selection1) + ','
    if (database != None): command += 'Database=' + cstr(database) + ','
    if (passes != None): command += 'Passes=' + cstr(passes) + ','
    if (evalue != None): command += 'EValue=' + cstr(evalue) + ','
    if (hits != None): command += 'Hits=' + cstr(hits) + ','
    if (order != None): command += 'Order=' + cstr(order) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    return (runretval(command[:-1], True))


# BOUND VALUE TO INTERVAL
# =======================
def Bound(value, Min=None, Max=None):
    command = 'Bound '
    command += 'Value=' + cstr(value) + ','
    if (Min != None): command += 'Min=' + cstr(Min) + ','
    if (Max != None): command += 'Max=' + cstr(Max) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SET/GET CELL BOUNDARY
# =====================
def Boundary(Type=None):
    command = 'Boundary '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SIMULATION BRAKE
# ================
def Brake(speed):
    command = 'Brake '
    command += 'Speed=' + cstr(speed) + ','
    return (runretval(command[:-1], True))


# BUILD A BRIDGE BETWEEN TWO ATOMS
# ================================
def BridgeAtom(selection1, selection2, name):
    command = 'BridgeAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# SET WEB BROWSER
# ===============
def Browser(com):
    command = 'Browser '
    command += 'Command=' + cstr(com) + ','
    return (runretval(command[:-1], True))


# BUILD SINGLE ATOM
# =================
def BuildAtom(element, copies=None, selection1=None):
    command = 'BuildAtom '
    command += 'Element=' + cstr(element) + ','
    if (copies != None): command += 'Copies=' + cstr(copies) + ','
    if (selection1 != None): command += selstr(selection1) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# BUILD A GRID OF ATOMS
# =====================
def BuildGrid(element=None, x=None, y=None, z=None, spacing=None):
    command = 'BuildGrid '
    if (element != None): command += 'Element=' + cstr(element) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (spacing != None): command += 'Spacing=' + cstr(spacing) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# BUILD FUNCTIONAL GROUP
# ======================
def BuildGroup(name):
    command = 'BuildGroup '
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# BUILD CENTRAL OR TERMINAL LOOP
# ==============================
def BuildLoop(selection1, sequence, selection2, structures=None, mutate=None, bumpsum=None, secstr=None):
    command = 'BuildLoop '
    command += selstr(selection1) + ','
    command += 'Sequence=' + cstr(sequence) + ','
    command += selstr(selection2) + ','
    if (structures != None): command += 'Structures=' + cstr(structures) + ','
    if (mutate != None): command += 'Mutate=' + cstr(mutate) + ','
    if (bumpsum != None): command += 'Bumpsum=' + cstr(bumpsum) + ','
    if (secstr != None): command += 'SecStr=' + cstr(secstr) + ','
    return (runretval(command[:-1], True))


# BUILD PEPTIDE OR NUCLEIC ACID CHAIN
# ===================================
def BuildMol(filename, sequence=None, Type=None):
    command = 'BuildMol '
    command += 'Filename=' + cstr(filename) + ','
    if (sequence != None): command += 'Sequence=' + cstr(sequence) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# BUILD SINGLE RESIDUE
# ====================
def BuildRes(name, psi=None, tau=None, center=None, isomer=None, useph=None):
    command = 'BuildRes '
    command += 'Name=' + cstr(name) + ','
    if (psi != None): command += 'Psi=' + cstr(psi) + ','
    if (tau != None): command += 'Tau=' + cstr(tau) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (isomer != None): command += 'Isomer=' + cstr(isomer) + ','
    if (useph != None): command += 'UsepH=' + cstr(useph) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# BUILD SINGLE RESIDUE
# ====================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def BuildRes2(name, alpha=None, beta=None, gamma=None, center=None):
    command = 'BuildRes '
    command += 'Name=' + cstr(name) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (beta != None): command += 'Beta=' + cstr(beta) + ','
    if (gamma != None): command += 'Gamma=' + cstr(gamma) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# BUILD MOLECULE FROM SMILES STRING
# =================================
def BuildSMILES(string, sort=None):
    command = 'BuildSMILES '
    command += 'String=' + cstr(string) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# BUILD SYMMETRY RELATED RESIDUES
# ===============================
def BuildSymRes(selection1):
    command = 'BuildSymRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# CALCULATE CAVITY VOLUMES (ALL OR SELECTED)
# ==========================================
def CaviVol(Type=None):
    command = 'CaviVol '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE CAVITY VOLUMES (ALL)
# ==============================
def CaviVolAll(Type=None):
    command = 'CaviVolAll '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE CAVITY VOLUMES (OBJECT)
# =================================
def CaviVolObj(selection1, Type=None):
    command = 'CaviVolObj '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE CAVITY VOLUMES (MOLECULE)
# ===================================
def CaviVolMol(selection1, Type=None):
    command = 'CaviVolMol '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE CAVITY VOLUMES (RESIDUE)
# ==================================
def CaviVolRes(selection1, Type=None):
    command = 'CaviVolRes '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE CAVITY VOLUMES (ATOM)
# ===============================
def CaviVolAtom(selection1, Type=None):
    command = 'CaviVolAtom '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CHANGE WORKING DIRECTORY
# ========================
def CD(noname1, onstartup=None):
    command = 'CD '
    command += cstr(noname1) + ','
    if (onstartup != None): command += 'OnStartUp=' + cstr(onstartup) + ','
    return (runretval(command[:-1], True))


# SET/GET SIMULATION CELL DIMENSIONS
# ==================================
def Cell(x=None, y=None, z=None, alpha=None, beta=None, gamma=None, center=None):
    command = 'Cell '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (beta != None): command += 'Beta=' + cstr(beta) + ','
    if (gamma != None): command += 'Gamma=' + cstr(gamma) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    return (runretval(command[:-1], True))


# SET/GET SIMULATION CELL DIMENSIONS
# ==================================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def CellAuto(extension=None, shape=None, selection1=None):
    command = 'Cell Auto,'
    if (extension != None): command += 'Extension=' + cstr(extension) + ','
    if (shape != None): command += 'Shape=' + cstr(shape) + ','
    if (selection1 != None): command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SET/GET SIMULATION CELL DIMENSIONS
# ==================================
# THIS IS ALTERNATIVE 3, WITH DIFFERENT PARAMETERS
def CellCrystal(selection1):
    command = 'Cell Crystal,'
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# CENTER ATOMS OR POLYGON MESHES (ALL OR SELECTED)
# ================================================
def Center(coordsys=None):
    command = 'Center '
    if (coordsys != None): command += 'CoordSys=' + cstr(coordsys) + ','
    return (runretval(command[:-1], True))


# CENTER ATOMS OR POLYGON MESHES (ALL)
# ====================================
def CenterAll(coordsys=None):
    command = 'CenterAll '
    if (coordsys != None): command += 'CoordSys=' + cstr(coordsys) + ','
    return (runretval(command[:-1], True))


# CENTER ATOMS OR POLYGON MESHES (OBJECT)
# =======================================
def CenterObj(selection1, coordsys=None):
    command = 'CenterObj '
    command += selstr(selection1) + ','
    if (coordsys != None): command += 'CoordSys=' + cstr(coordsys) + ','
    return (runretval(command[:-1], True))


# CENTER ATOMS OR POLYGON MESHES (MOLECULE)
# =========================================
def CenterMol(selection1, coordsys=None):
    command = 'CenterMol '
    command += selstr(selection1) + ','
    if (coordsys != None): command += 'CoordSys=' + cstr(coordsys) + ','
    return (runretval(command[:-1], True))


# CENTER ATOMS OR POLYGON MESHES (RESIDUE)
# ========================================
def CenterRes(selection1, coordsys=None):
    command = 'CenterRes '
    command += selstr(selection1) + ','
    if (coordsys != None): command += 'CoordSys=' + cstr(coordsys) + ','
    return (runretval(command[:-1], True))


# CENTER ATOMS OR POLYGON MESHES (ATOM)
# =====================================
def CenterAtom(selection1, coordsys=None):
    command = 'CenterAtom '
    command += selstr(selection1) + ','
    if (coordsys != None): command += 'CoordSys=' + cstr(coordsys) + ','
    return (runretval(command[:-1], True))


# SET/GET THE SUMMED UP CHARGE (ALL OR SELECTED)
# ==============================================
def Charge(e=None):
    command = 'Charge '
    if (e != None): command += 'e=' + cstr(e) + ','
    return (runretval(command[:-1], True))


# SET/GET THE SUMMED UP CHARGE (ALL)
# ==================================
def ChargeAll(e=None):
    command = 'ChargeAll '
    if (e != None): command += 'e=' + cstr(e) + ','
    return (runretval(command[:-1], True))


# SET/GET THE SUMMED UP CHARGE (OBJECT)
# =====================================
def ChargeObj(selection1, e=None):
    command = 'ChargeObj '
    command += selstr(selection1) + ','
    if (e != None): command += 'e=' + cstr(e) + ','
    return (runretval(command[:-1], True))


# SET/GET THE SUMMED UP CHARGE (MOLECULE)
# =======================================
def ChargeMol(selection1, e=None):
    command = 'ChargeMol '
    command += selstr(selection1) + ','
    if (e != None): command += 'e=' + cstr(e) + ','
    return (runretval(command[:-1], True))


# SET/GET THE SUMMED UP CHARGE (RESIDUE)
# ======================================
def ChargeRes(selection1, e=None):
    command = 'ChargeRes '
    command += selstr(selection1) + ','
    if (e != None): command += 'e=' + cstr(e) + ','
    return (runretval(command[:-1], True))


# SET/GET THE SUMMED UP CHARGE (ATOM)
# ===================================
def ChargeAtom(selection1, e=None):
    command = 'ChargeAtom '
    command += selstr(selection1) + ','
    if (e != None): command += 'e=' + cstr(e) + ','
    return (runretval(command[:-1], True))


# CHECK STRUCTURE QUALITY (ALL OR SELECTED)
# =========================================
def Check(Type, filename=None):
    command = 'Check '
    command += 'Type=' + cstr(Type) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# CHECK STRUCTURE QUALITY (ALL)
# =============================
def CheckAll(Type, filename=None):
    command = 'CheckAll '
    command += 'Type=' + cstr(Type) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# CHECK STRUCTURE QUALITY (OBJECT)
# ================================
def CheckObj(selection1, Type, filename=None):
    command = 'CheckObj '
    command += selstr(selection1) + ','
    command += 'Type=' + cstr(Type) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# CHECK STRUCTURE QUALITY (RESIDUE)
# =================================
def CheckRes(selection1, Type, filename=None):
    command = 'CheckRes '
    command += selstr(selection1) + ','
    command += 'Type=' + cstr(Type) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# CHECK STRUCTURE QUALITY (ATOM)
# ==============================
def CheckAtom(selection1, Type, filename=None):
    command = 'CheckAtom '
    command += selstr(selection1) + ','
    command += 'Type=' + cstr(Type) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# CLASSIFY RESTRAINTS (ALL OR SELECTED)
# =====================================
def ClassRest(Class, component, number, newclass):
    command = 'ClassRest '
    command += 'Class=' + cstr(Class) + ','
    command += 'Component=' + cstr(component) + ','
    command += 'Number=' + cstr(number) + ','
    command += 'NewClass=' + cstr(newclass) + ','
    return (runretval(command[:-1], True))


# CLASSIFY RESTRAINTS (ALL)
# =========================
def ClassRestAll(Class, component, number, newclass):
    command = 'ClassRestAll '
    command += 'Class=' + cstr(Class) + ','
    command += 'Component=' + cstr(component) + ','
    command += 'Number=' + cstr(number) + ','
    command += 'NewClass=' + cstr(newclass) + ','
    return (runretval(command[:-1], True))


# CLASSIFY RESTRAINTS (OBJECT)
# ============================
def ClassRestObj(selection1, Class, component, number, newclass):
    command = 'ClassRestObj '
    command += selstr(selection1) + ','
    command += 'Class=' + cstr(Class) + ','
    command += 'Component=' + cstr(component) + ','
    command += 'Number=' + cstr(number) + ','
    command += 'NewClass=' + cstr(newclass) + ','
    return (runretval(command[:-1], True))


# CLASSIFY RESTRAINTS (MOLECULE)
# ==============================
def ClassRestMol(selection1, Class, component, number, newclass):
    command = 'ClassRestMol '
    command += selstr(selection1) + ','
    command += 'Class=' + cstr(Class) + ','
    command += 'Component=' + cstr(component) + ','
    command += 'Number=' + cstr(number) + ','
    command += 'NewClass=' + cstr(newclass) + ','
    return (runretval(command[:-1], True))


# CLASSIFY RESTRAINTS (RESIDUE)
# =============================
def ClassRestRes(selection1, Class, component, number, newclass):
    command = 'ClassRestRes '
    command += selstr(selection1) + ','
    command += 'Class=' + cstr(Class) + ','
    command += 'Component=' + cstr(component) + ','
    command += 'Number=' + cstr(number) + ','
    command += 'NewClass=' + cstr(newclass) + ','
    return (runretval(command[:-1], True))


# CLASSIFY RESTRAINTS (ATOM)
# ==========================
def ClassRestAtom(selection1, Class, component, number, newclass):
    command = 'ClassRestAtom '
    command += selstr(selection1) + ','
    command += 'Class=' + cstr(Class) + ','
    command += 'Component=' + cstr(component) + ','
    command += 'Number=' + cstr(number) + ','
    command += 'NewClass=' + cstr(newclass) + ','
    return (runretval(command[:-1], True))


# CLEAN OBJECTS FOR MOLECULAR DYNAMICS SIMULATION (ALL OR SELECTED)
# =================================================================
def Clean(skip=None):
    command = 'Clean '
    if (skip != None): command += 'Skip=' + cstr(skip) + ','
    return (runretval(command[:-1], True))


# CLEAN OBJECTS FOR MOLECULAR DYNAMICS SIMULATION (ALL)
# =====================================================
def CleanAll(skip=None):
    command = 'CleanAll '
    if (skip != None): command += 'Skip=' + cstr(skip) + ','
    return (runretval(command[:-1], True))


# CLEAN OBJECTS FOR MOLECULAR DYNAMICS SIMULATION (OBJECT)
# ========================================================
def CleanObj(selection1, skip=None):
    command = 'CleanObj '
    command += selstr(selection1) + ','
    if (skip != None): command += 'Skip=' + cstr(skip) + ','
    return (runretval(command[:-1], True))


# CLEAR SCENE
# ===========
def Clear():
    command = 'Clear '
    return (runretval(command[:-1], True))


# COLOR BONDS
# ===========
def ColorBonds(color):
    command = 'ColorBonds '
    command += 'Color=' + cstr(color) + ','
    return (runretval(command[:-1], True))


# COLOR BACKGROUND
# ================
def ColorBG(topleft, bottomleft=None, topright=None, bottomright=None):
    command = 'ColorBG '
    command += 'TopLeft=' + cstr(topleft) + ','
    if (bottomleft != None): command += 'BottomLeft=' + cstr(bottomleft) + ','
    if (topright != None): command += 'TopRight=' + cstr(topright) + ','
    if (bottomright != None): command += 'BottomRight=' + cstr(bottomright) + ','
    return (runretval(command[:-1], True))


# SET OVERALL OBJECT INSTANCE COLORS AT A FAR DISTANCE (ALL OR SELECTED)
# ======================================================================
def ColorFar(Type, first, second=None):
    command = 'ColorFar '
    command += 'Type=' + cstr(Type) + ','
    command += 'First=' + cstr(first) + ','
    if (second != None): command += 'Second=' + cstr(second) + ','
    return (runretval(command[:-1], True))


# SET OVERALL OBJECT INSTANCE COLORS AT A FAR DISTANCE (ALL)
# ==========================================================
def ColorFarAll(Type, first, second=None):
    command = 'ColorFarAll '
    command += 'Type=' + cstr(Type) + ','
    command += 'First=' + cstr(first) + ','
    if (second != None): command += 'Second=' + cstr(second) + ','
    return (runretval(command[:-1], True))


# SET OVERALL OBJECT INSTANCE COLORS AT A FAR DISTANCE (OBJECT)
# =============================================================
def ColorFarObj(selection1, Type, first, second=None):
    command = 'ColorFarObj '
    command += selstr(selection1) + ','
    command += 'Type=' + cstr(Type) + ','
    command += 'First=' + cstr(first) + ','
    if (second != None): command += 'Second=' + cstr(second) + ','
    return (runretval(command[:-1], True))


# SET OVERALL OBJECT INSTANCE COLORS AT A FAR DISTANCE (MOLECULE)
# ===============================================================
def ColorFarMol(selection1, Type, first, second=None):
    command = 'ColorFarMol '
    command += selstr(selection1) + ','
    command += 'Type=' + cstr(Type) + ','
    command += 'First=' + cstr(first) + ','
    if (second != None): command += 'Second=' + cstr(second) + ','
    return (runretval(command[:-1], True))


# SET OVERALL OBJECT INSTANCE COLORS AT A FAR DISTANCE (RESIDUE)
# ==============================================================
def ColorFarRes(selection1, Type, first, second=None):
    command = 'ColorFarRes '
    command += selstr(selection1) + ','
    command += 'Type=' + cstr(Type) + ','
    command += 'First=' + cstr(first) + ','
    if (second != None): command += 'Second=' + cstr(second) + ','
    return (runretval(command[:-1], True))


# SET OVERALL OBJECT INSTANCE COLORS AT A FAR DISTANCE (ATOM)
# ===========================================================
def ColorFarAtom(selection1, Type, first, second=None):
    command = 'ColorFarAtom '
    command += selstr(selection1) + ','
    command += 'Type=' + cstr(Type) + ','
    command += 'First=' + cstr(first) + ','
    if (second != None): command += 'Second=' + cstr(second) + ','
    return (runretval(command[:-1], True))


# COLOR FOG
# =========
def ColorFog(color):
    command = 'ColorFog '
    command += 'Color=' + cstr(color) + ','
    return (runretval(command[:-1], True))


# COLOR HYDROGEN BONDS
# ====================
def ColorHBo(color=None, alpha=None, inherit=None):
    command = 'ColorHBo '
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (inherit != None): command += 'Inherit=' + cstr(inherit) + ','
    return (runretval(command[:-1], True))


# COLOR POLYGON MESH
# ==================
def ColorMesh(selection1, color=None):
    command = 'ColorMesh '
    command += selstr(selection1) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    return (runretval(command[:-1], True))


# SET/GET DEFAULT COLOR PARAMETERS
# ================================
def ColorPar(scheme, name=None, color=None, value=None):
    command = 'ColorPar '
    command += 'Scheme=' + cstr(scheme) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (value != None): command += 'Value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# COLOR SURFACE (ALL OR SELECTED)
# ===============================
def ColorSurf(Type=None, outcol=None, outalpha=None, incol=None, inalpha=None, specular=None):
    command = 'ColorSurf '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# COLOR SURFACE (ALL)
# ===================
def ColorSurfAll(Type=None, outcol=None, outalpha=None, incol=None, inalpha=None, specular=None):
    command = 'ColorSurfAll '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# COLOR SURFACE (OBJECT)
# ======================
def ColorSurfObj(selection1, Type=None, outcol=None, outalpha=None, incol=None, inalpha=None, specular=None):
    command = 'ColorSurfObj '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM COLORS (ALL OR SELECTED)
# =====================================
def Color(first=None, second=None, segments=None, mapcons=None, filename=None, consmin=None):
    command = 'Color '
    if (first != None): command += 'first=' + cstr(first) + ','
    if (second != None): command += 'second=' + cstr(second) + ','
    if (segments != None): command += 'Segments=' + cstr(segments) + ','
    if (mapcons != None): command += 'MapCons=' + cstr(mapcons) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    if (consmin != None): command += 'ConsMin=' + cstr(consmin) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM COLORS (ALL OR SELECTED)
# =====================================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def ColorFile(filename=None):
    command = 'Color File,'
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM COLORS (ALL)
# =========================
def ColorAll(first=None, second=None, segments=None, mapcons=None, filename=None, consmin=None):
    command = 'ColorAll '
    if (first != None): command += 'first=' + cstr(first) + ','
    if (second != None): command += 'second=' + cstr(second) + ','
    if (segments != None): command += 'Segments=' + cstr(segments) + ','
    if (mapcons != None): command += 'MapCons=' + cstr(mapcons) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    if (consmin != None): command += 'ConsMin=' + cstr(consmin) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM COLORS (ALL)
# =========================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def ColorAllFile(filename=None):
    command = 'ColorAll File,'
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM COLORS (OBJECT)
# ============================
def ColorObj(selection1, first=None, second=None, segments=None, mapcons=None, filename=None, consmin=None):
    command = 'ColorObj '
    command += selstr(selection1) + ','
    if (first != None): command += 'first=' + cstr(first) + ','
    if (second != None): command += 'second=' + cstr(second) + ','
    if (segments != None): command += 'Segments=' + cstr(segments) + ','
    if (mapcons != None): command += 'MapCons=' + cstr(mapcons) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    if (consmin != None): command += 'ConsMin=' + cstr(consmin) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM COLORS (OBJECT)
# ============================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def ColorObjFile(noname1=None, filename=None):
    command = 'ColorObj File,'
    if (noname1 != None): command += cstr(noname1) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM COLORS (MOLECULE)
# ==============================
def ColorMol(selection1, first=None, second=None, segments=None, mapcons=None, filename=None, consmin=None):
    command = 'ColorMol '
    command += selstr(selection1) + ','
    if (first != None): command += 'first=' + cstr(first) + ','
    if (second != None): command += 'second=' + cstr(second) + ','
    if (segments != None): command += 'Segments=' + cstr(segments) + ','
    if (mapcons != None): command += 'MapCons=' + cstr(mapcons) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    if (consmin != None): command += 'ConsMin=' + cstr(consmin) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM COLORS (MOLECULE)
# ==============================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def ColorMolFile(noname1=None, filename=None):
    command = 'ColorMol File,'
    if (noname1 != None): command += cstr(noname1) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM COLORS (RESIDUE)
# =============================
def ColorRes(selection1, first=None, second=None, segments=None, mapcons=None, filename=None, consmin=None):
    command = 'ColorRes '
    command += selstr(selection1) + ','
    if (first != None): command += 'first=' + cstr(first) + ','
    if (second != None): command += 'second=' + cstr(second) + ','
    if (segments != None): command += 'Segments=' + cstr(segments) + ','
    if (mapcons != None): command += 'MapCons=' + cstr(mapcons) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    if (consmin != None): command += 'ConsMin=' + cstr(consmin) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM COLORS (RESIDUE)
# =============================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def ColorResFile(noname1=None, filename=None):
    command = 'ColorRes File,'
    if (noname1 != None): command += cstr(noname1) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM COLORS (ATOM)
# ==========================
def ColorAtom(selection1, first=None, second=None, segments=None, mapcons=None, filename=None, consmin=None):
    command = 'ColorAtom '
    command += selstr(selection1) + ','
    if (first != None): command += 'first=' + cstr(first) + ','
    if (second != None): command += 'second=' + cstr(second) + ','
    if (segments != None): command += 'Segments=' + cstr(segments) + ','
    if (mapcons != None): command += 'MapCons=' + cstr(mapcons) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    if (consmin != None): command += 'ConsMin=' + cstr(consmin) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM COLORS (ATOM)
# ==========================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def ColorAtomFile(noname1=None, filename=None):
    command = 'ColorAtom File,'
    if (noname1 != None): command += cstr(noname1) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# COMPARE BONDS
# =============
def CompareBond(selection1, selection2, selection3, selection4, checkmol=None):
    command = 'CompareBond '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += selstr(selection3) + ','
    command += selstr(selection4) + ','
    if (checkmol != None): command += 'CheckMol=' + cstr(checkmol) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# COMPARE ATOMS AND RESIDUES (RESIDUE)
# ====================================
def CompareRes(selection1, selection2, checkmol=None):
    command = 'CompareRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (checkmol != None): command += 'CheckMol=' + cstr(checkmol) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# COMPARE ATOMS AND RESIDUES (ATOM)
# =================================
def CompareAtom(selection1, selection2, checkmol=None):
    command = 'CompareAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (checkmol != None): command += 'CheckMol=' + cstr(checkmol) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SET/GET COMPOUND NAMES OF MOLECULES
# ===================================
def CompoundMol(selection1, name=None):
    command = 'CompoundMol '
    command += selstr(selection1) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# SET/GET CONSOLE MODE
# ====================
def Console(flag=None):
    command = 'Console '
    if (flag != None): command += 'Flag=' + cstr(flag) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SET CONSOLE PARAMETERS
# ======================
def ConsolePar(font=None, height=None, antialias=None):
    command = 'ConsolePar '
    if (font != None): command += 'Font=' + cstr(font) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (antialias != None): command += 'Antialias=' + cstr(antialias) + ','
    return (runretval(command[:-1], True))


# SET/GET COORDINATE SYSTEM
# =========================
def CoordSys(handed=None):
    command = 'CoordSys '
    if (handed != None): command += 'handed=' + cstr(handed) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# CALCULATE CONTACT SURFACE AREAS (OBJECT)
# ========================================
def ConSurfObj(selection1, selection2, cutoff=None, subtract=None, Type=None, unit=None):
    command = 'ConSurfObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE CONTACT SURFACE AREAS (MOLECULE)
# ==========================================
def ConSurfMol(selection1, selection2, cutoff=None, subtract=None, Type=None, unit=None):
    command = 'ConSurfMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE CONTACT SURFACE AREAS (RESIDUE)
# =========================================
def ConSurfRes(selection1, selection2, cutoff=None, subtract=None, Type=None, unit=None):
    command = 'ConSurfRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE CONTACT SURFACE AREAS (ATOM)
# ======================================
def ConSurfAtom(selection1, selection2, cutoff=None, subtract=None, Type=None, unit=None):
    command = 'ConSurfAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# COPY FILE
# =========
def CopyFile(srcfilename=None, dstfilename=None, append=None):
    command = 'CopyFile '
    if (srcfilename != None): command += 'SrcFilename=' + cstr(srcfilename) + ','
    if (dstfilename != None): command += 'DstFilename=' + cstr(dstfilename) + ','
    if (append != None): command += 'append=' + cstr(append) + ','
    return (runretval(command[:-1], True))


# COPY VISUALIZATION STYLE BETWEEN OBJECTS
# ========================================
def CopyStyleObj(selection1, selection2, match=None):
    command = 'CopyStyleObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    return (runretval(command[:-1], True))


# CORRECT CIS-PEPTIDE BONDS DURING A SIMULATION
# =============================================
def CorrectCis(Type, old=None, proline=None):
    command = 'CorrectCis '
    command += 'Type=' + cstr(Type) + ','
    if (old != None): command += 'Old=' + cstr(old) + ','
    if (proline != None): command += 'Proline=' + cstr(proline) + ','
    return (runretval(command[:-1], True))


# CORRECT NAMING CONVENTIONS DURING A SIMULATION
# ==============================================
def CorrectConv(flag):
    command = 'CorrectConv '
    command += 'Flag=' + cstr(flag) + ','
    return (runretval(command[:-1], True))


# CORRECT SOLUTE DRIFT DURING A SIMULATION
# ========================================
def CorrectDrift(flag):
    command = 'CorrectDrift '
    command += 'Flag=' + cstr(flag) + ','
    return (runretval(command[:-1], True))


# CORRECT WRONG ISOMERS DURING A SIMULATION
# =========================================
def CorrectIso(Type, old=None):
    command = 'CorrectIso '
    command += 'Type=' + cstr(Type) + ','
    if (old != None): command += 'Old=' + cstr(old) + ','
    return (runretval(command[:-1], True))


# CORRECT KNOTS AND OTHER ENTANGLEMENTS DURING A SIMULATION
# =========================================================
def CorrectKnots(flag):
    command = 'CorrectKnots '
    command += 'Flag=' + cstr(flag) + ','
    return (runretval(command[:-1], True))


# COUNT BONDS
# ===========
def CountBond(selection1, selection2, Type=None):
    command = 'CountBond '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# COUNT CONTACTS (OBJECT)
# =======================
def CountConObj(selection1, selection2, cutoff=None, subtract=None, energy=None, exclude=None, occluded=None,
                unit=None):
    command = 'CountConObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (energy != None): command += 'Energy=' + cstr(energy) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# COUNT CONTACTS (MOLECULE)
# =========================
def CountConMol(selection1, selection2, cutoff=None, subtract=None, energy=None, exclude=None, occluded=None,
                unit=None):
    command = 'CountConMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (energy != None): command += 'Energy=' + cstr(energy) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# COUNT CONTACTS (RESIDUE)
# ========================
def CountConRes(selection1, selection2, cutoff=None, subtract=None, energy=None, exclude=None, occluded=None,
                unit=None):
    command = 'CountConRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (energy != None): command += 'Energy=' + cstr(energy) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# COUNT CONTACTS (ATOM)
# =====================
def CountConAtom(selection1, selection2, cutoff=None, subtract=None, energy=None, exclude=None, occluded=None,
                 unit=None):
    command = 'CountConAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (energy != None): command += 'Energy=' + cstr(energy) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# COUNT SELECTED UNITS (OBJECT)
# =============================
def CountObj(selection1):
    command = 'CountObj '
    command += selstr(selection1) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# COUNT SELECTED UNITS (MOLECULE)
# ===============================
def CountMol(selection1):
    command = 'CountMol '
    command += selstr(selection1) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# COUNT SELECTED UNITS (RESIDUE)
# ==============================
def CountRes(selection1):
    command = 'CountRes '
    command += selstr(selection1) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# COUNT SELECTED UNITS (ATOM)
# ===========================
def CountAtom(selection1):
    command = 'CountAtom '
    command += selstr(selection1) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# CRYSTALLIZE OBJECTS TO FILL THE UNIT CELL (ALL OR SELECTED)
# ===========================================================
def Crystallize(center=None):
    command = 'Crystallize '
    if (center != None): command += 'Center=' + cstr(center) + ','
    return (runretval(command[:-1], True))


# CRYSTALLIZE OBJECTS TO FILL THE UNIT CELL (ALL)
# ===============================================
def CrystallizeAll(center=None):
    command = 'CrystallizeAll '
    if (center != None): command += 'Center=' + cstr(center) + ','
    return (runretval(command[:-1], True))


# CRYSTALLIZE OBJECTS TO FILL THE UNIT CELL (OBJECT)
# ==================================================
def CrystallizeObj(selection1, center=None):
    command = 'CrystallizeObj '
    command += selstr(selection1) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    return (runretval(command[:-1], True))


# SET FORCE CUTOFF DISTANCE
# =========================
def Cutoff(distance):
    command = 'Cutoff '
    command += 'Distance=' + cstr(distance) + ','
    return (runretval(command[:-1], True))


# CUT OBJECTS OPEN (ALL OR SELECTED)
# ==================================
def Cut(secstr=None):
    command = 'Cut '
    if (secstr != None): command += 'SecStr=' + cstr(secstr) + ','
    return (runretval(command[:-1], True))


# CUT OBJECTS OPEN (ALL)
# ======================
def CutAll(secstr=None):
    command = 'CutAll '
    if (secstr != None): command += 'SecStr=' + cstr(secstr) + ','
    return (runretval(command[:-1], True))


# CUT OBJECTS OPEN (OBJECT)
# =========================
def CutObj(selection1, secstr=None):
    command = 'CutObj '
    command += selstr(selection1) + ','
    if (secstr != None): command += 'SecStr=' + cstr(secstr) + ','
    return (runretval(command[:-1], True))


# CALCULATE CYSTEINE BRIDGE ENERGIES
# ==================================
def CysEnergyRes(selection1, selection2):
    command = 'CysEnergyRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    return (runretval(command[:-1], True))


# CALCULATE DYNAMIC CROSS-CORRELATION MATRIX
# ==========================================
def DCCM():
    command = 'DCCM '
    return (runretval(command[:-1], True))


# CONVERT 3D TO 2D COORDINATES, CREATING A FLAT STRUCTURAL FORMULA (ALL OR SELECTED)
# ==================================================================================
def Deflate(formulacol=None):
    command = 'Deflate '
    if (formulacol != None): command += 'FormulaCol=' + cstr(formulacol) + ','
    return (runretval(command[:-1], True))


# CONVERT 3D TO 2D COORDINATES, CREATING A FLAT STRUCTURAL FORMULA (ALL)
# ======================================================================
def DeflateAll(formulacol=None):
    command = 'DeflateAll '
    if (formulacol != None): command += 'FormulaCol=' + cstr(formulacol) + ','
    return (runretval(command[:-1], True))


# CONVERT 3D TO 2D COORDINATES, CREATING A FLAT STRUCTURAL FORMULA (OBJECT)
# =========================================================================
def DeflateObj(selection1, formulacol=None):
    command = 'DeflateObj '
    command += selstr(selection1) + ','
    if (formulacol != None): command += 'FormulaCol=' + cstr(formulacol) + ','
    return (runretval(command[:-1], True))


# CONVERT 3D TO 2D COORDINATES, CREATING A FLAT STRUCTURAL FORMULA (MOLECULE)
# ===========================================================================
def DeflateMol(selection1, formulacol=None):
    command = 'DeflateMol '
    command += selstr(selection1) + ','
    if (formulacol != None): command += 'FormulaCol=' + cstr(formulacol) + ','
    return (runretval(command[:-1], True))


# CONVERT 3D TO 2D COORDINATES, CREATING A FLAT STRUCTURAL FORMULA (RESIDUE)
# ==========================================================================
def DeflateRes(selection1, formulacol=None):
    command = 'DeflateRes '
    command += selstr(selection1) + ','
    if (formulacol != None): command += 'FormulaCol=' + cstr(formulacol) + ','
    return (runretval(command[:-1], True))


# CONVERT 3D TO 2D COORDINATES, CREATING A FLAT STRUCTURAL FORMULA (ATOM)
# =======================================================================
def DeflateAtom(selection1, formulacol=None):
    command = 'DeflateAtom '
    command += selstr(selection1) + ','
    if (formulacol != None): command += 'FormulaCol=' + cstr(formulacol) + ','
    return (runretval(command[:-1], True))


# GET DEGREES OF FREEDOM
# ======================
def DegFreedom():
    command = 'DegFreedom '
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# DELETE COVALENT BONDS
# =====================
def DelBond(selection1, selection2, lenmin=None):
    command = 'DelBond '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (lenmin != None): command += 'LenMin=' + cstr(lenmin) + ','
    return (runretval(command[:-1], True))


# DELETE FILE
# ===========
def DelFile(filename):
    command = 'DelFile '
    command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# DELETE ALL HYDROGENS (ALL OR SELECTED)
# ======================================
def DelHyd():
    command = 'DelHyd '
    return (runretval(command[:-1], True))


# DELETE ALL HYDROGENS (ALL)
# ==========================
def DelHydAll():
    command = 'DelHydAll '
    return (runretval(command[:-1], True))


# DELETE ALL HYDROGENS (OBJECT)
# =============================
def DelHydObj(selection1):
    command = 'DelHydObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DELETE IMAGES
# =============
def DelImage(selection1):
    command = 'DelImage '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DELETE RESTRAINTS (ALL OR SELECTED)
# ===================================
def DelRest(Class=None, component=None, number=None):
    command = 'DelRest '
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    if (number != None): command += 'Number=' + cstr(number) + ','
    return (runretval(command[:-1], True))


# DELETE RESTRAINTS (ALL)
# =======================
def DelRestAll(Class=None, component=None, number=None):
    command = 'DelRestAll '
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    if (number != None): command += 'Number=' + cstr(number) + ','
    return (runretval(command[:-1], True))


# DELETE RESTRAINTS (OBJECT)
# ==========================
def DelRestObj(selection1, Class=None, component=None, number=None):
    command = 'DelRestObj '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    if (number != None): command += 'Number=' + cstr(number) + ','
    return (runretval(command[:-1], True))


# DELETE RESTRAINTS (MOLECULE)
# ============================
def DelRestMol(selection1, Class=None, component=None, number=None):
    command = 'DelRestMol '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    if (number != None): command += 'Number=' + cstr(number) + ','
    return (runretval(command[:-1], True))


# DELETE RESTRAINTS (RESIDUE)
# ===========================
def DelRestRes(selection1, Class=None, component=None, number=None):
    command = 'DelRestRes '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    if (number != None): command += 'Number=' + cstr(number) + ','
    return (runretval(command[:-1], True))


# DELETE RESTRAINTS (ATOM)
# ========================
def DelRestAtom(selection1, Class=None, component=None, number=None):
    command = 'DelRestAtom '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    if (number != None): command += 'Number=' + cstr(number) + ','
    return (runretval(command[:-1], True))


# DELETE TABLES
# =============
def DelTab(selection1):
    command = 'DelTab '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DELETE VIEW
# ===========
def DelView(selection1):
    command = 'DelView '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DELETE ALL WATER MOLECULES (ALL OR SELECTED)
# ============================================
def DelWater():
    command = 'DelWater '
    return (runretval(command[:-1], True))


# DELETE ALL WATER MOLECULES (ALL)
# ================================
def DelWaterAll():
    command = 'DelWaterAll '
    return (runretval(command[:-1], True))


# DELETE ALL WATER MOLECULES (OBJECT)
# ===================================
def DelWaterObj(selection1):
    command = 'DelWaterObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DELETE YANACONDA VARIABLE
# =========================
def DelVar(name, renumber=None, matchnum=None):
    command = 'DelVar '
    command += 'Name=' + cstr(name) + ','
    if (renumber != None): command += 'Renumber=' + cstr(renumber) + ','
    if (matchnum != None): command += 'MatchNum=' + cstr(matchnum) + ','
    return (runretval(command[:-1], True))


# DELETE ATOMS AND OBJECTS (ALL OR SELECTED)
# ==========================================
def Del(center=None):
    command = 'Del '
    if (center != None): command += 'Center=' + cstr(center) + ','
    return (runretval(command[:-1], True))


# DELETE ATOMS AND OBJECTS (ALL)
# ==============================
def DelAll(center=None):
    command = 'DelAll '
    if (center != None): command += 'Center=' + cstr(center) + ','
    return (runretval(command[:-1], True))


# DELETE ATOMS AND OBJECTS (OBJECT)
# =================================
def DelObj(selection1, center=None):
    command = 'DelObj '
    command += selstr(selection1) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    return (runretval(command[:-1], True))


# DELETE ATOMS AND OBJECTS (MOLECULE)
# ===================================
def DelMol(selection1, center=None):
    command = 'DelMol '
    command += selstr(selection1) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    return (runretval(command[:-1], True))


# DELETE ATOMS AND OBJECTS (RESIDUE)
# ==================================
def DelRes(selection1, center=None):
    command = 'DelRes '
    command += selstr(selection1) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    return (runretval(command[:-1], True))


# DELETE ATOMS AND OBJECTS (ATOM)
# ===============================
def DelAtom(selection1, center=None):
    command = 'DelAtom '
    command += selstr(selection1) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    return (runretval(command[:-1], True))


# SET/GET DIHEDRAL ANGLE BETWEEN ATOMS
# ====================================
def Dihedral(selection1, selection2, selection3, selection4, bound=None, set=None):
    command = 'Dihedral '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += selstr(selection3) + ','
    command += selstr(selection4) + ','
    if (bound != None): command += 'bound=' + cstr(bound) + ','
    if (set != None): command += 'set=' + cstr(set) + ','
    return (runretval(command[:-1], True))


# CALCULATE ELECTRIC DIPOLE MOMENTS (OBJECT)
# ==========================================
def DipoleObj(selection1):
    command = 'DipoleObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# CALCULATE ELECTRIC DIPOLE MOMENTS (MOLECULE)
# ============================================
def DipoleMol(selection1):
    command = 'DipoleMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# CALCULATE ELECTRIC DIPOLE MOMENTS (RESIDUE)
# ===========================================
def DipoleRes(selection1):
    command = 'DipoleRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# CALCULATE ELECTRIC DIPOLE MOMENTS (ATOM)
# ========================================
def DipoleAtom(selection1):
    command = 'DipoleAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SET/GET DISTANCE BETWEEN ATOMS
# ==============================
def Distance(selection1, selection2, bound=None, set=None):
    command = 'Distance '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (bound != None): command += 'bound=' + cstr(bound) + ','
    if (set != None): command += 'set=' + cstr(set) + ','
    return (runretval(command[:-1], True))


# DOWNLOAD FILE FROM INTERNET
# ===========================
def Download(url, filename):
    command = 'Download '
    command += 'URL=' + cstr(url) + ','
    command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# DRAW A LINE
# ===========
def DrawLine(startx, starty, endx=None, endy=None, color=None, width=None, round=None):
    command = 'DrawLine '
    command += 'StartX=' + cstr(startx) + ','
    command += 'StartY=' + cstr(starty) + ','
    if (endx != None): command += 'EndX=' + cstr(endx) + ','
    if (endy != None): command += 'EndY=' + cstr(endy) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (width != None): command += 'Width=' + cstr(width) + ','
    if (round != None): command += 'Round=' + cstr(round) + ','
    return (runretval(command[:-1], True))


# DUPLICATE VIEW
# ==============
def DuplicateView(selection1, name, hud=None):
    command = 'DuplicateView '
    command += selstr(selection1) + ','
    command += 'Name=' + cstr(name) + ','
    if (hud != None): command += 'HUD=' + cstr(hud) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# DUPLICATE OBJECTS (ALL OR SELECTED)
# ===================================
def Duplicate():
    command = 'Duplicate '
    return (runretval(command[:-1], True))


# DUPLICATE OBJECTS (ALL)
# =======================
def DuplicateAll():
    command = 'DuplicateAll '
    return (runretval(command[:-1], True))


# DUPLICATE OBJECTS (OBJECT)
# ==========================
def DuplicateObj(selection1):
    command = 'DuplicateObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DUPLICATE OBJECTS (MOLECULE)
# ============================
def DuplicateMol(selection1):
    command = 'DuplicateMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DUPLICATE OBJECTS (RESIDUE)
# ===========================
def DuplicateRes(selection1):
    command = 'DuplicateRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DUPLICATE OBJECTS (ATOM)
# ========================
def DuplicateAtom(selection1):
    command = 'DuplicateAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# GET CHEMICAL ELEMENT
# ====================
def ElementAtom(selection1):
    command = 'ElementAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SET ENERGY UNIT
# ===============
def EnergyUnit(name):
    command = 'EnergyUnit '
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# CALCULATE FORCE FIELD ENERGIES (ALL OR SELECTED)
# ================================================
def Energy(component, *arglist2):
    command = 'Energy '
    command += 'Component=' + cstr(component) + ','
    # ANY NUMBER OF VARIABLE ARGUMENTS CAN FOLLOW
    for arglist in arglist2:
        if (type(arglist) != type([])): arglist = [arglist]
        for arg in arglist:
            command += cstr(arg, quoted=(type(arg) != type(1) and type(arg) != type(1.))) + ','
    return (runretval(command[:-1], True))


# CALCULATE FORCE FIELD ENERGIES (ALL)
# ====================================
def EnergyAll(component, *arglist2):
    command = 'EnergyAll '
    command += 'Component=' + cstr(component) + ','
    # ANY NUMBER OF VARIABLE ARGUMENTS CAN FOLLOW
    for arglist in arglist2:
        if (type(arglist) != type([])): arglist = [arglist]
        for arg in arglist:
            command += cstr(arg, quoted=(type(arg) != type(1) and type(arg) != type(1.))) + ','
    return (runretval(command[:-1], True))


# CALCULATE FORCE FIELD ENERGIES (OBJECT)
# =======================================
def EnergyObj(selection1, component, *arglist2):
    command = 'EnergyObj '
    command += selstr(selection1) + ','
    command += 'Component=' + cstr(component) + ','
    # ANY NUMBER OF VARIABLE ARGUMENTS CAN FOLLOW
    for arglist in arglist2:
        if (type(arglist) != type([])): arglist = [arglist]
        for arg in arglist:
            command += cstr(arg, quoted=(type(arg) != type(1) and type(arg) != type(1.))) + ','
    return (runretval(command[:-1], True))


# CALCULATE FORCE FIELD ENERGIES (MOLECULE)
# =========================================
def EnergyMol(selection1, component, *arglist2):
    command = 'EnergyMol '
    command += selstr(selection1) + ','
    command += 'Component=' + cstr(component) + ','
    # ANY NUMBER OF VARIABLE ARGUMENTS CAN FOLLOW
    for arglist in arglist2:
        if (type(arglist) != type([])): arglist = [arglist]
        for arg in arglist:
            command += cstr(arg, quoted=(type(arg) != type(1) and type(arg) != type(1.))) + ','
    return (runretval(command[:-1], True))


# CALCULATE FORCE FIELD ENERGIES (RESIDUE)
# ========================================
def EnergyRes(selection1, component, *arglist2):
    command = 'EnergyRes '
    command += selstr(selection1) + ','
    command += 'Component=' + cstr(component) + ','
    # ANY NUMBER OF VARIABLE ARGUMENTS CAN FOLLOW
    for arglist in arglist2:
        if (type(arglist) != type([])): arglist = [arglist]
        for arg in arglist:
            command += cstr(arg, quoted=(type(arg) != type(1) and type(arg) != type(1.))) + ','
    return (runretval(command[:-1], True))


# CALCULATE FORCE FIELD ENERGIES (ATOM)
# =====================================
def EnergyAtom(selection1, component, *arglist2):
    command = 'EnergyAtom '
    command += selstr(selection1) + ','
    command += 'Component=' + cstr(component) + ','
    # ANY NUMBER OF VARIABLE ARGUMENTS CAN FOLLOW
    for arglist in arglist2:
        if (type(arglist) != type([])): arglist = [arglist]
        for arg in arglist:
            command += cstr(arg, quoted=(type(arg) != type(1) and type(arg) != type(1.))) + ','
    return (runretval(command[:-1], True))


# CHOOSE AND CONTROL EXPERIMENTS
# ==============================
def Experiment(noname1):
    command = 'Experiment '
    command += cstr(noname1) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# CHOOSE AND CONTROL EXPERIMENTS
# ==============================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def ExperimentMinimization(convergence=None):
    command = 'Experiment Minimization\n'
    if (convergence != None): command += '  convergence ' + cstr(convergence) + '\n'
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# CHOOSE AND CONTROL EXPERIMENTS
# ==============================
# THIS IS ALTERNATIVE 3, WITH DIFFERENT PARAMETERS
def ExperimentNeutralization(waterdensity=None, nacl=None, ph=None, pkafile=None, speed=None, ions=None):
    command = 'Experiment Neutralization\n'
    if (waterdensity != None): command += '  waterdensity ' + cstr(waterdensity) + '\n'
    if (nacl != None): command += '  nacl ' + cstr(nacl) + '\n'
    if (ph != None): command += '  ph ' + cstr(ph) + '\n'
    if (pkafile != None): command += '  pkafile ' + cstr(pkafile) + '\n'
    if (speed != None): command += '  speed ' + cstr(speed) + '\n'
    if (ions != None): command += '  ions ' + cstr(ions) + '\n'
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# CHOOSE AND CONTROL EXPERIMENTS
# ==============================
# THIS IS ALTERNATIVE 4, WITH DIFFERENT PARAMETERS
def ExperimentMorphing(startobj=None, endobj=None, structures=None, structurefile=None, morphforce=None):
    command = 'Experiment Morphing\n'
    if (startobj != None): command += '  startobj ' + cstr(startobj) + '\n'
    if (endobj != None): command += '  endobj ' + cstr(endobj) + '\n'
    if (structures != None): command += '  structures ' + cstr(structures) + '\n'
    if (structurefile != None): command += '  structurefile ' + cstr(structurefile) + '\n'
    if (morphforce != None): command += '  morphforce ' + cstr(morphforce) + '\n'
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# CHOOSE AND CONTROL EXPERIMENTS
# ==============================
# THIS IS ALTERNATIVE 5, WITH DIFFERENT PARAMETERS
def ExperimentDocking(method=None, ligandobj=None, receptorobj=None, runs=None, clusterrmsd=None, resultfile=None,
                      tmpfileid=None, gridparlist=None, dockparlist=None, setuponly=None):
    command = 'Experiment Docking\n'
    if (method != None): command += '  method ' + cstr(method) + '\n'
    if (ligandobj != None): command += '  ligandobj ' + cstr(ligandobj) + '\n'
    if (receptorobj != None): command += '  receptorobj ' + cstr(receptorobj) + '\n'
    if (runs != None): command += '  runs ' + cstr(runs) + '\n'
    if (clusterrmsd != None): command += '  clusterrmsd ' + cstr(clusterrmsd) + '\n'
    if (resultfile != None): command += '  resultfile ' + cstr(resultfile) + '\n'
    if (tmpfileid != None): command += '  tmpfileid ' + cstr(tmpfileid) + '\n'
    if (gridparlist != None):
        if (type(gridparlist) != type([])): gridparlist = [gridparlist]
        for value in gridparlist:
            command += '  gridpar ' + cstr(value) + '\n'
    if (dockparlist != None):
        if (type(dockparlist) != type([])): dockparlist = [dockparlist]
        for value in dockparlist:
            command += '  dockpar ' + cstr(value) + '\n'
    if (setuponly != None): command += '  setuponly ' + cstr(setuponly) + '\n'
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# CHOOSE AND CONTROL EXPERIMENTS
# ==============================
# THIS IS ALTERNATIVE 6, WITH DIFFERENT PARAMETERS
def ExperimentHomologyModeling(sequencefile=None, psiblasts=None, evalue=None, oligostate=None, templates=None,
                               alignments=None, alignfile=None, templateobj=None, loopsamples=None, speed=None,
                               animation=None, resultfile=None, termextension=None, residues=None, structprofile=None,
                               fixmodelres=None, looplenmax=None):
    command = 'Experiment HomologyModeling\n'
    if (sequencefile != None): command += '  sequencefile ' + cstr(sequencefile) + '\n'
    if (psiblasts != None): command += '  psiblasts ' + cstr(psiblasts) + '\n'
    if (evalue != None): command += '  evalue ' + cstr(evalue) + '\n'
    if (oligostate != None): command += '  oligostate ' + cstr(oligostate) + '\n'
    if (templates != None): command += '  templates ' + cstr(templates) + '\n'
    if (alignments != None): command += '  alignments ' + cstr(alignments) + '\n'
    if (alignfile != None): command += '  alignfile ' + cstr(alignfile) + '\n'
    if (templateobj != None): command += '  templateobj ' + cstr(templateobj) + '\n'
    if (loopsamples != None): command += '  loopsamples ' + cstr(loopsamples) + '\n'
    if (speed != None): command += '  speed ' + cstr(speed) + '\n'
    if (animation != None): command += '  animation ' + cstr(animation) + '\n'
    if (resultfile != None): command += '  resultfile ' + cstr(resultfile) + '\n'
    if (termextension != None): command += '  termextension ' + cstr(termextension) + '\n'
    if (residues != None): command += '  residues ' + cstr(residues) + '\n'
    if (structprofile != None): command += '  structprofile ' + cstr(structprofile) + '\n'
    if (fixmodelres != None): command += '  fixmodelres ' + cstr(fixmodelres) + '\n'
    if (looplenmax != None): command += '  looplenmax ' + cstr(looplenmax) + '\n'
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# CHOOSE AND CONTROL EXPERIMENTS
# ==============================
# THIS IS ALTERNATIVE 7, WITH DIFFERENT PARAMETERS
def ExperimentNMRFolding(startobj=None, restrainfile=None, structures=None, structurefile=None):
    command = 'Experiment NMRFolding\n'
    if (startobj != None): command += '  startobj ' + cstr(startobj) + '\n'
    if (restrainfile != None): command += '  restrainfile ' + cstr(restrainfile) + '\n'
    if (structures != None): command += '  structures ' + cstr(structures) + '\n'
    if (structurefile != None): command += '  structurefile ' + cstr(structurefile) + '\n'
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# GET FILE SIZE
# =============
def FileSize(filename):
    command = 'FileSize '
    command += 'Filename=' + cstr(filename) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# FILL SIMULATION CELL WITH OBJECT
# ================================
def FillCellObj(selection1, copies=None, density=None, bumpsum=None, randomori=None, dismin=None):
    command = 'FillCellObj '
    command += selstr(selection1) + ','
    if (copies != None): command += 'Copies=' + cstr(copies) + ','
    if (density != None): command += 'Density=' + cstr(density) + ','
    if (bumpsum != None): command += 'BumpSum=' + cstr(bumpsum) + ','
    if (randomori != None): command += 'RandomOri=' + cstr(randomori) + ','
    if (dismin != None): command += 'DisMin=' + cstr(dismin) + ','
    return (runretval(command[:-1], True))


# FILL SIMULATION CELL WITH WATER
# ===============================
def FillCellWater(density=None, probe=None, bumpsum=None, dismax=None):
    command = 'FillCellWater '
    if (density != None): command += 'Density=' + cstr(density) + ','
    if (probe != None): command += 'Probe=' + cstr(probe) + ','
    if (bumpsum != None): command += 'BumpSum=' + cstr(bumpsum) + ','
    if (dismax != None): command += 'DisMax=' + cstr(dismax) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# FILL OR CLEAR RECTANGULAR AREA
# ==============================
def FillRect(x=None, y=None, width=None, height=None, color=None):
    command = 'FillRect '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (width != None): command += 'Width=' + cstr(width) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    return (runretval(command[:-1], True))


# GET FIRST ATOM OR RESIDUE FACING EACH CAVITY AND THE CAVITY VOLUME (RESIDUE)
# ============================================================================
def FirstCaviRes(selection1, Type=None):
    command = 'FirstCaviRes '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# GET FIRST ATOM OR RESIDUE FACING EACH CAVITY AND THE CAVITY VOLUME (ATOM)
# =========================================================================
def FirstCaviAtom(selection1, Type=None):
    command = 'FirstCaviAtom '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# GET FIRST ATOM OR RESIDUE FACING EACH SURFACE AND THE SURFACE AREA (RESIDUE)
# ============================================================================
def FirstSurfRes(selection1, Type=None):
    command = 'FirstSurfRes '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# GET FIRST ATOM OR RESIDUE FACING EACH SURFACE AND THE SURFACE AREA (ATOM)
# =========================================================================
def FirstSurfAtom(selection1, Type=None):
    command = 'FirstSurfAtom '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CONSTRAIN BOND LENGTH DURING SIMULATION
# =======================================
def FixBond(selection1, selection2):
    command = 'FixBond '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    return (runretval(command[:-1], True))


# CONSTRAIN BOND ANGLE DURING SIMULATION
# ======================================
def FixAngle(selection1, selection2, selection3):
    command = 'FixAngle '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += selstr(selection3) + ','
    return (runretval(command[:-1], True))


# CONSTRAIN CRITICAL HYDROGEN BOND ANGLES DURING SIMULATION
# =========================================================
def FixHydAngle(selection1):
    command = 'FixHydAngle '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# FIX ATOMS DURING SIMULATION (ALL OR SELECTED)
# =============================================
def Fix():
    command = 'Fix '
    return (runretval(command[:-1], True))


# FIX ATOMS DURING SIMULATION (ALL)
# =================================
def FixAll():
    command = 'FixAll '
    return (runretval(command[:-1], True))


# FIX ATOMS DURING SIMULATION (OBJECT)
# ====================================
def FixObj(selection1):
    command = 'FixObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# FIX ATOMS DURING SIMULATION (MOLECULE)
# ======================================
def FixMol(selection1):
    command = 'FixMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# FIX ATOMS DURING SIMULATION (RESIDUE)
# =====================================
def FixRes(selection1):
    command = 'FixRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# FIX ATOMS DURING SIMULATION (ATOM)
# ==================================
def FixAtom(selection1):
    command = 'FixAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# FLIP TABLE AXES
# ===============
def FlipTab(selection1, firstdim, seconddim=None):
    command = 'FlipTab '
    command += selstr(selection1) + ','
    command += 'FirstDim=' + cstr(firstdim) + ','
    if (seconddim != None): command += 'SecondDim=' + cstr(seconddim) + ','
    return (runretval(command[:-1], True))


# SET FOG DENSITY
# ===============
def Fog(density=None, Range=None, dismin=None, dismax=None):
    command = 'Fog '
    if (density != None): command += 'Density=' + cstr(density) + ','
    if (Range != None): command += 'Range=' + cstr(Range) + ','
    if (dismin != None): command += 'DisMin=' + cstr(dismin) + ','
    if (dismax != None): command += 'DisMax=' + cstr(dismax) + ','
    return (runretval(command[:-1], True))


# SET FONT FOR 3D LETTERS
# =======================
def Font(name=None, height=None, color=None, alpha=None, spacing=None, depth=None, depthcol=None, depthalpha=None):
    command = 'Font '
    if (name != None): command += 'Name=' + cstr(name) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (spacing != None): command += 'Spacing=' + cstr(spacing) + ','
    if (depth != None): command += 'Depth=' + cstr(depth) + ','
    if (depthcol != None): command += 'DepthCol=' + cstr(depthcol) + ','
    if (depthalpha != None): command += 'DepthAlpha=' + cstr(depthalpha) + ','
    return (runretval(command[:-1], True))


# SWITCH FONT FOG ON/OFF
# ======================
def FontFog(flag):
    command = 'FontFog '
    command += 'Flag=' + cstr(flag) + ','
    return (runretval(command[:-1], True))


# SET/GET FORCE FIELD
# ===================
def ForceField(name=None, method=None, setpar=None):
    command = 'ForceField '
    if (name != None): command += 'Name=' + cstr(name) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (setpar != None): command += 'SetPar=' + cstr(setpar) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SET/GET FORCE ON ATOMS (ALL OR SELECTED)
# ========================================
def Force(x=None, y=None, z=None):
    command = 'Force '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET FORCE ON ATOMS (ALL)
# ============================
def ForceAll(x=None, y=None, z=None):
    command = 'ForceAll '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET FORCE ON ATOMS (OBJECT)
# ===============================
def ForceObj(selection1, x=None, y=None, z=None):
    command = 'ForceObj '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET FORCE ON ATOMS (MOLECULE)
# =================================
def ForceMol(selection1, x=None, y=None, z=None):
    command = 'ForceMol '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET FORCE ON ATOMS (RESIDUE)
# ================================
def ForceRes(selection1, x=None, y=None, z=None):
    command = 'ForceRes '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET FORCE ON ATOMS (ATOM)
# =============================
def ForceAtom(selection1, x=None, y=None, z=None):
    command = 'ForceAtom '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# FORMAT RESIDUE OUTPUT
# =====================
def FormatRes(output):
    command = 'FormatRes '
    command += 'Output=' + cstr(output) + ','
    return (runretval(command[:-1], True))


# CALCULATE FORMATION ENERGIES (ALL OR SELECTED)
# ==============================================
def FormEnergy():
    command = 'FormEnergy '
    return (runretval(command[:-1], True))


# CALCULATE FORMATION ENERGIES (ALL)
# ==================================
def FormEnergyAll():
    command = 'FormEnergyAll '
    return (runretval(command[:-1], True))


# CALCULATE FORMATION ENERGIES (OBJECT)
# =====================================
def FormEnergyObj(selection1):
    command = 'FormEnergyObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# CALCULATE FORMATION ENERGIES (MOLECULE)
# =======================================
def FormEnergyMol(selection1):
    command = 'FormEnergyMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# CALCULATE FORMATION ENERGIES (RESIDUE)
# ======================================
def FormEnergyRes(selection1):
    command = 'FormEnergyRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# CALCULATE FORMATION ENERGIES (ATOM)
# ===================================
def FormEnergyAtom(selection1):
    command = 'FormEnergyAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SET SCREEN UPDATE FREQUENCY
# ===========================
def FramesPerSec(number, redrawidle=None):
    command = 'FramesPerSec '
    command += 'Number=' + cstr(number) + ','
    if (redrawidle != None): command += 'RedrawIdle=' + cstr(redrawidle) + ','
    return (runretval(command[:-1], True))


# REMOVE BOND LENGTH CONSTRAINT DURING SIMULATION
# ===============================================
def FreeBond(selection1, selection2):
    command = 'FreeBond '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    return (runretval(command[:-1], True))


# FREE BOND ANGLE DURING SIMULATION
# =================================
def FreeAngle(selection1, selection2, selection3):
    command = 'FreeAngle '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += selstr(selection3) + ','
    return (runretval(command[:-1], True))


# FREE ATOMS DURING SIMULATION (ALL OR SELECTED)
# ==============================================
def Free():
    command = 'Free '
    return (runretval(command[:-1], True))


# FREE ATOMS DURING SIMULATION (ALL)
# ==================================
def FreeAll():
    command = 'FreeAll '
    return (runretval(command[:-1], True))


# FREE ATOMS DURING SIMULATION (OBJECT)
# =====================================
def FreeObj(selection1):
    command = 'FreeObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# FREE ATOMS DURING SIMULATION (MOLECULE)
# =======================================
def FreeMol(selection1):
    command = 'FreeMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# FREE ATOMS DURING SIMULATION (RESIDUE)
# ======================================
def FreeRes(selection1):
    command = 'FreeRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# FREE ATOMS DURING SIMULATION (ATOM)
# ===================================
def FreeAtom(selection1):
    command = 'FreeAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SWITCH FULLSCREEN MODE ON/OFF
# =============================
def FullScreen(flag):
    command = 'FullScreen '
    command += 'Flag=' + cstr(flag) + ','
    return (runretval(command[:-1], True))


# CALCULATE GLOBAL DISTANCE TEST (OBJECT)
# =======================================
def GDTObj(selection1, selection2, cutoff=None, match=None):
    command = 'GDTObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    return (runretval(command[:-1], True))


# CALCULATE GLOBAL DISTANCE TEST (MOLECULE)
# =========================================
def GDTMol(selection1, selection2, cutoff=None, match=None):
    command = 'GDTMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    return (runretval(command[:-1], True))


# CALCULATE GLOBAL DISTANCE TEST (RESIDUE)
# ========================================
def GDTRes(selection1, selection2, cutoff=None, match=None):
    command = 'GDTRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    return (runretval(command[:-1], True))


# CALCULATE GLOBAL DISTANCE TEST (ATOM)
# =====================================
def GDTAtom(selection1, selection2, cutoff=None, match=None):
    command = 'GDTAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    return (runretval(command[:-1], True))


# GRAB NEXT OBJECT FOR MOUSE MOVEMENT
# ===================================
def GrabNext():
    command = 'GrabNext '
    return (runretval(command[:-1], True))


# GRAB PREVIOUS OBJECT FOR MOUSE MOVEMENT
# =======================================
def GrabPrev():
    command = 'GrabPrev '
    return (runretval(command[:-1], True))


# GRAB OBJECT OR SCENE FOR MOUSE MOVEMENT (ALL OR SELECTED)
# =========================================================
def Grab():
    command = 'Grab '
    return (runretval(command[:-1], True))


# GRAB OBJECT OR SCENE FOR MOUSE MOVEMENT (ALL)
# =============================================
def GrabAll():
    command = 'GrabAll '
    return (runretval(command[:-1], True))


# GRAB OBJECT OR SCENE FOR MOUSE MOVEMENT (OBJECT)
# ================================================
def GrabObj(selection1):
    command = 'GrabObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# CALCULATE ANGLE BETWEEN TWO ATOM GROUPS
# =======================================
def GroupAngle(selection1, selection2, Range=None):
    command = 'GroupAngle '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (Range != None): command += 'Range=' + cstr(Range) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# CALCULATE BOUNDING BOX AROUND ATOM GROUP
# ========================================
def GroupBox(selection1, Type=None, coordsys=None):
    command = 'GroupBox '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (coordsys != None): command += 'CoordSys=' + cstr(coordsys) + ','
    return (runretval(command[:-1], True))


# CALCULATE GEOMETRIC CENTER OR CENTER OF MASS
# ============================================
def GroupCenter(selection1, coordsys=None, Type=None):
    command = 'GroupCenter '
    command += selstr(selection1) + ','
    if (coordsys != None): command += 'CoordSys=' + cstr(coordsys) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE DIHEDRAL ANGLE BETWEEN TWO ATOM GROUPS
# ================================================
def GroupDihedral(selection1, selection2):
    command = 'GroupDihedral '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# CALCULATE DISTANCE BETWEEN TWO ATOM GROUPS
# ==========================================
def GroupDistance(selection1, selection2, center=None):
    command = 'GroupDistance '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# CALCULATE OPTIMAL LINE THROUGH ATOM GROUP
# =========================================
def GroupLine(selection1, coordsys=None):
    command = 'GroupLine '
    command += selstr(selection1) + ','
    if (coordsys != None): command += 'CoordSys=' + cstr(coordsys) + ','
    return (runretval(command[:-1], True))


# CALCULATE OPTIMAL PLANE THROUGH ATOM GROUP
# ==========================================
def GroupPlane(selection1, coordsys=None):
    command = 'GroupPlane '
    command += selstr(selection1) + ','
    if (coordsys != None): command += 'CoordSys=' + cstr(coordsys) + ','
    return (runretval(command[:-1], True))


# ADD ATOMS TO GROUP (ALL OR SELECTED)
# ====================================
def Group(name):
    command = 'Group '
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# ADD ATOMS TO GROUP (ALL)
# ========================
def GroupAll(name):
    command = 'GroupAll '
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# ADD ATOMS TO GROUP (OBJECT)
# ===========================
def GroupObj(selection1, name):
    command = 'GroupObj '
    command += selstr(selection1) + ','
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# ADD ATOMS TO GROUP (MOLECULE)
# =============================
def GroupMol(selection1, name):
    command = 'GroupMol '
    command += selstr(selection1) + ','
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# ADD ATOMS TO GROUP (RESIDUE)
# ============================
def GroupRes(selection1, name):
    command = 'GroupRes '
    command += selstr(selection1) + ','
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# ADD ATOMS TO GROUP (ATOM)
# =========================
def GroupAtom(selection1, name):
    command = 'GroupAtom '
    command += selstr(selection1) + ','
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# HIDE ARROWS (ALL OR SELECTED)
# =============================
def HideArrow():
    command = 'HideArrow '
    return (runretval(command[:-1], True))


# HIDE ARROWS (ALL)
# =================
def HideArrowAll():
    command = 'HideArrowAll '
    return (runretval(command[:-1], True))


# HIDE ARROWS (OBJECT)
# ====================
def HideArrowObj(selection1):
    command = 'HideArrowObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE ARROWS (MOLECULE)
# ======================
def HideArrowMol(selection1):
    command = 'HideArrowMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE ARROWS (RESIDUE)
# =====================
def HideArrowRes(selection1):
    command = 'HideArrowRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE ARROWS (ATOM)
# ==================
def HideArrowAtom(selection1):
    command = 'HideArrowAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE HYDROGEN BONDS (ALL OR SELECTED)
# =====================================
def HideHBo():
    command = 'HideHBo '
    return (runretval(command[:-1], True))


# HIDE HYDROGEN BONDS (ALL)
# =========================
def HideHBoAll():
    command = 'HideHBoAll '
    return (runretval(command[:-1], True))


# HIDE HYDROGEN BONDS (OBJECT)
# ============================
def HideHBoObj(selection1):
    command = 'HideHBoObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE HYDROGEN BONDS (MOLECULE)
# ==============================
def HideHBoMol(selection1):
    command = 'HideHBoMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE HYDROGEN BONDS (RESIDUE)
# =============================
def HideHBoRes(selection1):
    command = 'HideHBoRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE HYDROGEN BONDS (ATOM)
# ==========================
def HideHBoAtom(selection1):
    command = 'HideHBoAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE IN HEAD-UP DISPLAY (MOLECULE)
# ==================================
def HideHUDMol(selection1):
    command = 'HideHUDMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE IN HEAD-UP DISPLAY (RESIDUE)
# =================================
def HideHUDRes(selection1):
    command = 'HideHUDRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE IN HEAD-UP DISPLAY (ATOM)
# ==============================
def HideHUDAtom(selection1):
    command = 'HideHUDAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE IMAGES
# ===========
def HideImage(selection1):
    command = 'HideImage '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE TEXT MESSAGE AT THE BOTTOM
# ===============================
def HideMessage():
    command = 'HideMessage '
    return (runretval(command[:-1], True))


# HIDE POLYGONS (ALL OR SELECTED)
# ===============================
def HidePolygon():
    command = 'HidePolygon '
    return (runretval(command[:-1], True))


# HIDE POLYGONS (ALL)
# ===================
def HidePolygonAll():
    command = 'HidePolygonAll '
    return (runretval(command[:-1], True))


# HIDE POLYGONS (OBJECT)
# ======================
def HidePolygonObj(selection1):
    command = 'HidePolygonObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE POLYGONS (MOLECULE)
# ========================
def HidePolygonMol(selection1):
    command = 'HidePolygonMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE POLYGONS (RESIDUE)
# =======================
def HidePolygonRes(selection1):
    command = 'HidePolygonRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE POLYGONS (ATOM)
# ====================
def HidePolygonAtom(selection1):
    command = 'HidePolygonAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE RESTRAINTS (ALL OR SELECTED)
# =================================
def HideRest(Class=None):
    command = 'HideRest '
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    return (runretval(command[:-1], True))


# HIDE RESTRAINTS (ALL)
# =====================
def HideRestAll(Class=None):
    command = 'HideRestAll '
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    return (runretval(command[:-1], True))


# HIDE RESTRAINTS (OBJECT)
# ========================
def HideRestObj(selection1, Class=None):
    command = 'HideRestObj '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    return (runretval(command[:-1], True))


# HIDE RESTRAINTS (MOLECULE)
# ==========================
def HideRestMol(selection1, Class=None):
    command = 'HideRestMol '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    return (runretval(command[:-1], True))


# HIDE RESTRAINTS (RESIDUE)
# =========================
def HideRestRes(selection1, Class=None):
    command = 'HideRestRes '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    return (runretval(command[:-1], True))


# HIDE RESTRAINTS (ATOM)
# ======================
def HideRestAtom(selection1, Class=None):
    command = 'HideRestAtom '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    return (runretval(command[:-1], True))


# HIDE SECONDARY STRUCTURE (ALL OR SELECTED)
# ==========================================
def HideSecStr(showatoms=None):
    command = 'HideSecStr '
    if (showatoms != None): command += 'ShowAtoms=' + cstr(showatoms) + ','
    return (runretval(command[:-1], True))


# HIDE SECONDARY STRUCTURE (ALL)
# ==============================
def HideSecStrAll(showatoms=None):
    command = 'HideSecStrAll '
    if (showatoms != None): command += 'ShowAtoms=' + cstr(showatoms) + ','
    return (runretval(command[:-1], True))


# HIDE SECONDARY STRUCTURE (OBJECT)
# =================================
def HideSecStrObj(selection1, showatoms=None):
    command = 'HideSecStrObj '
    command += selstr(selection1) + ','
    if (showatoms != None): command += 'ShowAtoms=' + cstr(showatoms) + ','
    return (runretval(command[:-1], True))


# HIDE SECONDARY STRUCTURE (MOLECULE)
# ===================================
def HideSecStrMol(selection1, showatoms=None):
    command = 'HideSecStrMol '
    command += selstr(selection1) + ','
    if (showatoms != None): command += 'ShowAtoms=' + cstr(showatoms) + ','
    return (runretval(command[:-1], True))


# HIDE SECONDARY STRUCTURE (RESIDUE)
# ==================================
def HideSecStrRes(selection1, showatoms=None):
    command = 'HideSecStrRes '
    command += selstr(selection1) + ','
    if (showatoms != None): command += 'ShowAtoms=' + cstr(showatoms) + ','
    return (runretval(command[:-1], True))


# HIDE SURFACE (ALL OR SELECTED)
# ==============================
def HideSurf(Type=None):
    command = 'HideSurf '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# HIDE SURFACE (ALL)
# ==================
def HideSurfAll(Type=None):
    command = 'HideSurfAll '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# HIDE SURFACE (OBJECT)
# =====================
def HideSurfObj(selection1, Type=None):
    command = 'HideSurfObj '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# HIDE SURFACE (MOLECULE)
# =======================
def HideSurfMol(selection1, Type=None):
    command = 'HideSurfMol '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# HIDE SURFACE (RESIDUE)
# ======================
def HideSurfRes(selection1, Type=None):
    command = 'HideSurfRes '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# HIDE SURFACE (ATOM)
# ===================
def HideSurfAtom(selection1, Type=None):
    command = 'HideSurfAtom '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# HIDE TRACE THROUGH ATOMS
# ========================
def HideTrace(selection1):
    command = 'HideTrace '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE ATOMS (ALL OR SELECTED)
# ============================
def Hide():
    command = 'Hide '
    return (runretval(command[:-1], True))


# HIDE ATOMS (ALL)
# ================
def HideAll():
    command = 'HideAll '
    return (runretval(command[:-1], True))


# HIDE ATOMS (OBJECT)
# ===================
def HideObj(selection1):
    command = 'HideObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE ATOMS (MOLECULE)
# =====================
def HideMol(selection1):
    command = 'HideMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE ATOMS (RESIDUE)
# ====================
def HideRes(selection1):
    command = 'HideRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# HIDE ATOMS (ATOM)
# =================
def HideAtom(selection1):
    command = 'HideAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SWITCH HEAD UP DISPLAY
# ======================
def HUD(show=None, antialias=None, fontsize=None):
    command = 'HUD '
    if (show != None): command += 'Show=' + cstr(show) + ','
    if (antialias != None): command += 'Antialias=' + cstr(antialias) + ','
    if (fontsize != None): command += 'FontSize=' + cstr(fontsize) + ','
    return (runretval(command[:-1], True))


# SWITCH IMAGE FOG ON/OFF
# =======================
def ImageFog(flag):
    command = 'ImageFog '
    command += 'Flag=' + cstr(flag) + ','
    return (runretval(command[:-1], True))


# GENERATE 3D COORDINATES FOR FLAT OR DISTORTED MOLECULES (ALL OR SELECTED)
# =========================================================================
def Inflate():
    command = 'Inflate '
    return (runretval(command[:-1], True))


# GENERATE 3D COORDINATES FOR FLAT OR DISTORTED MOLECULES (ALL)
# =============================================================
def InflateAll():
    command = 'InflateAll '
    return (runretval(command[:-1], True))


# GENERATE 3D COORDINATES FOR FLAT OR DISTORTED MOLECULES (OBJECT)
# ================================================================
def InflateObj(selection1):
    command = 'InflateObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# GENERATE 3D COORDINATES FOR FLAT OR DISTORTED MOLECULES (MOLECULE)
# ==================================================================
def InflateMol(selection1):
    command = 'InflateMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# GENERATE 3D COORDINATES FOR FLAT OR DISTORTED MOLECULES (RESIDUE)
# =================================================================
def InflateRes(selection1):
    command = 'InflateRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# GENERATE 3D COORDINATES FOR FLAT OR DISTORTED MOLECULES (ATOM)
# ==============================================================
def InflateAtom(selection1):
    command = 'InflateAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# INSTALL ACCESSORY PROGRAM
# =========================
def Install(program, code):
    command = 'Install '
    command += 'Program=' + cstr(program) + ','
    command += 'Code=' + cstr(code) + ','
    return (runretval(command[:-1], True))


# CREATE OBJECT INSTANCES FOR VISUALIZATION (ALL OR SELECTED)
# ===========================================================
def Instance(copies=None, group=None, x=None, y=None, z=None, rx=None, ry=None, rz=None):
    command = 'Instance '
    if (copies != None): command += 'Copies=' + cstr(copies) + ','
    if (group != None): command += 'Group=' + cstr(group) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (rx != None): command += 'RX=' + cstr(rx) + ','
    if (ry != None): command += 'RY=' + cstr(ry) + ','
    if (rz != None): command += 'RZ=' + cstr(rz) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# CREATE OBJECT INSTANCES FOR VISUALIZATION (ALL)
# ===============================================
def InstanceAll(copies=None, group=None, x=None, y=None, z=None, rx=None, ry=None, rz=None):
    command = 'InstanceAll '
    if (copies != None): command += 'Copies=' + cstr(copies) + ','
    if (group != None): command += 'Group=' + cstr(group) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (rx != None): command += 'RX=' + cstr(rx) + ','
    if (ry != None): command += 'RY=' + cstr(ry) + ','
    if (rz != None): command += 'RZ=' + cstr(rz) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# CREATE OBJECT INSTANCES FOR VISUALIZATION (OBJECT)
# ==================================================
def InstanceObj(selection1, copies=None, group=None, x=None, y=None, z=None, rx=None, ry=None, rz=None):
    command = 'InstanceObj '
    command += selstr(selection1) + ','
    if (copies != None): command += 'Copies=' + cstr(copies) + ','
    if (group != None): command += 'Group=' + cstr(group) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (rx != None): command += 'RX=' + cstr(rx) + ','
    if (ry != None): command += 'RY=' + cstr(ry) + ','
    if (rz != None): command += 'RZ=' + cstr(rz) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SET FORCE FIELD TERMS
# =====================
def Interactions(Type):
    command = 'Interactions '
    command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# PERFORM COLLISION DETECTION TO FIND INTERSECTING OBJECTS
# ========================================================
def IntersectObj(selection1, radiusscale1, selection2, radiusscale2=None):
    command = 'IntersectObj '
    command += selstr(selection1) + ','
    command += 'RadiusScale1=' + cstr(radiusscale1) + ','
    command += selstr(selection2) + ','
    if (radiusscale2 != None): command += 'RadiusScale2=' + cstr(radiusscale2) + ','
    return (runretval(command[:-1], True))


# JOIN OBJECTS TO ONE FINAL OBJECT
# ================================
def JoinObj(selection1, selection2, center=None):
    command = 'JoinObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    return (runretval(command[:-1], True))


# DELETE SPLIT POINTS (MOLECULE)
# ==============================
def JoinMol(selection1):
    command = 'JoinMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DELETE SPLIT POINTS (RESIDUE)
# =============================
def JoinRes(selection1):
    command = 'JoinRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DELETE SPLIT POINTS (ATOM)
# ==========================
def JoinAtom(selection1):
    command = 'JoinAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# CONFIGURE VIRTUAL ON-SCREEN KEYBOARD
# ====================================
def Keyboard(state, layout, size, keysize, alpha, gapalpha, feedback):
    command = 'Keyboard '
    command += 'State=' + cstr(state) + ','
    command += 'Layout=' + cstr(layout) + ','
    command += 'Size=' + cstr(size) + ','
    command += 'KeySize=' + cstr(keysize) + ','
    command += 'Alpha=' + cstr(alpha) + ','
    command += 'GapAlpha=' + cstr(gapalpha) + ','
    command += 'Feedback=' + cstr(feedback) + ','
    return (runretval(command[:-1], True))


# REMOVE FRACTIONAL BOND ORDERS
# =============================
def KekulizeBond(selection1, selection2):
    command = 'KekulizeBond '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    return (runretval(command[:-1], True))


# CALCULATE KINETIC ENERGY (ALL OR SELECTED)
# ==========================================
def KinEnergy(currenttime=None):
    command = 'KinEnergy '
    if (currenttime != None): command += 'CurrentTime=' + cstr(currenttime) + ','
    return (runretval(command[:-1], True))


# CALCULATE KINETIC ENERGY (ALL)
# ==============================
def KinEnergyAll(currenttime=None):
    command = 'KinEnergyAll '
    if (currenttime != None): command += 'CurrentTime=' + cstr(currenttime) + ','
    return (runretval(command[:-1], True))


# CALCULATE KINETIC ENERGY (OBJECT)
# =================================
def KinEnergyObj(selection1, currenttime=None):
    command = 'KinEnergyObj '
    command += selstr(selection1) + ','
    if (currenttime != None): command += 'CurrentTime=' + cstr(currenttime) + ','
    return (runretval(command[:-1], True))


# CALCULATE KINETIC ENERGY (MOLECULE)
# ===================================
def KinEnergyMol(selection1, currenttime=None):
    command = 'KinEnergyMol '
    command += selstr(selection1) + ','
    if (currenttime != None): command += 'CurrentTime=' + cstr(currenttime) + ','
    return (runretval(command[:-1], True))


# CALCULATE KINETIC ENERGY (RESIDUE)
# ==================================
def KinEnergyRes(selection1, currenttime=None):
    command = 'KinEnergyRes '
    command += selstr(selection1) + ','
    if (currenttime != None): command += 'CurrentTime=' + cstr(currenttime) + ','
    return (runretval(command[:-1], True))


# CALCULATE KINETIC ENERGY (ATOM)
# ===============================
def KinEnergyAtom(selection1, currenttime=None):
    command = 'KinEnergyAtom '
    command += selstr(selection1) + ','
    if (currenttime != None): command += 'CurrentTime=' + cstr(currenttime) + ','
    return (runretval(command[:-1], True))


# LABEL ATOM DISTANCES
# ====================
def LabelDis(selection1, selection2, format=None, height=None, color=None, x=None, y=None, z=None, bound=None,
             radius=None):
    command = 'LabelDis '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (bound != None): command += 'Bound=' + cstr(bound) + ','
    if (radius != None): command += 'Radius=' + cstr(radius) + ','
    return (runretval(command[:-1], True))


# SET LABEL PARAMETERS
# ====================
def LabelPar(font, height=None, color=None, ontop=None, shrink=None, fog=None):
    command = 'LabelPar '
    command += 'Font=' + cstr(font) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (ontop != None): command += 'OnTop=' + cstr(ontop) + ','
    if (shrink != None): command += 'Shrink=' + cstr(shrink) + ','
    if (fog != None): command += 'Fog=' + cstr(fog) + ','
    return (runretval(command[:-1], True))


# ADD LABELS (ALL OR SELECTED)
# ============================
def Label(format, height=None, color=None, x=None, y=None, z=None, convert=None):
    command = 'Label '
    command += 'Format=' + cstr(format) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (convert != None): command += 'Convert=' + cstr(convert) + ','
    return (runretval(command[:-1], True))


# ADD LABELS (ALL)
# ================
def LabelAll(format, height=None, color=None, x=None, y=None, z=None, convert=None):
    command = 'LabelAll '
    command += 'Format=' + cstr(format) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (convert != None): command += 'Convert=' + cstr(convert) + ','
    return (runretval(command[:-1], True))


# ADD LABELS (OBJECT)
# ===================
def LabelObj(selection1, format, height=None, color=None, x=None, y=None, z=None, convert=None):
    command = 'LabelObj '
    command += selstr(selection1) + ','
    command += 'Format=' + cstr(format) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (convert != None): command += 'Convert=' + cstr(convert) + ','
    return (runretval(command[:-1], True))


# ADD LABELS (MOLECULE)
# =====================
def LabelMol(selection1, format, height=None, color=None, x=None, y=None, z=None, convert=None):
    command = 'LabelMol '
    command += selstr(selection1) + ','
    command += 'Format=' + cstr(format) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (convert != None): command += 'Convert=' + cstr(convert) + ','
    return (runretval(command[:-1], True))


# ADD LABELS (SEGMENT)
# ====================
def LabelSeg(selection1, format, height=None, color=None, x=None, y=None, z=None, convert=None):
    command = 'LabelSeg '
    command += selstr(selection1) + ','
    command += 'Format=' + cstr(format) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (convert != None): command += 'Convert=' + cstr(convert) + ','
    return (runretval(command[:-1], True))


# ADD LABELS (RESIDUE)
# ====================
def LabelRes(selection1, format, height=None, color=None, x=None, y=None, z=None, convert=None):
    command = 'LabelRes '
    command += selstr(selection1) + ','
    command += 'Format=' + cstr(format) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (convert != None): command += 'Convert=' + cstr(convert) + ','
    return (runretval(command[:-1], True))


# ADD LABELS (ATOM)
# =================
def LabelAtom(selection1, format, height=None, color=None, x=None, y=None, z=None, convert=None):
    command = 'LabelAtom '
    command += selstr(selection1) + ','
    command += 'Format=' + cstr(format) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (convert != None): command += 'Convert=' + cstr(convert) + ','
    return (runretval(command[:-1], True))


# CONFIGURE THE LIGHT SOURCE
# ==========================
def LightSource(alpha=None, gamma=None, ambience=None, ambience2=None, shadow=None, shadowspeed=None, ambiencefps=None,
                softshadowfps=None, hardshadowfps=None, cellshadow=None):
    command = 'LightSource '
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (gamma != None): command += 'Gamma=' + cstr(gamma) + ','
    if (ambience != None): command += 'Ambience=' + cstr(ambience) + ','
    if (ambience2 != None): command += 'Ambience2=' + cstr(ambience2) + ','
    if (shadow != None): command += 'Shadow=' + cstr(shadow) + ','
    if (shadowspeed != None): command += 'ShadowSpeed=' + cstr(shadowspeed) + ','
    if (ambiencefps != None): command += 'AmbienceFPS=' + cstr(ambiencefps) + ','
    if (softshadowfps != None): command += 'SoftShadowFPS=' + cstr(softshadowfps) + ','
    if (hardshadowfps != None): command += 'HardShadowFPS=' + cstr(hardshadowfps) + ','
    if (cellshadow != None): command += 'CellShadow=' + cstr(cellshadow) + ','
    return (runretval(command[:-1], True))


# SET PER-ATOM LIGHTING (ALL OR SELECTED)
# =======================================
def Light(direction):
    command = 'Light '
    command += 'Direction=' + cstr(direction) + ','
    return (runretval(command[:-1], True))


# SET PER-ATOM LIGHTING (ALL)
# ===========================
def LightAll(direction):
    command = 'LightAll '
    command += 'Direction=' + cstr(direction) + ','
    return (runretval(command[:-1], True))


# SET PER-ATOM LIGHTING (OBJECT)
# ==============================
def LightObj(selection1, direction):
    command = 'LightObj '
    command += selstr(selection1) + ','
    command += 'Direction=' + cstr(direction) + ','
    return (runretval(command[:-1], True))


# SET PER-ATOM LIGHTING (MOLECULE)
# ================================
def LightMol(selection1, direction):
    command = 'LightMol '
    command += selstr(selection1) + ','
    command += 'Direction=' + cstr(direction) + ','
    return (runretval(command[:-1], True))


# SET PER-ATOM LIGHTING (RESIDUE)
# ===============================
def LightRes(selection1, direction):
    command = 'LightRes '
    command += selstr(selection1) + ','
    command += 'Direction=' + cstr(direction) + ','
    return (runretval(command[:-1], True))


# SET PER-ATOM LIGHTING (ATOM)
# ============================
def LightAtom(selection1, direction):
    command = 'LightAtom '
    command += selstr(selection1) + ','
    command += 'Direction=' + cstr(direction) + ','
    return (runretval(command[:-1], True))


# FIND BONDS AUTOMATICALLY (ALL OR SELECTED)
# ==========================================
def Link(deviation=None, Type=None):
    command = 'Link '
    if (deviation != None): command += 'Deviation=' + cstr(deviation) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# FIND BONDS AUTOMATICALLY (ALL)
# ==============================
def LinkAll(deviation=None, Type=None):
    command = 'LinkAll '
    if (deviation != None): command += 'Deviation=' + cstr(deviation) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# FIND BONDS AUTOMATICALLY (OBJECT)
# =================================
def LinkObj(selection1, deviation=None, Type=None):
    command = 'LinkObj '
    command += selstr(selection1) + ','
    if (deviation != None): command += 'Deviation=' + cstr(deviation) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# FIND BONDS AUTOMATICALLY (MOLECULE)
# ===================================
def LinkMol(selection1, deviation=None, Type=None):
    command = 'LinkMol '
    command += selstr(selection1) + ','
    if (deviation != None): command += 'Deviation=' + cstr(deviation) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# FIND BONDS AUTOMATICALLY (RESIDUE)
# ==================================
def LinkRes(selection1, deviation=None, Type=None):
    command = 'LinkRes '
    command += selstr(selection1) + ','
    if (deviation != None): command += 'Deviation=' + cstr(deviation) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# FIND BONDS AUTOMATICALLY (ATOM)
# ===============================
def LinkAtom(selection1, deviation=None, Type=None):
    command = 'LinkAtom '
    command += selstr(selection1) + ','
    if (deviation != None): command += 'Deviation=' + cstr(deviation) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# LIST CONTACTS (OBJECT)
# ======================
def ListConObj(selection1, selection2, cutoff=None, subtract=None, energy=None, exclude=None, occluded=None, sort=None,
               results=None):
    command = 'ListConObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (energy != None): command += 'Energy=' + cstr(energy) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# LIST CONTACTS (MOLECULE)
# ========================
def ListConMol(selection1, selection2, cutoff=None, subtract=None, energy=None, exclude=None, occluded=None, sort=None,
               results=None):
    command = 'ListConMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (energy != None): command += 'Energy=' + cstr(energy) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# LIST CONTACTS (RESIDUE)
# =======================
def ListConRes(selection1, selection2, cutoff=None, subtract=None, energy=None, exclude=None, occluded=None, sort=None,
               results=None):
    command = 'ListConRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (energy != None): command += 'Energy=' + cstr(energy) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# LIST CONTACTS (ATOM)
# ====================
def ListConAtom(selection1, selection2, cutoff=None, subtract=None, energy=None, exclude=None, occluded=None, sort=None,
                results=None):
    command = 'ListConAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (energy != None): command += 'Energy=' + cstr(energy) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# LIST DIRECTORY CONTENT
# ======================
def ListDir(filename):
    command = 'ListDir '
    command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# LIST HYDROGEN BONDS (OBJECT)
# ============================
def ListHBoObj(selection1, selection2, Min=None, results=None):
    command = 'ListHBoObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (Min != None): command += 'Min=' + cstr(Min) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# LIST HYDROGEN BONDS (MOLECULE)
# ==============================
def ListHBoMol(selection1, selection2, Min=None, results=None):
    command = 'ListHBoMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (Min != None): command += 'Min=' + cstr(Min) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# LIST HYDROGEN BONDS (RESIDUE)
# =============================
def ListHBoRes(selection1, selection2, Min=None, results=None):
    command = 'ListHBoRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (Min != None): command += 'Min=' + cstr(Min) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# LIST HYDROGEN BONDS (ATOM)
# ==========================
def ListHBoAtom(selection1, selection2, Min=None, results=None):
    command = 'ListHBoAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (Min != None): command += 'Min=' + cstr(Min) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# LIST INTERACTIONS (OBJECT)
# ==========================
def ListIntObj(selection1, selection2, Type, cutoff=None, exclude=None, occluded=None, sort=None, results=None):
    command = 'ListIntObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += 'Type=' + cstr(Type) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# LIST INTERACTIONS (MOLECULE)
# ============================
def ListIntMol(selection1, selection2, Type, cutoff=None, exclude=None, occluded=None, sort=None, results=None):
    command = 'ListIntMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += 'Type=' + cstr(Type) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# LIST INTERACTIONS (RESIDUE)
# ===========================
def ListIntRes(selection1, selection2, Type, cutoff=None, exclude=None, occluded=None, sort=None, results=None):
    command = 'ListIntRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += 'Type=' + cstr(Type) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# LIST INTERACTIONS (ATOM)
# ========================
def ListIntAtom(selection1, selection2, Type, cutoff=None, exclude=None, occluded=None, sort=None, results=None):
    command = 'ListIntAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += 'Type=' + cstr(Type) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# LOAD IMAGE FROM BMP FILE
# ========================
def LoadBmp(filename, transcol=None):
    command = 'LoadBmp '
    command += 'Filename=' + cstr(filename) + ','
    if (transcol != None): command += 'TransCol=' + cstr(transcol) + ','
    return (runretval(command[:-1], True))


# LOAD CIF OR MMCIF FILE
# ======================
def LoadCIF(filename, center=None, correct=None, model=None, missres=None):
    command = 'LoadCIF '
    command += 'Filename=' + cstr(filename) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (correct != None): command += 'Correct=' + cstr(correct) + ','
    if (model != None): command += 'Model=' + cstr(model) + ','
    if (missres != None): command += 'MissRes=' + cstr(missres) + ','
    return (runretval(command[:-1], True))


# LOAD AND VISUALIZE ELECTROSTATIC POTENTIAL
# ==========================================
def LoadESP(filename, style, Min=None, Max=None):
    command = 'LoadESP '
    command += 'Filename=' + cstr(filename) + ','
    command += 'Style=' + cstr(style) + ','
    if (Min != None): command += 'Min=' + cstr(Min) + ','
    if (Max != None): command += 'Max=' + cstr(Max) + ','
    return (runretval(command[:-1], True))


# LOAD AND VISUALIZE ELECTROSTATIC POTENTIAL
# ==========================================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def LoadESP2(filename, style, level=None):
    command = 'LoadESP '
    command += 'Filename=' + cstr(filename) + ','
    command += 'Style=' + cstr(style) + ','
    if (level != None): command += 'Level=' + cstr(level) + ','
    return (runretval(command[:-1], True))


# LOAD IMAGE FROM JPG FILE
# ========================
def LoadJPG(filename):
    command = 'LoadJPG '
    command += 'Filename=' + cstr(filename) + ','
    return (runretval(command[:-1], True))


# LOAD SIMULATION SNAPSHOT IN MDCRD FORMAT (ALL OR SELECTED)
# ==========================================================
def LoadMDCrd(filename, snapshot=None, assignsec=None):
    command = 'LoadMDCrd '
    command += 'Filename=' + cstr(filename) + ','
    if (snapshot != None): command += 'Snapshot=' + cstr(snapshot) + ','
    if (assignsec != None): command += 'assignSec=' + cstr(assignsec) + ','
    return (runretval(command[:-1], True))


# LOAD SIMULATION SNAPSHOT IN MDCRD FORMAT (ALL)
# ==============================================
def LoadMDCrdAll(filename, snapshot=None, assignsec=None):
    command = 'LoadMDCrdAll '
    command += 'Filename=' + cstr(filename) + ','
    if (snapshot != None): command += 'Snapshot=' + cstr(snapshot) + ','
    if (assignsec != None): command += 'assignSec=' + cstr(assignsec) + ','
    return (runretval(command[:-1], True))


# LOAD SIMULATION SNAPSHOT IN MDCRD FORMAT (OBJECT)
# =================================================
def LoadMDCrdObj(selection1, filename, snapshot=None, assignsec=None):
    command = 'LoadMDCrdObj '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    if (snapshot != None): command += 'Snapshot=' + cstr(snapshot) + ','
    if (assignsec != None): command += 'assignSec=' + cstr(assignsec) + ','
    return (runretval(command[:-1], True))


# STREAM MOVIE FROM MPEG4 FILE
# ============================
def LoadMPG(filename, loop, selection1):
    command = 'LoadMPG '
    command += 'Filename=' + cstr(filename) + ','
    command += 'Loop=' + cstr(loop) + ','
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# LOAD DISTANCE, DIHEDRAL AND RDC RESTRAINTS IN NMR EXCHANGE FORMAT
# =================================================================
def LoadNEF(filename, selection1, Class, nameformat):
    command = 'LoadNEF '
    command += 'Filename=' + cstr(filename) + ','
    command += selstr(selection1) + ','
    command += 'Class=' + cstr(Class) + ','
    command += 'NameFormat=' + cstr(nameformat) + ','
    return (runretval(command[:-1], True))


# LOAD PROTEIN DATA BANK FILE
# ===========================
def LoadPDB(filename, center=None, correct=None, model=None, download=None, seqres=None):
    """
    Loads a PDB file into YASARA.
    
    For much more detailed information, run ``Help LoadPDB`` in the YASARA console.
    
    :param filename: Filename of the PDB file or molecule ID if downloading from internet (see *download* parameter) 
    :type filename: str
    :param center: Either "Yes" or "No", aligns the center of the loaded molecule to the local coordinate system.
    :type center: str
    :param correct: Either "Yes" or "No", whether to attempt to correct errors after loading the model
    :type correct: str
    :param model: An integer denoting how many models to load from the provided filename.
    :type model: int
    :param download: Either "No", "Yes", "Latest", "PDBRedo", "Best" to determine whether and where to download from, 
                     for more information about this please see the detailed help in YASARA.
    :type download: str
    :param seqres: Either "Yes" or "no", determines whether to read the protein sequence from the PDB file.
    :type seqres: str
    """
    command = 'LoadPDB '
    command += 'Filename=' + cstr(filename) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (correct != None): command += 'Correct=' + cstr(correct) + ','
    if (model != None): command += 'Model=' + cstr(model) + ','
    if (download != None): command += 'Download=' + cstr(download) + ','
    if (seqres != None): command += 'SeqRes=' + cstr(seqres) + ','
    return (runretval(command[:-1], True))


# LOAD IMAGE FROM PNG FILE
# ========================
def LoadPNG(filename, transcol, selection1):
    """
    Loads a PNG file **WITHIN** YASARA.
    
    Notes:
        * For much more detailed information, run ``Help LoadPNG`` in the YASARA console.
        * See also SavePNG
    
    :param filename: The fileame of the image to load, *relative to the current working directory of YASARA*
    :type filename: str(path)
    :param transcol: A colour specification that YASARA will turn to transparent, for more information please see 
                     ``Help LoadPNG``.
    :type transcol: str(colour name, RGBHex, ...)
    :param selection1: An object selection number by which the image will be known to YASARA (please see help for more 
                       information.
    :type selection1: int
    """
    command = 'LoadPNG '
    command += 'Filename=' + cstr(filename) + ','
    command += 'TransCol=' + cstr(transcol) + ','
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# LOAD AMBER PREP TOPOLOGY
# ========================
def LoadPrep(filename, name=None):
    command = 'LoadPrep '
    command += 'Filename=' + cstr(filename) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# LOAD COMPLETE SCENE
# ===================
def LoadSce(filename, settings=None):
    command = 'LoadSce '
    command += 'Filename=' + cstr(filename) + ','
    if (settings != None): command += 'Settings=' + cstr(settings) + ','
    return (runretval(command[:-1], True))


# LOAD SIMULATION SNAPSHOT IN SIM FORMAT
# ======================================
def LoadSim(filename, assignsec=None):
    command = 'LoadSim '
    command += 'Filename=' + cstr(filename) + ','
    if (assignsec != None): command += 'assignSec=' + cstr(assignsec) + ','
    return runretval(command[:-1], True)


# LOAD FORMATTED TABLE
# ====================
def LoadTab(filename, dimensions=None, columns=None, rows=None, pages=None):
    command = 'LoadTab '
    command += 'Filename=' + cstr(filename) + ','
    if dimensions != None:
        command += 'Dimensions=' + cstr(dimensions) + ','
    if columns != None:
        command += 'Columns=' + cstr(columns) + ','
    if rows != None:
        command += 'Rows=' + cstr(rows) + ','
    if pages != None:
        command += 'Pages=' + cstr(pages) + ','
    result = runretval(command[:-1], True)
    if result != None and len(result):
        return result[0]
    return result


# LOAD DISTANCE, DIHEDRAL AND RDC RESTRAINTS IN XPLOR FORMAT
# ==========================================================
def LoadTbl(filename, selection1, Class=None, nameformat=None):
    command = 'LoadTbl '
    command += 'Filename=' + cstr(filename) + ','
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (nameformat != None): command += 'NameFormat=' + cstr(nameformat) + ','
    return (runretval(command[:-1], True))


# LOAD SIMULATION SNAPSHOT IN XTC FORMAT (ALL OR SELECTED)
# ========================================================
def LoadXTC(filename, snapshot=None, assignsec=None):
    command = 'LoadXTC '
    command += 'Filename=' + cstr(filename) + ','
    if (snapshot != None): command += 'Snapshot=' + cstr(snapshot) + ','
    if (assignsec != None): command += 'assignSec=' + cstr(assignsec) + ','
    return (runretval(command[:-1], True))


# LOAD SIMULATION SNAPSHOT IN XTC FORMAT (ALL)
# ============================================
def LoadXTCAll(filename, snapshot=None, assignsec=None):
    command = 'LoadXTCAll '
    command += 'Filename=' + cstr(filename) + ','
    if (snapshot != None): command += 'Snapshot=' + cstr(snapshot) + ','
    if (assignsec != None): command += 'assignSec=' + cstr(assignsec) + ','
    return (runretval(command[:-1], True))


# LOAD SIMULATION SNAPSHOT IN XTC FORMAT (OBJECT)
# ===============================================
def LoadXTCObj(selection1, filename, snapshot=None, assignsec=None):
    command = 'LoadXTCObj '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    if (snapshot != None): command += 'Snapshot=' + cstr(snapshot) + ','
    if (assignsec != None): command += 'assignSec=' + cstr(assignsec) + ','
    return (runretval(command[:-1], True))


# LOAD YASARA OBJECT
# ==================
def LoadYOb(filename):
    command = 'LoadYOb '
    command += 'Filename=' + cstr(filename) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# IMPORT FILE WITH OPENBABEL
# ==========================
def Load(format, filename, center=None, resonate=None, model=None):
    command = 'Load '
    command = command[:-1] + cstr(format) + ' '
    command += 'Filename=' + cstr(filename) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (resonate != None): command += 'Resonate=' + cstr(resonate) + ','
    if (model != None): command += 'Model=' + cstr(model) + ','
    return (runretval(command[:-1], True))


# LOG OUTPUT OF NEXT COMMAND
# ==========================
def LogAs(filename, append=None):
    command = 'LogAs '
    command += 'Filename=' + cstr(filename) + ','
    if (append != None): command += 'append=' + cstr(append) + ','
    return (runretval(command[:-1], True))


# LOG OUTPUT OF NEXT COMMAND
# ==========================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def LogAs2(filename, append, noname1):
    command = 'LogAs '
    command += 'Filename=' + cstr(filename) + ','
    command += 'append=' + cstr(append) + ','
    command += cstr(noname1) + ','
    return (runretval(command[:-1], True))


# LIST BONDS
# ==========
def ListBond(selection1, selection2, results=None, lenmin=None):
    command = 'ListBond '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    if (lenmin != None): command += 'LenMin=' + cstr(lenmin) + ','
    return list(runretval(command[:-1], True))


# LIST FLOATING ASSIGNMENTS (ALL OR SELECTED)
# ===========================================
def ListFloat(Type=None, format=None):
    command = 'ListFloat '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    return (runretval(command[:-1], True))


# LIST FLOATING ASSIGNMENTS (ALL)
# ===============================
def ListFloatAll(Type=None, format=None):
    command = 'ListFloatAll '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    return (runretval(command[:-1], True))


# LIST FLOATING ASSIGNMENTS (OBJECT)
# ==================================
def ListFloatObj(selection1, Type=None, format=None):
    command = 'ListFloatObj '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    return (runretval(command[:-1], True))


# LIST IMAGES
# ===========
def ListImage(selection1):
    command = 'ListImage '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# LIST RESTRAINTS AND ENERGIES (ALL OR SELECTED)
# ==============================================
def ListRest(Class=None, component=None, format=None, sort=None, dismin=None, dihmin=None, rdcmin=None,
             objectsmin=None):
    command = 'ListRest '
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    if (dismin != None): command += 'DisMin=' + cstr(dismin) + ','
    if (dihmin != None): command += 'DihMin=' + cstr(dihmin) + ','
    if (rdcmin != None): command += 'RDCMin=' + cstr(rdcmin) + ','
    if (objectsmin != None): command += 'ObjectsMin=' + cstr(objectsmin) + ','
    return (runretval(command[:-1], True))


# LIST RESTRAINTS AND ENERGIES (ALL)
# ==================================
def ListRestAll(Class=None, component=None, format=None, sort=None, dismin=None, dihmin=None, rdcmin=None,
                objectsmin=None):
    command = 'ListRestAll '
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    if (dismin != None): command += 'DisMin=' + cstr(dismin) + ','
    if (dihmin != None): command += 'DihMin=' + cstr(dihmin) + ','
    if (rdcmin != None): command += 'RDCMin=' + cstr(rdcmin) + ','
    if (objectsmin != None): command += 'ObjectsMin=' + cstr(objectsmin) + ','
    return (runretval(command[:-1], True))


# LIST RESTRAINTS AND ENERGIES (OBJECT)
# =====================================
def ListRestObj(selection1, Class=None, component=None, format=None, sort=None, dismin=None, dihmin=None, rdcmin=None,
                objectsmin=None):
    command = 'ListRestObj '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    if (dismin != None): command += 'DisMin=' + cstr(dismin) + ','
    if (dihmin != None): command += 'DihMin=' + cstr(dihmin) + ','
    if (rdcmin != None): command += 'RDCMin=' + cstr(rdcmin) + ','
    if (objectsmin != None): command += 'ObjectsMin=' + cstr(objectsmin) + ','
    return (runretval(command[:-1], True))


# LIST RESTRAINTS AND ENERGIES (MOLECULE)
# =======================================
def ListRestMol(selection1, Class=None, component=None, format=None, sort=None, dismin=None, dihmin=None, rdcmin=None,
                objectsmin=None):
    command = 'ListRestMol '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    if (dismin != None): command += 'DisMin=' + cstr(dismin) + ','
    if (dihmin != None): command += 'DihMin=' + cstr(dihmin) + ','
    if (rdcmin != None): command += 'RDCMin=' + cstr(rdcmin) + ','
    if (objectsmin != None): command += 'ObjectsMin=' + cstr(objectsmin) + ','
    return (runretval(command[:-1], True))


# LIST RESTRAINTS AND ENERGIES (RESIDUE)
# ======================================
def ListRestRes(selection1, Class=None, component=None, format=None, sort=None, dismin=None, dihmin=None, rdcmin=None,
                objectsmin=None):
    command = 'ListRestRes '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    if (dismin != None): command += 'DisMin=' + cstr(dismin) + ','
    if (dihmin != None): command += 'DihMin=' + cstr(dihmin) + ','
    if (rdcmin != None): command += 'RDCMin=' + cstr(rdcmin) + ','
    if (objectsmin != None): command += 'ObjectsMin=' + cstr(objectsmin) + ','
    return (runretval(command[:-1], True))


# LIST RESTRAINTS AND ENERGIES (ATOM)
# ===================================
def ListRestAtom(selection1, Class=None, component=None, format=None, sort=None, dismin=None, dihmin=None, rdcmin=None,
                 objectsmin=None):
    command = 'ListRestAtom '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    if (sort != None): command += 'Sort=' + cstr(sort) + ','
    if (dismin != None): command += 'DisMin=' + cstr(dismin) + ','
    if (dihmin != None): command += 'DihMin=' + cstr(dihmin) + ','
    if (rdcmin != None): command += 'RDCMin=' + cstr(rdcmin) + ','
    if (objectsmin != None): command += 'ObjectsMin=' + cstr(objectsmin) + ','
    return (runretval(command[:-1], True))


# LIST ATOMS MATCHING SMARTS STRING
# =================================
def ListSMARTS(string, selection1=None):
    command = 'ListSMARTS '
    command += 'String=' + cstr(string) + ','
    if (selection1 != None): command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# LIST ATOMS MATCHING SMILES STRING
# =================================
def ListSMILES(string, selection1=None):
    command = 'ListSMILES '
    command += 'String=' + cstr(string) + ','
    if (selection1 != None): command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# LIST SELECTION (OBJECT)
# =======================
def ListObj(selection1, format=None, compress=None):
    command = 'ListObj '
    command += selstr(selection1) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    if (compress != None): command += 'Compress=' + cstr(compress) + ','
    return (runretval(command[:-1], True))


# LIST SELECTION (MOLECULE)
# =========================
def ListMol(selection1, format=None, compress=None):
    command = 'ListMol '
    command += selstr(selection1) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    if (compress != None): command += 'Compress=' + cstr(compress) + ','
    return (runretval(command[:-1], True))


# LIST SELECTION (RESIDUE)
# ========================
def ListRes(selection1, format=None, compress=None):
    command = 'ListRes '
    command += selstr(selection1) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    if (compress != None): command += 'Compress=' + cstr(compress) + ','
    return (runretval(command[:-1], True))


# LIST SELECTION (ATOM)
# =====================
def ListAtom(selection1, format=None, compress=None):
    """
    Returns an array of atoms within a particular selection.

    Notes:
        * By default, only the YASARA atom IDs are returned. To change the amount of information
          returned for each at, see the in-program help by running a ``Help Label`` from the YASARA console.
        * See also ``yapycon_reformat_bondinfo_returned()`` for a convenience function to handle the return 
          value of List functions.
        * For more details on the parameters please do a ``Help ListAtom`` from within the YASARA console.
          
    :param selection1: A YASARA query expression.
    :type selection1: str
    :param format: A string containing specific attribute names to return. Returned values will conform to this 
                   string *as strictly as possible*. For example, ``"ATOMNUM,    ATOMELEMENT"`` will result in a return
                   value of ``128,    O`` (notice the exact number of spaces). For more information about the 
                   attributes accepted in ``format`` please run a ``Help Label`` from the YASARA console.
                   The attributes supported as of version 21.8.26 are: ``OBJNAME, OBJNUM, COMPOUND, MOLNAME, SEGNAME, 
                   RES, RESNAME, RESName, RESNAME1, RESNUM, RESNUMWIC, ATOMNAME, ATOMNAMEPDB, ATOMNAMEPDB3, 
                   ATOMNAMEIUPAC, ATOMNAMEXPLOR, ATOMNUM, ATOMELEMENT, ATOMElement, ATOMTYPE, CHARGE, CHIRALITYLD``
    :type format: str
    :param compress: Either "Yes" or "No", whether to apply a type of run-length compression to the returned results.
                     For more detailed information, please run a ``Help ListAtom`` from the YASARA console.
    :type compress: str
    """
    command = 'ListAtom '
    command += selstr(selection1) + ','

    if (format != None):
        command += 'Format=' + cstr(format) + ','

    if (compress != None):
        command += 'Compress=' + cstr(compress) + ','
        
    return list(runretval(command[:-1], True))


# SET LONG RANGE INTERACTIONS
# ===========================
def Longrange(Type):
    command = 'Longrange '
    command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CREATE EMPTY IMAGE
# ==================
def MakeImage(name, width=None, height=None, topcol=None, bottomcol=None):
    command = 'MakeImage '
    command += 'Name=' + cstr(name) + ','
    if (width != None): command += 'Width=' + cstr(width) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (topcol != None): command += 'TopCol=' + cstr(topcol) + ','
    if (bottomcol != None): command += 'BottomCol=' + cstr(bottomcol) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# CREATE OBJECT WITH ATTACHED IMAGE
# =================================
def MakeImageObj(name, selection1, width=None, height=None, depth=None):
    command = 'MakeImageObj '
    command += 'Name=' + cstr(name) + ','
    command += selstr(selection1) + ','
    if (width != None): command += 'Width=' + cstr(width) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (depth != None): command += 'Depth=' + cstr(depth) + ','
    return (runretval(command[:-1], True))


# MAKE A TABLE
# ============
def MakeTab(name, dimensions=None, columns=None, rows=None, pages=None):
    command = 'MakeTab '
    command += 'Name=' + cstr(name) + ','
    if (dimensions != None): command += 'Dimensions=' + cstr(dimensions) + ','
    if (columns != None): command += 'Columns=' + cstr(columns) + ','
    if (rows != None): command += 'Rows=' + cstr(rows) + ','
    if (pages != None): command += 'Pages=' + cstr(pages) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# MAKE TEXT OBJECT TO PRINT 3D LETTERS
# ====================================
def MakeTextObj(name=None, width=None, height=None):
    command = 'MakeTextObj '
    if (name != None): command += 'Name=' + cstr(name) + ','
    if (width != None): command += 'Width=' + cstr(width) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# CREATE AN EMPTY SECONDARY WINDOW
# ================================
def MakeWin(width=None, height=None, screen=None, fullscreen=None, topcol=None, bottomcol=None):
    command = 'MakeWin '
    if (width != None): command += 'Width=' + cstr(width) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (screen != None): command += 'Screen=' + cstr(screen) + ','
    if (fullscreen != None): command += 'FullScreen=' + cstr(fullscreen) + ','
    if (topcol != None): command += 'TopCol=' + cstr(topcol) + ','
    if (bottomcol != None): command += 'BottomCol=' + cstr(bottomcol) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOMS MARKED WITH FIREFLIES
# ===================================
def MarkAtom(selection1=None, selection2=None, selection3=None, selection4=None, zoom=None):
    command = 'MarkAtom '
    if (selection1 != None): command += selstr(selection1) + ','
    if (selection2 != None): command += selstr(selection2) + ','
    if (selection3 != None): command += selstr(selection3) + ','
    if (selection4 != None): command += selstr(selection4) + ','
    if (zoom != None): command += 'Zoom=' + cstr(zoom) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOMS MARKED WITH FIREFLIES
# ===================================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def MarkAtomNone():
    command = 'MarkAtom None,'
    return (runretval(command[:-1], True))


# CALCULATE MASS (ALL OR SELECTED)
# ================================
def Mass():
    command = 'Mass '
    return (runretval(command[:-1], True))


# CALCULATE MASS (ALL)
# ====================
def MassAll():
    command = 'MassAll '
    return (runretval(command[:-1], True))


# CALCULATE MASS (OBJECT)
# =======================
def MassObj(selection1):
    command = 'MassObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# CALCULATE MASS (MOLECULE)
# =========================
def MassMol(selection1):
    command = 'MassMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# CALCULATE MASS (RESIDUE)
# ========================
def MassRes(selection1):
    command = 'MassRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# CALCULATE MASS (ATOM)
# =====================
def MassAtom(selection1):
    command = 'MassAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SET MEMORY USAGE AND EXIT
# =========================
def Memory(size):
    command = 'Memory '
    command += 'Size=' + cstr(size) + ','
    return (runretval(command[:-1], True))


# SWITCH MENU ON/OFF
# ==================
def Menu(flag):
    command = 'Menu '
    command += 'Flag=' + cstr(flag) + ','
    return (runretval(command[:-1], True))


# MOVE POLYGON MESH
# =================
def MoveMesh(selection1, x=None, y=None, z=None):
    command = 'MoveMesh '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# MOVE ATOMS, OBJECTS OR THE SCENE (ALL OR SELECTED)
# ==================================================
def Move(x=None, y=None, z=None):
    command = 'Move '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# MOVE ATOMS, OBJECTS OR THE SCENE (ALL)
# ======================================
def MoveAll(x=None, y=None, z=None):
    command = 'MoveAll '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# MOVE ATOMS, OBJECTS OR THE SCENE (OBJECT)
# =========================================
def MoveObj(selection1, x=None, y=None, z=None):
    command = 'MoveObj '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# MOVE ATOMS, OBJECTS OR THE SCENE (MOLECULE)
# ===========================================
def MoveMol(selection1, x=None, y=None, z=None):
    command = 'MoveMol '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# MOVE ATOMS, OBJECTS OR THE SCENE (RESIDUE)
# ==========================================
def MoveRes(selection1, x=None, y=None, z=None):
    command = 'MoveRes '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# MOVE ATOMS, OBJECTS OR THE SCENE (ATOM)
# =======================================
def MoveAtom(selection1, x=None, y=None, z=None):
    command = 'MoveAtom '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET ENERGY MINIMIZATION STEP
# ============================
def MinStep(size):
    command = 'MinStep '
    command += 'Size=' + cstr(size) + ','
    return (runretval(command[:-1], True))


# CONVERT RESIDUE NAMES FROM 1- TO 3-LETTER CODE
# ==============================================
def Name3(sequence):
    command = 'Name3 '
    command += 'Sequence=' + cstr(sequence) + ','
    return (runretval(command[:-1], True))


# RENAME FILE
# ===========
def RenameFile(srcfilename=None, dstfilename=None, overwrite=None):
    command = 'RenameFile '
    if (srcfilename != None): command += 'SrcFilename=' + cstr(srcfilename) + ','
    if (dstfilename != None): command += 'DstFilename=' + cstr(dstfilename) + ','
    if (overwrite != None): command += 'Overwrite=' + cstr(overwrite) + ','
    return (runretval(command[:-1], True))


# SET/GET NAMES OF OBJECTS, SEGMENTS, MOLECULES, RESIDUES AND ATOMS (OBJECT)
# ==========================================================================
def NameObj(selection1, name=None):
    command = 'NameObj '
    command += selstr(selection1) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# SET/GET NAMES OF OBJECTS, SEGMENTS, MOLECULES, RESIDUES AND ATOMS (MOLECULE)
# ============================================================================
def NameMol(selection1, name=None):
    command = 'NameMol '
    command += selstr(selection1) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# SET/GET NAMES OF OBJECTS, SEGMENTS, MOLECULES, RESIDUES AND ATOMS (SEGMENT)
# ===========================================================================
def NameSeg(selection1, name=None):
    command = 'NameSeg '
    command += selstr(selection1) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# SET/GET NAMES OF OBJECTS, SEGMENTS, MOLECULES, RESIDUES AND ATOMS (RESIDUE)
# ===========================================================================
def NameRes(selection1, name=None):
    command = 'NameRes '
    command += selstr(selection1) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# SET/GET NAMES OF OBJECTS, SEGMENTS, MOLECULES, RESIDUES AND ATOMS (ATOM)
# ========================================================================
def NameAtom(selection1, name=None):
    command = 'NameAtom '
    command += selstr(selection1) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# ORIENT OBJECTS NICELY (ALL OR SELECTED)
# =======================================
def NiceOri(axis1=None, axis2=None):
    command = 'NiceOri '
    if (axis1 != None): command += 'Axis1=' + cstr(axis1) + ','
    if (axis2 != None): command += 'Axis2=' + cstr(axis2) + ','
    return (runretval(command[:-1], True))


# ORIENT OBJECTS NICELY (ALL)
# ===========================
def NiceOriAll(axis1=None, axis2=None):
    command = 'NiceOriAll '
    if (axis1 != None): command += 'Axis1=' + cstr(axis1) + ','
    if (axis2 != None): command += 'Axis2=' + cstr(axis2) + ','
    return (runretval(command[:-1], True))


# ORIENT OBJECTS NICELY (OBJECT)
# ==============================
def NiceOriObj(selection1, axis1=None, axis2=None):
    command = 'NiceOriObj '
    command += selstr(selection1) + ','
    if (axis1 != None): command += 'Axis1=' + cstr(axis1) + ','
    if (axis2 != None): command += 'Axis2=' + cstr(axis2) + ','
    return (runretval(command[:-1], True))


# SET/GET THE OCCUPANCY (ALL OR SELECTED)
# =======================================
def Occup(value=None):
    command = 'Occup '
    if (value != None): command += 'Value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE OCCUPANCY (ALL)
# ===========================
def OccupAll(value=None):
    command = 'OccupAll '
    if (value != None): command += 'Value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE OCCUPANCY (OBJECT)
# ==============================
def OccupObj(selection1, value=None):
    command = 'OccupObj '
    command += selstr(selection1) + ','
    if (value != None): command += 'Value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE OCCUPANCY (MOLECULE)
# ================================
def OccupMol(selection1, value=None):
    command = 'OccupMol '
    command += selstr(selection1) + ','
    if (value != None): command += 'Value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE OCCUPANCY (RESIDUE)
# ===============================
def OccupRes(selection1, value=None):
    command = 'OccupRes '
    command += selstr(selection1) + ','
    if (value != None): command += 'Value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE OCCUPANCY (ATOM)
# ============================
def OccupAtom(selection1, value=None):
    command = 'OccupAtom '
    command += selstr(selection1) + ','
    if (value != None): command += 'Value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# OLIGOMERIZE OBJECTS TO GENERATE THE BIOLOGICALLY ACTIVE FORM (ALL OR SELECTED)
# ==============================================================================
def Oligomerize(center=None, instance=None):
    command = 'Oligomerize '
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (instance != None): command += 'Instance=' + cstr(instance) + ','
    return (runretval(command[:-1], True))


# OLIGOMERIZE OBJECTS TO GENERATE THE BIOLOGICALLY ACTIVE FORM (ALL)
# ==================================================================
def OligomerizeAll(center=None, instance=None):
    command = 'OligomerizeAll '
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (instance != None): command += 'Instance=' + cstr(instance) + ','
    return (runretval(command[:-1], True))


# OLIGOMERIZE OBJECTS TO GENERATE THE BIOLOGICALLY ACTIVE FORM (OBJECT)
# =====================================================================
def OligomerizeObj(selection1, center=None, instance=None):
    command = 'OligomerizeObj '
    command += selstr(selection1) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (instance != None): command += 'Instance=' + cstr(instance) + ','
    return (runretval(command[:-1], True))


# SET ERROR ACTION
# ================
def OnError(action):
    command = 'OnError '
    command += 'Action=' + cstr(action) + ','
    return (runretval(command[:-1], True))


# OPTIMIZE HYDROGEN BONDING NETWORK (ALL OR SELECTED)
# ===================================================
def OptHyd(method):
    command = 'OptHyd '
    command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# OPTIMIZE HYDROGEN BONDING NETWORK (ALL)
# =======================================
def OptHydAll(method):
    command = 'OptHydAll '
    command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# OPTIMIZE HYDROGEN BONDING NETWORK (OBJECT)
# ==========================================
def OptHydObj(selection1, method):
    command = 'OptHydObj '
    command += selstr(selection1) + ','
    command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# OPTIMIZE CENTRAL OR TERMINAL LOOP
# =================================
def OptimizeLoop(selection1, selection2, samples=None, secstr=None):
    command = 'OptimizeLoop '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (samples != None): command += 'Samples=' + cstr(samples) + ','
    if (secstr != None): command += 'SecStr=' + cstr(secstr) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# OPTIMIZE MOLECULAR GEOMETRY (ALL OR SELECTED)
# =============================================
def Optimize(method=None, structures=None):
    command = 'Optimize '
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (structures != None): command += 'Structures=' + cstr(structures) + ','
    return (runretval(command[:-1], True))


# OPTIMIZE MOLECULAR GEOMETRY (ALL)
# =================================
def OptimizeAll(method=None, structures=None):
    command = 'OptimizeAll '
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (structures != None): command += 'Structures=' + cstr(structures) + ','
    return (runretval(command[:-1], True))


# OPTIMIZE MOLECULAR GEOMETRY (OBJECT)
# ====================================
def OptimizeObj(selection1, method=None, structures=None):
    command = 'OptimizeObj '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (structures != None): command += 'Structures=' + cstr(structures) + ','
    return (runretval(command[:-1], True))


# OPTIMIZE MOLECULAR GEOMETRY (MOLECULE)
# ======================================
def OptimizeMol(selection1, method=None, structures=None):
    command = 'OptimizeMol '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (structures != None): command += 'Structures=' + cstr(structures) + ','
    return (runretval(command[:-1], True))


# OPTIMIZE MOLECULAR GEOMETRY (RESIDUE)
# =====================================
def OptimizeRes(selection1, method=None, structures=None):
    command = 'OptimizeRes '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (structures != None): command += 'Structures=' + cstr(structures) + ','
    return (runretval(command[:-1], True))


# GET VECTOR ORIENTATION
# ======================
def OriVec(x1=None, y1=None, z1=None, x2=None, y2=None, z2=None):
    command = 'OriVec '
    if (x1 != None): command += 'X1=' + cstr(x1) + ','
    if (y1 != None): command += 'Y1=' + cstr(y1) + ','
    if (z1 != None): command += 'Z1=' + cstr(z1) + ','
    if (x2 != None): command += 'X2=' + cstr(x2) + ','
    if (y2 != None): command += 'Y2=' + cstr(y2) + ','
    if (z2 != None): command += 'Z2=' + cstr(z2) + ','
    return (runretval(command[:-1], True))


# SET/GET OBJECT OR SCENE ORIENTATION (ALL OR SELECTED)
# =====================================================
def Ori(alpha=None, beta=None, gamma=None):
    command = 'Ori '
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (beta != None): command += 'Beta=' + cstr(beta) + ','
    if (gamma != None): command += 'Gamma=' + cstr(gamma) + ','
    return (runretval(command[:-1], True))


# SET/GET OBJECT OR SCENE ORIENTATION (ALL)
# =========================================
def OriAll(alpha=None, beta=None, gamma=None):
    command = 'OriAll '
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (beta != None): command += 'Beta=' + cstr(beta) + ','
    if (gamma != None): command += 'Gamma=' + cstr(gamma) + ','
    return (runretval(command[:-1], True))


# SET/GET OBJECT OR SCENE ORIENTATION (OBJECT)
# ============================================
def OriObj(selection1, alpha=None, beta=None, gamma=None):
    command = 'OriObj '
    command += selstr(selection1) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (beta != None): command += 'Beta=' + cstr(beta) + ','
    if (gamma != None): command += 'Gamma=' + cstr(gamma) + ','
    return (runretval(command[:-1], True))


# SET PERMISSIONS OF THE YASARA INSTALL DIRECTORY
# ===============================================
def PermitAccess():
    command = 'PermitAccess '
    return (runretval(command[:-1], True))


# SET/GET DEFAULT PH
# ==================
def pH(value=None, update=None):
    command = 'pH '
    if (value != None): command += 'Value=' + cstr(value) + ','
    if (update != None): command += 'update=' + cstr(update) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SET/GET RESIDUE PKA
# ===================
def pKaRes(selection1, value=None):
    command = 'pKaRes '
    command += selstr(selection1) + ','
    if (value != None): command += 'value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# PLAY BACK MACRO
# ===============
def PlayMacro(filename, label, onstartup=None):
    command = 'PlayMacro '
    command += 'Filename=' + cstr(filename) + ','
    command += 'Label=' + cstr(label) + ','
    if (onstartup != None): command += 'OnStartup=' + cstr(onstartup) + ','
    return (runretval(command[:-1], True))


# SET STYLE OF MOUSE POINTER
# ==========================
def PointerStyle(Type=None):
    command = 'PointerStyle '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# SET POINT AND LINE RADIUS AND PLASTICITY IN WIRE FRAMES
# =======================================================
def PointPar(radius=None, plastic=None):
    command = 'PointPar '
    if (radius != None): command += 'Radius=' + cstr(radius) + ','
    if (plastic != None): command += 'plastic=' + cstr(plastic) + ','
    return (runretval(command[:-1], True))


# SET/GET POLYGON SMOOTHNESS AND REFLECTIVITY
# ===========================================
def PolygonPar(smoothness=None, reflection=None):
    command = 'PolygonPar '
    if (smoothness != None): command += 'Smoothness=' + cstr(smoothness) + ','
    if (reflection != None): command += 'Reflection=' + cstr(reflection) + ','
    return (runretval(command[:-1], True))


# POLYMERIZE OBJECTS
# ==================
def Polymerize(selection1, selection2, copies=None, dihedral=None):
    command = 'Polymerize '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (copies != None): command += 'Copies=' + cstr(copies) + ','
    if (dihedral != None): command += 'Dihedral=' + cstr(dihedral) + ','
    return (runretval(command[:-1], True))


# POSITION AND JUSTIFY TEXT
# =========================
def PosText(x=None, y=None, justify=None):
    command = 'PosText '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (justify != None): command += 'justify=' + cstr(justify) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM POSITIONS (MOLECULE)
# =================================
def PosMol(selection1, x=None, y=None, z=None, coordsys=None, mean=None):
    command = 'PosMol '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (coordsys != None): command += 'CoordSys=' + cstr(coordsys) + ','
    if (mean != None): command += 'Mean=' + cstr(mean) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM POSITIONS (RESIDUE)
# ================================
def PosRes(selection1, x=None, y=None, z=None, coordsys=None, mean=None):
    command = 'PosRes '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (coordsys != None): command += 'CoordSys=' + cstr(coordsys) + ','
    if (mean != None): command += 'Mean=' + cstr(mean) + ','
    return (runretval(command[:-1], True))


# SET/GET ATOM POSITIONS (ATOM)
# =============================
def PosAtom(selection1, x=None, y=None, z=None, coordsys=None, mean=None):
    command = 'PosAtom '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (coordsys != None): command += 'CoordSys=' + cstr(coordsys) + ','
    if (mean != None): command += 'Mean=' + cstr(mean) + ','
    return (runretval(command[:-1], True))


# SET/GET OBJECT OR SCENE POSITION AND ORIENTATION (ALL OR SELECTED)
# ==================================================================
def PosOri(x=None, y=None, z=None, alpha=None, beta=None, gamma=None):
    command = 'PosOri '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (beta != None): command += 'Beta=' + cstr(beta) + ','
    if (gamma != None): command += 'Gamma=' + cstr(gamma) + ','
    return (runretval(command[:-1], True))


# SET/GET OBJECT OR SCENE POSITION AND ORIENTATION (ALL)
# ======================================================
def PosOriAll(x=None, y=None, z=None, alpha=None, beta=None, gamma=None):
    command = 'PosOriAll '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (beta != None): command += 'Beta=' + cstr(beta) + ','
    if (gamma != None): command += 'Gamma=' + cstr(gamma) + ','
    return (runretval(command[:-1], True))


# SET/GET OBJECT OR SCENE POSITION AND ORIENTATION (OBJECT)
# =========================================================
def PosOriObj(selection1, x=None, y=None, z=None, alpha=None, beta=None, gamma=None):
    command = 'PosOriObj '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (beta != None): command += 'Beta=' + cstr(beta) + ','
    if (gamma != None): command += 'Gamma=' + cstr(gamma) + ','
    return (runretval(command[:-1], True))


# SET/GET OBJECT OR SCENE POSITION (ALL OR SELECTED)
# ==================================================
def Pos(x=None, y=None, z=None):
    command = 'Pos '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET OBJECT OR SCENE POSITION (ALL)
# ======================================
def PosAll(x=None, y=None, z=None):
    command = 'PosAll '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET OBJECT OR SCENE POSITION (OBJECT)
# =========================================
def PosObj(selection1, x=None, y=None, z=None):
    command = 'PosObj '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET PRESSURE CONTROL
# ====================
def PressureCtrl(Type, pressure=None, name=None, density=None, axis=None):
    command = 'PressureCtrl '
    command += 'Type=' + cstr(Type) + ','
    if (pressure != None): command += 'Pressure=' + cstr(pressure) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    if (density != None): command += 'Density=' + cstr(density) + ','
    if (axis != None): command += 'Axis=' + cstr(axis) + ','
    return (runretval(command[:-1], True))


# PRINT TEXT
# ==========
def Print(text, convert=None):
    command = 'Print '
    command += 'Text=' + cstr(text, 1) + ','
    if (convert != None): command += 'Convert=' + cstr(convert) + ','
    return (runretval(command[:-1], True))


# PRINT TO CONSOLE
# ================
def PrintCon():
    command = 'PrintCon '
    return (runretval(command[:-1], True))


# PRINT TO HEAD UP DISPLAY
# ========================
def PrintHUD():
    command = 'PrintHUD '
    return (runretval(command[:-1], True))


# PRINT TO IMAGE
# ==============
def PrintImage(selection1):
    command = 'PrintImage '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# PRINT TO TEXT OBJECT
# ====================
def PrintObj(selection1):
    command = 'PrintObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# PRINT TO SECONDARY WINDOW
# =========================
def PrintWin():
    command = 'PrintWin '
    return (runretval(command[:-1], True))


# SET/GET NUMBER OF PROCESSORS TO USE
# ===================================
def Processors(cputhreads=None, gpu=None):
    command = 'Processors '
    if (cputhreads != None): command += 'CPUThreads=' + cstr(cputhreads) + ','
    if (gpu != None): command += 'GPU=' + cstr(gpu) + ','
    return (runretval(command[:-1], True))


# SET PERSPECTIVE OR PARALLEL PROJECTION
# ======================================
def Projection(Type):
    command = 'Projection '
    command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# SET/GET THE PROPERTY VALUE (ALL OR SELECTED)
# ============================================
def Prop(value=None):
    command = 'Prop '
    if (value != None): command += 'value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE PROPERTY VALUE (ALL)
# ================================
def PropAll(value=None):
    command = 'PropAll '
    if (value != None): command += 'value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE PROPERTY VALUE (OBJECT)
# ===================================
def PropObj(selection1, value=None):
    command = 'PropObj '
    command += selstr(selection1) + ','
    if (value != None): command += 'value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE PROPERTY VALUE (MOLECULE)
# =====================================
def PropMol(selection1, value=None):
    command = 'PropMol '
    command += selstr(selection1) + ','
    if (value != None): command += 'value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE PROPERTY VALUE (RESIDUE)
# ====================================
def PropRes(selection1, value=None):
    command = 'PropRes '
    command += selstr(selection1) + ','
    if (value != None): command += 'value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET THE PROPERTY VALUE (ATOM)
# =================================
def PropAtom(selection1, value=None):
    command = 'PropAtom '
    command += selstr(selection1) + ','
    if (value != None): command += 'value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# PRINT WORKING DIRECTORY
# =======================
def PWD():
    command = 'PWD '
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SET QUANTUM MECHANICS METHOD
# ============================
def QuantumMechanics(method):
    command = 'QuantumMechanics '
    command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# CALCULATE THE RADIUS (ALL OR SELECTED)
# ======================================
def Radius(center=None, Type=None):
    command = 'Radius '
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE THE RADIUS (ALL)
# ==========================
def RadiusAll(center=None, Type=None):
    command = 'RadiusAll '
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE THE RADIUS (OBJECT)
# =============================
def RadiusObj(selection1, center=None, Type=None):
    command = 'RadiusObj '
    command += selstr(selection1) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE THE RADIUS (MOLECULE)
# ===============================
def RadiusMol(selection1, center=None, Type=None):
    command = 'RadiusMol '
    command += selstr(selection1) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE THE RADIUS (RESIDUE)
# ==============================
def RadiusRes(selection1, center=None, Type=None):
    command = 'RadiusRes '
    command += selstr(selection1) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE THE RADIUS (ATOM)
# ===========================
def RadiusAtom(selection1, center=None, Type=None):
    command = 'RadiusAtom '
    command += selstr(selection1) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# DISPLAY ERROR MESSAGE
# =====================
def RaiseError(text=None):
    command = 'RaiseError '
    if (text != None): command += 'Text=' + cstr(text, 1) + ','
    return (runretval(command[:-1], True))


# CREATE RAYTRACED SCREENSHOT USING POVRAY
# ========================================
def RayTrace(filename, x=None, y=None, 
             zoom=None, atoms=None, labelshadow=None, 
             secalpha=None, display=None,
             outline=None, background=None):
    """
    Creates a raytraced screenshot of the current YASARA scene via POVRay.

    Notes:
        * More details about POVRay are available `here <https://www.povray.org/>`_
        * The side effect of this command is very similar to ``SavePNG()``, only that the
          "screenshot" is produced via a different means.
        * Similarly to ``SavePNG()``, the raytraced image is returned in YaPyCon as a
          numpy array.

    :param filename: The filename to save the screenshot to (relative to ``workdir``).
    :type filename: str(path).
    :param x: The desired width of the raytraced image
    :type x: int
    :param y: The desired height of the raytraced image
    :type y: int
    :param zoom: The "ball zoom" factor (Please see ``Help Raytrace`` from the YASARA Console)
    :type zoom: float
    :param atoms: Either "Balls" or "Blobs", what sort of POVRay primitive to use to represent the atoms.
    :type atoms: str
    :param labelshadow: Either "Yes" or "No", determines whether text elements cast shadows.
    :type labelshadow: str
    :param secalpha: The secondary structure alpha blending factor as a percentage (%).
    :type secalpha: float
    :param display: Either "On" or "Off", determines whether to show the POVRay window during raytracing or not.
    :type display": str
    :param outline: Radius of "comic outline" in Angstrom
    :type outline: float
    :param background: Either "On" or "Off", determines whether to leave the background transparent or not.
    :type background: str
    """
    command = 'RayTrace '
    command += 'Filename=' + cstr(filename) + ','
    if x is not None: 
        command += 'X=' + cstr(x) + ','
    if y is not None: 
        command += 'Y=' + cstr(y) + ','
    if zoom is not None: 
        command += 'zoom=' + cstr(zoom) + ','
    if atoms is not None: 
        command += 'Atoms=' + cstr(atoms) + ','
    if labelshadow is not None: 
        command += 'LabelShadow=' + cstr(labelshadow) + ','
    if secalpha is not None: 
        command += 'SecAlpha=' + cstr(secalpha) + ','
    if display is not None: 
        command += 'Display=' + cstr(display) + ','
    if outline is not None: 
        command += 'Outline=' + cstr(outline) + ','
    if background is not None: 
        command += 'Background=' + cstr(background) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    command_result = runretval(command[:-1], 1)

    return yapycon_access_image_returned(filename, command_result)


# CALCULATE RADIAL DISTRIBUTION FUNCTION
# ======================================
def RDF(normbins=None):
    command = 'RDF '
    if (normbins != None): command += 'NormBins=' + cstr(normbins) + ','
    return (runretval(command[:-1], True))


# RECORD ALL CONSOLE OUTPUT IN A LOG FILE
# =======================================
def RecordLog(filename, append=None):
    command = 'RecordLog '
    command += 'Filename=' + cstr(filename) + ','
    if (append != None): command += 'append=' + cstr(append) + ','
    return (runretval(command[:-1], True))


# REGULARIZE COVALENT GEOMETRY (ALL OR SELECTED)
# ==============================================
def Regularize(sigmas=None):
    command = 'Regularize '
    if (sigmas != None): command += 'Sigmas=' + cstr(sigmas) + ','
    return (runretval(command[:-1], True))


# REGULARIZE COVALENT GEOMETRY (ALL)
# ==================================
def RegularizeAll(sigmas=None):
    command = 'RegularizeAll '
    if (sigmas != None): command += 'Sigmas=' + cstr(sigmas) + ','
    return (runretval(command[:-1], True))


# REGULARIZE COVALENT GEOMETRY (OBJECT)
# =====================================
def RegularizeObj(selection1, sigmas=None):
    command = 'RegularizeObj '
    command += selstr(selection1) + ','
    if (sigmas != None): command += 'Sigmas=' + cstr(sigmas) + ','
    return (runretval(command[:-1], True))


# REMOVE FROM ENVIRONMENT FOR SURFACE CALCULATIONS (ALL OR SELECTED)
# ==================================================================
def RemoveEnv():
    command = 'RemoveEnv '
    return (runretval(command[:-1], True))


# REMOVE FROM ENVIRONMENT FOR SURFACE CALCULATIONS (ALL)
# ======================================================
def RemoveEnvAll():
    command = 'RemoveEnvAll '
    return (runretval(command[:-1], True))


# REMOVE FROM ENVIRONMENT FOR SURFACE CALCULATIONS (OBJECT)
# =========================================================
def RemoveEnvObj(selection1):
    command = 'RemoveEnvObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# REMOVE FROM ENVIRONMENT FOR SURFACE CALCULATIONS (MOLECULE)
# ===========================================================
def RemoveEnvMol(selection1):
    command = 'RemoveEnvMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# REMOVE FROM ENVIRONMENT FOR SURFACE CALCULATIONS (RESIDUE)
# ==========================================================
def RemoveEnvRes(selection1):
    command = 'RemoveEnvRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# REMOVE FROM ENVIRONMENT FOR SURFACE CALCULATIONS (ATOM)
# =======================================================
def RemoveEnvAtom(selection1):
    command = 'RemoveEnvAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# REMOVE OBJECTS FROM THE SOUP (ALL OR SELECTED)
# ==============================================
def Remove():
    command = 'Remove '
    return (runretval(command[:-1], True))


# REMOVE OBJECTS FROM THE SOUP (ALL)
# ==================================
def RemoveAll():
    command = 'RemoveAll '
    return (runretval(command[:-1], True))


# REMOVE OBJECTS FROM THE SOUP (OBJECT)
# =====================================
def RemoveObj(selection1):
    command = 'RemoveObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# PREDICT SECONDARY STRUCTURE (ALL OR SELECTED)
# =============================================
def PredSecStr(method=None):
    command = 'PredSecStr '
    if (method != None): command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# PREDICT SECONDARY STRUCTURE (ALL)
# =================================
def PredSecStrAll(method=None):
    command = 'PredSecStrAll '
    if (method != None): command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# PREDICT SECONDARY STRUCTURE (OBJECT)
# ====================================
def PredSecStrObj(selection1, method=None):
    command = 'PredSecStrObj '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# PREDICT SECONDARY STRUCTURE (MOLECULE)
# ======================================
def PredSecStrMol(selection1, method=None):
    command = 'PredSecStrMol '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# PREDICT SECONDARY STRUCTURE (RESIDUE)
# =====================================
def PredSecStrRes(selection1, method=None):
    command = 'PredSecStrRes '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# SET YANACONDA RANDOM NUMBER SEED
# ================================
def RandomSeed(number):
    command = 'RandomSeed '
    command += 'Number=' + cstr(number) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SET/GET RENDERING LIBRARY AND GPU
# =================================
def Renderer(library=None, gpu=None):
    command = 'Renderer '
    if (library != None): command += 'Library=' + cstr(library) + ','
    if (gpu != None): command += 'GPU=' + cstr(gpu) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# NUMBER OBJECTS (ALL OR SELECTED)
# ================================
def Number(first=None):
    command = 'Number '
    if (first != None): command += 'first=' + cstr(first) + ','
    return (runretval(command[:-1], True))


# NUMBER OBJECTS (ALL)
# ====================
def NumberAll(first=None):
    command = 'NumberAll '
    if (first != None): command += 'first=' + cstr(first) + ','
    return (runretval(command[:-1], True))


# NUMBER OBJECTS (OBJECT)
# =======================
def NumberObj(selection1, first=None):
    command = 'NumberObj '
    command += selstr(selection1) + ','
    if (first != None): command += 'first=' + cstr(first) + ','
    return (runretval(command[:-1], True))


# NUMBER RESIDUES
# ===============
def NumberRes(selection1, first=None, inscode=None, increment=None):
    command = 'NumberRes '
    command += selstr(selection1) + ','
    if (first != None): command += 'First=' + cstr(first) + ','
    if (inscode != None): command += 'InsCode=' + cstr(inscode) + ','
    if (increment != None): command += 'Increment=' + cstr(increment) + ','
    return (runretval(command[:-1], True))


# NUMBER ATOMS
# ============
def NumberAtom(selection1, first=None):
    command = 'NumberAtom '
    command += selstr(selection1) + ','
    if (first != None): command += 'First=' + cstr(first) + ','
    return (runretval(command[:-1], True))


# SET/GET KEYBOARD REPEAT RATE
# ============================
def RepeatKey(delay=None, interval=None):
    command = 'RepeatKey '
    if (delay != None): command += 'Delay=' + cstr(delay) + ','
    if (interval != None): command += 'Interval=' + cstr(interval) + ','
    return (runretval(command[:-1], True))


# REPLACE RESIDUES
# ================
def ReplaceRes(selection1, selection2, superpose=None, addbonds=None, renumberres=None, renamemol=None):
    command = 'ReplaceRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (superpose != None): command += 'Superpose=' + cstr(superpose) + ','
    if (addbonds != None): command += 'AddBonds=' + cstr(addbonds) + ','
    if (renumberres != None): command += 'RenumberRes=' + cstr(renumberres) + ','
    if (renamemol != None): command += 'RenameMol=' + cstr(renamemol) + ','
    return (runretval(command[:-1], True))


# SET/GET OBJECT X-RAY RESOLUTION (ALL OR SELECTED)
# =================================================
def Resolution(value=None):
    command = 'Resolution '
    if (value != None): command += 'Value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET OBJECT X-RAY RESOLUTION (ALL)
# =====================================
def ResolutionAll(value=None):
    command = 'ResolutionAll '
    if (value != None): command += 'Value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# SET/GET OBJECT X-RAY RESOLUTION (OBJECT)
# ========================================
def ResolutionObj(selection1, value=None):
    command = 'ResolutionObj '
    command += selstr(selection1) + ','
    if (value != None): command += 'Value=' + cstr(value) + ','
    return (runretval(command[:-1], True))


# INTRODUCE FRACTIONAL BOND ORDERS
# ================================
def ResonateBond(selection1, selection2):
    command = 'ResonateBond '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    return (runretval(command[:-1], True))


# CALCULATE RESTRAINT ENERGIES (ALL OR SELECTED)
# ==============================================
def RestEnergy(component=None):
    command = 'RestEnergy '
    if (component != None): command += 'Component=' + cstr(component) + ','
    return (runretval(command[:-1], True))


# CALCULATE RESTRAINT ENERGIES (ALL)
# ==================================
def RestEnergyAll(component=None):
    command = 'RestEnergyAll '
    if (component != None): command += 'Component=' + cstr(component) + ','
    return (runretval(command[:-1], True))


# CALCULATE RESTRAINT ENERGIES (OBJECT)
# =====================================
def RestEnergyObj(selection1, component=None):
    command = 'RestEnergyObj '
    command += selstr(selection1) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    return (runretval(command[:-1], True))


# GET RESTRAINT VIOLATION STATISTICS (ALL OR SELECTED)
# ====================================================
def RestViol():
    command = 'RestViol '
    return (runretval(command[:-1], True))


# GET RESTRAINT VIOLATION STATISTICS (ALL)
# ========================================
def RestViolAll():
    command = 'RestViolAll '
    return (runretval(command[:-1], True))


# GET RESTRAINT VIOLATION STATISTICS (OBJECT)
# ===========================================
def RestViolObj(selection1):
    command = 'RestViolObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# RESTRAIN DISTANCE
# =================
def RestrainDis(selection1, selection2, Class, d, dminus, dplus):
    command = 'RestrainDis '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += 'Class=' + cstr(Class) + ','
    command += 'd=' + cstr(d) + ','
    command += 'dminus=' + cstr(dminus) + ','
    command += 'dplus=' + cstr(dplus) + ','
    return (runretval(command[:-1], True))


# RESTRAIN DIHEDRAL ANGLE
# =======================
def RestrainDih(selection1, selection2, selection3, selection4, Class, c, equil, delta, exponent=None):
    command = 'RestrainDih '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += selstr(selection3) + ','
    command += selstr(selection4) + ','
    command += 'Class=' + cstr(Class) + ','
    command += 'C=' + cstr(c) + ','
    command += 'Equil=' + cstr(equil) + ','
    command += 'Delta=' + cstr(delta) + ','
    if (exponent != None): command += 'Exponent=' + cstr(exponent) + ','
    return (runretval(command[:-1], True))


# SET/GET RESTRAINING PARAMETERS
# ==============================
def RestrainPar(average=None, ceil=None, dismin=None, monomers=None, joindis=None, floatgroups=None, showamb=None,
                periodic=None):
    command = 'RestrainPar '
    if (average != None): command += 'Average=' + cstr(average) + ','
    if (ceil != None): command += 'Ceil=' + cstr(ceil) + ','
    if (dismin != None): command += 'DisMin=' + cstr(dismin) + ','
    if (monomers != None): command += 'Monomers=' + cstr(monomers) + ','
    if (joindis != None): command += 'JoinDis=' + cstr(joindis) + ','
    if (floatgroups != None): command += 'FloatGroups=' + cstr(floatgroups) + ','
    if (showamb != None): command += 'ShowAmb=' + cstr(showamb) + ','
    if (periodic != None): command += 'Periodic=' + cstr(periodic) + ','
    return (runretval(command[:-1], True))


# SET/GET RESTRAINING POTENTIAL FUNCTIONS
# =======================================
def RestrainPot(name=None, sqconstant=None, sqoffset=None, sqexponent=None, rswitch=None, soexponent=None,
                asymptote=None, gamma=None, rdcforceconst=None, rdcerrorscale=None, update=None):
    command = 'RestrainPot '
    if (name != None): command += 'Name=' + cstr(name) + ','
    if (sqconstant != None): command += 'SqConstant=' + cstr(sqconstant) + ','
    if (sqoffset != None): command += 'SqOffset=' + cstr(sqoffset) + ','
    if (sqexponent != None): command += 'SqExponent=' + cstr(sqexponent) + ','
    if (rswitch != None): command += 'rSwitch=' + cstr(rswitch) + ','
    if (soexponent != None): command += 'SoExponent=' + cstr(soexponent) + ','
    if (asymptote != None): command += 'Asymptote=' + cstr(asymptote) + ','
    if (gamma != None): command += 'Gamma=' + cstr(gamma) + ','
    if (rdcforceconst != None): command += 'RDCForceConst=' + cstr(rdcforceconst) + ','
    if (rdcerrorscale != None): command += 'RDCErrorScale=' + cstr(rdcerrorscale) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    return (runretval(command[:-1], True))


# CALCULATE ROOT MEAN SQUARE FLUCTUATIONS AND B-FACTORS (MOLECULE)
# ================================================================
def RMSFMol(selection1, unit=None):
    command = 'RMSFMol '
    command += selstr(selection1) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE ROOT MEAN SQUARE FLUCTUATIONS AND B-FACTORS (RESIDUE)
# ===============================================================
def RMSFRes(selection1, unit=None):
    command = 'RMSFRes '
    command += selstr(selection1) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE ROOT MEAN SQUARE FLUCTUATIONS AND B-FACTORS (ATOM)
# ============================================================
def RMSFAtom(selection1, unit=None):
    command = 'RMSFAtom '
    command += selstr(selection1) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE RMSDS (OBJECT)
# ========================
def RMSDObj(selection1, selection2, match=None, flip=None, unit=None):
    command = 'RMSDObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    if (flip != None): command += 'Flip=' + cstr(flip) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE RMSDS (MOLECULE)
# ==========================
def RMSDMol(selection1, selection2, match=None, flip=None, unit=None):
    command = 'RMSDMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    if (flip != None): command += 'Flip=' + cstr(flip) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE RMSDS (RESIDUE)
# =========================
def RMSDRes(selection1, selection2, match=None, flip=None, unit=None):
    command = 'RMSDRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    if (flip != None): command += 'Flip=' + cstr(flip) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE RMSDS (ATOM)
# ======================
def RMSDAtom(selection1, selection2, match=None, flip=None, unit=None):
    command = 'RMSDAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    if (flip != None): command += 'Flip=' + cstr(flip) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# ROTATE ATOMS, OBJECTS OR THE SCENE (ALL OR SELECTED)
# ====================================================
def Rotate(x=None, y=None, z=None):
    command = 'Rotate '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# ROTATE ATOMS, OBJECTS OR THE SCENE (ALL)
# ========================================
def RotateAll(x=None, y=None, z=None):
    command = 'RotateAll '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# ROTATE ATOMS, OBJECTS OR THE SCENE (OBJECT)
# ===========================================
def RotateObj(selection1, x=None, y=None, z=None):
    command = 'RotateObj '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# ROTATE ATOMS, OBJECTS OR THE SCENE (MOLECULE)
# =============================================
def RotateMol(selection1, x=None, y=None, z=None):
    command = 'RotateMol '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# ROTATE ATOMS, OBJECTS OR THE SCENE (RESIDUE)
# ============================================
def RotateRes(selection1, x=None, y=None, z=None):
    command = 'RotateRes '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# ROTATE ATOMS, OBJECTS OR THE SCENE (ATOM)
# =========================================
def RotateAtom(selection1, x=None, y=None, z=None):
    command = 'RotateAtom '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# ROTATE ATOMS ABOUT A SPECIFIED AXIS (ALL OR SELECTED)
# =====================================================
def RotAxis(px, py, pz, dx, dy, dz, angle):
    command = 'RotAxis '
    command += 'PX=' + cstr(px) + ','
    command += 'PY=' + cstr(py) + ','
    command += 'PZ=' + cstr(pz) + ','
    command += 'DX=' + cstr(dx) + ','
    command += 'DY=' + cstr(dy) + ','
    command += 'DZ=' + cstr(dz) + ','
    command += 'Angle=' + cstr(angle) + ','
    return (runretval(command[:-1], True))


# ROTATE ATOMS ABOUT A SPECIFIED AXIS (ALL)
# =========================================
def RotAxisAll(px, py, pz, dx, dy, dz, angle):
    command = 'RotAxisAll '
    command += 'PX=' + cstr(px) + ','
    command += 'PY=' + cstr(py) + ','
    command += 'PZ=' + cstr(pz) + ','
    command += 'DX=' + cstr(dx) + ','
    command += 'DY=' + cstr(dy) + ','
    command += 'DZ=' + cstr(dz) + ','
    command += 'Angle=' + cstr(angle) + ','
    return (runretval(command[:-1], True))


# ROTATE ATOMS ABOUT A SPECIFIED AXIS (OBJECT)
# ============================================
def RotAxisObj(selection1, px, py, pz, dx, dy, dz, angle):
    command = 'RotAxisObj '
    command += selstr(selection1) + ','
    command += 'PX=' + cstr(px) + ','
    command += 'PY=' + cstr(py) + ','
    command += 'PZ=' + cstr(pz) + ','
    command += 'DX=' + cstr(dx) + ','
    command += 'DY=' + cstr(dy) + ','
    command += 'DZ=' + cstr(dz) + ','
    command += 'Angle=' + cstr(angle) + ','
    return (runretval(command[:-1], True))


# ROTATE ATOMS ABOUT A SPECIFIED AXIS (MOLECULE)
# ==============================================
def RotAxisMol(selection1, px, py, pz, dx, dy, dz, angle):
    command = 'RotAxisMol '
    command += selstr(selection1) + ','
    command += 'PX=' + cstr(px) + ','
    command += 'PY=' + cstr(py) + ','
    command += 'PZ=' + cstr(pz) + ','
    command += 'DX=' + cstr(dx) + ','
    command += 'DY=' + cstr(dy) + ','
    command += 'DZ=' + cstr(dz) + ','
    command += 'Angle=' + cstr(angle) + ','
    return (runretval(command[:-1], True))


# ROTATE ATOMS ABOUT A SPECIFIED AXIS (RESIDUE)
# =============================================
def RotAxisRes(selection1, px, py, pz, dx, dy, dz, angle):
    command = 'RotAxisRes '
    command += selstr(selection1) + ','
    command += 'PX=' + cstr(px) + ','
    command += 'PY=' + cstr(py) + ','
    command += 'PZ=' + cstr(pz) + ','
    command += 'DX=' + cstr(dx) + ','
    command += 'DY=' + cstr(dy) + ','
    command += 'DZ=' + cstr(dz) + ','
    command += 'Angle=' + cstr(angle) + ','
    return (runretval(command[:-1], True))


# ROTATE ATOMS ABOUT A SPECIFIED AXIS (ATOM)
# ==========================================
def RotAxisAtom(selection1, px, py, pz, dx, dy, dz, angle):
    command = 'RotAxisAtom '
    command += selstr(selection1) + ','
    command += 'PX=' + cstr(px) + ','
    command += 'PY=' + cstr(py) + ','
    command += 'PZ=' + cstr(pz) + ','
    command += 'DX=' + cstr(dx) + ','
    command += 'DY=' + cstr(dy) + ','
    command += 'DZ=' + cstr(dz) + ','
    command += 'Angle=' + cstr(angle) + ','
    return (runretval(command[:-1], True))


# RUN MOPAC FOR CUSTOM CALCULATION (ALL OR SELECTED)
# ==================================================
def RunMOPAC(keywords):
    command = 'RunMOPAC '
    command += 'Keywords=' + cstr(keywords) + ','
    return (runretval(command[:-1], True))


# RUN MOPAC FOR CUSTOM CALCULATION (ALL)
# ======================================
def RunMOPACAll(keywords):
    command = 'RunMOPACAll '
    command += 'Keywords=' + cstr(keywords) + ','
    return (runretval(command[:-1], True))


# RUN MOPAC FOR CUSTOM CALCULATION (OBJECT)
# =========================================
def RunMOPACObj(selection1, keywords):
    command = 'RunMOPACObj '
    command += selstr(selection1) + ','
    command += 'Keywords=' + cstr(keywords) + ','
    return (runretval(command[:-1], True))


# RUN MOPAC FOR CUSTOM CALCULATION (MOLECULE)
# ===========================================
def RunMOPACMol(selection1, keywords):
    command = 'RunMOPACMol '
    command += selstr(selection1) + ','
    command += 'Keywords=' + cstr(keywords) + ','
    return (runretval(command[:-1], True))


# RUN MOPAC FOR CUSTOM CALCULATION (RESIDUE)
# ==========================================
def RunMOPACRes(selection1, keywords):
    command = 'RunMOPACRes '
    command += selstr(selection1) + ','
    command += 'Keywords=' + cstr(keywords) + ','
    return (runretval(command[:-1], True))


# RUN MOPAC FOR CUSTOM CALCULATION (ATOM)
# =======================================
def RunMOPACAtom(selection1, keywords):
    command = 'RunMOPACAtom '
    command += selstr(selection1) + ','
    command += 'Keywords=' + cstr(keywords) + ','
    return (runretval(command[:-1], True))


# SAMPLE DIHEDRAL ANGLES
# ======================
def SampleDih(selection1, method=None, structures=None, dihedrals=None, bumpsum=None, scaffold=None, devmax=None,
              devbins=None):
    command = 'SampleDih '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (structures != None): command += 'Structures=' + cstr(structures) + ','
    if (dihedrals != None): command += 'Dihedrals=' + cstr(dihedrals) + ','
    if (bumpsum != None): command += 'Bumpsum=' + cstr(bumpsum) + ','
    if (scaffold != None): command += 'Scaffold=' + cstr(scaffold) + ','
    if (devmax != None): command += 'DevMax=' + cstr(devmax) + ','
    if (devbins != None): command += 'DevBins=' + cstr(devbins) + ','
    return (runretval(command[:-1], True))


# SAMPLE CENTRAL OR TERMINAL LOOP
# ===============================
def SampleLoop(selection1, selection2, structures=None, bumpsum=None, secstr=None):
    command = 'SampleLoop '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (structures != None): command += 'Structures=' + cstr(structures) + ','
    if (bumpsum != None): command += 'Bumpsum=' + cstr(bumpsum) + ','
    if (secstr != None): command += 'SecStr=' + cstr(secstr) + ','
    return (runretval(command[:-1], True))


# SAVE ALIGNMENT BETWEEN OBJECTS
# ==============================
def SaveAli(selection1, selection2, method=None, filename=None, format=None):
    command = 'SaveAli '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (filename != None): command += 'Filename=' + cstr(filename) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE SCREENSHOT AS UNCOMPRESSED WINDOWS BITMAP
# ==============================================
def SaveBmp(filename, menu=None, depthmap=None):
    command = 'SaveBmp '
    command += 'Filename=' + cstr(filename) + ','
    if (menu != None): command += 'Menu=' + cstr(menu) + ','
    if (depthmap != None): command += 'DepthMap=' + cstr(depthmap) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE CIF OR MMCIF FILE
# ======================
def SaveCIF(selection1, filename, format=None, transform=None):
    command = 'SaveCIF '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    if (transform != None): command += 'Transform=' + cstr(transform) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE ELECTROSTATIC POTENTIAL MAP
# ================================
def SaveESP(filename, method=None):
    command = 'SaveESP '
    command += 'Filename=' + cstr(filename) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE A MACRO TO RESTORE THE CURRENT STATE
# =========================================
def SaveMacro(filename, component):
    command = 'SaveMacro '
    command += 'Filename=' + cstr(filename) + ','
    command += 'Component=' + cstr(component) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE SIMULATION SNAPSHOTS IN MDCRD FORMAT
# =========================================
def SaveMDCrd(filename, steps, selection1):
    command = 'SaveMDCrd '
    command += 'Filename=' + cstr(filename) + ','
    command += 'Steps=' + cstr(steps) + ','
    command += selstr(selection1) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE MPEG4 VIDEO
# ================
def SaveMPG(filename, x=None, y=None, fps=None, quality=None, skip=None, raytrace=None, menu=None, justmacro=None,
            frames=None):
    command = 'SaveMPG '
    command += 'Filename=' + cstr(filename) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (fps != None): command += 'FPS=' + cstr(fps) + ','
    if (quality != None): command += 'Quality=' + cstr(quality) + ','
    if (skip != None): command += 'Skip=' + cstr(skip) + ','
    if (raytrace != None): command += 'RayTrace=' + cstr(raytrace) + ','
    if (menu != None): command += 'Menu=' + cstr(menu) + ','
    if (justmacro != None): command += 'justMacro=' + cstr(justmacro) + ','
    if (frames != None): command += 'Frames=' + cstr(frames) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    result = runretval(command[:-1], 1)
    if (result != None and len(result)): return (result[0])
    return (result)


# SAVE DISTANCE, DIHEDRAL AND RDC RESTRAINTS IN NMR EXCHANGE FORMAT
# =================================================================
def SaveNEF(selection1, filename, component=None):
    command = 'SaveNEF '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE PROTEIN DATA BANK FILE
# ===========================
def SavePDB(selection1, filename, format=None, transform=None, usecif=None):
    command = 'SavePDB '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    if (format != None): command += 'Format=' + cstr(format) + ','
    if (transform != None): command += 'Transform=' + cstr(transform) + ','
    if (usecif != None): command += 'UseCIF=' + cstr(usecif) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE PLOT
# =========
def SavePlot(filename, selection1, width, height, title, Type, xcolumn, ycolumn, ycolumns, xlabel, ylabel, legendpos,
             graphname, *arglist2):
    command = 'SavePlot '
    command += 'Filename=' + cstr(filename) + ','
    command += selstr(selection1) + ','
    command += 'Width=' + cstr(width) + ','
    command += 'Height=' + cstr(height) + ','
    command += 'Title=' + cstr(title) + ','
    command += 'Type=' + cstr(Type) + ','
    command += 'XColumn=' + cstr(xcolumn) + ','
    command += 'YColumn=' + cstr(ycolumn) + ','
    command += 'YColumns=' + cstr(ycolumns) + ','
    command += 'XLabel=' + cstr(xlabel) + ','
    command += 'YLabel=' + cstr(ylabel) + ','
    command += 'LegendPos=' + cstr(legendpos) + ','
    command += 'Graphname=' + cstr(graphname) + ','
    # ANY NUMBER OF VARIABLE ARGUMENTS CAN FOLLOW
    for arglist in arglist2:
        if (type(arglist) != type([])): arglist = [arglist]
        for arg in arglist:
            command += cstr(arg, quoted=(type(arg) != type(1) and type(arg) != type(1.))) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE SCREENSHOT AS COMPRESSED PNG BITMAP
# ========================================
def SavePNG(filename, menu=None, depthmap=None):
    """
    Saves a simple screenshot of the current state of YASARA.
    
    Notes:
        * ``SavePNG`` Does not work if YASARA runs in text or console mode, for more information please run a 
          ``Help SavePNG`` and read the in-program documentation.
        * If Matplotlib is installed on the activated environment, **the yasara_kernel function** returns the 
          image as a numpy array.
          
    :param filename: Filename to save the screenshot at. By default, the current working directory is in variable
                     ``workdir``
    :type filename: str(path)
    :param menu: Either "Yes" or "No", whether to include the menu and status bars in the screenshot.
    :type menu: str
    :param depthmap: Either "Yes" or "No", saves a grayscale image that represents the depth map of the current scene.
    :type depthmap: str
    
    :returns: Numpy array if matplotlib available or the response from YASARA.
    """ 
    command = 'SavePNG '
    command += 'Filename=' + cstr(filename) + ','
    if menu != None:
        command += 'Menu=' + cstr(menu) + ','
    if depthmap != None:
        command += 'DepthMap=' + cstr(depthmap) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE TH
    # READS
    command_result = runretval(command[:-1], 1)
    return yapycon_access_image_returned(filename, command_result) 


# SAVE POVRAY SCENE DESCRIPTION
# =============================
def SavePOV(filename, zoom=None, atoms=None, labelshadow=None, secalpha=None):
    command = 'SavePOV '
    command += 'Filename=' + cstr(filename) + ','
    if (zoom != None): command += 'Zoom=' + cstr(zoom) + ','
    if (atoms != None): command += 'Atoms=' + cstr(atoms) + ','
    if (labelshadow != None): command += 'LabelShadow=' + cstr(labelshadow) + ','
    if (secalpha != None): command += 'SecAlpha=' + cstr(secalpha) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE AMBER PREP TOPOLOGY (ALL OR SELECTED)
# ==========================================
def SavePrep(filename, hydnumbers=None, reorder=None):
    command = 'SavePrep '
    command += 'Filename=' + cstr(filename) + ','
    if (hydnumbers != None): command += 'HydNumbers=' + cstr(hydnumbers) + ','
    if (reorder != None): command += 'Reorder=' + cstr(reorder) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE AMBER PREP TOPOLOGY (ALL)
# ==============================
def SavePrepAll(filename, hydnumbers=None, reorder=None):
    command = 'SavePrepAll '
    command += 'Filename=' + cstr(filename) + ','
    if (hydnumbers != None): command += 'HydNumbers=' + cstr(hydnumbers) + ','
    if (reorder != None): command += 'Reorder=' + cstr(reorder) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE AMBER PREP TOPOLOGY (OBJECT)
# =================================
def SavePrepObj(selection1, filename, hydnumbers=None, reorder=None):
    command = 'SavePrepObj '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    if (hydnumbers != None): command += 'HydNumbers=' + cstr(hydnumbers) + ','
    if (reorder != None): command += 'Reorder=' + cstr(reorder) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE AMBER PREP TOPOLOGY (MOLECULE)
# ===================================
def SavePrepMol(selection1, filename, hydnumbers=None, reorder=None):
    command = 'SavePrepMol '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    if (hydnumbers != None): command += 'HydNumbers=' + cstr(hydnumbers) + ','
    if (reorder != None): command += 'Reorder=' + cstr(reorder) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE AMBER PREP TOPOLOGY (RESIDUE)
# ==================================
def SavePrepRes(selection1, filename, hydnumbers=None, reorder=None):
    command = 'SavePrepRes '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    if (hydnumbers != None): command += 'HydNumbers=' + cstr(hydnumbers) + ','
    if (reorder != None): command += 'Reorder=' + cstr(reorder) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE COMPLETE SCENE
# ===================
def SaveSce(filename):
    command = 'SaveSce '
    command += 'Filename=' + cstr(filename) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE RESIDUE SEQUENCE (OBJECT)
# ==============================
def SaveSeqObj(selection1, filename, join=None):
    command = 'SaveSeqObj '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    if (join != None): command += 'Join=' + cstr(join) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE RESIDUE SEQUENCE (MOLECULE)
# ================================
def SaveSeqMol(selection1, filename, join=None):
    command = 'SaveSeqMol '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    if (join != None): command += 'Join=' + cstr(join) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE RESIDUE SEQUENCE (RESIDUE)
# ===============================
def SaveSeqRes(selection1, filename, join=None):
    command = 'SaveSeqRes '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    if (join != None): command += 'Join=' + cstr(join) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE SIMULATION SNAPSHOTS IN SIM FORMAT
# =======================================
def SaveSim(filename, steps=None, number=None):
    command = 'SaveSim '
    command += 'Filename=' + cstr(filename) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (number != None): command += 'Number=' + cstr(number) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE FORMATTED TABLE
# ====================
def SaveTab(selection1, filename, format, columns, numformat, header):
    command = 'SaveTab '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    command += 'Format=' + cstr(format) + ','
    command += 'Columns=' + cstr(columns) + ','
    command += 'NumFormat=' + cstr(numformat) + ','
    command += 'Header=' + cstr(header) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE DISTANCE, DIHEDRAL AND RDC RESTRAINTS IN XPLOR FORMAT
# ==========================================================
def SaveTbl(selection1, filename, component=None, nameformat=None):
    command = 'SaveTbl '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    if (component != None): command += 'Component=' + cstr(component) + ','
    if (nameformat != None): command += 'NameFormat=' + cstr(nameformat) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE ALIAS/WAVEFRONT OBJECT
# ===========================
def SaveWOb(selection1, filename, interpolcol=None, level=None, ballzoom=None):
    command = 'SaveWOb '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    if (interpolcol != None): command += 'InterpolCol=' + cstr(interpolcol) + ','
    if (level != None): command += 'Level=' + cstr(level) + ','
    if (ballzoom != None): command += 'BallZoom=' + cstr(ballzoom) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE SIMULATION SNAPSHOTS IN XTC FORMAT
# =======================================
def SaveXTC(filename, steps, selection1):
    command = 'SaveXTC '
    command += 'Filename=' + cstr(filename) + ','
    command += 'Steps=' + cstr(steps) + ','
    command += selstr(selection1) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SAVE YASARA OBJECT
# ==================
def SaveYOb(selection1, filename):
    command = 'SaveYOb '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# EXPORT FILE WITH OPENBABEL
# ==========================
def Save(format, selection1, filename, nameformat=None, transform=None):
    command = 'Save '
    command = command[:-1] + cstr(format) + ' '
    command += selstr(selection1) + ','
    command += 'Filename=' + cstr(filename) + ','
    if (nameformat != None): command += 'NameFormat=' + cstr(nameformat) + ','
    if (transform != None): command += 'Transform=' + cstr(transform) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# SET/GET FORCE SCALING FACTORS
# =============================
def ScaleForce(component=None, factor=None):
    command = 'ScaleForce '
    if (component != None): command += 'Component=' + cstr(component) + ','
    if (factor != None): command += 'Factor=' + cstr(factor) + ','
    return (runretval(command[:-1], True))


# SCALE RESTRAINTS (ALL OR SELECTED)
# ==================================
def ScaleRest(Class=None, distance=None, dihedral=None, rdc=None):
    command = 'ScaleRest '
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (distance != None): command += 'Distance=' + cstr(distance) + ','
    if (dihedral != None): command += 'Dihedral=' + cstr(dihedral) + ','
    if (rdc != None): command += 'RDC=' + cstr(rdc) + ','
    return (runretval(command[:-1], True))


# SCALE RESTRAINTS (ALL)
# ======================
def ScaleRestAll(Class=None, distance=None, dihedral=None, rdc=None):
    command = 'ScaleRestAll '
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (distance != None): command += 'Distance=' + cstr(distance) + ','
    if (dihedral != None): command += 'Dihedral=' + cstr(dihedral) + ','
    if (rdc != None): command += 'RDC=' + cstr(rdc) + ','
    return (runretval(command[:-1], True))


# SCALE RESTRAINTS (OBJECT)
# =========================
def ScaleRestObj(selection1, Class=None, distance=None, dihedral=None, rdc=None):
    command = 'ScaleRestObj '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (distance != None): command += 'Distance=' + cstr(distance) + ','
    if (dihedral != None): command += 'Dihedral=' + cstr(dihedral) + ','
    if (rdc != None): command += 'RDC=' + cstr(rdc) + ','
    return (runretval(command[:-1], True))


# SCALE RESTRAINTS (MOLECULE)
# ===========================
def ScaleRestMol(selection1, Class=None, distance=None, dihedral=None, rdc=None):
    command = 'ScaleRestMol '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (distance != None): command += 'Distance=' + cstr(distance) + ','
    if (dihedral != None): command += 'Dihedral=' + cstr(dihedral) + ','
    if (rdc != None): command += 'RDC=' + cstr(rdc) + ','
    return (runretval(command[:-1], True))


# SCALE RESTRAINTS (RESIDUE)
# ==========================
def ScaleRestRes(selection1, Class=None, distance=None, dihedral=None, rdc=None):
    command = 'ScaleRestRes '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (distance != None): command += 'Distance=' + cstr(distance) + ','
    if (dihedral != None): command += 'Dihedral=' + cstr(dihedral) + ','
    if (rdc != None): command += 'RDC=' + cstr(rdc) + ','
    return (runretval(command[:-1], True))


# SCALE RESTRAINTS (ATOM)
# =======================
def ScaleRestAtom(selection1, Class=None, distance=None, dihedral=None, rdc=None):
    command = 'ScaleRestAtom '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    if (distance != None): command += 'Distance=' + cstr(distance) + ','
    if (dihedral != None): command += 'Dihedral=' + cstr(dihedral) + ','
    if (rdc != None): command += 'RDC=' + cstr(rdc) + ','
    return (runretval(command[:-1], True))


# SCALE ATOM POSITIONS AND POLYGON MESHES (ALL OR SELECTED)
# =========================================================
def Scale(x=None, y=None, z=None):
    command = 'Scale '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SCALE ATOM POSITIONS AND POLYGON MESHES (ALL)
# =============================================
def ScaleAll(x=None, y=None, z=None):
    command = 'ScaleAll '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SCALE ATOM POSITIONS AND POLYGON MESHES (OBJECT)
# ================================================
def ScaleObj(selection1, x=None, y=None, z=None):
    command = 'ScaleObj '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SCALE ATOM POSITIONS AND POLYGON MESHES (MOLECULE)
# ==================================================
def ScaleMol(selection1, x=None, y=None, z=None):
    command = 'ScaleMol '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SCALE ATOM POSITIONS AND POLYGON MESHES (RESIDUE)
# =================================================
def ScaleRes(selection1, x=None, y=None, z=None):
    command = 'ScaleRes '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SCALE ATOM POSITIONS AND POLYGON MESHES (ATOM)
# ==============================================
def ScaleAtom(selection1, x=None, y=None, z=None):
    command = 'ScaleAtom '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# FIX YASARA WINDOW ON A CERTAIN SCREEN
# =====================================
def Screen(number):
    command = 'Screen '
    command += 'Number=' + cstr(number) + ','
    return (runretval(command[:-1], True))


# SET/GET WINDOW AND FULLSCREEN SIZE
# ==================================
def ScreenSize(x=None, y=None, scale=None):
    command = 'ScreenSize '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (scale != None): command += 'Scale=' + cstr(scale) + ','
    return (runretval(command[:-1], True))


# SET SECONDARY STRUCTURE DISPLAY PARAMETERS
# ==========================================
def SecStrPar(strandwidth, strandheight, strandslope, arrowheight, strandperf, helixwidth, helixheight, helixslope,
              helixperf, helixsection, tuberadius, tubeellip, gaps, coltrans):
    command = 'SecStrPar '
    command += 'StrandWidth=' + cstr(strandwidth) + ','
    command += 'StrandHeight=' + cstr(strandheight) + ','
    command += 'StrandSlope=' + cstr(strandslope) + ','
    command += 'ArrowHeight=' + cstr(arrowheight) + ','
    command += 'StrandPerf=' + cstr(strandperf) + ','
    command += 'HelixWidth=' + cstr(helixwidth) + ','
    command += 'HelixHeight=' + cstr(helixheight) + ','
    command += 'HelixSlope=' + cstr(helixslope) + ','
    command += 'HelixPerf=' + cstr(helixperf) + ','
    command += 'HelixSection=' + cstr(helixsection) + ','
    command += 'TubeRadius=' + cstr(tuberadius) + ','
    command += 'TubeEllip=' + cstr(tubeellip) + ','
    command += 'Gaps=' + cstr(gaps) + ','
    command += 'ColTrans=' + cstr(coltrans) + ','
    return (runretval(command[:-1], True))


# SET/GET SECONDARY STRUCTURE (ALL OR SELECTED)
# =============================================
def SecStr(Type=None):
    command = 'SecStr '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# SET/GET SECONDARY STRUCTURE (ALL)
# =================================
def SecStrAll(Type=None):
    command = 'SecStrAll '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# SET/GET SECONDARY STRUCTURE (OBJECT)
# ====================================
def SecStrObj(selection1, Type=None):
    command = 'SecStrObj '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# SET/GET SECONDARY STRUCTURE (MOLECULE)
# ======================================
def SecStrMol(selection1, Type=None):
    command = 'SecStrMol '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# SET/GET SECONDARY STRUCTURE (RESIDUE)
# =====================================
def SecStrRes(selection1, Type=None):
    command = 'SecStrRes '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# SET/GET THE SEGMENT NAME (ALL OR SELECTED)
# ==========================================
def Seg(name=None):
    command = 'Seg '
    if (name != None): command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# SET/GET THE SEGMENT NAME (ALL)
# ==============================
def SegAll(name=None):
    command = 'SegAll '
    if (name != None): command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# SET/GET THE SEGMENT NAME (OBJECT)
# =================================
def SegObj(selection1, name=None):
    command = 'SegObj '
    command += selstr(selection1) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# SET/GET THE SEGMENT NAME (MOLECULE)
# ===================================
def SegMol(selection1, name=None):
    command = 'SegMol '
    command += selstr(selection1) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# SET/GET THE SEGMENT NAME (RESIDUE)
# ==================================
def SegRes(selection1, name=None):
    command = 'SegRes '
    command += selstr(selection1) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# SET/GET THE SEGMENT NAME (ATOM)
# ===============================
def SegAtom(selection1, name=None):
    command = 'SegAtom '
    command += selstr(selection1) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# INTERACTIVELY SELECT ATOMS WITHIN AN ARBITRARY AREA (OBJECT)
# ============================================================
def SelectAreaObj():
    command = 'SelectAreaObj '
    return (runretval(command[:-1], True))


# INTERACTIVELY SELECT ATOMS WITHIN AN ARBITRARY AREA (MOLECULE)
# ==============================================================
def SelectAreaMol():
    command = 'SelectAreaMol '
    return (runretval(command[:-1], True))


# INTERACTIVELY SELECT ATOMS WITHIN AN ARBITRARY AREA (RESIDUE)
# =============================================================
def SelectAreaRes():
    command = 'SelectAreaRes '
    return (runretval(command[:-1], True))


# INTERACTIVELY SELECT ATOMS WITHIN AN ARBITRARY AREA (ATOM)
# ==========================================================
def SelectAreaAtom():
    command = 'SelectAreaAtom '
    return (runretval(command[:-1], True))


# INTERACTIVELY SELECT ATOMS WITHIN A RECTANGULAR BOX (OBJECT)
# ============================================================
def SelectBoxObj():
    command = 'SelectBoxObj '
    return (runretval(command[:-1], True))


# INTERACTIVELY SELECT ATOMS WITHIN A RECTANGULAR BOX (MOLECULE)
# ==============================================================
def SelectBoxMol():
    command = 'SelectBoxMol '
    return (runretval(command[:-1], True))


# INTERACTIVELY SELECT ATOMS WITHIN A RECTANGULAR BOX (RESIDUE)
# =============================================================
def SelectBoxRes():
    command = 'SelectBoxRes '
    return (runretval(command[:-1], True))


# INTERACTIVELY SELECT ATOMS WITHIN A RECTANGULAR BOX (ATOM)
# ==========================================================
def SelectBoxAtom():
    command = 'SelectBoxAtom '
    return (runretval(command[:-1], True))


# INTERACTIVELY SELECT ATOMS WITHIN A SPHERE AROUND OTHER ATOMS (OBJECT)
# ======================================================================
def SelectSphereObj(selection1):
    command = 'SelectSphereObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# INTERACTIVELY SELECT ATOMS WITHIN A SPHERE AROUND OTHER ATOMS (MOLECULE)
# ========================================================================
def SelectSphereMol(selection1):
    command = 'SelectSphereMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# INTERACTIVELY SELECT ATOMS WITHIN A SPHERE AROUND OTHER ATOMS (RESIDUE)
# =======================================================================
def SelectSphereRes(selection1):
    command = 'SelectSphereRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# INTERACTIVELY SELECT ATOMS WITHIN A SPHERE AROUND OTHER ATOMS (ATOM)
# ====================================================================
def SelectSphereAtom(selection1):
    command = 'SelectSphereAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SELECT TABLE TO ADD CELLS
# =========================
def SelectTab(selection1):
    command = 'SelectTab '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SELECT ATOMS (ALL OR SELECTED)
# ==============================
def Select(mode=None):
    command = 'Select '
    if (mode != None): command += 'Mode=' + cstr(mode) + ','
    return (runretval(command[:-1], True))


# SELECT ATOMS (ALL)
# ==================
def SelectAll(mode=None):
    command = 'SelectAll '
    if (mode != None): command += 'Mode=' + cstr(mode) + ','
    return (runretval(command[:-1], True))


# SELECT ATOMS (OBJECT)
# =====================
def SelectObj(selection1, mode=None):
    command = 'SelectObj '
    command += selstr(selection1) + ','
    if (mode != None): command += 'Mode=' + cstr(mode) + ','
    return (runretval(command[:-1], True))


# SELECT ATOMS (MOLECULE)
# =======================
def SelectMol(selection1, mode=None):
    command = 'SelectMol '
    command += selstr(selection1) + ','
    if (mode != None): command += 'Mode=' + cstr(mode) + ','
    return (runretval(command[:-1], True))


# SELECT ATOMS (RESIDUE)
# ======================
def SelectRes(selection1, mode=None):
    command = 'SelectRes '
    command += selstr(selection1) + ','
    if (mode != None): command += 'Mode=' + cstr(mode) + ','
    return (runretval(command[:-1], True))


# SELECT ATOMS (ATOM)
# ===================
def SelectAtom(selection1, mode=None):
    command = 'SelectAtom '
    command += selstr(selection1) + ','
    if mode is not None:
        command += 'Mode=' + cstr(mode) + ','
    return runretval(command[:-1], False)


# SWITCH SEQUENCE SELECTOR ON/OFF
# ===============================
def SeqSelector(flag):
    command = 'SeqSelector '
    command += 'Flag=' + cstr(flag) + ','
    return (runretval(command[:-1], True))


# GET RESIDUE SEQUENCE (ALL OR SELECTED)
# ======================================
def Sequence(join=None):
    command = 'Sequence '
    if (join != None): command += 'Join=' + cstr(join) + ','
    return (runretval(command[:-1], True))


# GET RESIDUE SEQUENCE (ALL)
# ==========================
def SequenceAll(join=None):
    command = 'SequenceAll '
    if (join != None): command += 'Join=' + cstr(join) + ','
    return (runretval(command[:-1], True))


# GET RESIDUE SEQUENCE (OBJECT)
# =============================
def SequenceObj(selection1, join=None):
    command = 'SequenceObj '
    command += selstr(selection1) + ','
    if (join != None): command += 'Join=' + cstr(join) + ','
    return (runretval(command[:-1], True))


# GET RESIDUE SEQUENCE (MOLECULE)
# ===============================
def SequenceMol(selection1, join=None):
    command = 'SequenceMol '
    command += selstr(selection1) + ','
    if (join != None): command += 'Join=' + cstr(join) + ','
    return (runretval(command[:-1], True))


# GET RESIDUE SEQUENCE (RESIDUE)
# ==============================
def SequenceRes(selection1, join=None):
    command = 'SequenceRes '
    command += selstr(selection1) + ','
    if (join != None): command += 'Join=' + cstr(join) + ','
    return (runretval(command[:-1], True))


# SHIFT ATOM COLORS (ALL OR SELECTED)
# ===================================
def ShiftColor(color, shift=None):
    command = 'ShiftColor '
    command += 'color=' + cstr(color) + ','
    if (shift != None): command += 'Shift=' + cstr(shift) + ','
    return (runretval(command[:-1], True))


# SHIFT ATOM COLORS (ALL)
# =======================
def ShiftColorAll(color, shift=None):
    command = 'ShiftColorAll '
    command += 'color=' + cstr(color) + ','
    if (shift != None): command += 'Shift=' + cstr(shift) + ','
    return (runretval(command[:-1], True))


# SHIFT ATOM COLORS (OBJECT)
# ==========================
def ShiftColorObj(selection1, color, shift=None):
    command = 'ShiftColorObj '
    command += selstr(selection1) + ','
    command += 'color=' + cstr(color) + ','
    if (shift != None): command += 'Shift=' + cstr(shift) + ','
    return (runretval(command[:-1], True))


# SHIFT ATOM COLORS (MOLECULE)
# ============================
def ShiftColorMol(selection1, color, shift=None):
    command = 'ShiftColorMol '
    command += selstr(selection1) + ','
    command += 'color=' + cstr(color) + ','
    if (shift != None): command += 'Shift=' + cstr(shift) + ','
    return (runretval(command[:-1], True))


# SHIFT ATOM COLORS (RESIDUE)
# ===========================
def ShiftColorRes(selection1, color, shift=None):
    command = 'ShiftColorRes '
    command += selstr(selection1) + ','
    command += 'color=' + cstr(color) + ','
    if (shift != None): command += 'Shift=' + cstr(shift) + ','
    return (runretval(command[:-1], True))


# SHIFT ATOM COLORS (ATOM)
# ========================
def ShiftColorAtom(selection1, color, shift=None):
    command = 'ShiftColorAtom '
    command += selstr(selection1) + ','
    command += 'color=' + cstr(color) + ','
    if (shift != None): command += 'Shift=' + cstr(shift) + ','
    return (runretval(command[:-1], True))


# SHOW ARROWS BETWEEN ATOMS OR POINTS
# ===================================
def ShowArrow(start, selection1, end, selection2, radius=None, heads=None, color=None, dismax=None, visualize=None):
    command = 'ShowArrow '
    command += 'Start=' + cstr(start) + ','
    command += selstr(selection1) + ','
    command += 'End=' + cstr(end) + ','
    command += selstr(selection2) + ','
    if (radius != None): command += 'Radius=' + cstr(radius) + ','
    if (heads != None): command += 'Heads=' + cstr(heads) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (dismax != None): command += 'DisMax=' + cstr(dismax) + ','
    if (visualize != None): command += 'Visualize=' + cstr(visualize) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW ARROWS BETWEEN ATOMS OR POINTS
# ===================================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def ShowArrow2(start, x, y, z, end, x2=None, y2=None, z2=None, radius=None, heads=None, color=None):
    command = 'ShowArrow '
    command += 'Start=' + cstr(start) + ','
    command += 'X=' + cstr(x) + ','
    command += 'Y=' + cstr(y) + ','
    command += 'Z=' + cstr(z) + ','
    command += 'End=' + cstr(end) + ','
    if (x2 != None): command += 'X=' + cstr(x2) + ','
    if (y2 != None): command += 'Y=' + cstr(y2) + ','
    if (z2 != None): command += 'Z=' + cstr(z2) + ','
    if (radius != None): command += 'Radius=' + cstr(radius) + ','
    if (heads != None): command += 'Heads=' + cstr(heads) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW ARROWS BETWEEN ATOMS OR POINTS
# ===================================
# THIS IS ALTERNATIVE 3, WITH DIFFERENT PARAMETERS
def ShowArrow3(start, selection1, x, y, z, end, selection2, x2=None, y2=None, z2=None, radius=None, heads=None,
               color=None, dismax=None):
    command = 'ShowArrow '
    command += 'Start=' + cstr(start) + ','
    command += selstr(selection1) + ','
    command += 'X=' + cstr(x) + ','
    command += 'Y=' + cstr(y) + ','
    command += 'Z=' + cstr(z) + ','
    command += 'End=' + cstr(end) + ','
    command += selstr(selection2) + ','
    if (x2 != None): command += 'X=' + cstr(x2) + ','
    if (y2 != None): command += 'Y=' + cstr(y2) + ','
    if (z2 != None): command += 'Z=' + cstr(z2) + ','
    if (radius != None): command += 'Radius=' + cstr(radius) + ','
    if (heads != None): command += 'Heads=' + cstr(heads) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (dismax != None): command += 'DisMax=' + cstr(dismax) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW ARROWS BETWEEN ATOMS OR POINTS
# ===================================
# THIS IS ALTERNATIVE 4, WITH DIFFERENT PARAMETERS
def ShowArrow4(start, selection1, dis, end, selection2, dis2=None, radius=None, heads=None, color=None, dismax=None):
    command = 'ShowArrow '
    command += 'Start=' + cstr(start) + ','
    command += selstr(selection1) + ','
    command += 'Dis=' + cstr(dis) + ','
    command += 'End=' + cstr(end) + ','
    command += selstr(selection2) + ','
    if (dis2 != None): command += 'Dis=' + cstr(dis2) + ','
    if (radius != None): command += 'Radius=' + cstr(radius) + ','
    if (heads != None): command += 'Heads=' + cstr(heads) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (dismax != None): command += 'DisMax=' + cstr(dismax) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW A RECTANGULAR BOX
# ======================
def ShowBox(width=None, height=None, depth=None, leftcol=None, rightcol=None, bottomcol=None, topcol=None,
            frontcol=None, backcol=None):
    command = 'ShowBox '
    if (width != None): command += 'Width=' + cstr(width) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (depth != None): command += 'Depth=' + cstr(depth) + ','
    if (leftcol != None): command += 'LeftCol=' + cstr(leftcol) + ','
    if (rightcol != None): command += 'RightCol=' + cstr(rightcol) + ','
    if (bottomcol != None): command += 'BottomCol=' + cstr(bottomcol) + ','
    if (topcol != None): command += 'TopCol=' + cstr(topcol) + ','
    if (frontcol != None): command += 'FrontCol=' + cstr(frontcol) + ','
    if (backcol != None): command += 'BackCol=' + cstr(backcol) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW CLICKABLE BUTTON
# =====================
def ShowButton(text, x=None, y=None, width=None, height=None, border=None, color=None, action=None):
    command = 'ShowButton '
    command += 'Text=' + cstr(text, 1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (width != None): command += 'Width=' + cstr(width) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (border != None): command += 'Border=' + cstr(border) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (action != None): command += 'Action=' + cstr(action) + ','
    return (runretval(command[:-1], True))


# SHOW CAVITIES (ALL OR SELECTED)
# ===============================
def ShowCavi(Type=None, outcol=None, outalpha=None, incol=None, inalpha=None, specular=None):
    command = 'ShowCavi '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW CAVITIES (ALL)
# ===================
def ShowCaviAll(Type=None, outcol=None, outalpha=None, incol=None, inalpha=None, specular=None):
    command = 'ShowCaviAll '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW CAVITIES (OBJECT)
# ======================
def ShowCaviObj(selection1, Type=None, outcol=None, outalpha=None, incol=None, inalpha=None, specular=None):
    command = 'ShowCaviObj '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW CAVITIES (MOLECULE)
# ========================
def ShowCaviMol(selection1, Type=None, outcol=None, outalpha=None, incol=None, inalpha=None, specular=None):
    command = 'ShowCaviMol '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW CAVITIES (RESIDUE)
# =======================
def ShowCaviRes(selection1, Type=None, outcol=None, outalpha=None, incol=None, inalpha=None, specular=None):
    command = 'ShowCaviRes '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW CAVITIES (ATOM)
# ====================
def ShowCaviAtom(selection1, Type=None, outcol=None, outalpha=None, incol=None, inalpha=None, specular=None):
    command = 'ShowCaviAtom '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW A CONE, CYLINDER, PYRAMID OR PRISM
# =======================================
def ShowCone(bottomradius=None, topradius=None, height=None, edges=None, bottomcol=None, topcol=None, sidecol=None,
             alpha=None, smooth=None):
    command = 'ShowCone '
    if (bottomradius != None): command += 'BottomRadius=' + cstr(bottomradius) + ','
    if (topradius != None): command += 'TopRadius=' + cstr(topradius) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (edges != None): command += 'Edges=' + cstr(edges) + ','
    if (bottomcol != None): command += 'BottomCol=' + cstr(bottomcol) + ','
    if (topcol != None): command += 'TopCol=' + cstr(topcol) + ','
    if (sidecol != None): command += 'SideCol=' + cstr(sidecol) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (smooth != None): command += 'Smooth=' + cstr(smooth) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW CONTACT SURFACE (OBJECT)
# =============================
def ShowConSurfObj(selection1, selection2, cutoff=None, subtract=None, Type=None, outcol=None, outalpha=None,
                   incol=None, inalpha=None, specular=None):
    command = 'ShowConSurfObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW CONTACT SURFACE (MOLECULE)
# ===============================
def ShowConSurfMol(selection1, selection2, cutoff=None, subtract=None, Type=None, outcol=None, outalpha=None,
                   incol=None, inalpha=None, specular=None):
    command = 'ShowConSurfMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW CONTACT SURFACE (RESIDUE)
# ==============================
def ShowConSurfRes(selection1, selection2, cutoff=None, subtract=None, Type=None, outcol=None, outalpha=None,
                   incol=None, inalpha=None, specular=None):
    command = 'ShowConSurfRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW CONTACT SURFACE (ATOM)
# ===========================
def ShowConSurfAtom(selection1, selection2, cutoff=None, subtract=None, Type=None, outcol=None, outalpha=None,
                    incol=None, inalpha=None, specular=None):
    command = 'ShowConSurfAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW CONTACTS (OBJECT)
# ======================
def ShowConObj(selection1, selection2, cutoff=None, subtract=None, energy=None, exclude=None, occluded=None):
    command = 'ShowConObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (energy != None): command += 'Energy=' + cstr(energy) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW CONTACTS (MOLECULE)
# ========================
def ShowConMol(selection1, selection2, cutoff=None, subtract=None, energy=None, exclude=None, occluded=None):
    command = 'ShowConMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (energy != None): command += 'Energy=' + cstr(energy) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW CONTACTS (RESIDUE)
# =======================
def ShowConRes(selection1, selection2, cutoff=None, subtract=None, energy=None, exclude=None, occluded=None):
    command = 'ShowConRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (energy != None): command += 'Energy=' + cstr(energy) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW CONTACTS (ATOM)
# ====================
def ShowConAtom(selection1, selection2, cutoff=None, subtract=None, energy=None, exclude=None, occluded=None):
    command = 'ShowConAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (subtract != None): command += 'Subtract=' + cstr(subtract) + ','
    if (energy != None): command += 'Energy=' + cstr(energy) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW ELECTROSTATIC POTENTIAL
# ============================
def ShowESP():
    RaiseError('This command is only available with extensions Points,Density,Contour in Python')


# SHOW ELECTROSTATIC POTENTIAL
# ============================
# THIS IS ALTERNATIVE 1, WITH DIFFERENT PARAMETERS
def ShowESPPoints(method=None, resolution=None, Min=None, Max=None):
    command = 'ShowESP Points,'
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (resolution != None): command += 'Resolution=' + cstr(resolution) + ','
    if (Min != None): command += 'Min=' + cstr(Min) + ','
    if (Max != None): command += 'Max=' + cstr(Max) + ','
    return (runretval(command[:-1], True))


# SHOW ELECTROSTATIC POTENTIAL
# ============================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def ShowESPDensity(method=None, resolution=None, Min=None, Max=None):
    command = 'ShowESP Density,'
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (resolution != None): command += 'Resolution=' + cstr(resolution) + ','
    if (Min != None): command += 'Min=' + cstr(Min) + ','
    if (Max != None): command += 'Max=' + cstr(Max) + ','
    return (runretval(command[:-1], True))


# SHOW ELECTROSTATIC POTENTIAL
# ============================
# THIS IS ALTERNATIVE 3, WITH DIFFERENT PARAMETERS
def ShowESPContour(method=None, resolution=None, level=None):
    command = 'ShowESP Contour,'
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (resolution != None): command += 'Resolution=' + cstr(resolution) + ','
    if (level != None): command += 'Level=' + cstr(level) + ','
    return (runretval(command[:-1], True))


# SHOW HYDROGEN BONDS (ALL OR SELECTED)
# =====================================
def ShowHBo(extend=None):
    command = 'ShowHBo '
    if (extend != None): command += 'Extend=' + cstr(extend) + ','
    return (runretval(command[:-1], True))


# SHOW HYDROGEN BONDS (ALL)
# =========================
def ShowHBoAll(extend=None):
    command = 'ShowHBoAll '
    if (extend != None): command += 'Extend=' + cstr(extend) + ','
    return (runretval(command[:-1], True))


# SHOW HYDROGEN BONDS (OBJECT)
# ============================
def ShowHBoObj(selection1, extend=None):
    command = 'ShowHBoObj '
    command += selstr(selection1) + ','
    if (extend != None): command += 'Extend=' + cstr(extend) + ','
    return (runretval(command[:-1], True))


# SHOW HYDROGEN BONDS (MOLECULE)
# ==============================
def ShowHBoMol(selection1, extend=None):
    command = 'ShowHBoMol '
    command += selstr(selection1) + ','
    if (extend != None): command += 'Extend=' + cstr(extend) + ','
    return (runretval(command[:-1], True))


# SHOW HYDROGEN BONDS (RESIDUE)
# =============================
def ShowHBoRes(selection1, extend=None):
    command = 'ShowHBoRes '
    command += selstr(selection1) + ','
    if (extend != None): command += 'Extend=' + cstr(extend) + ','
    return (runretval(command[:-1], True))


# SHOW HYDROGEN BONDS (ATOM)
# ==========================
def ShowHBoAtom(selection1, extend=None):
    command = 'ShowHBoAtom '
    command += selstr(selection1) + ','
    if (extend != None): command += 'Extend=' + cstr(extend) + ','
    return (runretval(command[:-1], True))


# SHOW IN HEAD-UP DISPLAY (MOLECULE)
# ==================================
def ShowHUDMol(selection1):
    command = 'ShowHUDMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SHOW IN HEAD-UP DISPLAY (RESIDUE)
# =================================
def ShowHUDRes(selection1):
    command = 'ShowHUDRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SHOW IN HEAD-UP DISPLAY (ATOM)
# ==============================
def ShowHUDAtom(selection1):
    command = 'ShowHUDAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SHOW IMAGES
# ===========
def ShowImage(selection1, x=None, y=None, width=None, height=None, alpha=None, priority=None):
    command = 'ShowImage '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (width != None): command += 'Width=' + cstr(width) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (priority != None): command += 'Priority=' + cstr(priority) + ','
    return (runretval(command[:-1], True))


# SHOW INTERACTIONS (OBJECT)
# ==========================
def ShowIntObj(selection1, selection2, Type, cutoff=None, exclude=None, occluded=None):
    command = 'ShowIntObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += 'Type=' + cstr(Type) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW INTERACTIONS (MOLECULE)
# ============================
def ShowIntMol(selection1, selection2, Type, cutoff=None, exclude=None, occluded=None):
    command = 'ShowIntMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += 'Type=' + cstr(Type) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW INTERACTIONS (RESIDUE)
# ===========================
def ShowIntRes(selection1, selection2, Type, cutoff=None, exclude=None, occluded=None):
    command = 'ShowIntRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += 'Type=' + cstr(Type) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW INTERACTIONS (ATOM)
# ========================
def ShowIntAtom(selection1, selection2, Type, cutoff=None, exclude=None, occluded=None):
    command = 'ShowIntAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += 'Type=' + cstr(Type) + ','
    if (cutoff != None): command += 'Cutoff=' + cstr(cutoff) + ','
    if (exclude != None): command += 'Exclude=' + cstr(exclude) + ','
    if (occluded != None): command += 'Occluded=' + cstr(occluded) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW ION BINDING SITES (ALL OR SELECTED)
# ========================================
def ShowIonSites(ion):
    command = 'ShowIonSites '
    command += 'Ion=' + cstr(ion) + ','
    return (runretval(command[:-1], True))


# SHOW ION BINDING SITES (ALL)
# ============================
def ShowIonSitesAll(ion):
    command = 'ShowIonSitesAll '
    command += 'Ion=' + cstr(ion) + ','
    return (runretval(command[:-1], True))


# SHOW ION BINDING SITES (OBJECT)
# ===============================
def ShowIonSitesObj(selection1, ion):
    command = 'ShowIonSitesObj '
    command += selstr(selection1) + ','
    command += 'Ion=' + cstr(ion) + ','
    return (runretval(command[:-1], True))


# SHOW KNOWLEDGE-BASED POTENTIAL
# ==============================
def ShowKBP(selection1, selection2, name=None, Type=None, size=None):
    command = 'ShowKBP '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (size != None): command += 'Size=' + cstr(size) + ','
    return (runretval(command[:-1], True))


# SHOW TEXT MESSAGE AT THE BOTTOM
# ===============================
def ShowMessage(text):
    """
    Displays a simple message to the user **within** YASARA.

    :param text:
    :type text: str


    """
    command = 'ShowMessage '
    command += 'Text=' + cstr(text, 1) + ','
    return (runretval(command[:-1], True))


# SHOW RESTRAINTS (ALL OR SELECTED)
# =================================
def ShowRest(Class=None):
    command = 'ShowRest '
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    return (runretval(command[:-1], True))


# SHOW RESTRAINTS (ALL)
# =====================
def ShowRestAll(Class=None):
    command = 'ShowRestAll '
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    return (runretval(command[:-1], True))


# SHOW RESTRAINTS (OBJECT)
# ========================
def ShowRestObj(selection1, Class=None):
    command = 'ShowRestObj '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    return (runretval(command[:-1], True))


# SHOW RESTRAINTS (MOLECULE)
# ==========================
def ShowRestMol(selection1, Class=None):
    command = 'ShowRestMol '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    return (runretval(command[:-1], True))


# SHOW RESTRAINTS (RESIDUE)
# =========================
def ShowRestRes(selection1, Class=None):
    command = 'ShowRestRes '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    return (runretval(command[:-1], True))


# SHOW RESTRAINTS (ATOM)
# ======================
def ShowRestAtom(selection1, Class=None):
    command = 'ShowRestAtom '
    command += selstr(selection1) + ','
    if (Class != None): command += 'Class=' + cstr(Class) + ','
    return (runretval(command[:-1], True))


# SHOW SIDE-CHAIN ROTAMERS (ALL OR SELECTED)
# ==========================================
def ShowRota():
    command = 'ShowRota '
    return (runretval(command[:-1], True))


# SHOW SIDE-CHAIN ROTAMERS (ALL)
# ==============================
def ShowRotaAll():
    command = 'ShowRotaAll '
    return (runretval(command[:-1], True))


# SHOW SIDE-CHAIN ROTAMERS (OBJECT)
# =================================
def ShowRotaObj(selection1):
    command = 'ShowRotaObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SHOW SIDE-CHAIN ROTAMERS (MOLECULE)
# ===================================
def ShowRotaMol(selection1):
    command = 'ShowRotaMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SHOW SIDE-CHAIN ROTAMERS (RESIDUE)
# ==================================
def ShowRotaRes(selection1):
    command = 'ShowRotaRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SHOW SECONDARY STRUCTURE (ALL OR SELECTED)
# ==========================================
def ShowSecStr(style=None, hideatoms=None):
    command = 'ShowSecStr '
    if (style != None): command += 'Style=' + cstr(style) + ','
    if (hideatoms != None): command += 'HideAtoms=' + cstr(hideatoms) + ','
    return (runretval(command[:-1], True))


# SHOW SECONDARY STRUCTURE (ALL)
# ==============================
def ShowSecStrAll(style=None, hideatoms=None):
    command = 'ShowSecStrAll '
    if (style != None): command += 'Style=' + cstr(style) + ','
    if (hideatoms != None): command += 'HideAtoms=' + cstr(hideatoms) + ','
    return (runretval(command[:-1], True))


# SHOW SECONDARY STRUCTURE (OBJECT)
# =================================
def ShowSecStrObj(selection1, style=None, hideatoms=None):
    command = 'ShowSecStrObj '
    command += selstr(selection1) + ','
    if (style != None): command += 'Style=' + cstr(style) + ','
    if (hideatoms != None): command += 'HideAtoms=' + cstr(hideatoms) + ','
    return (runretval(command[:-1], True))


# SHOW SECONDARY STRUCTURE (MOLECULE)
# ===================================
def ShowSecStrMol(selection1, style=None, hideatoms=None):
    command = 'ShowSecStrMol '
    command += selstr(selection1) + ','
    if (style != None): command += 'Style=' + cstr(style) + ','
    if (hideatoms != None): command += 'HideAtoms=' + cstr(hideatoms) + ','
    return (runretval(command[:-1], True))


# SHOW SECONDARY STRUCTURE (RESIDUE)
# ==================================
def ShowSecStrRes(selection1, style=None, hideatoms=None):
    command = 'ShowSecStrRes '
    command += selstr(selection1) + ','
    if (style != None): command += 'Style=' + cstr(style) + ','
    if (hideatoms != None): command += 'HideAtoms=' + cstr(hideatoms) + ','
    return (runretval(command[:-1], True))


# CREATE A SIMULATION CELL OBJECT TO VISUALIZE NEIGHBORING CELLS
# ==============================================================
def ShowCell(x=None, y=None, z=None, alpha=None, beta=None, gamma=None):
    command = 'ShowCell '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (beta != None): command += 'Beta=' + cstr(beta) + ','
    if (gamma != None): command += 'Gamma=' + cstr(gamma) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW SIMULATION NEIGHBOR SEARCH GRID
# ====================================
def ShowGrid(Type=None, center=None, color=None):
    command = 'ShowGrid '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW A SPHERE OR ELLIPSOID
# ==========================
def ShowSphere(radius=None, color=None, alpha=None, level=None, scaley=None, scalez=None):
    command = 'ShowSphere '
    if (radius != None): command += 'Radius=' + cstr(radius) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    if (level != None): command += 'Level=' + cstr(level) + ','
    if (scaley != None): command += 'ScaleY=' + cstr(scaley) + ','
    if (scalez != None): command += 'ScaleZ=' + cstr(scalez) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW POLYGON BETWEEN ATOMS OR POINTS
# ====================================
def ShowPolygon():
    RaiseError('This command is only available with extensions Atoms,Points in Python')


# SHOW POLYGON BETWEEN ATOMS OR POINTS
# ====================================
# THIS IS ALTERNATIVE 1, WITH DIFFERENT PARAMETERS
def ShowPolygonAtoms(color, alpha, vertices, selection1, selection2, selection3, selection4=None, selection5=None,
                     selection6=None, selection7=None, selection8=None):
    command = 'ShowPolygon Atoms,'
    command += 'Color=' + cstr(color) + ','
    command += 'Alpha=' + cstr(alpha) + ','
    command += 'Vertices=' + cstr(vertices) + ','
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += selstr(selection3) + ','
    if (selection4 != None): command += selstr(selection4) + ','
    if (selection5 != None): command += selstr(selection5) + ','
    if (selection6 != None): command += selstr(selection6) + ','
    if (selection7 != None): command += selstr(selection7) + ','
    if (selection8 != None): command += selstr(selection8) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW POLYGON BETWEEN ATOMS OR POINTS
# ====================================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def ShowPolygonPoints(color, alpha, vertices, x1, y1, z1, x2=None, y2=None, z2=None, x3=None, y3=None, z3=None, x4=None,
                      y4=None, z4=None, x5=None, y5=None, z5=None, x6=None, y6=None, z6=None, x7=None, y7=None, z7=None,
                      x8=None, y8=None, z8=None):
    command = 'ShowPolygon Points,'
    command += 'Color=' + cstr(color) + ','
    command += 'Alpha=' + cstr(alpha) + ','
    command += 'Vertices=' + cstr(vertices) + ','
    command += 'X1=' + cstr(x1) + ','
    command += 'Y1=' + cstr(y1) + ','
    command += 'Z1=' + cstr(z1) + ','
    if (x2 != None): command += 'X2=' + cstr(x2) + ','
    if (y2 != None): command += 'Y2=' + cstr(y2) + ','
    if (z2 != None): command += 'Z2=' + cstr(z2) + ','
    if (x3 != None): command += 'X3=' + cstr(x3) + ','
    if (y3 != None): command += 'Y3=' + cstr(y3) + ','
    if (z3 != None): command += 'Z3=' + cstr(z3) + ','
    if (x4 != None): command += 'X4=' + cstr(x4) + ','
    if (y4 != None): command += 'Y4=' + cstr(y4) + ','
    if (z4 != None): command += 'Z4=' + cstr(z4) + ','
    if (x5 != None): command += 'X5=' + cstr(x5) + ','
    if (y5 != None): command += 'Y5=' + cstr(y5) + ','
    if (z5 != None): command += 'Z5=' + cstr(z5) + ','
    if (x6 != None): command += 'X6=' + cstr(x6) + ','
    if (y6 != None): command += 'Y6=' + cstr(y6) + ','
    if (z6 != None): command += 'Z6=' + cstr(z6) + ','
    if (x7 != None): command += 'X7=' + cstr(x7) + ','
    if (y7 != None): command += 'Y7=' + cstr(y7) + ','
    if (z7 != None): command += 'Z7=' + cstr(z7) + ','
    if (x8 != None): command += 'X8=' + cstr(x8) + ','
    if (y8 != None): command += 'Y8=' + cstr(y8) + ','
    if (z8 != None): command += 'Z8=' + cstr(z8) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW POLYGON INSIDE RING (ALL OR SELECTED)
# ==========================================
def ShowRing(color=None, alpha=None):
    command = 'ShowRing '
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    return (runretval(command[:-1], True))


# SHOW POLYGON INSIDE RING (ALL)
# ==============================
def ShowRingAll(color=None, alpha=None):
    command = 'ShowRingAll '
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    return (runretval(command[:-1], True))


# SHOW POLYGON INSIDE RING (OBJECT)
# =================================
def ShowRingObj(selection1, color=None, alpha=None):
    command = 'ShowRingObj '
    command += selstr(selection1) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    return (runretval(command[:-1], True))


# SHOW POLYGON INSIDE RING (MOLECULE)
# ===================================
def ShowRingMol(selection1, color=None, alpha=None):
    command = 'ShowRingMol '
    command += selstr(selection1) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    return (runretval(command[:-1], True))


# SHOW POLYGON INSIDE RING (RESIDUE)
# ==================================
def ShowRingRes(selection1, color=None, alpha=None):
    command = 'ShowRingRes '
    command += selstr(selection1) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    return (runretval(command[:-1], True))


# SHOW POLYGON INSIDE RING (ATOM)
# ===============================
def ShowRingAtom(selection1, color=None, alpha=None):
    command = 'ShowRingAtom '
    command += selstr(selection1) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    return (runretval(command[:-1], True))


# SHOW A SPHERICAL ENVIRONMENT
# ============================
def ShowSkySphere(filename):
    command = 'ShowSkySphere '
    command += 'Filename=' + cstr(filename) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW SURFACE (ALL OR SELECTED)
# ==============================
def ShowSurf(Type=None, update=None, outcol=None, outalpha=None, incol=None, inalpha=None, specular=None):
    command = 'ShowSurf '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW SURFACE (ALL)
# ==================
def ShowSurfAll(Type=None, update=None, outcol=None, outalpha=None, incol=None, inalpha=None, specular=None):
    command = 'ShowSurfAll '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW SURFACE (OBJECT)
# =====================
def ShowSurfObj(selection1, Type=None, update=None, outcol=None, outalpha=None, incol=None, inalpha=None,
                specular=None):
    command = 'ShowSurfObj '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW SURFACE (MOLECULE)
# =======================
def ShowSurfMol(selection1, Type=None, update=None, outcol=None, outalpha=None, incol=None, inalpha=None,
                specular=None):
    command = 'ShowSurfMol '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW SURFACE (RESIDUE)
# ======================
def ShowSurfRes(selection1, Type=None, update=None, outcol=None, outalpha=None, incol=None, inalpha=None,
                specular=None):
    command = 'ShowSurfRes '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW SURFACE (ATOM)
# ===================
def ShowSurfAtom(selection1, Type=None, update=None, outcol=None, outalpha=None, incol=None, inalpha=None,
                 specular=None):
    command = 'ShowSurfAtom '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    if (outcol != None): command += 'OutCol=' + cstr(outcol) + ','
    if (outalpha != None): command += 'OutAlpha=' + cstr(outalpha) + ','
    if (incol != None): command += 'InCol=' + cstr(incol) + ','
    if (inalpha != None): command += 'InAlpha=' + cstr(inalpha) + ','
    if (specular != None): command += 'Specular=' + cstr(specular) + ','
    return (runretval(command[:-1], True))


# SHOW TABLE DATA AS 3D OBJECT
# ============================
def ShowTab(selection1, width=None, Range=None, Min=None, mincol=None, Max=None, maxcol=None, style=None):
    command = 'ShowTab '
    command += selstr(selection1) + ','
    if (width != None): command += 'Width=' + cstr(width) + ','
    if (Range != None): command += 'Range=' + cstr(Range) + ','
    if (Min != None): command += 'Min=' + cstr(Min) + ','
    if (mincol != None): command += 'MinCol=' + cstr(mincol) + ','
    if (Max != None): command += 'Max=' + cstr(Max) + ','
    if (maxcol != None): command += 'MaxCol=' + cstr(maxcol) + ','
    if (style != None): command += 'Style=' + cstr(style) + ','
    return (runretval(command[:-1], True))


# SHOW A TORUS
# ============
def ShowTorus(largeradius=None, largeedges=None, smallradius=None, smalledges=None, color=None, alpha=None):
    command = 'ShowTorus '
    if (largeradius != None): command += 'LargeRadius=' + cstr(largeradius) + ','
    if (largeedges != None): command += 'LargeEdges=' + cstr(largeedges) + ','
    if (smallradius != None): command += 'SmallRadius=' + cstr(smallradius) + ','
    if (smalledges != None): command += 'SmallEdges=' + cstr(smalledges) + ','
    if (color != None): command += 'Color=' + cstr(color) + ','
    if (alpha != None): command += 'Alpha=' + cstr(alpha) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SHOW TRACE THROUGH ATOMS
# ========================
def ShowTrace(selection1):
    command = 'ShowTrace '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# OPEN A FILE IN THE WEB BROWSER
# ==============================
def ShowURL(name):
    command = 'ShowURL '
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# SHOW VIEW
# =========
def ShowView(selection1):
    command = 'ShowView '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SHOW A USER INTERFACE WINDOW AND OBTAIN THE INPUT MADE
# ======================================================
def ShowWin(Type, title, *arglist2):
    command = 'ShowWin '
    command += 'Type=' + cstr(Type) + ','
    command += 'Title=' + cstr(title) + ','
    # ANY NUMBER OF VARIABLE ARGUMENTS CAN FOLLOW
    for arglist in arglist2:
        if (type(arglist) != type([])): arglist = [arglist]
        for arg in arglist:
            command += cstr(arg, quoted=(type(arg) != type(1) and type(arg) != type(1.))) + ','
    return (runretval(command[:-1], True))


# SHOW POLYGON MESH AS WIRE FRAME (ALL OR SELECTED)
# =================================================
def ShowWire(update=None, mesh=None, side=None):
    command = 'ShowWire '
    if (update != None): command += 'Update=' + cstr(update) + ','
    if (mesh != None): command += 'Mesh=' + cstr(mesh) + ','
    if (side != None): command += 'Side=' + cstr(side) + ','
    return (runretval(command[:-1], True))


# SHOW POLYGON MESH AS WIRE FRAME (ALL)
# =====================================
def ShowWireAll(update=None, mesh=None, side=None):
    command = 'ShowWireAll '
    if (update != None): command += 'Update=' + cstr(update) + ','
    if (mesh != None): command += 'Mesh=' + cstr(mesh) + ','
    if (side != None): command += 'Side=' + cstr(side) + ','
    return (runretval(command[:-1], True))


# SHOW POLYGON MESH AS WIRE FRAME (OBJECT)
# ========================================
def ShowWireObj(selection1, update=None, mesh=None, side=None):
    command = 'ShowWireObj '
    command += selstr(selection1) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    if (mesh != None): command += 'Mesh=' + cstr(mesh) + ','
    if (side != None): command += 'Side=' + cstr(side) + ','
    return (runretval(command[:-1], True))


# SHOW ATOMS (ALL OR SELECTED)
# ============================
def Show():
    command = 'Show '
    return (runretval(command[:-1], True))


# SHOW ATOMS (ALL)
# ================
def ShowAll():
    command = 'ShowAll '
    return (runretval(command[:-1], True))


# SHOW ATOMS (OBJECT)
# ===================
def ShowObj(selection1):
    command = 'ShowObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SHOW ATOMS (MOLECULE)
# =====================
def ShowMol(selection1):
    command = 'ShowMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SHOW ATOMS (RESIDUE)
# ====================
def ShowRes(selection1):
    command = 'ShowRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SHOW ATOMS (ATOM)
# =================
def ShowAtom(selection1):
    command = 'ShowAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SET/GET SIMULATION STATE
# ========================
def Sim(control=None, In=None):
    command = 'Sim '
    if (control != None): command += 'Control=' + cstr(control) + ','
    if (In != None): command += 'in=' + cstr(In) + ','
    return (runretval(command[:-1], True))


# SET SIMULATION SPEED
# ====================
def SimSpeed(Type):
    command = 'SimSpeed '
    command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# SET/GET NUMBER OF SIMULATION STEPS PER SCREEN AND PAIRLIST UPDATE
# =================================================================
def SimSteps(screen=None, pairlist=None):
    command = 'SimSteps '
    if (screen != None): command += 'Screen=' + cstr(screen) + ','
    if (pairlist != None): command += 'Pairlist=' + cstr(pairlist) + ','
    return (runretval(command[:-1], True))


# GET SOLVENT DENSITY IN SIMULATION CELL
# ======================================
def SolvDensity(name=None):
    command = 'SolvDensity '
    if (name != None): command += 'Name=' + cstr(name) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# CALCULATE SOLVATION ENERGY (ALL OR SELECTED)
# ============================================
def SolvEnergy(method=None):
    command = 'SolvEnergy '
    if (method != None): command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# CALCULATE SOLVATION ENERGY (ALL)
# ================================
def SolvEnergyAll(method=None):
    command = 'SolvEnergyAll '
    if (method != None): command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# CALCULATE SOLVATION ENERGY (OBJECT)
# ===================================
def SolvEnergyObj(selection1, method=None):
    command = 'SolvEnergyObj '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# CALCULATE SOLVATION ENERGY (MOLECULE)
# =====================================
def SolvEnergyMol(selection1, method=None):
    command = 'SolvEnergyMol '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# CALCULATE SOLVATION ENERGY (RESIDUE)
# ====================================
def SolvEnergyRes(selection1, method=None):
    command = 'SolvEnergyRes '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# CALCULATE SOLVATION ENERGY (ATOM)
# =================================
def SolvEnergyAtom(selection1, method=None):
    command = 'SolvEnergyAtom '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# SET/GET SOLVATION PARAMETERS
# ============================
def SolvPar(esolute=None, esolvent=None, resolution=None, ioncon=None):
    command = 'SolvPar '
    if (esolute != None): command += 'eSolute=' + cstr(esolute) + ','
    if (esolvent != None): command += 'eSolvent=' + cstr(esolvent) + ','
    if (resolution != None): command += 'Resolution=' + cstr(resolution) + ','
    if (ioncon != None): command += 'IonCon=' + cstr(ioncon) + ','
    return (runretval(command[:-1], True))


# ASSIGN COMMAND TO SPACEBALL BUTTON
# ==================================
def SpaceballButton(number, com):
    command = 'SpaceballButton '
    command += 'Number=' + cstr(number) + ','
    command += 'Command=' + cstr(com) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SET SPACEBALL PARAMETERS
# ========================
def SpaceballPar(mode=None, movescale=None, rotatescale=None):
    command = 'SpaceballPar '
    if (mode != None): command += 'Mode=' + cstr(mode) + ','
    if (movescale != None): command += 'MoveScale=' + cstr(movescale) + ','
    if (rotatescale != None): command += 'RotateScale=' + cstr(rotatescale) + ','
    return (runretval(command[:-1], True))


# DETERMINE FIRST AND LAST UNIT SPANNING A SELECTION (OBJECT)
# ===========================================================
def SpanObj(selection1):
    command = 'SpanObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DETERMINE FIRST AND LAST UNIT SPANNING A SELECTION (RESIDUE)
# ============================================================
def SpanRes(selection1):
    command = 'SpanRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DETERMINE FIRST AND LAST UNIT SPANNING A SELECTION (ATOM)
# =========================================================
def SpanAtom(selection1):
    command = 'SpanAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SPEED UP MOVEMENTS WHEN GRAPHICS ARE SLOW
# =========================================
def SpeedUp(status=None):
    command = 'SpeedUp '
    if (status != None): command += 'Status=' + cstr(status) + ','
    return (runretval(command[:-1], True))


# SET/GET SPEED AND VELOCITY OF ATOMS (ALL OR SELECTED)
# =====================================================
def Speed(x=None, y=None, z=None):
    command = 'Speed '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET SPEED AND VELOCITY OF ATOMS (ALL)
# =========================================
def SpeedAll(x=None, y=None, z=None):
    command = 'SpeedAll '
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET SPEED AND VELOCITY OF ATOMS (OBJECT)
# ============================================
def SpeedObj(selection1, x=None, y=None, z=None):
    command = 'SpeedObj '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET SPEED AND VELOCITY OF ATOMS (MOLECULE)
# ==============================================
def SpeedMol(selection1, x=None, y=None, z=None):
    command = 'SpeedMol '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET SPEED AND VELOCITY OF ATOMS (RESIDUE)
# =============================================
def SpeedRes(selection1, x=None, y=None, z=None):
    command = 'SpeedRes '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SET/GET SPEED AND VELOCITY OF ATOMS (ATOM)
# ==========================================
def SpeedAtom(selection1, x=None, y=None, z=None):
    command = 'SpeedAtom '
    command += selstr(selection1) + ','
    if (x != None): command += 'X=' + cstr(x) + ','
    if (y != None): command += 'Y=' + cstr(y) + ','
    if (z != None): command += 'Z=' + cstr(z) + ','
    return (runretval(command[:-1], True))


# SPLIT OBJECTS AT SPLIT POINTS (ALL OR SELECTED)
# ===============================================
def Split(center=None, selection1=None, keep=None):
    command = 'Split '
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (selection1 != None): command += selstr(selection1) + ','
    if (keep != None): command += 'Keep=' + cstr(keep) + ','
    return (runretval(command[:-1], True))


# SPLIT OBJECTS AT SPLIT POINTS (ALL)
# ===================================
def SplitAll(center=None, selection1=None, keep=None):
    command = 'SplitAll '
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (selection1 != None): command += selstr(selection1) + ','
    if (keep != None): command += 'Keep=' + cstr(keep) + ','
    return (runretval(command[:-1], True))


# SPLIT OBJECTS AT SPLIT POINTS (OBJECT)
# ======================================
def SplitObj(selection1, center=None, selection2=None, keep=None):
    command = 'SplitObj '
    command += selstr(selection1) + ','
    if (center != None): command += 'Center=' + cstr(center) + ','
    if (selection2 != None): command += selstr(selection2) + ','
    if (keep != None): command += 'Keep=' + cstr(keep) + ','
    return (runretval(command[:-1], True))


# INTRODUCE SPLIT POINTS (MOLECULE)
# =================================
def SplitMol(selection1):
    command = 'SplitMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# INTRODUCE SPLIT POINTS (RESIDUE)
# ================================
def SplitRes(selection1):
    command = 'SplitRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# INTRODUCE SPLIT POINTS (ATOM)
# =============================
def SplitAtom(selection1):
    command = 'SplitAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SET STEREO MODE
# ===============
def Stereo(mode):
    command = 'Stereo '
    command += 'Mode=' + cstr(mode) + ','
    return (runretval(command[:-1], True))


# SET STEREO PARAMETERS
# =====================
def StereoPar(eyedis=None, protru=None):
    command = 'StereoPar '
    if (eyedis != None): command += 'EyeDis=' + cstr(eyedis) + ','
    if (protru != None): command += 'ProTru=' + cstr(protru) + ','
    return (runretval(command[:-1], True))


# SET STICK RADIUS
# ================
def StickRadius(percent):
    command = 'StickRadius '
    command += 'percent=' + cstr(percent) + ','
    return (runretval(command[:-1], True))


# STYLE ATOMS AS STICKS (ALL OR SELECTED)
# =======================================
def Stick():
    command = 'Stick '
    return (runretval(command[:-1], True))


# STYLE ATOMS AS STICKS (ALL)
# ===========================
def StickAll():
    command = 'StickAll '
    return (runretval(command[:-1], True))


# STYLE ATOMS AS STICKS (OBJECT)
# ==============================
def StickObj(selection1):
    command = 'StickObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# STYLE ATOMS AS STICKS (MOLECULE)
# ================================
def StickMol(selection1):
    command = 'StickMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# STYLE ATOMS AS STICKS (RESIDUE)
# ===============================
def StickRes(selection1):
    command = 'StickRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# STYLE ATOMS AS STICKS (ATOM)
# ============================
def StickAtom(selection1):
    command = 'StickAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# STOP LOG RECORDER
# =================
def StopLog():
    command = 'StopLog '
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    return (runretval(command[:-1], 1))


# # STOP RUNNING PLUGIN
# # ===================
# def StopPlugin():
# global std_relay_service, t

# # Shutdown the "service"
# std_relay_service.close()
# # Shutdown the registry
# t.close()


# command='StopPlugin '
# return(runretval(command[:-1],True))

# SET GENERAL DISPLAY STYLE
# =========================
def Style(backbone=None, sidechain=None, hetgroup=None, save=None):
    command = 'Style '
    if (backbone != None): command += 'Backbone=' + cstr(backbone) + ','
    if (sidechain != None): command += 'Sidechain=' + cstr(sidechain) + ','
    if (hetgroup != None): command += 'Hetgroup=' + cstr(hetgroup) + ','
    if (save != None): command += 'Save=' + cstr(save) + ','
    return (runretval(command[:-1], True))


# STYLE WINDOWS
# =============
def StyleWin(Type):
    command = 'StyleWin '
    command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# SUPERPOSE MULTIPLE OBJECTS (OBJECT)
# ===================================
def SupMultiObj(selection1, method=None, match=None, flip=None, unit=None):
    command = 'SupMultiObj '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    if (flip != None): command += 'Flip=' + cstr(flip) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# SUPERPOSE MULTIPLE OBJECTS (MOLECULE)
# =====================================
def SupMultiMol(selection1, method=None, match=None, flip=None, unit=None):
    command = 'SupMultiMol '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    if (flip != None): command += 'Flip=' + cstr(flip) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# SUPERPOSE MULTIPLE OBJECTS (RESIDUE)
# ====================================
def SupMultiRes(selection1, method=None, match=None, flip=None, unit=None):
    command = 'SupMultiRes '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    if (flip != None): command += 'Flip=' + cstr(flip) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# SUPERPOSE MULTIPLE OBJECTS (ATOM)
# =================================
def SupMultiAtom(selection1, method=None, match=None, flip=None, unit=None):
    command = 'SupMultiAtom '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    if (flip != None): command += 'Flip=' + cstr(flip) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# SUPERPOSE OBJECTS ON ORDERED UNITS (MOLECULE)
# =============================================
def SupOrderedMol(selection1, selection2, selection3, selection4, selection5, selection6, *arglist2):
    command = 'SupOrderedMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += selstr(selection3) + ','
    command += selstr(selection4) + ','
    command += selstr(selection5) + ','
    command += selstr(selection6) + ','
    # ANY NUMBER OF VARIABLE ARGUMENTS CAN FOLLOW
    for arglist in arglist2:
        if (type(arglist) != type([])): arglist = [arglist]
        for arg in arglist:
            command += cstr(arg, quoted=(type(arg) != type(1) and type(arg) != type(1.))) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SUPERPOSE OBJECTS ON ORDERED UNITS (RESIDUE)
# ============================================
def SupOrderedRes(selection1, selection2, selection3, selection4, selection5, selection6, *arglist2):
    command = 'SupOrderedRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += selstr(selection3) + ','
    command += selstr(selection4) + ','
    command += selstr(selection5) + ','
    command += selstr(selection6) + ','
    # ANY NUMBER OF VARIABLE ARGUMENTS CAN FOLLOW
    for arglist in arglist2:
        if (type(arglist) != type([])): arglist = [arglist]
        for arg in arglist:
            command += cstr(arg, quoted=(type(arg) != type(1) and type(arg) != type(1.))) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SUPERPOSE OBJECTS ON ORDERED UNITS (ATOM)
# =========================================
def SupOrderedAtom(selection1, selection2, selection3, selection4, selection5, selection6, *arglist2):
    command = 'SupOrderedAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    command += selstr(selection3) + ','
    command += selstr(selection4) + ','
    command += selstr(selection5) + ','
    command += selstr(selection6) + ','
    # ANY NUMBER OF VARIABLE ARGUMENTS CAN FOLLOW
    for arglist in arglist2:
        if (type(arglist) != type([])): arglist = [arglist]
        for arg in arglist:
            command += cstr(arg, quoted=(type(arg) != type(1) and type(arg) != type(1.))) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SUPERPOSE OBJECTS (OBJECT)
# ==========================
def SupObj(selection1, selection2, match=None, flip=None, unit=None):
    command = 'SupObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    if (flip != None): command += 'Flip=' + cstr(flip) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# SUPERPOSE OBJECTS (MOLECULE)
# ============================
def SupMol(selection1, selection2, match=None, flip=None, unit=None):
    command = 'SupMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    if (flip != None): command += 'Flip=' + cstr(flip) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# SUPERPOSE OBJECTS (RESIDUE)
# ===========================
def SupRes(selection1, selection2, match=None, flip=None, unit=None):
    command = 'SupRes '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    if (flip != None): command += 'Flip=' + cstr(flip) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# SUPERPOSE OBJECTS (ATOM)
# ========================
def SupAtom(selection1, selection2, match=None, flip=None, unit=None):
    command = 'SupAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (match != None): command += 'Match=' + cstr(match) + ','
    if (flip != None): command += 'Flip=' + cstr(flip) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# SET/GET SURFACE PARAMETERS
# ==========================
def SurfPar(probe=None, resolution=None, molecular=None, espmax=None, smoothcut=None, radii=None, unite=None):
    command = 'SurfPar '
    if (probe != None): command += 'Probe=' + cstr(probe) + ','
    if (resolution != None): command += 'Resolution=' + cstr(resolution) + ','
    if (molecular != None): command += 'Molecular=' + cstr(molecular) + ','
    if (espmax != None): command += 'ESPMax=' + cstr(espmax) + ','
    if (smoothcut != None): command += 'SmoothCut=' + cstr(smoothcut) + ','
    if (radii != None): command += 'Radii=' + cstr(radii) + ','
    if (unite != None): command += 'Unite=' + cstr(unite) + ','
    return (runretval(command[:-1], True))


# CALCULATE DISTANCE FROM SURFACE (OBJECT)
# ========================================
def SurfDisObj(selection1, Type, results=None):
    command = 'SurfDisObj '
    command += selstr(selection1) + ','
    command += 'Type=' + cstr(Type) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# CALCULATE DISTANCE FROM SURFACE (MOLECULE)
# ==========================================
def SurfDisMol(selection1, Type, results=None):
    command = 'SurfDisMol '
    command += selstr(selection1) + ','
    command += 'Type=' + cstr(Type) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# CALCULATE DISTANCE FROM SURFACE (RESIDUE)
# =========================================
def SurfDisRes(selection1, Type, results=None):
    command = 'SurfDisRes '
    command += selstr(selection1) + ','
    command += 'Type=' + cstr(Type) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# CALCULATE DISTANCE FROM SURFACE (ATOM)
# ======================================
def SurfDisAtom(selection1, Type, results=None):
    command = 'SurfDisAtom '
    command += selstr(selection1) + ','
    command += 'Type=' + cstr(Type) + ','
    if (results != None): command += 'Results=' + cstr(results) + ','
    return (runretval(command[:-1], True))


# CALCULATE ELECTROSTATIC SURFACE POTENTIALS (ALL OR SELECTED)
# ============================================================
def SurfESP(Type=None, method=None, unit=None):
    command = 'SurfESP '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE ELECTROSTATIC SURFACE POTENTIALS (ALL)
# ================================================
def SurfESPAll(Type=None, method=None, unit=None):
    command = 'SurfESPAll '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE ELECTROSTATIC SURFACE POTENTIALS (OBJECT)
# ===================================================
def SurfESPObj(selection1, Type=None, method=None, unit=None):
    command = 'SurfESPObj '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE ELECTROSTATIC SURFACE POTENTIALS (MOLECULE)
# =====================================================
def SurfESPMol(selection1, Type=None, method=None, unit=None):
    command = 'SurfESPMol '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE ELECTROSTATIC SURFACE POTENTIALS (RESIDUE)
# ====================================================
def SurfESPRes(selection1, Type=None, method=None, unit=None):
    command = 'SurfESPRes '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE ELECTROSTATIC SURFACE POTENTIALS (ATOM)
# =================================================
def SurfESPAtom(selection1, Type=None, method=None, unit=None):
    command = 'SurfESPAtom '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE SURFACE AREAS (ALL OR SELECTED)
# =========================================
def Surf(Type=None, unit=None):
    command = 'Surf '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE SURFACE AREAS (ALL)
# =============================
def SurfAll(Type=None, unit=None):
    command = 'SurfAll '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE SURFACE AREAS (OBJECT)
# ================================
def SurfObj(selection1, Type=None, unit=None):
    command = 'SurfObj '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE SURFACE AREAS (MOLECULE)
# ==================================
def SurfMol(selection1, Type=None, unit=None):
    command = 'SurfMol '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE SURFACE AREAS (RESIDUE)
# =================================
def SurfRes(selection1, Type=None, unit=None):
    command = 'SurfRes '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CALCULATE SURFACE AREAS (ATOM)
# ==============================
def SurfAtom(selection1, Type=None, unit=None):
    command = 'SurfAtom '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    return (runretval(command[:-1], True))


# CHANGE CHEMICAL ELEMENT OR ADD FUNCTIONAL GROUP
# ===============================================
def SwapAtom(selection1, element, updatebonds=None, updatehyd=None, rename=None, attachpoint=None):
    command = 'SwapAtom '
    command += selstr(selection1) + ','
    command += 'Element=' + cstr(element) + ','
    if (updatebonds != None): command += 'UpdateBonds=' + cstr(updatebonds) + ','
    if (updatehyd != None): command += 'UpdateHyd=' + cstr(updatehyd) + ','
    if (rename != None): command += 'Rename=' + cstr(rename) + ','
    if (attachpoint != None): command += 'AttachPoint=' + cstr(attachpoint) + ','
    return (runretval(command[:-1], True))


# SWAP ORDER OF COVALENT BONDS
# ============================
def SwapBond(selection1, selection2, order=None, update=None):
    command = 'SwapBond '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (order != None): command += 'Order=' + cstr(order) + ','
    if (update != None): command += 'Update=' + cstr(update) + ','
    return (runretval(command[:-1], True))


# SWAP HYDROGEN ORDERING IN RESIDUES (ALL OR SELECTED)
# ====================================================
def SwapHyd(order):
    command = 'SwapHyd '
    command += 'Order=' + cstr(order) + ','
    return (runretval(command[:-1], True))


# SWAP HYDROGEN ORDERING IN RESIDUES (ALL)
# ========================================
def SwapHydAll(order):
    command = 'SwapHydAll '
    command += 'Order=' + cstr(order) + ','
    return (runretval(command[:-1], True))


# SWAP HYDROGEN ORDERING IN RESIDUES (OBJECT)
# ===========================================
def SwapHydObj(selection1, order):
    command = 'SwapHydObj '
    command += selstr(selection1) + ','
    command += 'Order=' + cstr(order) + ','
    return (runretval(command[:-1], True))


# SWAP IMAGES
# ===========
def SwapImage(selection1, selection2):
    command = 'SwapImage '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    return (runretval(command[:-1], True))


# SWAP TWO OBJECTS IN THE LIST
# ============================
def SwapObj(selection1, selection2):
    command = 'SwapObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    return (runretval(command[:-1], True))


# SWAP ATOM POSITIONS
# ===================
def SwapPosAtom(selection1, selection2, bound=None):
    command = 'SwapPosAtom '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (bound != None): command += 'Bound=' + cstr(bound) + ','
    return (runretval(command[:-1], True))


# SWAP RESIDUE SIDE-CHAINS
# ========================
def SwapRes(selection1, new, isomer=None):
    command = 'SwapRes '
    command += selstr(selection1) + ','
    command += 'new=' + cstr(new) + ','
    if (isomer != None): command += 'Isomer=' + cstr(isomer) + ','
    return (runretval(command[:-1], True))


# SWITCH OBJECTS ON/OFF (ALL OR SELECTED)
# =======================================
def Switch(visibility=None, wait=None):
    command = 'Switch '
    if (visibility != None): command += 'Visibility=' + cstr(visibility) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# SWITCH OBJECTS ON/OFF (ALL)
# ===========================
def SwitchAll(visibility=None, wait=None):
    command = 'SwitchAll '
    if (visibility != None): command += 'Visibility=' + cstr(visibility) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# SWITCH OBJECTS ON/OFF (OBJECT)
# ==============================
def SwitchObj(selection1, visibility=None, wait=None):
    command = 'SwitchObj '
    command += selstr(selection1) + ','
    if (visibility != None): command += 'Visibility=' + cstr(visibility) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# GET SYSTEM TIME
# ===============
def SystemTime():
    command = 'SystemTime '
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SET/GET TABLE CELLS
# ===================
def Tab(selection1, column=None, row=None, page=None, set=None, numformat=None):
    command = 'Tab '
    command += selstr(selection1) + ','
    if (column != None): command += 'Column=' + cstr(column) + ','
    if (row != None): command += 'Row=' + cstr(row) + ','
    if (page != None): command += 'Page=' + cstr(page) + ','
    if (set != None): command += 'Set=' + cstr(set) + ','
    if (numformat != None): command += 'NumFormat=' + cstr(numformat) + ','
    return (runretval(command[:-1], True))


# SET/GET SIMULATION TEMPERATURE
# ==============================
def Temp(degrees=None, reassign=None):
    command = 'Temp '
    if (degrees != None): command += 'degrees=' + cstr(degrees) + ','
    if (reassign != None): command += 'Reassign=' + cstr(reassign) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SET TEMPERATURE CONTROL
# =======================
def TempCtrl(Type):
    command = 'TempCtrl '
    command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# SET/GET SIMULATION TIME
# =======================
def Time(fs=None):
    command = 'Time '
    if (fs != None): command += 'FS=' + cstr(fs) + ','
    result = runretval(command[:-1], True)
    if (result != None and len(result)): return (result[0])
    return (result)


# SET SIMULATION TIMESTEP
# =======================
def TimeStep(inter=None, intra=None):
    command = 'TimeStep '
    if (inter != None): command += 'Inter=' + cstr(inter) + ','
    if (intra != None): command += 'Intra=' + cstr(intra) + ','
    return (runretval(command[:-1], True))


# TRANSFER OBJECTS INTO ANOTHER COORDINATE SYSTEM (ALL OR SELECTED)
# =================================================================
def Transfer(selection1, local=None):
    command = 'Transfer '
    command += selstr(selection1) + ','
    if (local != None): command += 'Local=' + cstr(local) + ','
    return (runretval(command[:-1], True))


# TRANSFER OBJECTS INTO ANOTHER COORDINATE SYSTEM (ALL)
# =====================================================
def TransferAll(selection1, local=None):
    command = 'TransferAll '
    command += selstr(selection1) + ','
    if (local != None): command += 'Local=' + cstr(local) + ','
    return (runretval(command[:-1], True))


# TRANSFER OBJECTS INTO ANOTHER COORDINATE SYSTEM (OBJECT)
# ========================================================
def TransferObj(selection1, selection2, local=None):
    command = 'TransferObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (local != None): command += 'Local=' + cstr(local) + ','
    return (runretval(command[:-1], True))


# GET PREVIOUSLY APPLIED TRANSFORMATIONS
# ======================================
def Transformation(Type=None, number=None):
    command = 'Transformation '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    if (number != None): command += 'Number=' + cstr(number) + ','
    return (runretval(command[:-1], True))


# TRANSFORM OBJECTS (ALL OR SELECTED)
# ===================================
def Transform(keeppos=None):
    command = 'Transform '
    if (keeppos != None): command += 'KeepPos=' + cstr(keeppos) + ','
    return (runretval(command[:-1], True))


# TRANSFORM OBJECTS (ALL)
# =======================
def TransformAll(keeppos=None):
    command = 'TransformAll '
    if (keeppos != None): command += 'KeepPos=' + cstr(keeppos) + ','
    return (runretval(command[:-1], True))


# TRANSFORM OBJECTS (OBJECT)
# ==========================
def TransformObj(selection1, keeppos=None):
    command = 'TransformObj '
    command += selstr(selection1) + ','
    if (keeppos != None): command += 'KeepPos=' + cstr(keeppos) + ','
    return (runretval(command[:-1], True))


# TWIST OBJECTS TO IMPROVE STRUCTURAL ALIGNMENT (OBJECT)
# ======================================================
def TwistObj(selection1, selection2, strength=None, structures=None):
    command = 'TwistObj '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (strength != None): command += 'Strength=' + cstr(strength) + ','
    if (structures != None): command += 'Structures=' + cstr(structures) + ','
    return (runretval(command[:-1], True))


# TWIST OBJECTS TO IMPROVE STRUCTURAL ALIGNMENT (MOLECULE)
# ========================================================
def TwistMol(selection1, selection2, strength=None, structures=None):
    command = 'TwistMol '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (strength != None): command += 'Strength=' + cstr(strength) + ','
    if (structures != None): command += 'Structures=' + cstr(structures) + ','
    return (runretval(command[:-1], True))


# GET THE ATOM TYPE
# =================
def TypeAtom(selection1, method=None):
    command = 'TypeAtom '
    command += selstr(selection1) + ','
    if (method != None): command += 'Method=' + cstr(method) + ','
    return (runretval(command[:-1], True))


# ASSIGN BOND ORDERS AUTOMATICALLY
# ================================
def TypeBond(selection1, selection2, usetopo=None, kekulize=None, hydmissing=None):
    command = 'TypeBond '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (usetopo != None): command += 'useTopo=' + cstr(usetopo) + ','
    if (kekulize != None): command += 'Kekulize=' + cstr(kekulize) + ','
    if (hydmissing != None): command += 'HydMissing=' + cstr(hydmissing) + ','
    return (runretval(command[:-1], True))


# SET NUMBER OF UNDO LEVELS
# =========================
def UndoLevels(number):
    command = 'UndoLevels '
    command += 'Number=' + cstr(number) + ','
    return (runretval(command[:-1], True))


# REMOVE ATOMS FROM GROUP (ALL OR SELECTED)
# =========================================
def Ungroup(name):
    command = 'Ungroup '
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# REMOVE ATOMS FROM GROUP (ALL)
# =============================
def UngroupAll(name):
    command = 'UngroupAll '
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# REMOVE ATOMS FROM GROUP (OBJECT)
# ================================
def UngroupObj(selection1, name):
    command = 'UngroupObj '
    command += selstr(selection1) + ','
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# REMOVE ATOMS FROM GROUP (MOLECULE)
# ==================================
def UngroupMol(selection1, name):
    command = 'UngroupMol '
    command += selstr(selection1) + ','
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# REMOVE ATOMS FROM GROUP (RESIDUE)
# =================================
def UngroupRes(selection1, name):
    command = 'UngroupRes '
    command += selstr(selection1) + ','
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# REMOVE ATOMS FROM GROUP (ATOM)
# ==============================
def UngroupAtom(selection1, name):
    command = 'UngroupAtom '
    command += selstr(selection1) + ','
    command += 'Name=' + cstr(name) + ','
    return (runretval(command[:-1], True))


# DELETE DISTANCES LABELS
# =======================
def UnlabelDis(selection1, selection2, bound=None):
    command = 'UnlabelDis '
    command += selstr(selection1) + ','
    command += selstr(selection2) + ','
    if (bound != None): command += 'bound=' + cstr(bound) + ','
    return (runretval(command[:-1], True))


# DELETE LABELS (ALL OR SELECTED)
# ===============================
def Unlabel():
    command = 'Unlabel '
    return (runretval(command[:-1], True))


# DELETE LABELS (ALL)
# ===================
def UnlabelAll():
    command = 'UnlabelAll '
    return (runretval(command[:-1], True))


# DELETE LABELS (OBJECT)
# ======================
def UnlabelObj(selection1):
    command = 'UnlabelObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DELETE LABELS (MOLECULE)
# ========================
def UnlabelMol(selection1):
    command = 'UnlabelMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DELETE LABELS (SEGMENT)
# =======================
def UnlabelSeg(selection1):
    command = 'UnlabelSeg '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DELETE LABELS (RESIDUE)
# =======================
def UnlabelRes(selection1):
    command = 'UnlabelRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# DELETE LABELS (ATOM)
# ====================
def UnlabelAtom(selection1):
    command = 'UnlabelAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# LET ANIMATED IMAGE DISAPPEAR
# ============================
def UnrestImage(selection1):
    command = 'UnrestImage '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# UNSELECT ATOMS (ALL OR SELECTED)
# ================================
def Unselect():
    command = 'Unselect '
    return (runretval(command[:-1], True))


# UNSELECT ATOMS (ALL)
# ====================
def UnselectAll():
    command = 'UnselectAll '
    return (runretval(command[:-1], True))


# UNSELECT ATOMS (OBJECT)
# =======================
def UnselectObj(selection1):
    command = 'UnselectObj '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# UNSELECT ATOMS (MOLECULE)
# =========================
def UnselectMol(selection1):
    command = 'UnselectMol '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# UNSELECT ATOMS (RESIDUE)
# ========================
def UnselectRes(selection1):
    command = 'UnselectRes '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# UNSELECT ATOMS (ATOM)
# =====================
def UnselectAtom(selection1):
    command = 'UnselectAtom '
    command += selstr(selection1) + ','
    return (runretval(command[:-1], True))


# SET USER INPUT
# ==============
def UserInput(status=None):
    command = 'UserInput '
    if (status != None): command += 'Status=' + cstr(status) + ','
    return (runretval(command[:-1], True))


# GET ORIENTATION VECTORS
# =======================
def VecOri(alpha, beta, gamma):
    command = 'VecOri '
    command += 'Alpha=' + cstr(alpha) + ','
    command += 'Beta=' + cstr(beta) + ','
    command += 'Gamma=' + cstr(gamma) + ','
    return (runretval(command[:-1], True))


# WAIT FOR CERTAIN TIME PERIOD OR CONDITION
# =========================================
def Wait(steps, unit=None):
    command = 'Wait '
    command += cstr(steps) + ','
    if (unit != None): command += 'Unit=' + cstr(unit) + ','
    # ALWAYS GET A RETURN VALUE TO SYNCHRONIZE THREADS
    result = runretval(command[:-1], 1)
    if (result != None and len(result)): return (result[0])
    return (result)


# TREAT WARNINGS AS ERRORS
# ========================
def WarnIsError(flag):
    command = 'WarnIsError '
    command += 'Flag=' + cstr(flag) + ','
    return (runretval(command[:-1], True))


# SET TIMEOUT FOR INTERNET CONNECTIONS
# ====================================
def WebTimeout(seconds=None):
    command = 'WebTimeout '
    if (seconds != None): command += 'Seconds=' + cstr(seconds) + ','
    return (runretval(command[:-1], True))


# CALCULATE VOLUMES (ALL OR SELECTED)
# ===================================
def Volume(Type=None):
    command = 'Volume '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE VOLUMES (ALL)
# =======================
def VolumeAll(Type=None):
    command = 'VolumeAll '
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE VOLUMES (OBJECT)
# ==========================
def VolumeObj(selection1, Type=None):
    command = 'VolumeObj '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE VOLUMES (MOLECULE)
# ============================
def VolumeMol(selection1, Type=None):
    command = 'VolumeMol '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE VOLUMES (RESIDUE)
# ===========================
def VolumeRes(selection1, Type=None):
    command = 'VolumeRes '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# CALCULATE VOLUMES (ATOM)
# ========================
def VolumeAtom(selection1, Type=None):
    command = 'VolumeAtom '
    command += selstr(selection1) + ','
    if (Type != None): command += 'Type=' + cstr(Type) + ','
    return (runretval(command[:-1], True))


# SET WINDOW FONT
# ===============
def WinFont(location, name=None, height=None):
    command = 'WinFont '
    command += 'Location=' + cstr(location) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    return (runretval(command[:-1], True))


# SET WINDOW BACKGROUND TEXTURE
# =============================
def WinTexture(number):
    command = 'WinTexture '
    command += 'Number=' + cstr(number) + ','
    return (runretval(command[:-1], True))


# WRITE HTML REPORT
# =================
def WriteReport():
    RaiseError('This command is only available with extensions Title,Heading,Paragraph,Table,Plot,Image,End in Python')


# WRITE HTML REPORT
# =================
# THIS IS ALTERNATIVE 1, WITH DIFFERENT PARAMETERS
def WriteReportTitle(filename, text):
    command = 'WriteReport Title,'
    command += 'Filename=' + cstr(filename) + ','
    command += 'Text=' + cstr(text, 1) + ','
    return (runretval(command[:-1], True))


# WRITE HTML REPORT
# =================
# THIS IS ALTERNATIVE 2, WITH DIFFERENT PARAMETERS
def WriteReportHeading(level, text):
    command = 'WriteReport Heading,'
    command += 'Level=' + cstr(level) + ','
    command += 'Text=' + cstr(text, 1) + ','
    return (runretval(command[:-1], True))


# WRITE HTML REPORT
# =================
# THIS IS ALTERNATIVE 3, WITH DIFFERENT PARAMETERS
def WriteReportParagraph(text):
    command = 'WriteReport Paragraph,'
    command += 'Text=' + cstr(text, 1) + ','
    return (runretval(command[:-1], True))


# WRITE HTML REPORT
# =================
# THIS IS ALTERNATIVE 4, WITH DIFFERENT PARAMETERS
def WriteReportTable(selection1, caption=None, numformat=None, rowsmax=None, infocolumn=None, datacolumn=None,
                     datacolumns=None, *arglist2):
    command = 'WriteReport Table,'
    command += selstr(selection1) + ','
    if (caption != None): command += 'Caption=' + cstr(caption) + ','
    if (numformat != None): command += 'NumFormat=' + cstr(numformat) + ','
    if (rowsmax != None): command += 'RowsMax=' + cstr(rowsmax) + ','
    if (infocolumn != None): command += 'InfoColumn=' + cstr(infocolumn) + ','
    if (datacolumn != None): command += 'DataColumn=' + cstr(datacolumn) + ','
    if (datacolumns != None): command += 'DataColumns=' + cstr(datacolumns) + ','
    # ANY NUMBER OF VARIABLE ARGUMENTS CAN FOLLOW
    for arglist in arglist2:
        if (type(arglist) != type([])): arglist = [arglist]
        for arg in arglist:
            command += cstr(arg, quoted=(type(arg) != type(1) and type(arg) != type(1.))) + ','
    return (runretval(command[:-1], True))


# WRITE HTML REPORT
# =================
# THIS IS ALTERNATIVE 5, WITH DIFFERENT PARAMETERS
def WriteReportPlot(caption, selection1, width, height, title, Type, xcolumn, ycolumn, ycolumns, xlabel, ylabel,
                    legendpos, graphname, *arglist2):
    command = 'WriteReport Plot,'
    command += 'Caption=' + cstr(caption) + ','
    command += selstr(selection1) + ','
    command += 'Width=' + cstr(width) + ','
    command += 'Height=' + cstr(height) + ','
    command += 'Title=' + cstr(title) + ','
    command += 'Type=' + cstr(Type) + ','
    command += 'XColumn=' + cstr(xcolumn) + ','
    command += 'YColumn=' + cstr(ycolumn) + ','
    command += 'YColumns=' + cstr(ycolumns) + ','
    command += 'XLabel=' + cstr(xlabel) + ','
    command += 'YLabel=' + cstr(ylabel) + ','
    command += 'LegendPos=' + cstr(legendpos) + ','
    command += 'GraphName=' + cstr(graphname) + ','
    # ANY NUMBER OF VARIABLE ARGUMENTS CAN FOLLOW
    for arglist in arglist2:
        if (type(arglist) != type([])): arglist = [arglist]
        for arg in arglist:
            command += cstr(arg, quoted=(type(arg) != type(1) and type(arg) != type(1.))) + ','
    return (runretval(command[:-1], True))


# WRITE HTML REPORT
# =================
# THIS IS ALTERNATIVE 6, WITH DIFFERENT PARAMETERS
def WriteReportImage(filename, style=None, caption=None, width=None, height=None, name=None, delete=None):
    command = 'WriteReport Image,'
    command += 'Filename=' + cstr(filename) + ','
    if (style != None): command += 'Style=' + cstr(style) + ','
    if (caption != None): command += 'Caption=' + cstr(caption) + ','
    if (width != None): command += 'Width=' + cstr(width) + ','
    if (height != None): command += 'Height=' + cstr(height) + ','
    if (name != None): command += 'Name=' + cstr(name) + ','
    if (delete != None): command += 'Delete=' + cstr(delete) + ','
    return (runretval(command[:-1], True))


# WRITE HTML REPORT
# =================
# THIS IS ALTERNATIVE 7, WITH DIFFERENT PARAMETERS
def WriteReportEnd():
    command = 'WriteReport End,'
    return (runretval(command[:-1], True))


# ZOOM IN ON ATOMS (ALL OR SELECTED)
# ==================================
def Zoom(steps=None, wait=None):
    command = 'Zoom '
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# ZOOM IN ON ATOMS (ALL)
# ======================
def ZoomAll(steps=None, wait=None):
    command = 'ZoomAll '
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# ZOOM IN ON ATOMS (OBJECT)
# =========================
def ZoomObj(selection1, steps=None, wait=None):
    command = 'ZoomObj '
    command += selstr(selection1) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# ZOOM IN ON ATOMS (MOLECULE)
# ===========================
def ZoomMol(selection1, steps=None, wait=None):
    command = 'ZoomMol '
    command += selstr(selection1) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# ZOOM IN ON ATOMS (RESIDUE)
# ==========================
def ZoomRes(selection1, steps=None, wait=None):
    command = 'ZoomRes '
    command += selstr(selection1) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# ZOOM IN ON ATOMS (ATOM)
# =======================
def ZoomAtom(selection1, steps=None, wait=None):
    command = 'ZoomAtom '
    command += selstr(selection1) + ','
    if (steps != None): command += 'Steps=' + cstr(steps) + ','
    if (wait != None): command += 'Wait=' + cstr(wait) + ','
    return (runretval(command[:-1], True))


# AA -- Nov 2021 --
# =================

def yapycon_get_connection_info():
    """
    Returns the connection info for the existing kernel. 
    
    Notes:
        * This is useful information when trying to connect to an existing kernel.
    """
    return std_relay_service.root.get_connection_info()


def yapycon_reformat_atominfo_returned(atom_info, format, delim=","):
    """
    Reformats a list of atom information returned from certain YASARA's List... functions, taking into account the 
    requested format.
    
    Notes: 
        * This is a convenience function that re-packages the strings that are returned from YASARA to dictionaries
          with the attribute names as keys and the return value marshaled to the right data type too.
    
    :param atom_info: A list of strings just as returned from a List command. For more information on attribute 
                      names run a "Help ListAtom" from within YASARA.
    :type atom_info: list
    :param format: A delimited string with field names defining the returned format. As of YASARA version 21.8.26, the 
                   marshalled attributes are ``RESNUMWIC, ATOMNUM, CHARGE``. For more information on the complete list
                   please run a "Help Label" from within YASARA.
    :type format: str
    :param delim: The delimiter used to delimit attributes in format, the default is ``,``.
    :type delim: str
    
    :returns: A list of dictionaries enabling fast lookups to the returned information.
    :rtype: list[dict[attr, value]]
    
    :raises: TypeError if ``atom_info`` is not a list or if ``format`` is not a str, ValueError if ``format`` contains
             duplicate attribute names.
    """
    atom_info_type = type(atom_info)
    format_type = type(format)

    if atom_info_type is not list:
        raise TypeError(f"atom_info expected to be list, received {atom_info_type}")
    if format_type is not str:
        raise TypeError(f"format expected to be str, received {format_type}")
    format_list = format.replace(" ", "").split(delim)
    if len(format_list) != len(set(format_list)):
        raise ValueError(f"Duplicate attribute names were found in format: {format}")
    
    # Type conversion lookup to marshall certain attributes in the right Python data type.
    attr_to_type = {"RESNUMWIC": int,
                    "ATOMNUM": int,
                    "CHARGE": float,}

    # Build a mapping key-->value where:
    #   * Key is the result of the delimited attributes list from the format variable; and
    #   * Value is the type converted result of the delimited attributes list from the returned information
    #       * If a type conversion is possible, otherwise the value is the returned value itself.
    return [dict(map(lambda x: (x[0],
                                attr_to_type[x[0]](x[1])) if x[0] in attr_to_type else (x[0], x[1]),
                 zip(format_list,
                     an_item.replace(" ", "").split(",")))) for an_item in atom_info]


def yapycon_reformat_bondinfo_returned(bond_info, num_of_results):
    """
    Reformats a list of (covalent) bond information returned from YASARA taking into account the requested format.

    Notes:
        * Similar functionality can be provided to "decode" (or "repackage") the output of the rest of the 
          ``List...`` YASARA functions.
                     
    :param bond_info: The raw output from ``ListBond()``
    :type bond_info: list
    :param num_of_results: The number of results that was passed to ``ListBond()``, which determines the structure of
                           the returned results.
    :type num_of_results: int
    
    :returns: A list of dictionaries whose keys are determined by ``num_of_results``. The keys are:
              ``atomnum_sel1, atomnum_sel2, bond_order, bond_length``. This means that if ``num_of_results=2``, the
              returned dictionaries will have a length of two and contain the first two keys (i.e. ``atomnum_sel1,
              atomnum_sel2``). Similarly for ``1<=num_of_results<=4``.
    :rtype: list[dict[str, num]]
    :raises: ``TypeError`` if ``bond_info`` is not a list, if ``num_of_results`` is not ``int`` and ``ValueError`` if
             ``num_of_results`` is out of the interval ``[1,4]``.
    """
    bond_info_type = type(bond_info)
    num_of_results_type = type(num_of_results)

    if bond_info_type is not list:
        raise TypeError(f"bond_info expected to be list, received {bond_info_type}")
    if num_of_results_type is not int:
        raise TypeError(f"num_of_results expected to be int, received {num_of_results_type}")
    if not (1 <= num_of_results <= 4):
        raise ValueError(f"num_of_results should take a value between 1 and 4, received: {num_of_results}")
        
    bond_attrs = ["atomnum_sel1", "atomnum_sel2", "bond_order", "bond_length"][0:num_of_results]

    return [dict(zip(bond_attrs,
                     bond_info[an_item_idx:(an_item_idx+num_of_results)])) for an_item_idx in range(0,
                                                                                                    len(bond_info),
                                                                                                    num_of_results)]

def yapycon_access_image_returned(filename, current_retval=None):
    """
    Opens and returns an image as a numpy array
    
    Notes:
        * This function is used throughout yasara_kernel wherever YASARA commands are returning images so that it is 
          easier to plot them in a Jupyter control.
    
    :param filename: The graphics file that a particular command (e.g. SavePNG, RayTrace) produces
    :type filename: str(path)
    :param current_retval: The result of runretval for the command that produces the output.This guarantess that the
                           image will have been saved and simplifies the re-usability of the function.
    :type current_retval: list
    :returns: A numpy array if Matplotlib is available and the file could be located or None otherwise
    :rtype: numpy | None    
    """
    # YaPyCon Modification (Dec 2021)
    # The following code is not part of yasara.py.
    # It attempts to read the image in filename and
    #  returns it to the command line where it can be
    # plotted using matplotlib.
    if MATPLOTLIB_AVAILABLE and os.path.exists(filename):
        image_data = plt.imread(filename)
    if image_data is not None:
        return image_data
    else:
        return current_retval

# INITIALIZE THE PLUGIN
# =====================
# Get the "bridge" to the already initialised module information.
# Exception handling is necessary here to allow Sphinx to import the module for documentation purposes.
try:
    std_relay_service = rpyc.connect("localhost", 18861)
    
    # Retrieve the variables that have already been initialised 
    plugin = std_relay_service.root.get_plugin()
    request = std_relay_service.root.get_request_str()
    opsys = std_relay_service.root.get_opsys()
    version = std_relay_service.root.get_version()
    serialnumber = std_relay_service.root.get_serialnumber()
    stage = std_relay_service.root.get_stage()
    owner = std_relay_service.root.get_owner()
    permissions = std_relay_service.root.get_permissions()
    workdir = std_relay_service.root.get_workdir()
    selection = std_relay_service.root.get_selection()
    com = std_relay_service.root.get_com()
    
    # Change the current working directory to the working directory of YASARA
    os.chdir(workdir)
except ConnectionRefusedError:
    # TODO: MID, A better (noisier) way is required to complain about yasara_kernel.py having been imported OUTSIDE of YaPyCon.
    pass