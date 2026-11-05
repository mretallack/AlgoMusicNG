#!/usr/bin/env python3
"""Extract the per-sample filenotes (file comments) from the AlgoMusic LHA.

The original binary reads each sample's AmigaDOS **file comment** (the
"filenote") and parses ``VOLUME=x``, ``FINETUNE=x``, ``PHASERDEPTH=x`` and
``PHASERSPEED=x`` out of it -- see ``FUN_00109fe0`` @ 0x109fe0 and the
"Sample options" chapter of ``AlgoMusic.guide``.

Those comments live in the LHA archive (level-0 header: the name field is
``"dir\\file\\0comment"``).  When the archive is extracted onto a normal
filesystem they are silently dropped, so we mine them once here and cache
them as ``algomusic/sample_comments.json`` keyed by ``"Category/Name"``.
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEFAULT_LHA = os.path.join(REPO, "AlgoMusic2_4.lha")
OUT = os.path.join(REPO, "algomusic", "sample_comments.json")

_METHODS = {
    "-lh0-", "-lh1-", "-lh2-", "-lh3-", "-lh4-",
    "-lh5-", "-lh6-", "-lh7-", "-lzs-", "-lz5-",
}


def iter_entries(blob):
    """Yield ``(name, comment)`` for every member of an LHA archive."""
    n = len(blob)
    off = 0
    while off + 22 <= n:
        hsz = blob[off]
        if hsz < 22:
            break
        method = blob[off + 2:off + 7].decode("latin1", "replace")
        if method not in _METHODS:
            break
        comp = struct.unpack_from("<I", blob, off + 7)[0]
        level = blob[off + 20]
        namelen = blob[off + 21]
        namefield = blob[off + 22:off + 22 + namelen]
        p = off + 22 + namelen
        if level >= 1:                       # skip extended headers
            while True:
                esz = struct.unpack_from("<H", blob, p)[0]
                if esz == 0:
                    break
                p += esz
        p += 2                               # header CRC
        name, _, comment = namefield.partition(b"\x00")
        yield (name.decode("latin1").replace("\\", "/"),
               comment.decode("latin1", "replace").strip())
        off = p + comp


def extract(lha_path=DEFAULT_LHA):
    blob = open(lha_path, "rb").read()
    out = {}
    for name, comment in iter_entries(blob):
        if not name.startswith("AlgoMusic/"):
            continue
        rel = name[len("AlgoMusic/"):]
        cat = rel.split("/", 1)[0]
        if cat in ("Acid", "Bass", "Chords", "Melody", "Rhythm", "Speech") \
                and "/" in rel and comment:
            out[rel] = comment
    return out


def main():
    lha = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LHA
    data = extract(lha)
    with open(OUT, "w") as f:
        json.dump(data, f, indent=0, sort_keys=True)
        f.write("\n")
    print("wrote %d sample comments to %s" % (len(data), OUT))


if __name__ == "__main__":
    main()
