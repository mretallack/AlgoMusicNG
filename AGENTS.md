# AGENTS.md — working guide for this repository

This repo is a **from-scratch, byte-faithful re-implementation in Python of the
Amiga program _AlgoMusic_ v2.4** (giftware © 1995–1997 Thomas Schürger). The
goal is: *for the same seed, produce exactly the same song* the original 68000
binary produces.

Everything here is reverse-engineered. There is **no original source**. Read
this file before changing code.

---

## 1. What is in the tree

| path | what it is |
|------|------------|
| `algomusic/` | the Python package (the port) |
| `algomusic/rng.py` | exact AlgoMusic PRNG (`srand`/`rand`), recovered from the binary |
| `algomusic/song.py` | selector helpers + generator + title builder |
| `algomusic/samples.py` | loader for the real 8SVX sample bank |
| `algomusic/sample_comments.json` | per-sample filenotes (VOLUME/FINETUNE/PHASER) mined from the LHA |
| `algomusic/render.py` | offline renderers (`render_samples` = real bank, `render` = oscillator synth) |
| `algomusic/db.json` | decoded musical database (phrases, drums, words, …) |
| `algomusic/__main__.py` | CLI (`python -m algomusic --seed $4002 out.wav`) |
| `work/` | RE artefacts: `algomusic.bin`, relocations, `decompiled_all.c`, `tables.json`, `db_dump.txt`, Ghidra project |
| `tools/` | helper scripts (Ghidra export, hunk extraction, table extraction, **vamos patch**) |
| `docs/` | `groundtruth.md`, `sequencer_0x106256.md`, `sample_options.md`, this workflow doc |
| `full/AlgoMusic/` | the **real sample bank** (8SVX + a few headerless raw files) and the original `AlgoMusic.000` binary |
| `orig/`, `*.lha` | original distribution archives |

---

## 2. The one rule

**Fidelity over neatness.** Never invent behaviour, table values, call orders or
moduli. If you are not sure, disassemble and prove it. Prefer ugly-but-exact.

The RNG stream is *global and sequential*: a single extra or missing `rand()`
anywhere shifts every later decision (including the song title). So pay
attention not just to *what* is computed but to *how many* `rand()` calls each
step consumes and in what order.

---

## 3. Tools you will need

### Static analysis (already done, artefacts in `work/`)
* `work/decompiled_all.c` — Ghidra headless decompilation of all 136 functions.
  **Primary reference.** Function names are `FUN_00xxxxxx` where `xxxxxx` is the
  load address (`0x100000` base).
* `work/algomusic.bin` — raw loaded image; `work/algomusic.relocs` — relocations.
* `work/tables.json`, `work/db_dump.txt` — decoded data tables.
* Capstone is used ad hoc to disassemble a range:
  ```python
  from capstone import *
  data = open('work/algomusic.bin','rb').read(); base = 0x100000
  md = Cs(CS_ARCH_M68K, CS_MODE_BIG_ENDIAN)
  for i in md.disasm(data[0x106256-base:0x1072d2-base], 0x106256):
      print("%08x  %-20s %s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
  ```
* A4-relative globals: SAS/C keeps globals at negative offsets from A4. Edit
  `tools/ghidra_*.py` to re-run Ghidra if you need a fresh decompile
  (`~/ghidra*/support/analyzeHeadless`, processor `68000:BE:32:default`,
  scripts marked `# @runtime Jython`).

### Dynamic ground truth (the important one)
The original binary runs under **vamos** and writes a `LOG=` file, giving a
byte-exact reference (song name + length) per seed. See
`docs/groundtruth.md` for the full recipe. Short version:

```sh
python3 tools/patch_vamos_exall.py        # one-off: adds DOS ExAll to amitools
cd full/AlgoMusic
timeout 60 ~/.local/bin/vamos -q -V "Work:$PWD" -a "PROGDIR:Work:" \
  -O "graphics.library=mode:fake,version:40,num_fake_funcs:300" \
  Work:AlgoMusic.000 NOENV SAFE INIT '$4002' LOG=gt.log NOALLOC
```

**Why the patch exists:** the sample loader uses `AllocDosObject(DOS_EXALLCONTROL)`
+ `ExAll`, which amitools 0.8.1 did not implement; without it every drawer read
as empty and the binary quit before the play loop. `tools/patch_vamos_exall.py`
adds both and is idempotent. Re-apply it after any amitools upgrade.

Useful vamos flags: `-V Work:/abs` maps a volume, `-a PROGDIR:Work:` creates an
assign (the binary locks `PROGDIR:`, not the volume name), `-O lib=mode:fake,...`
fakes a library. The emulator faults in the Paula/audio layer *after* the log
line — that is fine and expected.

---

## 4. How the original is structured (call order matters!)

```
main  FUN_00105fdc
 └─ FUN_00108c56            read prefs/ENV
 └─ FUN_0010538c(0)         parse config (INIT RANDOM=$xxx, VOLUME, BPM, …)
 └─ FUN_001059e6
     └─ FUN_00105caa
         ├─ FUN_0010c87a(seed)      srand(seed)          <-- RNG starts here
         ├─ FUN_001094b4()          ExAll scan of drawers (no RNG)
         └─ FUN_001095ea()          sample-bank pick + load  <-- RNG!
 └─ loop:
     ├─ _DAT_001281a4 = FUN_0010be8c()   (division helper — see below)
     ├─ FUN_00106256()          SEQUENCER: builds the song      <-- RNG!
     ├─ FUN_0010a400()          write LOG= line
     ├─ FUN_00108f40()          audio
     └─ FUN_001073e6()          player + FUN_00108816() TITLE   <-- RNG!
```

Notes:
* `FUN_0010be8c` / `FUN_0010bebe` / `FUN_0010bf50` are **SAS/C runtime maths
  helpers**, not RNG consumers. `FUN_0010bebe` = 32-bit unsigned divide
  (quotient→D0, remainder→D1); the `rand()%n` sites pass D0=rand, D1=n.
* The **sample-bank pick** happens *before* the sequencer and consumes RNG:
  `FUN_001095ea` calls `FUN_00109bfa(cat)` for Cats in the order
  `3,1,2,0,8,4,5,6,7` (Chords, Melody, Acid, Bass, BreakBeat, Base, Clap,
  Hihat, Snare). Each draws `rand()%count` with an anti-repeat retry. The
  `count`s and patterns are tabulated in `docs/groundtruth.md`.
* The **title** `FUN_00108816` runs *last*, inside the player `FUN_001073e6`,
  on the same RNG stream — so it must be rolled after the sequencer.

---

## 5. Where fidelity currently stands

Done / faithful:
* PRNG (`FUN_0010c844` / `FUN_0010c87a`) — exact.
* `srand` call site and *that* the sample pick precedes generation.
* Selectors `FUN_0010861c` / `FUN_00108710` / `FUN_00108794` / `FUN_001086dc`
  (one `rand()` per modulo, sticky/anti-repeat behaviour).
* Sample-drawer scan (`FUN_001094b4`, via `algomusic/amigapattern.py`) and the
  sample pickers `FUN_00109bfa` (`Generator.sample_pick`).
* **The whole RNG stream of `FUN_00106256`** for a default (no-prefs) run —
  see `docs/sequencer_0x106256.md`.
* Title builder `FUN_00108816`.
* **`tools/verify_groundtruth.py`: song name *and* length match the original
  for 20/20 seeds.** The name is a downstream checksum of the RNG stream, so
  this is strong evidence the stream is byte-exact.

Outstanding (this is the work list):
1. ~~**Note-level playback tables of `FUN_00106256`**~~ — **done**: the step
   loop is ported in `Song.build_tables()` (chord/bass/lead/drum period, voice,
   amp, trigger tables) and rendered by `render_tables()` (`freq = 3546895 /
   period`).  The chord/bass/lead pitch and all onsets/rests are exact; the
   instrument choice is now exact too (see the recovered
   `FUN_001095ea`/`FUN_0010996c` voice→sample map in
   `docs/sequencer_0x106256.md`).  
2. **`0x10e946 != 0` melody-roll variant** and `0x10e92e`/`0x10e93e` (arp vs
   melody lead; bass/arp phasing) — not exercised by a plain `INIT $seed` run.
3. **Sample-DB parsing** `FUN_00109c72` / `FUN_00109dea` / `FUN_00109fe0`
   (filenotes → VOLUME/FINETUNE/PHASER…) — **done** for VOLUME + normal-sample
   FINETUNE (+ the speech/breakbeat `(30000-ft)/bpm` rule).  The filenotes live
   in the LHA archive, not the extracted files; `tools/extract_comments.py`
   caches them in `algomusic/sample_comments.json` and `render_tables()` applies
   them.  PHASERDEPTH/SPEED (a sample-start **sweep**, not a timbre filter) are
   parsed, and the sequencer-side triangle oscillator (`0x1068f2`) is now
   reproduced by `Song.build_tables()` (`phaser_step`) into the bass/lead
   offset tables (`0x120998`/`0x123998`) when `generate(filenotes=True)` armed a
   voice; the *renderer* still plays from offset 0.
   **Beware:** arming the phaser consumes RNG in the sequencer (`0x1062b8`), so
   it changes the *composition* (title/length), not just the timbre.  Every
   seed picks a phaser-armed acid sample, so our comment-less ground truth only
   holds with the phaser **off** — we therefore do not draw that RNG.  See
   `docs/sample_options.md`.
4. Speech path `FUN_0010ab38` / `FUN_0010b0a2` (only when `SPEECH` is set).
5. Paula player `FUN_001073e6` 16-voice allocation, the `0x1285d8` per-voice
   ring and the `0x12865c` voice→sample table (needed for an exact drum
   instrument map).
6. NOTE: capturing the *original's* Paula output under vamos was attempted and
   abandoned — vamos does not emulate the custom chips and the player is
   interrupt-driven.  See `docs/paula_capture.md`.

**Verification gate:** `make verify` runs all checks and must pass:
* `python3 tools/verify_groundtruth.py` → `20/20 seeds match` (name + length vs
  the original's `LOG=` line); add more seeds from `docs/groundtruth.md`.
* `python3 tools/verify_tables.py` → `10/10 seeds OK` (self-consistency of
  `Song.build_tables`: lengths, determinism, period/voice ranges).
* `python3 tools/verify_comments.py` → `PASS` (filenote parser, the FINETUNE
  period formula vs the guide's table, the comment cache vs the LHA, and the
  phaser triangle / sweep-off table fill).
* (manual, needs the running original) `tools/dump_vamos_tables.py` +
  `tools/compare_tables.py` diff our tables against the original's captured
  under vamos: **everything is byte-exact** (chord/bass/drum/lead
  period+voice+amp), confirmed on 4 seeds.  The old 72/1664 `lead_period`
  residual was a per-step runtime patch of `char_table['2']`/`['5']` for
  minor chords — see docs/sequencer_0x106256.md.

---

## 6. Project conventions

* Python 3.13; no third-party deps for the package itself (numpy not required).
* `python3` not `python`.
* Keep responses/commits concise and factual.
* Run the CLI to smoke-test: `python3 -m algomusic --seed '$4002' /tmp/x.wav`.
  (The output path needs `-o`; the default renderer is `render_tables`.)
* Commit messages: one-line summary + bullets, prefixed by area, e.g.
  `sequencer: port per-step note-table fill`.
* Update `docs/` (and this file) whenever you learn something about the binary
  that a future agent would need. **Never let docs drift from the code.**

## 7. Legal

AlgoMusic is giftware © Thomas Schürger. Binary, samples and archives are
included only for interoperability/analysis. Independent reverse-engineering;
no original sources exist.
