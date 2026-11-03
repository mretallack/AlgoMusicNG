"""Primitives recovered from the AlgoMusic sequencer `FUN_00106256`.

This module currently implements the small, self-contained helpers the sequencer
step loop relies on.  They are exact 1:1 ports from the disassembly and are the
groundwork for the (still outstanding) per-step playback-table fill:

* `FUN_00107340` -- parse a 3-char note token `"<letter><quality><octave>"` into
  a semitone value `octave_index*12 + letter_index`.
* `FUN_001072d2` -- turn that value (plus transpose) into a Paula period.
* the arrangement-character -> drum-pattern-index map used by the step loop.
* the A4+0x5d character-flag table (bit0 = upper-case letter, bit1 = lower-case).

Everything here is derived from `work/decompiled_all.c` and the raw disassembly;
see `docs/sequencer_0x106256.md`.
"""

from .song import load_db

# --- period table (12 longs at 0x10e700) -----------------------------------
# one entry per semitone; FUN_001072d2 octave-shifts these.
_PERIODS = None


def _db():
    global _PERIODS
    d = load_db()
    if _PERIODS is None:
        _PERIODS = d["periods"]
    return d


def note_to_period(value):
    """FUN_001072d2: semitone value -> Paula period.

    Splits `value` into an octave (`sVar3`, starting at 1) and a semitone
    index 0..11, then shifts the period right by the octave (or left for
    negative octaves) and doubles it until it reaches >= 0x7f.
    """
    periods = _db()["periods"]
    s = 1
    while value > 0xB:
        value -= 0xC
        s += 1
    while value < 0:
        value += 0xC
        s -= 1
    if s < 0:
        u = (periods[value] << (-s)) & 0xFFFFFFFF
        while (u & 0xFFFF) < 0x7F:
            u = ((u & 0xFFFF) * 2) & 0xFFFFFFFF
    else:
        u = periods[value] >> s
        while (u & 0xFFFF) < 0x7F:
            u = ((u & 0xFFFF) * 2) & 0xFFFFFFFF
    return u & 0xFFFF


def _letter_index(letter):
    """Match a note letter against the notename table's first characters."""
    names = _db()["notenames"]  # c c# d d# e f f# g g# a a# h
    low = letter.lower()
    for i, n in enumerate(names):
        if n[0].lower() == low:
            return i
    return None


def parse_note(token):
    """FUN_00107340: 3-char token -> `octave_index*12 + letter_index`.

    The token is `"<letter><quality><octave-digit>"`; only the *letter* is used
    for the pitch class (the phrases never use accidentals).  Returns ``None``
    on an unrecognised letter.
    """
    if not token:
        return None
    letter = token[0]
    idx = _letter_index(letter)
    if idx is None:
        return None
    octave_index = 0
    if len(token) > 2 and token[2] != "\0":
        octave_index = ord(token[2]) - 0x31
    return octave_index * 0xC + idx


# --- arrangement char -> drum pattern index (0x1064a6 region) --------------
def drum_pattern_index(ch):
    """Map an arrangement-string character to an index in `drum_patterns`.

    Byte arithmetic exactly as in the binary (the comparison is on a byte):
    ``b = ch - '1'``; if ``b < 0x30`` keep it unless ``b > 8`` in which case
    ``b = ch - 0x1e``; otherwise ``b = ch + 0xa8`` (mod 256).
    """
    b = (ord(ch) - 0x31) & 0xFF
    if b < 0x30:
        if b > 8:
            b = (ord(ch) - 0x1E) & 0xFF
    else:
        b = (ord(ch) + 0xA8) & 0xFF
    return b


def char_flags(ch):
    """The A4+0x5d character table: bit0 = upper-case, bit1 = lower-case."""
    f = 0
    if ch.isupper():
        f |= 1
    if ch.islower():
        f |= 2
    return f
