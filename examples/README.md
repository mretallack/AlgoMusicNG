# Examples

Rendered songs, kept as audible reference output of the re-implementation.

| file | seed | title | length |
|------|------|-------|--------|
| `blue-lady-stinky-policeman-88700d6c.mp3` | `$88700d6c` | The blue lady and the stinky policeman | 02m 36s |
| `my-cindy-is-your-scientist-74f1bc07.mp3` | `$74f1bc07` | My Cindy is your scientist | 03m 24s |

## The blue lady and the stinky policeman — `INIT $88700d6c`

* **Seed / `RandomInit`:** `$88700d6c` (hex), `2289044844` (decimal)
* **Title:** *The blue lady and the stinky policeman*
* **Length:** 02m 36s (26 patterns × 64 steps = 1664 steps at BPM 160)
* **Transpose:** −1 · **step period:** 32 · **timing:** 512 · **arrangement:** 5

This seed was chosen because its **title and length** have been independently
confirmed against the original AlgoMusic v2.4 (the `LOG=` line below). The
audio is a faithful reconstruction, not a bit-exact capture — see the fidelity
notes at the end. The original's `LOG=` line under vamos reads:

```
Date      Time   Songname                           Randominit  Nr  Length
04-11-26 14:02  The blue lady and the stinky pol... $88700d6c   1 (02m 36s)
```

(The 34-char LOG column truncates the name; the full name is as above.)

### Reproduce

```sh
# WAV, exact step tables + real 8SVX sample bank (default renderer)
python3 -m algomusic -s '$88700d6c' -o blue-lady.wav

# then, if you want the MP3 that is committed here
ffmpeg -y -i blue-lady.wav -codec:a libmp3lame -qscale:a 2 \
    blue-lady-stinky-policeman-88700d6c.mp3
```

Defaults used: BPM 160, finetune 100, `render_tables` (no `--synth`/`--approx`).

### Instrument selection (from the picked sample-drawer entries)

`Song.picks` for this seed — the same drawers the original picks from:

| category | file |
|----------|------|
| Chords (3)    | `C-Maj` |
| Melody (1)    | `Pizza` |
| Acid (2)      | `Wet2` |
| Bass (0)      | `KnisterBass2` |
| BreakBeat (8) | `Breakbeat-1` |
| Base (4)      | `Base-7` |
| Clap (5)      | `Clap-Hand` |
| Hihat (6)     | `Hihat-5` |
| Snare (7)     | `Snare-Cool` |

Drum voice ids used: `0x9, 0xa, 0xb, 0xc, 0xd, 0xf` (Base, Hihat, Clap,
Base+Clap, Clap+Hihat, Base+Hihat).

### Per-sample options (filenotes)

The picked bass, `KnisterBass2`, carries a filenote `FINETUNE=1110`; `Wet2`
carries `PHASERDEPTH=13000 PHASERSPEED=100`. These come from the LHA file
comments (lost on a normal filesystem) — see `../docs/sample_options.md`.
The bass FINETUNE is applied (`period * 1000/(1000+1110)`); the PHASER sweep is
modelled in `build_tables` and applied by the renderer as a sample-start
offset (0 for this comment-less example).

Note: `Wet2` being phaser-armed means the *distributed* original would draw two
extra `rand()` when generating this seed and produce a **different song**
("Selfish woman in space", 4m 00s) — the title/length above are the
comment-less ground truth. We deliberately keep the composition comment-less
and apply only the timbre-only options.

### Fidelity notes

Exact (ported 1:1 from the binary — see `../docs/sequencer_0x106256.md` and
`../docs/sample_options.md`):

* the whole RNG stream of the sequencer, so the **title** is byte-exact
  (`tools/verify_groundtruth.py`, 20/20 seeds);
* the per-step period/voice/amp tables — **byte-exact** against the original's
  captured RAM (`tools/compare_tables.py`);
* the voice→sample instrument map (`FUN_001095ea`/`FUN_0010996c`) and playback
  rate (`AUDxPER = period`);
* per-sample `VOLUME` and normal-sample `FINETUNE` (the filenote post-loop
  `0x1071a8`; `tools/verify_comments.py`).

> Because the checked-out bank has no filenotes, the vamos ground truth is the
> *un-finetuned* configuration — so the committed MP3 (which does apply
> `FINETUNE=1110` to the bass) is **not** expected to match a comment-less
> capture sample-for-sample.

Not yet modelled (affects the audio, not the notes/timing): the player's
4-channel voice allocation (channel stealing/retrigger when more than four
voices coincide). The mix in the MP3 is therefore a close but not bit-identical
rendition.

## My Cindy is your scientist — `INIT $74f1bc07`

* **Seed / `RandomInit`:** `$74f1bc07` (hex), `1961999367` (decimal)
* **Title:** *My Cindy is your scientist*
* **Length:** 03m 24s (34 patterns × 64 steps = 2176 steps at BPM 160)
* **Transpose:** −2 · **step period:** 8 · **timing:** 256 · **arrangement:** 2

This is a **randomly chosen seed** (not one of the ground-truth-verified ones);
it is included as a second audible reference of the default renderer. The
title/length are what the port produces; they have not been checked against a
`LOG=` capture of the original.

### Reproduce

```sh
# WAV, exact step tables + real 8SVX sample bank (default renderer)
python3 -m algomusic -s '$74f1bc07' -o my-cindy.wav

# then, if you want the MP3 that is committed here
ffmpeg -y -i my-cindy.wav -codec:a libmp3lame -qscale:a 2 \
    my-cindy-is-your-scientist-74f1bc07.mp3
```

Defaults used: BPM 160, finetune 100, `render_tables` (no `--synth`/`--approx`).

### Instrument selection (from the picked sample-drawer entries)

`Song.picks` for this seed:

| category | file |
|----------|------|
| Chords (3)    | `Strange-Maj` |
| Melody (1)    | `Pianosolo` |
| Acid (2)      | `Distorted` |
| Bass (0)      | `BigBass2` |
| BreakBeat (8) | `breakbeat-6` |
| Base (4)      | `Base-3` |
| Clap (5)      | `Clap-3` |
| Hihat (6)     | `Hihat-8` |
| Snare (7)     | `Snare-3` |

Drum voice ids used: `0x9, 0xa, 0xb, 0xc, 0xd, 0xe, 0xf` (all seven drum
voices). Lead voice `7` (melody), bass voice `6`, chord voices `0..5`.

### Per-sample options (filenotes)

The picked samples carry these LHA filenotes (see `../docs/sample_options.md`):

| sample | filenote |
|--------|----------|
| `Melody/Pianosolo` | `VOLUME=40` |
| `Bass/BigBass2`   | `FINETUNE=1000` |
| `Acid/Distorted`  | `PHASERDEPTH=13000 PHASERSPEED=16` |

`VOLUME=40` and `FINETUNE=1000` are applied by the renderer. As with the first
example, `Distorted` being phaser-armed means the *distributed* original would
draw two extra `rand()` and produce a **different song**; the composition here
is the comment-less one, and the phaser sweep is not applied (the committed MP3
is the comment-less configuration).

### Fidelity notes

Same as the first example: the RNG stream / title, the per-step
period/voice/amp tables, the voice→sample map and per-sample VOLUME/FINETUNE
are exact; the player's 4-channel voice allocation is not modelled, so the mix
is a close but not bit-identical rendition.
