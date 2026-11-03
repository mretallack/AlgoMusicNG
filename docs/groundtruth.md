# Ground-truth reference (original under vamos)

After patching vamos to implement `DOS ExAll` (see `tools/patch_vamos_exall.py`),
the original `AlgoMusic.000` binary runs far enough to generate a song and write
its `LOG=` file.  That log line is our byte-exact reference for the RNG stream,
the sample-database scan and the generator.

## How to reproduce

```sh
python3 tools/patch_vamos_exall.py          # one-off, patches the local amitools

cd full/AlgoMusic
rm -f gt.log
timeout 60 ~/.local/bin/vamos -q \
    -V "Work:$PWD" -a "PROGDIR:Work:" \
    -O "graphics.library=mode:fake,version:40,num_fake_funcs:300" \
    Work:AlgoMusic.000 NOENV SAFE INIT '$4002' LOG=gt.log NOALLOC
cat gt.log
```

The emulator still faults in the audio/Paula layer (`PC=fffffffc`) *after* the
log line is written, so the `LOG=` output is complete and usable.

## Reference table

| seed        | song name                          | length  |
|-------------|------------------------------------|---------|
| `$00000001` | The red John and the nude Jack     | 03m 24s |
| `$00000002` | Blue, thin and potential           | 04m 36s |
| `$00000003` | Where's that shitty pigeon?        | 03m 00s |
| `$00000010` | Another fat busdriver              | 03m 00s |
| `$00000100` | Another bizzare salesman           | 03m 12s |
| `$00001234` | Meet the mad wife                  | 02m 36s |
| `$00004002` | Where's that elderly jogger?       | 02m 36s |
| `$0000ABCD` | Stupid and shitty                  | 04m 36s |
| `$0000FFFF` | Sweet and dreaming                 | 03m 24s |
| `$7FFFFFFF` | Another needful moon               | 04m 36s |

(The `Nr` column is always `1`; a fresh `INIT` runs a single song before the
play loop needs input.)

## Sample-database scan (Drives the RNG before generation)

`FUN_001094b4` scans the sample drawers with `ExAll`, storing one list per
category.  `FUN_001095ea` then calls `FUN_00109bfa(cat)` for each category in
this order, and every call consumes one or more `rand()` values:

`Chords(3)`, `Melody(1)`, `Acid(2)`, `Bass(0)`, `BreakBeat(8)`, `Base(4)`,
`Clap(5)`, `Hihat(6)`, `Snare(7)`.

`FUN_00109bfa` draws `r = rand() % count` and retries while `r` equals the
previous pick for that category (and `count > 1`).  `count` is the number of
drawer entries matching the pattern:

| cat | drawer  | pattern        | matches |
|-----|---------|----------------|---------|
| 0   | Bass    | `~(.Readme)`   | 15 |
| 1   | Melody  | `~(.Readme)`   | 10 |
| 2   | Acid    | `~(.Readme)`   | 10 |
| 3   | Chords  | `#?Maj`        |  3 |
| 4   | Rhythm  | `Base-#?`      |  7 |
| 5   | Rhythm  | `Clap-#?`      | 10 |
| 6   | Rhythm  | `Hihat-#?`     |  8 |
| 7   | Rhythm  | `Snare-#?`     |  4 |
| 8   | Rhythm  | `BreakBeat-#?` |  7 |

`FUN_001094b4` / `FUN_00109bfa` run *before* the generator (`FUN_00106256`), so
these draws shift the whole RNG stream.  Our Python port must replay them to
land on the same title.

## Status

* `LOG=` line now obtainable (vamos block removed by the ExAll patch).
* Full sequencer `FUN_00106256` port still outstanding; once done, compare the
  generated title against the table above for the same seed.
