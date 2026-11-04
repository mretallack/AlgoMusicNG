# Examples

Rendered songs, kept as audible reference output of the re-implementation.

| file | seed | title | length |
|------|------|-------|--------|
| `blue-lady-stinky-policeman-88700d6c.mp3` | `$88700d6c` | The blue lady and the stinky policeman | 02m 36s |

## The blue lady and the stinky policeman — `INIT $88700d6c`

* **Seed / `RandomInit`:** `$88700d6c` (hex), `2289044844` (decimal)
* **Title:** *The blue lady and the stinky policeman*
* **Length:** 02m 36s (26 patterns × 64 steps = 1664 steps at BPM 160)
* **Transpose:** −1 · **step period:** 32 · **timing:** 512 · **arrangement:** 5

This seed was chosen because it has been **independently confirmed against the
original AlgoMusic v2.4** — both the generated *title* and the *audio* match
(played on real v2.4 and compared by ear). The original's `LOG=` line under
vamos reads:

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

### Fidelity notes

Exact (ported 1:1 from the binary — see `../docs/sequencer_0x106256.md`):

* the whole RNG stream of the sequencer, so the **title** is byte-exact
  (`tools/verify_groundtruth.py`, 20/20 seeds);
* the per-step period/voice/amp tables — **byte-exact** against the original's
  captured RAM (`tools/compare_tables.py`);
* the voice→sample instrument map (`FUN_001095ea`/`FUN_0010996c`) and playback
  rate (`AUDxPER = period`).

Not yet modelled (affects timbre, not notes/timing): per-sample
VOLUME/FINETUNE from the 8SVX comments, and the player's 16-voice allocation /
ring. The mix in the MP3 is therefore a close but not bit-identical rendition.
