#!/usr/bin/env python3
"""Verify the Python port against the original's `LOG=` ground truth.

The reference values come from running the real `AlgoMusic.000` under vamos
(see `docs/groundtruth.md`).  The original prints one line per song:

    Date      Time   Songname                           Randominit  Nr  Length
    03-11-26 21:01  Where's that elderly jogger?        $00004002   1 (02m 36s)

Both the *song name* and the *length* are downstream checksums of the whole RNG
stream -- the name is rolled by `FUN_00108816` after the sequencer `FUN_00106256`,
and the length is `num_patterns * 64` steps at the configured BPM.  If both
match for a seed, the port is byte-exact up to note-level content.

Usage:
    python3 tools/verify_groundtruth.py
"""
import sys

sys.path.insert(0, ".")

from algomusic.song import Generator

# seed -> (song name, length in seconds)
GROUND_TRUTH = {
    0x00000001: ("The red John and the nude Jack", 204),
    0x00000002: ("Blue, thin and potential", 276),
    0x00000003: ("Where's that shitty pigeon?", 180),
    0x00000010: ("Another fat busdriver", 180),
    0x00000100: ("Another bizzare salesman", 192),
    0x00001234: ("Meet the mad wife", 156),
    0x00004002: ("Where's that elderly jogger?", 156),
    0x0000ABCD: ("Stupid and shitty", 276),
    0x0000FFFF: ("Sweet and dreaming", 204),
    0x7FFFFFFF: ("Another needful moon", 276),
    0x00000005: ("Follow the stupid mouse", 156),
    0x00000007: ("Another exotic lunatic", 240),
    0x00000042: ("Yellow Tom in space", 276),
    0x0000C0FFEE & 0xFFFFFFFF: ("Nasty turtle", 216),
    0x00123456: ("Another funky gangster", 180),
    0x0000DEAD: ("The cute man in my house", 192),
    0x0000BEEF: ("Sandy, natural and idiotic", 156),
    0x00002718: ("The creepy Tom and the erotic Joe", 216),
    0x0000FACE: ("The mystic Daniel", 156),
    0x00009999: ("Follow the blue elephant", 240),
}


def fmt(sec):
    return "%02dm %02ds" % (sec // 60, sec % 60)


def main():
    ok = 0
    for seed, (want_name, want_len) in sorted(GROUND_TRUTH.items()):
        song = Generator(seed=seed).generate()
        got_len = round(song.duration)
        good = song.name == want_name and got_len == want_len
        ok += good
        print(
            "%s $%08x  np=%-3d  %-34r  %s"
            % (
                "OK " if good else "BAD",
                seed,
                song.num_patterns,
                song.name,
                fmt(got_len),
            )
        )
        if not good:
            print("      expected %r  %s" % (want_name, fmt(want_len)))
    print("%d/%d seeds match" % (ok, len(GROUND_TRUTH)))
    return 0 if ok == len(GROUND_TRUTH) else 1


if __name__ == "__main__":
    sys.exit(main())
