# Plan: capture the original's audio (Paula) under vamos

Goal: hear/record the **original** AlgoMusic, not our re-implementation.

## Why we can't today

`vamos` emulates the AmigaOS *API* (exec/dos/graphics/…), **not the custom
chips**.  AlgoMusic plays music by writing to the Paula registers in the
`$DFF000` page (`AUD0..3 LCH/LCL/LEN/PER/VOL/DAT`, plus DMACON).  Under vamos
those addresses are unmapped, so the binary faults (`PC=fffffffc`) as soon as it
reaches the audio layer — it emits the `LOG=` line and dies.  That is fine for
ground truth but produces no sound.

`FS-UAE` would work but needs a Kickstart/AROS ROM, which we do not have
(downloads are blocked / Kickstart is copyrighted).

## Approach: a Paula capture device in vamos

Add a memory-mapped region for `$DFF000..$DFF200` to the vamos machine and
record register writes, then reconstruct PCM offline from the real 8SVX bank.

### Steps

1. **Find the crash.** Run under vamos and confirm the fault is a write to
   `$DFFxxx` (or a jump through a null vector after such a write).  Use
   `-r`/`-I` tracing around `FUN_00108f40` → `FUN_001002b4` and `FUN_001073e6`.
   Note: the resolved Paula writes in the decompile are only `FUN_00108f7c`
   (DMACON/volume-off); the player likely writes through a runtime-computed
   pointer, so grep the *disassembly* for `0dff` immediates rather than globals.
2. **Map the page.** In amitools, add a `PaulaDevice` to the memory map for
   `0xDFF000-0xDFF200` (look at how `vamos` maps `0xBFE001` — the CIAA is
   already special-cased somewhere in `machine/mem.py` / `lib/Cia*`).
   Handle reads (DMACONR, ADKCONR, POTGOR, …) returning sane values and accept
   writes.
3. **Record.** On each `AUDxLCH/LCL` write, capture the sample pointer; on
   `AUDxLEN` the length; `AUDxPER` the period; `AUDxVOL` the volume; `AUDxDAT`
   a manual sample.  Also record `DMACON` enable bits per channel and a
   timestamp (instruction count or a virtual 50 Hz tick) so relative timing is
   preserved.
4. **Reconstruct.** Replay each channel: fetch bytes from the captured pointer
   (they live in the sample bank we already have), step the pointer at
   `PER`-derived rate (PAL clock / period) and mix with `VOL`, honouring the
   loop (`LEN` + one-shot vs repeat).  This is the same maths as
   `algomusic/render.py` already uses for `render_samples`, but driven by the
   *captured registers* instead of our own arrangement.
5. **Verify.** The captured stream should be as long as the `LOG=` length
   (`num_patterns*64` 16th-notes) and the note onsets should line up with the
   title/length we already match.

### Risks / blockers

* The player is interrupt/timer driven; under vamos there is no vblank.  If the
  play loop never advances, we must either drive interrupts virtually (tick the
  song from the captured `DMACON` cadence) or fall back to *driving the player
  ourselves*: call `FUN_001073e6` per tick from a harness.  Establish this
  early — it decides whether this approach is viable at all.
* Some registers are write-only or read differently; model only what the binary
  reads back.
* `DST`/`DSBLANK`/audio-filter bits can be ignored for a first pass.

### Fallback if the player won't advance

Instead of capturing, *emulate the player's table reads ourselves*: finish the
note-level port of `FUN_00106256` (per-step period/voice/amplitude tables) and
drive `render_samples` from those tables.  `algomusic/sequencer.py` already has
the note parser, period lookup and drum-pattern index map; what remains is the
step-loop table fill.  This stays inside our own code and needs no hardware
emulation, but it is only as faithful as our port.


## Findings 2026-11-03 (option 2 recon, failed)

Tried the capture route; it is **not viable as sketched**:

1. **The custom-chip hook never fires.** Instrumented
   `vamos/machine/hwaccess.py::cc_w16`/`cc_r16` (env-gated file log) and ran
   the original to the crash: **zero** `$DFxxxx` accesses recorded. The
   decompiled Paula writes (`FUN_00108f7c`: `DMACON`, `AUDx VOL`) apparently
   never execute; the player writes registers through a *runtime-computed*
   pointer that dies first.
2. **The crash is not a Paula fault.** The run prints the `LOG=` line, prints
   `Playing song "..."`, then dies at `PC=fffffffc` with
   `InvalidMemoryAccessError R(2): fffffa`. That is an exception-vector fetch
   (interrupt), consistent with an **interrupt/timer-driven player standing up
   its VBlank/audio interrupt** — and there is no vblank in vamos.
3. **`machine68k`'s special-range API is not usable from Python.**
   `Memory.set_special_range_write_funcs(addr, num_pages, w8, w16, w32)` is
   undocumented; probing it standalone showed
   `set_special_range_write_funcs(0xDF0000, 1, None, fn, None)` does **not**
   cover `0xDF0000`/`0xDFF096` (writes raise `MemoryError`), and larger
   page counts either still don't cover or **segfault** the extension. So even
   `HWAccess`'s own `$BFxxxx`/`$DFxxxx` ranges are effectively dead — vamos
   genuinely does not emulate the custom chips.

**Conclusion:** capturing Paula under vamos would require reworking machine68k
memory dispatch (C-level) plus a virtual interrupt/timer source to keep the
player alive. Out of scope. Pivoting to the documented **fallback**: finish the
note-level port of `FUN_00106256` and drive `render_samples` from those tables.
