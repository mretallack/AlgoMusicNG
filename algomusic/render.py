"""Render a generated Song to a WAV file.

Two back-ends live here:

* ``render``          -- the original oscillator synth (kept for reference).
* ``render_samples``  -- plays the **real 8SVX instrument bank** on a virtual
  Paula: chord / bass / melody samples are resampled to the required note
  frequency (ratio derived from the note vs. an instrument reference pitch),
  drum samples play one-shot at their natural rate.  This is what makes the
  re-implementation actually *sound* like AlgoMusic.
"""
import math
import struct
import wave

from .song import parse_phrase, chord_notes, parse_note
from .samples import SampleBank

SR = 44100

# reference pitches used to transpose each instrument family (Hz)
REF_PITCH = {"chords": 261.63, "bass": 82.41, "melody": 523.25}


def midi_from(semi, octave, root_octave=1):
    return 36 + octave * 12 + semi


def _freq(midi, finetune):
    f = 440.0 * (2.0 ** ((midi - 69) / 12.0))
    return f * (1.0 + finetune / 1000.0)


def _softclip(v, knee=0.8):
    """Scale with no distortion below `knee`; round off only the last dB or so.

    An unconditional `tanh(x * 1.15)` put the whole mix into saturation, which
    made loud overlapping voices (bass + kick) sound overdriven.  Below `knee`
    this is exactly linear.
    """
    a = abs(v)
    if a > knee:
        a = knee + (1.0 - knee) * math.tanh((a - knee) / (1.0 - knee))
    return math.copysign(a, v)


# --------------------------------------------------------------------------
# sample playback on a virtual Paula
# --------------------------------------------------------------------------
def _play(buf, smp, ratio, start, dur_samples, gain, loop=False,
          loop_start=0, loop_len=0):
    n = len(buf)
    m = len(smp)
    if m <= 1 or ratio <= 0:
        return
    if loop and loop_len > 0:
        ls, le = loop_start, loop_start + loop_len
    else:
        ls, le = 0, m
    pos = 0.0
    end = start + dur_samples
    i = start
    attack = 64
    release = 256
    while i < end and i < n:
        j = int(pos)
        if j >= m:
            j = m - 1
        k = j + 1 if j + 1 < m else j
        frac = pos - j
        v = smp[j] + (smp[k] - smp[j]) * frac
        # short declick envelope
        g = gain
        if i - start < attack:
            g *= (i - start) / attack
        # amplitude matched roughly to the sample's own peak
        buf[i] += g * v
        pos += ratio
        if pos >= le or pos >= m:
            if loop:
                pos = ls + (pos - le)
                if pos >= m:
                    pos -= (m - ls)
            else:
                break
        i += 1


def render_samples(song, path, bank=None, gain=0.62, loops=2):
    bank = bank or SampleBank()
    step = 60.0 / song.bpm / 4.0
    step_n = step * SR
    total = int(song.total_steps * step * SR) + SR // 2
    buf = [0.0] * total

    drum_map = {"1": "kick", "2": "snare", "3": "hat", "4": "clap"}

    for pi, patt in enumerate(song.patterns):
        pstart = int(pi * 64 * step_n)

        steps, toks = parse_phrase(patt["chord"] or "")
        if toks:
            seg = 64.0 / len(toks)
            for ti, tok in enumerate(toks):
                smp, rate, ls, ll = bank.chord_sample(tok)
                p = parse_note(tok)
                if p is None:
                    continue
                semi, octv, _c, _m = p
                f = _freq(midi_from(semi, octv), song.finetune)
                ratio = min(4.0, max(0.25, f / REF_PITCH["chords"])) * (rate / SR)
                st = pstart + int(ti * seg * step_n)
                dur = int(seg * step_n * 0.98) + 1
                _play(buf, smp, ratio, st, dur, gain * 0.5, loop=True,
                      loop_start=ls, loop_len=ll)
                # bass: same root, one octave down, distinct sample
                bsmp, brate, bls, bll = bank.bass
                fb = _freq(midi_from(semi, octv), song.finetune)
                bratio = min(4.0, max(0.25, fb / REF_PITCH["bass"])) * (brate / SR)
                _play(buf, bsmp, bratio, st, dur, gain * 0.45, loop=True,
                      loop_start=bls, loop_len=bll)

        # melody: walk chord tones on non-dash steps of the melody phrase
        mel = patt.get("melody") or ""
        chord_pool = []
        for tok in toks:
            chord_pool.extend(chord_notes(tok))
        if chord_pool and mel:
            msmp, mrate, mls, mll = bank.melody
            j = 0
            for si, ch in enumerate(mel[:64]):
                if ch in ("-", " "):
                    continue
                semi, octv = chord_pool[j % len(chord_pool)]
                j += 1
                f = _freq(midi_from(semi, octv + 1), song.finetune)
                ratio = min(4.0, max(0.25, f / REF_PITCH["melody"])) * (mrate / SR)
                st = pstart + int(si * step_n)
                _play(buf, msmp, ratio, st, int(step_n * 1.8), gain * 0.34,
                      loop=True, loop_start=mls, loop_len=mll)

        # drums
        dr = patt.get("drums") or ""
        for si, ch in enumerate(dr[:64]):
            if ch in ("-", " "):
                continue
            kind = drum_map.get(ch, "hat")
            dsmp = bank.drums.get(kind)
            if not dsmp:
                continue
            smp, rate, _ls, _ll = dsmp
            st = pstart + int(si * step_n)
            _play(buf, smp, rate / SR, st, len(smp) + 1, gain * 0.8)

    peak = max(1e-9, max(abs(x) for x in buf))
    scale = 0.9 / peak
    data = bytearray()
    for x in buf:
        v = _softclip(x * scale)
        s = int(max(-1.0, min(1.0, v)) * 32767)
        data += struct.pack("<hh", s, s)

    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(data))
    return path


# --------------------------------------------------------------------------
# original oscillator synth (kept for reference / fallback)
# --------------------------------------------------------------------------
def _env(n, i, attack=0.005, release=0.05):
    a = int(attack * SR)
    r = int(release * SR)
    if i < a:
        return i / a
    if i > n - r:
        return max(0.0, (n - i) / r)
    return 1.0


def _sine(f, buf, start, dur, amp):
    n = len(buf)
    for i in range(int(dur * SR)):
        k = start + i
        if k >= n:
            break
        buf[k] += amp * _env(int(dur * SR), i) * math.sin(2 * math.pi * f * i / SR)


def _saw(f, buf, start, dur, amp):
    n = len(buf)
    p = SR / f
    for i in range(int(dur * SR)):
        k = start + i
        if k >= n:
            break
        ph = (i % p) / p
        buf[k] += amp * _env(int(dur * SR), i) * (2 * ph - 1)


def _square(f, buf, start, dur, amp):
    n = len(buf)
    p = SR / f
    for i in range(int(dur * SR)):
        k = start + i
        if k >= n:
            break
        ph = (i % p) / p
        buf[k] += amp * _env(int(dur * SR), i, 0.002, 0.02) * (1.0 if ph < 0.5 else -1.0)


def _noise(buf, start, dur, amp, decay=0.99, lp=0.6):
    import random
    n = len(buf)
    rng = random.Random(1234 + start)
    prev = 0.0
    total = int(dur * SR)
    for i in range(total):
        k = start + i
        if k >= n:
            break
        v = rng.uniform(-1, 1)
        prev = prev * lp + v * (1 - lp)
        e = (decay ** (i / (SR * 0.02))) if decay < 1 else max(0.0, 1 - i / total)
        buf[k] += amp * e * prev


def _kick(buf, start, amp):
    n = len(buf)
    dur = 0.18
    for i in range(int(dur * SR)):
        k = start + i
        if k >= n:
            break
        f = 120 * math.exp(-i / (SR * 0.05)) + 45
        e = math.exp(-i / (SR * 0.08))
        buf[k] += amp * e * math.sin(2 * math.pi * f * i / SR)


def render(song, path, drum_map=None, gain=0.28):
    step = 60.0 / song.bpm / 4.0
    total = int(song.total_steps * step * SR) + SR // 2
    buf = [0.0] * total

    drum_map = drum_map or {"1": "kick", "2": "snare", "3": "hat", "4": "clap"}

    for pi, patt in enumerate(song.patterns):
        pstart_step = pi * 64
        pstart = int(pstart_step * step * SR)

        steps, toks = parse_phrase(patt["chord"] or "")
        if toks:
            seg = 64.0 / len(toks)
            for ti, tok in enumerate(toks):
                notes = chord_notes(tok)
                if not notes:
                    continue
                st = pstart + int(ti * seg * step * SR)
                dur = seg * step
                for (semi, octv) in notes:
                    _sine(_freq(midi_from(semi, octv), song.finetune), buf, st, dur, gain * 0.22)

        if toks:
            seg = 64.0 / len(toks)
            for ti, tok in enumerate(toks):
                p = parse_note(tok)
                if not p:
                    continue
                semi, octv, _c, _m = p
                st = pstart + int(ti * seg * step * SR)
                _saw(_freq(midi_from(semi, max(0, octv)), song.finetune), buf, st, seg * step * 0.95, gain * 0.4)

        mel = patt.get("melody") or ""
        steps2, toks2 = parse_phrase(patt["chord"] or "")
        chord_pool = []
        for tok in toks2:
            chord_pool.extend(chord_notes(tok))
        if chord_pool and mel:
            j = 0
            for si, ch in enumerate(mel[:64]):
                if ch == "-" or ch == " ":
                    continue
                semi, octv = chord_pool[j % len(chord_pool)]
                j += 1
                st = pstart + int(si * step * SR)
                _square(_freq(midi_from(semi, octv + 1), song.finetune), buf, st, step * 1.8, gain * 0.16)

        dr = patt.get("drums") or ""
        for si, ch in enumerate(dr[:64]):
            if ch in ("-", " "):
                continue
            st = pstart + int(si * step * SR)
            kind = drum_map.get(ch, "hat")
            if kind == "kick":
                _kick(buf, st, gain * 0.9)
            elif kind == "snare":
                _noise(buf, st, 0.14, gain * 0.6, lp=0.35)
            elif kind == "clap":
                _noise(buf, st, 0.12, gain * 0.5, lp=0.5)
            else:
                _noise(buf, st, 0.05, gain * 0.28, lp=0.9)

    peak = max(1e-9, max(abs(x) for x in buf))
    scale = 0.9 / peak
    data = bytearray()
    for x in buf:
        v = _softclip(x * scale)
        s = int(max(-1.0, min(1.0, v)) * 32767)
        data += struct.pack("<hh", s, s)

    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(data))
    return path


# --------------------------------------------------------------------------
# table-driven renderer: plays the exact per-step tables from the sequencer
# --------------------------------------------------------------------------
PAL_CLOCK = 3546895          # Amiga PAL Paula clock (Hz)

# Chord voice id -> name suffix.  FUN_001095ea loads the six chord slots from
# the *picked* Chords drawer entry (always a "...-Maj" file) by name surgery:
# it appends "6"/"4" and replaces the quality with "Min" (see FUN_0010c354 and
# the strings at 0x104a44="6" / 0x104a46="Min").  So voice 0..5 are
# prefix-Maj / -Min / -Maj6 / -Min6 / -Maj4 / -Min4.
_CHORD_SUFFIX = ["-Maj", "-Min", "-Maj6", "-Min6", "-Maj4", "-Min4"]

# Drum voice id -> list of picked Rhythm sources, from FUN_0010996c:
#   voice 9   = Base(4)          voice 0xb = Clap(5)
#   voice 0xa = Hihat(6)         voice 0xc = Base+Clap
#   voice 0xf = Base+Hihat       voice 0xd = Clap+Hihat
#   voice 0xe = Snare(7)         voice 0x10 = BreakBeat(8)
# (the original *pre-mixes* the two sources into one chip buffer; we just
# trigger both at the same step, which is audibly and rhythmically identical.)
_DRUM_CAT = {0x9: (4,), 0xA: (6,), 0xB: (5,), 0xC: (4, 5),
             0xD: (5, 6), 0xE: (7,), 0xF: (4, 6), 0x10: (8,)}


def _period_ratio(period):
    """Source samples consumed per output sample for a Paula period.

    The original sets `AUDxPER = period`, so Paula replays the sample bytes at
    `clock / period` bytes per second -- *independent* of the sample's own
    rate.  We render at `SR`, so advancing `(clock / period) / SR` source
    samples per output sample reproduces that exactly.  (Dividing by the
    sample's rate instead made chords/bass/lead play ~5x too fast.)
    """
    if period <= 0:
        return 0.0
    f = PAL_CLOCK / period
    return min(8.0, max(0.02, f / SR))


def apply_finetune(period, finetune):
    """Scale a note period by a sample's FINETUNE (permille of frequency).

    The guide's ``Factor = (x+1000)/1000`` is on *frequency*, so the period
    scales by ``1000/(x+1000)``.  The binary does exactly this in the sequencer
    post-loop (``0x1071a8``), reading ``0x12865c[voice]`` (filled by
    ``FUN_00109fe0`` from the filenote) and dividing with the signed 32-bit
    helper ``FUN_0010be8c``.  ``finetune == 0`` (no comment) leaves the period
    untouched; ``finetune == 1000`` doubles the pitch (period/2).
    """
    if not finetune or period <= 0:
        return period
    num = period * 1000
    den = 1000 + finetune
    q = abs(num) // abs(den)
    return -q if (num < 0) != (den < 0) else q


def _vol_scale(meta):
    """Amplitude scale from a sample's VOLUME option (0..64, default 64)."""
    v = meta.get("volume", 64)
    return max(0.0, min(1.0, v / 64.0))


def render_tables(song, path, bank=None, gain=0.6, loops=1):
    """Render using the exact note-level tables (`song.tables`).

    Chord, bass and lead (melody/arp) now use the *exact* Paula period the
    original computed (`3546895 / period`), and every onset/rest comes from the
    step tables rather than a re-derivation of the arrangement.  Drums trigger
    on the table's non-rest steps; the voice-id -> sample mapping comes from
    FUN_0010996c (exact).
    """
    if not getattr(song, "tables", None):
        return render_samples(song, path, bank=bank, gain=gain, loops=loops)
    bank = bank or SampleBank()
    T = song.tables
    step = 60.0 / song.bpm / 4.0
    step_n = step * SR
    nsteps = song.total_steps
    total = int(nsteps * step * SR) + SR // 2
    buf = [0.0] * total

    _DEF_META = {"volume": 64, "finetune": 0, "phaser_depth": 0,
                 "phaser_speed": 0}

    def _rmeta(rel):
        return bank.meta(rel) if rel else _DEF_META

    def hit(i, smp_info, period, vol, dur, gloop=True):
        if not smp_info:
            return
        smp, rate, ls, ll = smp_info
        r = _period_ratio(period)
        if r == 0.0:
            return
        _play(buf, smp, r, int(i * step_n), int(dur), vol, loop=gloop,
              loop_start=ls, loop_len=ll)

    def _smp(sub, name):
        return bank._get("%s/%s" % (sub, name)) if name else None

    # resolve instruments from the *picked* sample-drawer entries, exactly as
    # FUN_001095ea does (`song.picks` = {cat: (index, filename)}).
    picks = getattr(song, "picks", {}) or {}

    def pick_name(cat):
        v = picks.get(cat)
        return v[1] if v else None

    chord_prefix = (pick_name(3) or "C-Maj")
    chord_prefix = chord_prefix[:-4] if chord_prefix.endswith("-Maj") else "C"
    chord_paths = ["Chords/" + chord_prefix + s for s in _CHORD_SUFFIX]
    chord_smps = [_smp("Chords", chord_prefix + s) for s in _CHORD_SUFFIX]
    if not chord_smps[0]:
        chord_smps = [bank.chords.get("C-Maj")] * 6
    chord_meta = [_rmeta(p) for p in chord_paths]

    bass_name = pick_name(0)
    bass_smp = _smp("Bass", bass_name) or bank.bass
    bass_meta = _rmeta("Bass/" + bass_name if bass_name else None)
    lead_name = pick_name(1)
    lead_smp = _smp("Melody", lead_name) or bank.melody
    lead_meta = _rmeta("Melody/" + lead_name if lead_name else None)

    drum_smps = {}
    for v, cats in _DRUM_CAT.items():
        drum_smps[v] = [(_smp("Rhythm", pick_name(c)),
                         "Rhythm/" + pick_name(c) if pick_name(c) else None)
                        for c in cats]

    for i in range(nsteps):
        # chord
        if T["chord_voice"][i] != 0xFFFF:
            v = T["chord_voice"][i]
            m = chord_meta[v] if 0 <= v < 6 else chord_meta[0]
            hit(i, chord_smps[v] if 0 <= v < 6 else chord_smps[0],
                apply_finetune(T["chord_period"][i], m["finetune"]),
                gain * 0.5 * _vol_scale(m), step_n * 1.05)
        # bass
        if T["bass_voice"][i] != 0xFFFF:
            hit(i, bass_smp,
                apply_finetune(T["bass_period"][i], bass_meta["finetune"]),
                gain * 0.45 * _vol_scale(bass_meta), step_n * 1.05)
        # lead
        if T["lead_voice"][i] != 0xFFFF:
            hit(i, lead_smp,
                apply_finetune(T["lead_period"][i], lead_meta["finetune"]),
                gain * 0.36 * _vol_scale(lead_meta), step_n * 1.9)
    # ---- drums: one-shot, one Paula voice each ---------------------------
    # The player allocates a fixed voice per drum id, so a new hit *retriggers*
    # (cuts) the previous one instead of piling on top -- and it plays the whole
    # sample at its natural rate.  Accumulating overlapping one-shots (and
    # cutting them short) made the drums muddy and far too loud.  Two-source
    # voices (0xc/0xd/0xf) are pre-mixed by the original into one buffer at the
    # default volume, so their per-sample VOLUME comments do not apply; a
    # breakbeat (voice 0x10) plays at the BPM-locked period (30000-ft)/bpm.
    drum_hits = {}
    for i in range(nsteps):
        if T["drum_period"][i] != 0xFFFF:
            drum_hits.setdefault(T["drum_period"][i], []).append(i)
    for v, steps in drum_hits.items():
        srcs = [(s, rel) for (s, rel) in drum_smps.get(v, ()) if s]
        combined = len(srcs) > 1
        for k, stp in enumerate(steps):
            start = int(stp * step_n)
            if k + 1 < len(steps):
                dur = int(steps[k + 1] * step_n) - start
            else:
                dur = None                       # play the sample out
            vdrum = gain * 0.30 * (min(200, T["drum_vol"][stp]) / 200.0)
            for smp_info, rel in srcs:
                smp, rate, _ls, _ll = smp_info
                meta = _rmeta(rel)
                vs = 1.0 if combined else _vol_scale(meta)
                if v == 0x10:
                    per = max(1.0, (30000.0 - meta["finetune"]) / song.bpm)
                    r = _period_ratio(per)
                    _play(buf, smp, r if r > 0 else rate / SR, start,
                          dur if dur is not None else len(buf), vdrum * vs)
                else:
                    _play(buf, smp, rate / SR, start,
                          dur if dur is not None else len(buf), vdrum * vs)

    peak = max(1e-9, max(abs(x) for x in buf))
    scale = 0.9 / peak
    data = bytearray()
    for x in buf:
        v = _softclip(x * scale)
        s = int(max(-1.0, min(1.0, v)) * 32767)
        data += struct.pack("<hh", s, s)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(data))
    return path
