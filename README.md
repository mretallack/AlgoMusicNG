# AlgoMusic — a Linux/Python re-implementation

**AlgoMusic** (Thomas Schürger, 1995–1997) was an Amiga "algorithmic Techno/House
song player": it composes and plays a brand new song, forever, out of a set of
built-in musical patterns. It was released as *giftware*, binary only —
nobody has published a Linux port or a source reconstruction.

This repository reverse-engineers the original 68000 binary and re-implements
the generator in Python.

```
orig/                     the original Aminet archive (update + full) and unpacked files
full/                     full 1.3 MB archive (includes the sample bank)
work/                     relocated flat 68k image, Ghidra project, decompiled C
tools/                    extraction / Ghidra helpers + verify, vamos-dump, compare
docs/                     RE notes (sequencer, ground truth, Paula capture)
AGENTS.md                 working guide for the codebase
algomusic/                the Python re-implementation
  db.json                 musical database extracted from the binary
  rng.py                  exact PRNG
  song.py                 generator (RNG stream + step-loop playback tables)
  sequencer.py            recovered sequencer primitives (note parse/period)
  samples.py              loader for the real 8SVX sample bank
  amigapattern.py         AmigaDOS pattern matching for the drawer scan
  render.py               WAV renderers (real sample bank / oscillator synth)
  __main__.py             CLI
```

## Recovered from the binary

### The PRNG (byte-exact)
Found at `0x10c844` / `0x10c87a`:

```
srand(seed):  state = seed - 1
rand():       u = (state * 0xE5D + 0xE60) & 0x7FFFFFFF
              state = u - 1
              return u
```

`rand() % n` is used for every selection. The default seed comes from the system
clock; `INIT $hex` on the command line makes songs reproducible.

### The musical database
The code segment carries a read-only data area whose tables are reachable
through pointer arrays in data segment #1 (`0x10dfec`). Recovered tables:

| table | count | meaning |
|-------|------:|---------|
| `song_structs` | 70 | note phrases (chords/bass), 2-digit length prefix |
| `drums_a` / `drums_b` | 17 / 14 | 64-step rhythm patterns (values 1–4) |
| `melody_a` / `melody_b` | 23 / 12 | melody trigger patterns |
| `arps` | 39 | arpeggio trigger patterns |
| `rhythm_mix` | 4 | break-beat variants |
| `song_structures` | 27 | 9 arrangements × 3 strings (arrangement, melody, extra) |
| `speech_pat` | 55 | speech-sample triggers |
| `free_melody` | 21 | "free melody" Markov table (a–u) |
| `echo` | 8 | echo variants |
| `adjectives`, `nouns` | 78 / 71 | song-title vocabulary |
| `notenames` | 12 | c,c#,d,…,a#,h (German notation) |

A note token is 3 chars: `[letter][quality][octave]`, e.g. `a-1` = A minor
triad oct. 0, `C62` = C major-6 oct. 1 (func `0x107340` parses it).

## Usage

```bash
# show the recovered database sizes
python3 -m algomusic --info

# render a song (reproducible seed, default BPM 160)
python3 -m algomusic -s '$4002' -o song.wav

# different tempo / finetune, five songs
python3 -m algomusic -b 176 -f 100 -n 5 -o out.wav

# forced oscillator synth instead of the real 8SVX sample bank
python3 -m algomusic -s '$4002' --synth -o song.wav
```

By default the renderer (`render_tables`) plays the **real 8SVX instrument
bank** shipped with the Amiga package
(`full/AlgoMusic/{Chords,Bass,Melody,Rhythm,Acid}`) driven by the exact
per-step period tables from the sequencer: `freq = 3546895 / period`, resampled
against each sample's own rate; drums play one-shot. Use `--approx` for the old
arrangement-based renderer and `--synth` for the plain oscillator fallback.

Instruments are resolved from the *picked* sample-drawer entries exactly as
`FUN_001095ea`/`FUN_0010996c` do (six chord slots built by name surgery, drums
from the picked Base/Clap/Hihat/Snare/BreakBeat, two-source voices triggered
together).  Pitch, all onsets/rests and the instrument choice therefore come
straight from the binary; only per-sample VOLUME/FINETUNE comments and the
player's 16-voice ring are not modelled yet.

## Reproducing the analysis

```bash
make download     # fetch the Aminet archives
make extract      # relocate the 68000 binary -> flat image + reloc list
make ghidra       # (optional) headless Ghidra decompile -> work/decompiled_all.c
make db           # rebuild algomusic/db.json from the image
make verify       # ground-truth (name+length) and table self-consistency checks
```

Requires `python3`, `amitools`+`machine68k` (`pip install amitools machine68k`),
`lha`, and — for `make ghidra` — Ghidra 11+ and Java 17+.

## Fidelity / roadmap to byte-exact output

**Exact (ported 1:1 from the binary):**
* the PRNG (`0x10c844`/`0x10c87a`);
* every musical table and the title vocabulary;
* note/chord token parsing (`0x107340`);
* the selector helpers: `0x10861c` (category selector incl. its "sticky"
  repeat + reroll conditions), `0x108710` (70-slot permutation) and
  `0x108794` (9-slot permutation) — including the exact one-`rand()`-per-modulo
  behaviour (`rand() % n`, *not* two calls);
* the per-song call order of `0x106256` for structure / phrase / rhythm /
  melody / arp / echo selection, using the original moduli
  (`%17, %14, %24, %39, %8, %4, %70, %9`);
* the **sample-drawer scan** (`0x1094b4`, AmigaDOS patterns) and the sample
  pickers (`0x109bfa`) whose `rand()%count` draws run *before* the sequencer;
* the **whole RNG stream of `0x106256`** for a default run (transpose, the
  arrangement/phrase permutations, the optional step-period and timing rolls,
  the echo / rhythm-mix selectors and the four per-pattern selectors);
* the **title builder `0x108816`** including template fall-through (case 1
  falls into case 2) and the exact retry loops;
* the **note-level output of `0x106256`** — the per-step chord/bass/lead/drum
  period, voice, amplitude and trigger tables (`Song.build_tables()`), using the
  `0x10e6d0` char→semitone table (including the per-step minor-chord patch of
  its `'2'`/`'5'` entries) and signed-16-bit note arithmetic.  Consumes no RNG
  in a default run, so it does not disturb the stream.

The consequence: for the same seed the generated **song name** *and* **song
length** now match the original — verified for 20 seeds in
`tools/verify_groundtruth.py`. (The name is a downstream checksum of the entire
RNG stream, so matching it means the stream is byte-exact.)

Note on `0x10be8c` / `0x10bebe` / `0x10bf50`: these are **SAS/C runtime maths
helpers**, not RNG consumers — `0x10bebe` is 32-bit unsigned division
(quotient in D0, remainder in D1), `0x10be8c` is the modulo and `0x10bf50` is
the 16×16→32 multiply. The moduli are `rand() % n`; the remainder is what every
caller reads. So they shift *nothing*.

**Still needed for *note-level* bit-identical output:**
1. the `0x10e946 != 0` "random melody" variant of `0x106256` (the melody-roll
   retry loops, ring `0x111170`, interval tables `0x10e730/40/5c`) and the
   `0x10e92e`/`0x10e93e` alternate lead/phasing modes;
2. the speech path `0x10ab38`/`0x10b0a2` (only with the `SPEECH` switch);
3. Paula player `0x1073e6`: 16-voice allocation and the `0x1285d8` per-voice
   ring — the per-step period/onset tables *and* the voice→sample instrument
   map are already exact (the latter recovered from the sample loader
   `0x1095ea`/`0x10996c`);
4. sample-DB comment parsing (`0x109c72`…) for per-sample VOLUME/FINETUNE.

**Verification / ground truth.** The original now runs under `vamos`
(`pip install 'amitools[vamos]'`) far enough to generate a song and write its
`LOG=` file — that line is our byte-exact reference. This required teaching
vamos the `DOS ExAll` call the sample loader relies on; apply the shim with

```sh
python3 tools/patch_vamos_exall.py
```

then run (see `docs/groundtruth.md` for the full recipe):

```sh
cd full/AlgoMusic
timeout 60 ~/.local/bin/vamos -q -V "Work:$PWD" -a "PROGDIR:Work:" \
  -O "graphics.library=mode:fake,version:40,num_fake_funcs:300" \
  Work:AlgoMusic.000 NOENV SAFE INIT '$4002' LOG=gt.log NOALLOC
```

which emits

```
Date      Time   Songname                           Randominit  Nr  Length
03-11-26 21:01  Where's that elderly jogger?        $00004002   1 (02m 36s)
```

A table of seed -> song-name references lives in `docs/groundtruth.md`. The
emulator still faults in the Paula/audio layer *after* the log line is written,
which does not affect the reference.

Beyond the name/length, the original writes its per-step playback tables into
emulated RAM *before* it reaches that fault, so `tools/dump_vamos_tables.py`
can snapshot them and `tools/compare_tables.py` can diff them against our port:

```sh
python3 tools/dump_vamos_tables.py '$4002' /tmp/orig_4002.bin
python3 tools/compare_tables.py   '$4002' /tmp/orig_4002.bin
```

**All eleven tables (chord/bass/drum/lead period+voice+amp) are byte-exact**,
confirmed on four seeds (`$4002`, `$1`, `$1e240`, `$c0ffee`). The only historic
residual — 72 `lead_period` steps on minor chords — was the original's per-step
runtime patch of `char_table['2']`/`['5']` (see `docs/sequencer_0x106256.md`).

## Legal

AlgoMusic is giftware © Thomas Schürger. The binary and samples are included
here only for interoperability/analysis. No original source was available; this
is an independent reverse-engineering effort.
