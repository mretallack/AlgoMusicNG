#!/usr/bin/env python3
"""Sanity-check the note-level tables produced by `Song.build_tables()`.

These are *self-consistency* checks (we have no audio ground truth), designed
to catch the failure modes we actually hit while porting the step loop:

  * wrong table length (must be num_patterns*64);
  * a non-rest period below 0x7f -- `FUN_001072d2` never returns <0x7f, so any
    such value means a sign/overflow bug (this is exactly the bug that made
    `0x1072d2` spin forever: feeding it an un-sign-extended short);
  * non-determinism (same seed must give byte-identical tables);
  * a voice id outside the small set the player routes on.

Run:  python3 tools/verify_tables.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algomusic.song import Generator  # noqa: E402

SEEDS = [0x4002, 0x0000FFFF, 0x00123456, 0x00C0FFEE, 0x7FFFFFFF, 0x12345678,
         0x0BADF00D, 0x00000001, 0xABCDEF01, 0x0001E240]

NOTE_TABLES = ("chord", "bass", "lead")
VOICES = {
    "chord_voice": set(range(0, 6)) | {0xFFFF},
    "bass_voice": {6, 0xFFFF},
    "lead_voice": {7, 8, 0xFFFF},
    "drum_period": set(range(9, 0x11)) | {0xFFFF},
}


def check(seed):
    g = Generator(seed)
    s = g.generate()
    s2 = Generator(seed).generate()
    n = s.total_steps
    fails = []
    if n != s.num_patterns * 64:
        fails.append("total_steps %d != %d*64" % (n, s.num_patterns))
    for k, v in s.tables.items():
        if len(v) != n:
            fails.append("%s len %d != %d" % (k, len(v), n))
        if v != s2.tables[k]:
            fails.append("%s non-deterministic" % k)
    # bass/lead periods come straight from FUN_001072d2 (always >= 0x7f);
    # chord periods are that period >> (comp-digit), so they may be smaller.
    for ch in ("bass", "lead"):
        for i, p in enumerate(s.tables["%s_period" % ch]):
            rest = s.tables["%s_voice" % ch][i] == 0xFFFF
            if not rest and not (0x7F <= p <= 0xFFFF):
                fails.append("%s_period[%d]=%#x out of range" % (ch, i, p))
                break
    for i, p in enumerate(s.tables["chord_period"]):
        if not (0 <= p <= 0xFFFF):
            fails.append("chord_period[%d]=%#x out of range" % (i, p))
            break
    for k, allowed in VOICES.items():
        bad = [x for x in set(s.tables[k]) if x not in allowed]
        if bad:
            fails.append("%s has unexpected voices %s" % (k, bad))
    return fails


def main():
    total_fail = 0
    for seed in SEEDS:
        fails = check(seed)
        if fails:
            total_fail += 1
            print("FAIL $%08x" % seed)
            for f in fails:
                print("   -", f)
        else:
            print("OK   $%08x" % seed)
    if total_fail:
        print("%d/%d seeds failed" % (total_fail, len(SEEDS)))
        return 1
    print("%d/%d seeds OK" % (len(SEEDS), len(SEEDS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
