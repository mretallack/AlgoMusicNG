# @runtime Jython
# Ghidra pre-analysis script (Jython).
# Applies the Amiga absreloc32 relocation list: creates memory references and
# recovers functions for relocation targets that point into code segments.
# @category Amiga

import os

BASE = 0x100000
RELOCS_FILE = "/home/mark/git/AlgoMusic/work/algomusic.relocs"

# (start, size) of code segments in the flat image
CODE_SEGS = [
    (0x100000, 0xDFEC),
    (0x1299CC, 0x1F8),
    (0x129BC4, 0x170),
]

from ghidra.program.model.symbol import RefType, SourceType

refmgr = currentProgram.getReferenceManager()
af = currentProgram.getAddressFactory()
space = af.getDefaultAddressSpace()
fm = currentProgram.getFunctionManager()
listing = currentProgram.getListing()


def in_code(addr_int):
    for start, size in CODE_SEGS:
        if start <= addr_int < start + size:
            return True
    return False


nref = 0
nfunc = 0
with open(RELOCS_FILE) as f:
    for line in f:
        parts = line.split()
        if len(parts) != 2:
            continue
        off = int(parts[0], 16)
        tgt = int(parts[1], 16)
        src = space.getAddress(BASE + off)
        dst = space.getAddress(tgt)
        try:
            refmgr.addMemoryReference(src, dst, RefType.DATA, SourceType.USER_DEFINED, 0)
            nref += 1
        except Exception, e:
            pass
        if in_code(tgt):
            fn = fm.getFunctionAt(dst)
            if fn is None:
                try:
                    disassemble(dst)
                    createFunction(dst, None)
                    nfunc += 1
                except:
                    pass

print("ghidra_prep: applied %d refs, created %d functions" % (nref, nfunc))
