#!/usr/bin/env python3
"""Compare `Song.build_tables()` against the original's tables under vamos.

Pair with tools/dump_vamos_tables.py:

    python3 tools/dump_vamos_tables.py '$4002' /tmp/orig_4002.bin
    python3 tools/compare_tables.py '$4002' /tmp/orig_4002.bin

Status (seed $4002): chord/bass/drum period+voice+amp and lead voice/amp match
byte-for-byte; ~4% of `lead_period` steps differ by a semitone on minor-chord
melody notes -- see docs/sequencer_0x106256.md ("known residual").
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from algomusic.song import Generator  # noqa: E402

GHIDRA_BASE = 0x100000
VAMOS_BASE = 0x21AC
DELTA = VAMOS_BASE - GHIDRA_BASE
DUMP_LO = 0x10000
DATA_SHIFT = 16   # data-hunk alignment quirk between our image and vamos RAM

TABLES = {
    "chord_period": 0x119198, "chord_voice": 0x113198,
    "bass_period": 0x11A998, "bass_voice": 0x114998, "bass_amp": 0x120998,
    "drum_period": 0x116198, "drum_vol": 0x11C198, "drum_off": 0x122198,
    "lead_period": 0x11D998, "lead_voice": 0x117998, "lead_amp": 0x123998,
}


def main():
    seed = sys.argv[1] if len(sys.argv) > 1 else "$4002"
    path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/orig_4002.bin"
    seed_i = int(seed.replace("$", "").replace("0x", ""), 16)
    d = open(path, "rb").read()

    def tbl(ghidra, n):
        a = ghidra + DELTA + DATA_SHIFT
        o = (a - DUMP_LO) // 2
        return list(struct.unpack(">%dH" % n, d[o * 2:o * 2 + 2 * n]))

    s = Generator(seed_i).generate()
    n = s.total_steps
    worse = 0
    for key, g in TABLES.items():
        orig = tbl(g, n)
        ours = s.tables[key]
        mm = sum(1 for o, u in zip(orig, ours) if o != u)
        flag = "" if mm == 0 else "   <-- %d mismatches" % mm
        if mm:
            worse += 1
        print("%-13s mismatches=%d/%d%s" % (key, mm, n, flag))
    return 0 if worse == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
