# RE notes: the sequencer `FUN_00106256` (0x106256..0x1072d2)

`0x106256` is the per-song generator. It is called once per song from the main
loop (`0x105fdc`); the title builder `0x108816` runs *after* it (inside the play
routine `0x1073e6`) on the **same RNG stream**, so the song name is a downstream
checksum of this function being byte-exact.

Frame: `suba.w #0xac,a7` + `movem.l d2-d7/a2-a3/a5-a6` (24B) + return addr.
Locals live at positive offsets from A7.

## Stack-offset → C-local map (recovered from the disassembly)

| off   | local            | meaning                                   |
|-------|------------------|-------------------------------------------|
| $38   | `local_9c`       | counter (0, only bumped when `0x10e946`)  |
| $3a/$3c/$3e | `local_9a/98/96` | melody side-loop counters/roll        |
| $40   | `local_94`       | last melody pitch (=-100)                 |
| $42   | `local_92`       | candidate melody pitch                    |
| $44   | `local_90`       | timing divider (see below)                |
| $46   | `local_8e`       | melody-ring write index                   |
| $48   | `local_8c`       | "new section" flag                        |
| $4a   | `local_8a`       | tweak-enable flag (=1)                    |
| $54   | `local_86[3]`    | arp selector                              |
| $56   | `local_7e`       | melody selector                           |
| $58..$5b | `local_7c`    | 4-byte scratch token                      |
| $5c   | `local_78`       | memset cursor                             |
| $60   | `local_74`       | structure length / 4                      |
| $64   | `local_70`       | drums_b len-1                             |
| $68   | `local_68`       | drums_a len-1                             |
| $6c   | `local_6c`       | note period                               |
| $74   | `local_60`       | melody token index                        |
| $7c   | `local_5c`       | transposed note                           |
| $80   | `local_54`       | global transpose                          |
| $84   | `local_88`       | octave tweak (-1/0/1)                     |
| $94   | `local_40`       | phrase token index (3,7,11,...)           |
| $9c   | `local_38`       | phrase length (strlen)                    |
| $a4   | `local_30`       | phrase step-count prefix                  |
| $a8/$b0 | `local_2c/24`  | drum_b / drum_a selector                  |
| $ac   | `local_28`       | arp len-1                                 |
| $bc   | `local_18`       | melody len-1                              |
| $c0   | `local_14`       | rhythm-mix ptr                            |
| $c4   | `local_10`       | arp phrase ptr                            |
| $c8   | `local_c`        | melody phrase ptr                         |
| $cc   | `local_8`        | structure-row ptr                         |

## Top-level flow (exact RNG order)

```
rand()%6 - 3                                   -> local_54 (transpose)
reset_selectors()                              # 0x1086dc
for i in 0..2:                                 # per-voice init
    if 0x113180[i]==0: local_86[i]=0; 0x11318c[i]=0; abStack_9f[i]=0
    else: local_86[i] = rand() % 0x113180[i]; abStack_9f[i] = rand() & 1
memset(0x125198..0x128198, 0x40)
g = perm9()                                    # 0x108794
0x128728 = g*3 ; +1 ; +2
0x128198 = 0
phrase = song_structs[perm70()]                 # 0x108710
local_38 = strlen(phrase)
local_74 = strlen(song_structures[0x128728]) >> 2
local_40 = 3
local_30 = phrase[0]*10 + phrase[1]            # 2-digit prefix
if SPEECH: 0x10ab38()
if 4 < local_30 < 0x40:
    switch (rand() & 7) { case 1,2: local_30 >>= 1; case 5: local_30 *= 2; }
local_90 = (local_38>>2) * local_30            # 0x10bf50 is just a 16x16 mul
while local_90 <= 0x20: local_90 <<= 1
local_90 <<= 1
if local_90 < 0x100 and (rand() & 1): local_90 <<= 1
local_30 -= 1
clear 0x10ff18[0..3], 0x10ff38[0..3]
echo = sel(6,8)   -> 0x1281d2                  # 0x10861c
rmix = sel(5,4)   -> local_14

for pat in 0 .. local_74-1:                     # outer pattern loop (d7)
    drum_a = sel(0,0x11)                        # 0x10861c
    drum_b = sel(1,0x0e)
    if (0x10e946==0) or local_8c!=0 or 0x128198!=0:
        if 0x10e946==0: mel = sel(3,0x18)
    else: mel = sel(3,0x0c)
    arp = sel(4,0x27)  -> local_86[3]
    ... strlen() of the four phrases ...
    for step in 0 .. 0x3f:                      # inner step loop (d6)
        if (step & 0xf)==0: pick structure row char -> local_8
        if (step & local_30)==0: read 3-char note token, parse (0x107340),
                                 period via 0x1072d2
        ... conditional rand() rolls for melody (see below) ...
        write chord/bass/arp/melody/drums into the per-step tables
```

### The `rand()` sites inside `0x106256`

Static sites: `0x10625e` (transpose), `0x1062b8`/`0x1062e4` (voice init),
`0x106426` (halve/double), `0x106498`, then in the melody/accompaniment block
`0x106f78, 0x106fa0, 0x106fc8, 0x106fde, 0x106ff8, 0x107082`.  Every modulus was
recovered from the disassembly:

* `0x10625e` → `%6`; `0x106f78` → `%5` (retry while ==5);
* `0x106fa0 / 0x106fc8 / 0x106fde` → `%6` (three melody-interval tables);
* `0x106ff8` → `&1`; `0x107082` → `&0xf`.

The jump table at `0x106440` (6 words, base `0x106442`) resolves to:
cases 1,2 → `local_30 >>= 1`; case 5 → `local_30 *= 2`; 0,3,4 → skip.

## Output tables (written per step, consumed by the player)

```
0x119198 chord periods   0x113198 chord voice/flags
0x11a998 bass  periods   0x114998 bass  voice     0x120998 bass  sweep-off
0x11d998 arp   periods   0x117998 arp   voice     0x123998 lead  sweep-off
                         0x11e198 melody periods 0x124998 melody voice 0x125d98 melody phasing
0x116198 drum  periods   0x11c198 drum  vol       0x122198 drum  off
0x111170 melody ring (up to 0x29 entries)  -- per-voice ring at 0x1285d8 etc.
0x10ff18 (4 dwords) / 0x10ff38 (4 words)   -- per-voice step counters
```

Note-char → period map uses the 12-entry `notenames` pointer table at `0x10e6d0`
plus the 12-entry period table at `0x10e700` (`[1050,991,935,882,833,786,...]`,
one semitone step ≈ 2^(-1/12)).  Melody interval tables: `0x10e730` (6),
`0x10e740` (14, major-ish), `0x10e75c` (14, minor-ish).

## The RNG stream is ported and verified

The *decisions* of `0x106256` are now ported (in `algomusic/song.py`), which is
all the RNG stream needs.  Two key simplifications, both proven from the
disassembly:

1. **With a default (no-prefs) run, `0x10e946 == 0`.**  The whole "melody roll"
   block (the retry loops around `0x106f78..0x1070ac`, which is where
   `0x106f78 %5`, `0x106fa0/0x106fc8/0x106fde %6`, `0x106ff8 &1`,
   `0x107082 &0xf` live) is behind `if (_DAT_0010e946 == 0) { simple } else {…
   rolls …}`.  So those sites do **not** execute for a plain `INIT $seed` run.
2. **`0x113180[0..2]` is all zero**, so the per-voice init (`0x1062aa`, which
   would draw `rand()%0x113180[i]` and `rand()&1` per voice) draws nothing.

So the RNG consumption of the sequencer is exactly:

```
rand() % 6 - 3                       # global transpose           0x10625e
FUN_001086dc()                       # reset sticky selectors     0x106286
g = perm9()                          # 0x108794 -> 0..8           0x10634a
phrase = song_structs[perm70()]      # 0x108710 -> 0..69          0x106378
step  = 10*(phrase[0]-'0')+(phrase[1]-'0')                      0x1063dc
num_patterns = strlen(song_structures[3*g]) >> 2
if 4 < step < 0x40:  rand() & 7      # halve/double               0x106426
timing = (len(phrase)>>2) * step                                0x106464
while timing <= 0x20: timing <<= 1
timing <<= 1
if timing < 0x100:   rand() & 1                                 0x106498
echo = sel(6,8)                      # 0x10861c                   0x1064e8
rmix = sel(5,4)                                                 0x106512
for each of num_patterns:
    sel(0,0x11); sel(1,0x0e); sel(3,0x18); sel(4,0x27)          0x106536
```

Verified by `tools/verify_groundtruth.py`: the resulting *title* (rolled last by
`0x108816`) and the *song length* match the original for 20/20 seeds.

## The step loop (decode)

Recovered while reading the loop; implemented where marked in
`algomusic/sequencer.py`.

* **Note parser `FUN_00107340`.** Token is `"<letter><quality><octave-digit>"`.
  Returns `(digit-'1')*12 + letter_index`, where `letter_index` is the first
  matching entry of the 12-entry notename table at `0x10e6d0` (`c c# d d# e f
  f# g g# a a# h`).  Only the letter is compared, so the phrases never use
  accidentals; the middle char (`-`, `4`, `6`, …) is a *quality*, read
  separately by the loop.  → `sequencer.parse_note`.
* **Period lookup `FUN_001072d2`.** Splits the (transposed) semitone value into
  octave + 0..11, shifts the 12-entry period table at `0x10e700`
  (`1050,991,935,882,833,786,742,700,661,624,589,556`) and doubles until the
  period reaches `>= 0x7f`.  → `sequencer.note_to_period`.
* **Two "rhythm" pattern tables.** `PTR_FUN_0010e108` (17 entries, `sel(0,0x11)`)
  is the **chord-comping** pattern: each char `'1'..'9'` shifts the chord period
  right by `char-'1'` (`0x119198[step] = period >> shift`), and resets every 16
  steps.  `PTR_FUN_0010e14c` (14 entries, `sel(1,0x0e)`) is the **bass**
  pattern.  (`song.py` still calls these `drums_a`/`drums_b`.)
* **Drum patterns.** The arrangement string `song_structures[3*g]` is indexed at
  `(step>>4) + pattern*4`; the char is mapped to an index into `PTR_FUN_0010e32c`
  (`drum_patterns`, 50 strings over `.-+:^*#X`) by
  `b = ch-'1'; if b<0x30: (if b>8: b=ch-0x1e) else b=ch+0xa8` — implemented as
  `sequencer.drum_pattern_index`.  The selected 16-char string names the drum
  voice (`-` rest; `.`,`+`,`:`,`^`,`*`,`#`,`X` → drum indexes) per step.
* **Character flags.** `A4+0x5d` is a 256-byte table, bit0 = upper-case letter,
  bit1 = lower-case (`sequencer.char_flags`); it decides chord quality
  (`&1`) and title capitalisation.
* **Oscillator (vibrato) state.** Three per-voice values `local_86[0..2]` plus a
  direction flag `abStack_9f[]` are reflected between `0x113180[i]` and
  `0x11318c[i]` every step and written to the amplitude tables.  In a default
  run all `0x113180` are zero, so these stay 0.

Output tables written per step (index = `DAT_00128198`, the global step counter):

```
chord  : 0x119198 period   0x113198 voice
bass   : 0x11a998 period   0x114998 voice  0x120998 sweep-off 0x125d98 phasing
arp    : 0x11d998 period   0x117998 voice  0x123998 sweep-off 0x127598 phasing
melody : 0x11d998 period   0x117998 voice  0x123998 sweep-off
drum   : 0x116198 period   0x11c198 volume 0x122198 offset
ring   : 0x111170 melody ring (up to 0x29 entries)
```

Each entry is 1 word per step (`DAT_00128198` steps total).  `0xffff` means
"rest / no note".

## The step loop is ported (`Song.build_tables`, in `algomusic/song.py`)

`Song.build_tables()` is a literal port of the step loop above and fills the
per-step playback tables.  It consumes **no RNG** in a default run (every
conditional roll sits behind `0x10e946 != 0`), so it is safe to run after
`generate()`.

Recovered specifics:

* **Voices are small ids**, not separate tables: chord `0/1` = maj/min (from the
  token's upper/lower case), `2/3` = maj6/min6, `4/5` = maj4/min4; bass `6`;
  melody `7`; arp `8`; drums `9..15`.  The player routes each step to one of 16
  hardware voices using the value stored in the parallel *voice* table; there is
  one note table per channel, not one per voice.
* **Char→semitone table at `0x10e6d0`** (256 shorts; extracted verbatim into
  `db.json` as `char_table`).  Pattern digits `'1'..'7'` are **chord tones**:
  `0,4,7,12,16,19,24` (root, 3rd, 5th, 8ve, 10th, 12th, 15th).  `'-'` is a rest
  and is compared *before* the table lookup (so it is never looked up).  Note
  this table physically abuts the period/small/major/minor tables — it is fine,
  the used indices are distinct.  Entries `'2'` and `'5'` are **patched every
  step** from the chord token's case (minor → 3/15, major → 4/16); see the
  "Resolved" section below.
* **Note arguments are signed 16-bit.** `0x1072d2` is fed `(short)(...)` values;
  the bass is `chord_semitone + ct[char] - 12` and the lead is
  `chord_semitone + ct[char] + quality(-1/0/+1)`.  Feeding the un-sign-extended
  value makes `0x1072d2`'s "double until >= 0x7f" loop spin forever when the
  shifted period underflows to 0.
* **Comping/bass/lead cursors** (`i_comp/i_bass/i_mel/i_arp`) increment every
  step and reset when `step & (len-1) == 0` — the masks are `strlen(pattern)-1`.
* **Drum row** = `drum_patterns[drum_pattern_index(arrangement0[(step>>4)+p*4])]`,
  read at `(step & 0xf)`.
* **Post-loop `0x1071a8`** is a no-op in a default run: it reads
  `0x12865c[voice]` (all zero) and only doubles periods `< 0x7f`, which
  `0x1072d2` never returns.

`algomusic/render.py::render_tables()` now plays these tables directly:
`freq = PAL_CLOCK / period`, resampled against the real 8SVX sample rate.  The
chord/bass/lead pitch and every onset/rest are therefore exact, and
instruments are chosen from the picked sample-drawer entries exactly as
`FUN_001095ea` does (see the instrument map below).  Per-sample VOLUME and
FINETUNE from the sample filenotes are applied too (see
`docs/sample_options.md`).  What is *not* yet modelled is the player's
16-voice allocation / ring.

## Still outstanding

* The `0x10e946 != 0` **melody-roll variant** (melody interval tables
  `0x10e730/0x10e740/0x10e75c`, ring `0x111170`) — behind a config bit that a
  plain `INIT $seed` run leaves 0.
* Speech path (`0x10ab38`/`0x10b0a2`, `SPEECH` only).
* `0x10e92e` (lead = melody vs arp) and `0x10e93e` (bass/arp phasing) alternate
  modes; `build_tables` implements the melody branch and the phasing branch is
  not reproduced.
* The player `0x1073e6`: 16-voice allocation and the per-voice ring at
  `0x1285d8`.  Per-voice **volume** defaults to `0x12860a=0x40`
  (set in `FUN_001095ea`) and is overridden by a sample's `VOLUME` filenote.
* PHASERDEPTH/PHASERSPEED sample-start sweep (acid/melody/bass): the
  sequencer-side triangle oscillator (`0x1068f2`) is now reproduced by
  `Song.build_tables()` (`phaser_step`), writing the per-step word offset into
  `0x120998`/`0x123998` when `generate(filenotes=True)` armed a voice.  The
  *renderer* still plays from offset 0 — applying the sweep to the audio
  needs the player's `AUDxPT = base + offset*2` write.  (The player reads
  offsets the same way from `0x11f198` at `0x107d22`; that table is written by
  the speech path `0x10b196`/`0x10b22c`/`0x10b2ce`.)

## Instrument map (recovered from `FUN_001095ea` / `FUN_0010996c`)

The sample loader tells us exactly which 8SVX file each voice id plays — no
guesswork left after this:

* **Chords.** Six slots are built from the *picked* Chords drawer entry (the
  drawer pattern `#?Maj` guarantees a `...-Maj` file).  `FUN_0010c354` appends
  `"6"`/`"4"` and substitutes `"Min"` (strings `0x104a44`/`0x104a46`), so
  voice `0..5` = `prefix-Maj / -Min / -Maj6 / -Min6 / -Maj4 / -Min4`.
* **Bass** = picked Bass entry (`picks[0]`); **lead** = picked Melody entry
  (`picks[1]`).  Playback rate is `(3546895/period) / sample_rate` — this is
  exactly what the original writes to `AUDxPER` for that sample, so lead/bass/
  chord **pitch is now sample-exact**.
* **Drums** (`FUN_0010996c` builds chip buffers `0x128320[voice]`):
  `9`=Base, `0xa`=Hihat, `0xb`=Clap, `0xc`=Base+Clap, `0xd`=Clap+Hihat,
  `0xe`=Snare, `0xf`=Base+Hihat, `0x10`=BreakBeat, where Base/Clap/Hihat/Snare/
  BreakBeat are the *picked* Rhythm entries (`picks[4..8]`).  The two-source
  voices are **pre-mixed** into one buffer; `render_tables` triggers both at the
  same step (equivalent).  Which drum char → which voice is in `build_tables`.

## How the port was verified

1. `tools/patch_vamos_exall.py` lets the original reach the play loop and emit
   `LOG=` (see `docs/groundtruth.md`).
2. A standalone experiment replayed sample-pick + sequencer RNG + title and
   compared the title against the `LOG=` table — now 20/20, which
   confirms the sample-pick counts, the selector logic and the RNG site order.
3. That logic was folded into `algomusic/song.py`; the length was then also
   confirmed (`num_patterns*64` 16th-notes at the BPM).

## Ground-truth validation (original's tables captured under vamos)

The original writes its per-step tables into **emulated RAM** *before* it faults
in the audio layer, so vamos can snapshot them (`tools/dump_vamos_tables.py`;
the image loads at base `0x21ac`, so a Ghidra address `G` is at
`G - 0x100000 + 0x21ac`, plus a 16-byte data-hunk quirk).  Diff our port with
`tools/compare_tables.py '$4002' /tmp/orig_4002.bin`.

Result for seed `$4002` (and the same everywhere):

| table | result |
|-------|--------|
| chord period/voice | **exact** |
| bass period/voice/sweep-off | **exact** |
| drum period/volume/offset | **exact** |
| lead **voice**/sweep-off | **exact** |
| lead period | **exact** |

**All tables are now byte-exact** for every seed tested (`$4002`, `$1`,
`$1e240`, `$c0ffee`).

### Resolved: the 72 "minor" lead-period steps — a runtime table patch

The melody lookup itself (`0x1070d2`) is a single table, `0x10e6d0`:
`local_92 = local_5c + *(short*)(0x10e6d0 + (local_88 + char)*2)`.  But the
step loop *rewrites* two entries of that shared char table **every step**, at
`0x1067bc`..`0x1067ec`:

```
btst.b #0, (a4+0x5d)[local_7c]      ; bit0 set = upper-case = major
bne major
minor:  move.w #3,  0x10e734        ; char_table['2'] (=0x10e6d0+0x64) = 3
        move.w #0xf,0x10e73a        ; char_table['5'] (=0x10e6d0+0x6a) = 0xf
major:  move.w #4,  0x10e734        ; char_table['2'] = 4   (the default)
        move.w #0x10,0x10e73a        ; char_table['5'] = 0x10 (the default)
```

So for a **minor** (lower-case) chord, chord tones `'2'` and `'5'` are a
semitone lower (3/15) than the stored defaults (4/16).  The patch is applied
*after* the chord token is read and *before* the bass/melody/arp writes, so it
also affects the bass and arp lookups whenever their char resolves to index
`0x32`/`0x35` (bass digit `2`, or a melody/arp char that lands there via
`local_88`).  `algomusic/song.py` models this with a `ct_at(idx, is_minor)`
lookup helper rather than mutating the shared db table.