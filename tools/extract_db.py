#!/usr/bin/env python3
"""Extract the AlgoMusic 'algorithmic database' tables from the relocated image.

The tables live in data segment #1 (0x10dfec..0x10e9b0) as arrays of absolute
pointers to NUL-terminated strings in the code segment's read-only data area.
Array boundaries were recovered from the decompiled selectors.
"""
import json, struct, sys

BASE = 0x100000
BIN = "/home/mark/git/AlgoMusic/work/algomusic.bin"
OUT = "/home/mark/git/AlgoMusic/algomusic/db.json"

d = open(BIN, "rb").read()


def rd(a):
    return struct.unpack_from(">i", d, a - BASE)[0]


def cstr(a):
    o = a - BASE
    if o < 0 or o >= len(d):
        return None
    j = d.find(b"\x00", o)
    s = d[o:j]
    if len(s) == 0:
        return None
    return s.decode("latin1")


def arr(start, count, name):
    out = []
    for i in range(count):
        p = rd(start + i * 4)
        out.append(cstr(p) if p else None)
    return name, out


# start address, count, name  (counts derived from selector ranges in code)
TABLES = [
    (0x10DFF0, 70, "song_structs"),   # leading 2-digit value + note pattern
    (0x10E108, 17, "drums_a"),        # rhythm patterns (chars 1-4, -)
    (0x10E14C, 14, "drums_b"),
    (0x10E184, 23, "melody_a"),
    (0x10E1E4, 12, "melody_b"),
    (0x10E214, 39, "arps"),
    (0x10E2B0, 4, "rhythm_mix"),
    (0x10E2C0, 27, "song_structures"),  # 9 groups of 3 arrangement strings
    (0x10E32C, 55, "speech_pat"),
    (0x10E408, 21, "free_melody"),
    (0x10E45C, 8, "echo"),
    (0x10E47C, 78, "adjectives"),
    (0x10E5B4, 71, "nouns"),
    (0x10E6D0, 12, "notenames"),
]

db = {}
for start, count, name in TABLES:
    _, vals = arr(start, count, name)
    db[name] = vals

db["_meta"] = {"base": "0x%08x" % BASE, "source": "AlgoMusic.000"}

with open(OUT, "w") as f:
    json.dump(db, f, indent=1)

for start, count, name in TABLES:
    vals = db[name]
    good = sum(1 for v in vals if v is not None)
    print("%-16s count=%-3d non-null=%d" % (name, count, good))
