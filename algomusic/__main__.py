"""Command line front-end, loosely following AlgoMusic's shell arguments.

Usage:
    python3 -m algomusic [BPM n] [FINETUNE n] [INIT $hex] [-o out.wav] [INFO]
"""
import argparse
import sys

from .song import Generator
from .render import render, render_samples


def main(argv=None):
    p = argparse.ArgumentParser(prog="algomusic", description="AlgoMusic (Python re-implementation)")
    p.add_argument("-b", "--bpm", type=int, default=160, help="tempo 84..200 (default 160)")
    p.add_argument("-f", "--finetune", type=int, default=100, help="global finetune permille")
    p.add_argument("-s", "--seed", default=None, help="INIT hex value (e.g. $4002) for reproducible songs")
    p.add_argument("-o", "--out", default="algomusic.wav", help="output WAV file")
    p.add_argument("-n", "--count", type=int, default=1, help="render N songs")
    p.add_argument("--info", action="store_true", help="print database statistics")
    p.add_argument("--synth", action="store_true",
                   help="use the oscillator synth instead of the real 8SVX sample bank")
    args = p.parse_args(argv)

    if args.info:
        from .song import load_db
        db = load_db()
        for k, v in db.items():
            if k == "_meta":
                continue
            print("%-16s %3d" % (k, len(v)))
        return 0

    if not (84 <= args.bpm <= 200):
        print("AlgoMusic: BPM out of range [84..200]!", file=sys.stderr)
        return 1

    seed = None
    if args.seed is not None:
        seed = int(args.seed.replace("$", "").replace("0x", ""), 16)

    gen = Generator(seed)
    for i in range(args.count):
        song = gen.generate(bpm=args.bpm, finetune=args.finetune)
        out = args.out if args.count == 1 else args.out.replace(".wav", "_%d.wav" % (i + 1))
        if args.synth:
            render(song, out)
        else:
            render_samples(song, out)
        print('Playing song "%s" ($%08x) -> %s' % (song.name, song.seed, out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
