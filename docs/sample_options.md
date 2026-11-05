# Per-sample options (the filenotes)

AlgoMusic lets you tune each sample individually by putting a **filenote**
(AmigaDOS file comment) on the sample file.  The parser is `FUN_00109fe0`
@ `0x109fe0`; the sequencer applies the result in its post-loop `0x1071a8`
(inside `FUN_00106256`).  The guide documents the syntax in the "Sample
options" chapter of `AlgoMusic.guide`.

Supported tokens (space separated, `KEY=value`; the bank also uses the sloppy
`KEY value` form):

| token | range | meaning |
|-------|-------|---------|
| `VOLUME` | 0..64 | relative sample volume (default 64) |
| `FINETUNE` | permille | added to the sample's normal frequency; may be negative |
| `PHASERDEPTH` | words | sample-start offset sweep amplitude (acid/melody/bass only) |
| `PHASERSPEED` | words | sample-start offset sweep step (acid/melody/bass only) |

Example (from the guide): `VOLUME=40 FINETUNE=1000 PHASERDEPTH=15000 PHASERSPEED=120`

## Where the filenotes live (and why they were missing)

The original reads the **FFS file comment**, not the IFF `ANNO` chunk.  The
distributed sample bank is an LHA archive whose per-member comments carry
these strings; when the archive is extracted onto a normal (non-Amiga)
filesystem they are silently dropped.  So the checked-out `full/AlgoMusic/`
tree has **no** filenotes even though the real program always saw them.

`tools/extract_comments.py` mines them back out of `AlgoMusic2_4.lha` and
caches them in `algomusic/sample_comments.json` (keyed `"Category/Name"`).
`algomusic/samples.py` loads that cache (`SampleBank.meta`, `parse_comment`).

The renderer always applies the **timbre-only** options (`VOLUME`, `FINETUNE`).
The phaser (which perturbs the composition) is only armed with
`Generator.generate(filenotes=True)` / `python3 -m algomusic --filenotes`.

> Caveat: the ground-truth tables captured under vamos (`tools/dump_vamos_tables.py`)
> were made from that comment-less extraction, so they are the **un-finetuned**
> tables.  `Song.build_tables()` therefore stays un-patched; the FINETUNE
> scaling is applied at render time, mirroring what the original does in
> `0x1071a8` immediately before playback.

## FINETUNE

For normal (chord/bass/melody/acid) samples the guide gives the *frequency*
factor `Factor = (x+1000)/1000`, so the **period** scales by `1000/(x+1000)`.
The binary does exactly this in `0x1071a8`: it loads `0x12865c[voice]` (filled
by `FUN_00109fe0`), computes `period*1000`, adds 1000 to the finetune, and
divides with the signed 32-bit helper `FUN_0010be8c`.  `x == 0` (no comment)
leaves the period untouched; `x == 1000` halves it (one octave up).

This is the *pitch* — not just timbre.  E.g. `Bass/KnisterBass2` has
`FINETUNE=1110`, so it plays ~2.11x the frequency of the un-finetuned base
period.  `algomusic/render.py::apply_finetune()` implements the formula and
`tools/verify_comments.py` checks it against the guide's table.

Speech and breakbeat samples use a different rule (period has to be locked to
the BPM): `period = (30000 - finetune) / bpm`.  This is implemented for the
breakbeat voice id `0x10`.

## VOLUME

Relative sample volume 0..64 ("default 64; if a sample is too loud use a
smaller value").  `FUN_00109fe0` stores it in `0x12860a[voice]` (rejecting
values > 64).  The renderer scales each note by `volume/64`.  The combined
drum voices (`0xc/0xd/0xf`) are pre-mixed by `FUN_00109a02` and keep the
default volume.

## PHASERDEPTH / PHASERSPEED

Moves the sample start offset to and fro while playing (the "transforming"
acid/bass/melody sound).  Depth is in words (2 bytes), so the offset sweeps
from 0 to `depth*2` bytes.  Speed is the per-step word delta; the initial offset
and direction are random.  `FUN_00109fe0` stores the depth/speed in
`0x113180`/`0x11318c` (acid → voice 0, melody → voice 1, bass → voice 2); the
sequencer `FUN_00106256` then runs a triangle oscillator over them (`0x1062b8`
init, `0x1063be`… update) and writes the running offset into the amp tables
(`0x120998` bass, `0x123998` lead).  Parsed and cached, but **not yet applied**
by `render_tables`.

> **Warning: `PHASERDEPTH` changes the song, not just the timbre.**
> When a picked acid/melody/bass sample is phaser-armed, the sequencer draws
> **two extra `rand()` per armed voice** at `0x1062b8`/`0x1062e4`
> (`local_86[i] = rand() % depth`, `abStack_9f[i] = rand() & 1`).  Those draws
> are on the same global stream as everything else, so they shift every later
> decision — including the `rand()&7` step-period tweak (which changes the
> **length**) and the title rolled by `FUN_00108816`.  Since *every* seed in the
> bank picks a phaser-armed acid sample, applying the filenotes moves the whole
> song-space.
>
> Our ground truth (and the committed example) is therefore the **comment-less**
> configuration: under vamos the extracted files have no filenotes, so the
> depths are 0 and no phaser RNG is drawn.  That is why `verify_groundtruth`
> says 20/20 — and why we deliberately do **not** consume the phaser RNG in
> `Generator.generate()`.  Reproducing the *distributed* program's songs would
> need a filenote-enabled ground truth, which vamos cannot currently produce.
