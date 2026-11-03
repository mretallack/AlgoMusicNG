# @runtime Jython
# Export decompiled C for every function, plus a symbol/string index.
# @category Amiga

from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

OUT_C = "/home/mark/git/AlgoMusic/work/decompiled_all.c"
OUT_FUNCS = "/home/mark/git/AlgoMusic/work/functions.txt"
OUT_STR = "/home/mark/git/AlgoMusic/work/strings.txt"

ifc = DecompInterface()
ifc.openProgram(currentProgram)
monitor = ConsoleTaskMonitor()
fm = currentProgram.getFunctionManager()

n = 0
with open(OUT_C, "w") as out, open(OUT_FUNCS, "w") as ff:
    for f in fm.getFunctions(True):
        n += 1
        ff.write("%s %s\n" % (f.getEntryPoint(), f.getName()))
        res = ifc.decompileFunction(f, 60, monitor)
        out.write("\n/* ===== %s @ %s ===== */\n" % (f.getName(), f.getEntryPoint()))
        if res is not None and res.decompileCompleted():
            out.write(res.getDecompiledFunction().getC())
        else:
            out.write("/* decompile failed */\n")

# defined strings
from ghidra.program.model.data import StringDataType
listing = currentProgram.getListing()
with open(OUT_STR, "w") as sf:
    it = listing.getDefinedData(True)
    for d in it:
        dt = d.getDataType()
        if isinstance(dt, StringDataType):
            val = d.getValue()
            if val is not None:
                s = str(val).replace("\n", "\\n")
                sf.write("%s %s\n" % (d.getAddress(), s))

print("ghidra_export: %d functions" % n)
