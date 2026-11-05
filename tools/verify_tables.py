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


def check(seed, **kw):
    g = Generator(seed)
    s = g.generate(**kw)
    s2 = Generator(seed).generate(**kw)
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


# Config-gated sequencer variants (see docs/sequencer_0x106256.md).  These are
# unverifiable offline (the original's LOG= line only exists for a default
# run), so we only check self-consistency + that each switch actually does
# something distinct.
VARIANTS = [
    {},
    {"arp_lead": True},
    {"bass_phasing": True},
    {"melody_variations": True},
    {"arp_lead": True, "bass_phasing": True},
    {"melody_variations": True, "arp_lead": True},
    {"speech": True},
]


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

    # --- config-gated variants -------------------------------------------
    vfail = 0
    for seed in SEEDS:
        base = Generator(seed).generate()
        for kw in VARIANTS:
            if not kw:
                continue
            name = "+".join(sorted(kw))
            fails = check(seed, **kw)
            if fails:
                print("FAIL $%08x [%s]" % (seed, name))
                for f in fails:
                    print("   -", f)
                vfail += 1
                continue
            # default spending of RNG is unchanged, so lengths must match
            if Generator(seed).generate(**kw).total_steps != base.total_steps:
                print("FAIL $%08x [%s] step count changed" % (seed, name))
                vfail += 1
    if vfail:
        total_fail += 1
        print("%d variant checks failed" % vfail)
    else:
        print("%d/%d variant configs OK" % (len(VARIANTS) - 1, len(VARIANTS) - 1))

    # the arp-lead switch must actually route the lead voice to the arp id (8)
    if any(8 in set(Generator(sd).generate(arp_lead=True).tables["lead_voice"])
           for sd in SEEDS):
        print("OK   arp_lead routes the lead to voice 8")
    else:
        print("FAIL arp_lead never produced lead voice 8")
        total_fail += 1
    # speech consumes RNG on the global stream -> a different title
    if Generator(0x4002).generate(speech=True).name != Generator(0x4002).generate().name:
        print("OK   speech changes the song (consumes RNG)")
    else:
        print("FAIL speech did not change the song")
        total_fail += 1

    if total_fail:
        print("%d check group(s) failed" % total_fail)
        return 1
    print("%d/%d seeds OK" % (len(SEEDS), len(SEEDS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
