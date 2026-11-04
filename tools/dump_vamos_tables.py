#!/usr/bin/env python3
"""Dump the sequencer's output tables from the *original* running under vamos.

The original builds its per-step tables (chord/bass/lead/drum period/voice/amp)
in emulated RAM *before* it reaches the audio layer and faults.  Under vamos the
binary loads at base **0x21ac** (not the Ghidra base 0x100000), so a table that
Ghidra addresses as `G` lives at `G - 0x100000 + 0x21ac`.

This harness runs the binary with the stock vamos `main()` and snapshots the
table region during `Machine.cleanup()`.  Use it to diff our port against the
original:

    python3 tools/dump_vamos_tables.py '$4002' /tmp/orig_tables.bin

then compare with `algomusic.song.Generator(seed).generate().tables`.

Requires the `DOS ExAll` shim (see tools/patch_vamos_exall.py) and amitools[vamos].
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.expanduser("~/.local/lib/python3.13/site-packages"))

import amitools.vamos.main as M  # noqa: E402

WORK = os.path.join(os.path.dirname(__file__), "..", "full", "AlgoMusic")
VAMOS_BASE = 0x21AC               # where vamos loads the image (entry PC)
GHIDRA_BASE = 0x100000
DELTA = VAMOS_BASE - GHIDRA_BASE  # add to a Ghidra address to get the vamos one

# Ghidra addresses of the output tables (see docs/sequencer_0x106256.md)
TABLES = {
    "chord_period": 0x119198, "chord_voice": 0x113198,
    "bass_period": 0x11A998, "bass_voice": 0x114998,
    "bass_amp": 0x120998, "bass_phase": 0x125D98,
    "drum_period": 0x116198, "drum_vol": 0x11C198, "drum_off": 0x122198,
    "lead_period": 0x11D998, "lead_voice": 0x117998,
    "lead_amp": 0x123998, "lead_phase": 0x127598,
    "step_counter": 0x128198, "melody_ring": 0x111170,
}

DATA = {"data": None, "err": None}


class Rec(M.Machine):
    @classmethod
    def from_cfg(cls, machine_cfg, use_labels=False):
        return super(Rec, cls).from_cfg(machine_cfg, use_labels)

    def cleanup(self):
        try:
            mem = self.get_mem()
            if mem is not None:
                buf = bytearray()
                for a in range(0x10000, 0x30000, 2):
                    buf += mem.r16(a).to_bytes(2, "big")
                DATA["data"] = bytes(buf)
        except Exception as e:  # noqa: BLE001
            DATA["err"] = repr(e)
        super(Rec, self).cleanup()


M.Machine = Rec


def main():
    seed = sys.argv[1] if len(sys.argv) > 1 else "$4002"
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/orig_tables.bin"
    work = os.path.abspath(WORK)
    os.chdir(work)

    args = [
        "-q", "-m", "8192",
        "-V", "Work:%s" % work,
        "-a", "PROGDIR:Work:",
        "-O", "graphics.library=mode:fake,version:40,num_fake_funcs:300",
        "Work:AlgoMusic.000", "NOENV", "SAFE", "INIT", seed,
        "LOG=gt.log", "NOALLOC",
    ]
    try:
        print("vamos rc", M.main(args=args))
    except SystemExit as e:  # noqa: BLE001
        print("exit", e)
    except Exception:  # noqa: BLE001
        traceback.print_exc()

    if DATA["err"]:
        print("dump error", DATA["err"])
    if DATA["data"] is None:
        print("no data captured")
        return 2
    open(out, "wb").write(DATA["data"])
    print("dumped %d bytes -> %s (table base region 0x10000..0x30000)"
          % (len(DATA["data"]), out))
    for name, g in sorted(TABLES.items()):
        print("  %-13s ghidra %#08x  vamos %#08x" % (name, g, g + DELTA))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
