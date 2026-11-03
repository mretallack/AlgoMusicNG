# AlgoMusic — a Linux/Python re-implementation

**AlgoMusic** (Thomas Schürger, 1995–1998) was an Amiga "algorithmic Techno/House
song player": it composes and plays a brand new song, forever, out of a set of
built-in musical patterns. It was released as *giftware*, binary only —
nobody has published a Linux port or a source reconstruction.

This repository reverse-engineers the original 68000 binary and re-implements
the generator in Python.

```
orig/                     the original Aminet archive (update + full) and unpacked files
full/                     full 1.3 MB archive (includes the sample bank)
work/                     relocated flat 68k image, Ghidra project, decompiled C
tools/                    extraction + Ghidra helper scripts
algomusic/                the Python re-implementation
  db.json                 musical database extracted from the binary
  rng.py                  exact PRNG
  song.py                 generator (RNG + database + selection logic)
  render.py               WAV renderer (synthesised voices)
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
```

## Reproducing the analysis

```bash
make download     # fetch the Aminet archives
make extract      # relocate the 68000 binary -> flat image + reloc list
make ghidra       # (optional) headless Ghidra decompile -> work/decompiled_all.c
make db           # rebuild algomusic/db.json from the image
```

Requires `python3`, `amitools`+`machine68k` (`pip install amitools machine68k`),
`lha`, and — for `make ghidra` — Ghidra 11+ and Java 17+.

## Fidelity

* **Exact:** the PRNG, all musical tables, the title vocabulary, note parsing.
* **Reconstructed:** the per-pattern selection logic (`rand()%n` with
  anti-repeat) and the arrangement walk — faithful to the decompiled control
  flow but not guaranteed bit-identical.
* **Approximated:** audio. The Amiga plays 8SVX samples through Paula; the
  renderer here synthesises four voices (chords/bass/melody/drums) instead, so
  it sounds like AlgoMusic but does not use the sample bank.

## Legal

AlgoMusic is giftware © Thomas Schürger. The binary and samples are included
here only for interoperability/analysis. No original source was available; this
is an independent reverse-engineering effort.
