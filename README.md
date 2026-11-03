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

# forced oscillator synth instead of the real 8SVX sample bank
python3 -m algomusic -s '$4002' --synth -o song.wav
```

By default the renderer plays the **real 8SVX instrument bank** shipped with
the Amiga package (`full/AlgoMusic/{Chords,Bass,Melody,Rhythm,Acid}`): chord,
bass and melody samples are resampled to the required note frequency on a
virtual Paula, drums play one-shot. Use `--synth` for the old oscillator
fallback.

## Reproducing the analysis

```bash
make download     # fetch the Aminet archives
make extract      # relocate the 68000 binary -> flat image + reloc list
make ghidra       # (optional) headless Ghidra decompile -> work/decompiled_all.c
make db           # rebuild algomusic/db.json from the image
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
  (`%17, %14, %24, %39, %8, %4, %70, %9`).

Note on `0x10be8c` / `0x10bebe` / `0x10bf50`: these are **SAS/C runtime maths
helpers**, not RNG consumers — `0x10bebe` is 32-bit unsigned division
(quotient in D0, remainder in D1), `0x10be8c` is the modulo and `0x10bf50` is
the 16×16→32 multiply. The moduli are `rand() % n`; the remainder is what every
caller reads. So they shift *nothing*.

**Still needed for *bit-identical* output:**
1. a full line-by-line port of the sequencer `0x106256` (the per-step
   chord/bass/melody/arp/drum note-table fill), including the implicit
   `rand() % n` sites and the `0x10bf50` timing divider — this is the part that
   consumes the bulk of the RNG stream and therefore fixes the song-name too,
   because `0x108816` (title builder) runs *after* `0x106256` on the same
   stream (it rolls adjective, noun, then one of 14 templates);
2. the speech path `0x10ab38`/`0x10b0a2` (only with the `SPEECH` switch);
3. Paula period/volume/offset timing of the player `0x1073e6` for exact audio
   (the new `render_samples` already plays the *real* 8SVX bank, so the timbre
   is right; the sample-level timing/offsets are not yet bit-exact).

**Verification / ground truth.** The original is a shell tool but needs
`graphics.library` + `intuition.library` and direct hardware access. Under
`vamos` (`pip install 'amitools[vamos]'`) it now starts: it locks `PROGDIR:`
for its data, scans every sample directory and creates its `AlgoMusic.port`,
with `graphics.library` supplied via `-O graphics.library=mode:fake,...`. It
then exits cleanly *before* the play loop (no `LOG=` line), because the
intuition/audio state it expects is absent. So we still have no ground-truth to
diff. A real FS-UAE/WinUAE + Kickstart run would emit the

```
Date  Time  Songname  Randominit  Nr  Length
```

log line to validate the port.

## Legal

AlgoMusic is giftware © Thomas Schürger. The binary and samples are included
here only for interoperability/analysis. No original source was available; this
is an independent reverse-engineering effort.
