#!/usr/bin/env python3
"""Verify the per-sample filenote handling (VOLUME / FINETUNE / PHASER*).

Checks three independent things:

1. ``parse_comment`` against the guide's own example string;
2. the FINETUNE -> period scaling against the guide's table
   (``Factor = (x+1000)/1000`` on *frequency*, i.e. period ``1000/(x+1000)``),
   which is exactly what ``FUN_00109fe0`` stores and ``0x1071a8`` applies;
3. if the LHA archive is present, that ``algomusic/sample_comments.json`` is
   still byte-for-byte reproducible from it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algomusic.samples import parse_comment, load_comments, COMMENTS_PATH
from algomusic.render import apply_finetune, PAL_CLOCK

fails = 0


def check(cond, msg):
    global fails
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


# 1. parser --------------------------------------------------------------
m = parse_comment("VOLUME=40 FINETUNE=1000 PHASERDEPTH=15000 PHASERSPEED=120")
check(m == {"volume": 40, "finetune": 1000,
            "phaser_depth": 15000, "phaser_speed": 120},
      "guide example string parses")
check(parse_comment("FINETUNE -14000")["finetune"] == -14000,
      "space-separated negative finetune parses")
check(parse_comment("")["volume"] == 64, "defaults: volume 64, ft 0")

# 2. finetune formula (frequency factor = (x+1000)/1000) ----------------
for x, freq_factor in ((0, 1.0), (1000, 2.0), (500, 1.5),
                       (-500, 0.5), (-750, 0.25)):
    p = 3000
    fp = apply_finetune(p, x)
    got = (PAL_CLOCK / fp) / (PAL_CLOCK / p)
    check(abs(got - freq_factor) < 0.01,
          "finetune %+d -> freq x%.3f (want x%.3f)" % (x, got, freq_factor))
check(apply_finetune(1234, 0) == 1234, "finetune 0 leaves period untouched")

# 3. archive <-> cache --------------------------------------------------
lha = os.path.join(os.path.dirname(COMMENTS_PATH), "..", "AlgoMusic2_4.lha")
if os.path.exists(lha):
    from tools.extract_comments import extract
    fresh = extract(lha)
    cached = load_comments()
    check(fresh == cached,
          "sample_comments.json matches fresh extraction (%d entries)"
          % len(cached))
else:
    print("skip: %s not present" % lha)
    check(len(load_comments()) == 56, "comment cache has 56 entries")

# 4. sanity: some known entries ----------------------------------------
c = load_comments()
check(c.get("Bass/KnisterBass2") == "FINETUNE=1110", "KnisterBass2 comment")
check(c.get("Bass/TechBass") == "FINETUNE=1000 VOLUME=56", "TechBass comment")
check("Rhythm/Breakbeat-1" in c, "breakbeat-1 comment present")

# 5. filenotes mode: the phaser arms RNG and must move the song ----------
from algomusic.song import Generator
a = Generator(0x88700d6c).generate()             # comment-less (verified)
b = Generator(0x88700d6c).generate(filenotes=True)
check(a.name == "The blue lady and the stinky policeman",
      "default seed is the verified comment-less song")
check(b.phaser[0][0] == 13000,
      "filenotes: Wet2 PHASERDEPTH arms voice 0")
check(a.name != b.name,
      "phaser RNG shifts the composition (config-B differs from config-A)")
check(Generator(0x88700d6c).generate(filenotes=True).name == b.name,
      "filenotes mode is deterministic")

# 6. phaser triangle oscillator + table fill ----------------------------
from algomusic.song import phaser_step

# bounce: from the peak (dir 1) it must fall to 0 and come back, never leave
# [0, depth].
depth, speed = 1000, 300
off, d = depth, 1
seen = []
for _ in range(20):
    off, d = phaser_step(depth, speed, off, d)
    seen.append(off)
check(all(0 <= v <= depth for v in seen), "phaser stays within [0, depth]")
check(min(seen) == 0 and max(seen) == depth,
      "phaser triangle reaches both 0 and depth")
check(phaser_step(0, 0, 0, 0) == (0, 0), "unarmed voice stays at 0")

# table fill: seed $1 picks Melody/MagicTubes (PHASERDEPTH=1200, armed) and
# Bass/KnisterBass2 (no phaser), Acid/Distorted (awaits the arp branch).
g1 = Generator(1)
s1 = g1.generate(filenotes=True)
check(s1.phaser[1][0] == 1200, "seed $1: MagicTubes arms melody (voice 1)")
t1 = g1.build_tables(s1)
check(any(t1["lead_amp"]) and all(0 <= v <= 1200 for v in t1["lead_amp"]),
      "filenotes: lead sweep-off table is filled within depth")
check(all(t1["bass_amp"][i] == 0 for i in range(len(t1["bass_amp"]))),
      "filenotes: unphased bass stays at offset 0")
# default (comment-less) run must leave the sweep tables at 0 (verified)
g0 = Generator(1)
s0 = g0.generate()
t0 = g0.build_tables(s0)
check(not any(t0["lead_amp"]) and not any(t0["bass_amp"]),
      "default: no sweep any voice (comment-less ground truth)")

print("\n%s (%d failures)" % ("PASS" if fails == 0 else "FAIL", fails))
sys.exit(1 if fails else 0)
