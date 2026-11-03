"""Render a generated Song to a WAV file.

The Amiga original plays 8SVX samples on Paula.  We do not have Paula here, so
this renderer synthesises the four voices (chords, bass, melody, drums) instead
of replaying the sample bank.  It is a "sounds like AlgoMusic" renderer, not a
sample-exact one.
"""
import math
import struct
import wave

from .song import parse_phrase, chord_notes, parse_note

SR = 44100


def midi_from(semi, octave, root_octave=1):
    # AlgoMusic octave 0 == our MIDI 36 (C2-ish); tuneable with finetune.
    return 36 + octave * 12 + semi


def _freq(midi, finetune):
    f = 440.0 * (2.0 ** ((midi - 69) / 12.0))
    return f * (1.0 + finetune / 1000.0)


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
    step = 60.0 / song.bpm / 4.0          # 16th note
    total = int(song.total_steps * step * SR) + SR // 2
    buf = [0.0] * total

    drum_map = drum_map or {"1": "kick", "2": "snare", "3": "hat", "4": "clap"}

    for pi, patt in enumerate(song.patterns):
        pstart_step = pi * 64
        pstart = int(pstart_step * step * SR)

        # ---- chords -------------------------------------------------
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

        # ---- bass (root of the same phrase, one octave down) --------
        if toks:
            seg = 64.0 / len(toks)
            for ti, tok in enumerate(toks):
                p = parse_note(tok)
                if not p:
                    continue
                semi, octv, _c, _m = p
                st = pstart + int(ti * seg * step * SR)
                _saw(_freq(midi_from(semi, max(0, octv)), song.finetune), buf, st, seg * step * 0.95, gain * 0.4)

        # ---- melody (chord tones triggered by the melody phrase) ----
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

        # ---- drums --------------------------------------------------
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

    # normalise + soft clip
    peak = max(1e-9, max(abs(x) for x in buf))
    scale = 0.95 / peak
    data = bytearray()
    for x in buf:
        v = x * scale
        v = math.tanh(v * 1.2)
        s = int(max(-1.0, min(1.0, v)) * 32767)
        data += struct.pack("<hh", s, s)

    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(data))
    return path
