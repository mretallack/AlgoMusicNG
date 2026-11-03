"""AlgoMusic song generation.

This mirrors the high level flow recovered from the 68000 binary:

  * seed the RNG (INIT hex value, or time)              -- func 0x105caa
  * pick a song structure (1 of 9 arrangement strings)   -- func 0x108794
  * pick a chord/bass phrase + rhythm + melody phrase    -- func 0x106256
    per pattern, using rand()%n selectors with anti-repeat
  * derive a song title from the adjective/noun word lists

Only the *musical* tables and the RNG are byte-exact; the selector logic is a
faithful reconstruction of the decompiled control flow but not guaranteed
bit-identical to the Amiga original.
"""
import json
import os
import time

from .rng import Rng

DB_PATH = os.path.join(os.path.dirname(__file__), "db.json")

NOTE_SEMITONES = {
    "c": 0, "c#": 1, "d": 2, "d#": 3, "e": 4, "f": 5,
    "f#": 6, "g": 7, "g#": 8, "a": 9, "a#": 10, "h": 11,
}

NAME_TEMPLATES = [
    "The %s %s", "An %s %s", "A %s %s", "Another %s %s", "%s %s",
    "Where's that %s %s?", "Meet the %s %s", "The %s %s in my house",
    "Follow the %s %s", "My %s is your %s", "The %s %s and the %s %s",
    "%s %s in space", "%s and %s", "%s %s strikes back", "%s, %s and %s",
]

# chord qualities by (case, middle char)
CHORD_INTERVALS = {
    ("M", "-"): [0, 4, 7],        # major
    ("m", "-"): [0, 3, 7],        # minor
    ("M", "6"): [0, 4, 7, 9],     # major 6
    ("m", "6"): [0, 3, 7, 9],     # minor 6
    ("M", "4"): [0, 5, 7],        # sus4
    ("m", "4"): [0, 5, 7],        # sus4
}


def load_db():
    with open(DB_PATH) as f:
        return json.load(f)


def _parse_int_prefix(s):
    """The two leading ASCII digits of a phrase encode its step count."""
    try:
        return int(s[:2])
    except ValueError:
        return 16


def parse_note(tok):
    """Return (midi_like_semitone, octave, case, middle)."""
    if len(tok) < 3:
        return None
    letter = tok[0]
    low = letter.lower()
    # 'h' is German for B; normalise accidental tokens
    semi = NOTE_SEMITONES.get(low)
    if semi is None:
        return None
    octave = ord(tok[2]) - ord("1")
    case = "M" if letter.isupper() else "m"
    return semi, octave, case, tok[1]


def chord_notes(tok):
    """Return list of (semitone, octave) for a chord token."""
    p = parse_note(tok)
    if p is None:
        return []
    semi, octave, case, mid = p
    intervals = CHORD_INTERVALS.get((case, mid), [0, 4, 7])
    return [(semi + iv, octave) for iv in intervals]


def parse_phrase(pattern):
    """Parse '16 C62 G61 a-1 ...' into (steps, [tokens])."""
    parts = pattern.split()
    if not parts:
        return 16, []
    steps = _parse_int_prefix(parts[0]) if parts[0][:2].isdigit() else 16
    if parts and parts[0][:2].isdigit() and len(parts[0]) <= 2:
        parts = parts[1:]
    return steps, parts


class NoteEvent:
    def __init__(self, step, voice, kind, token):
        self.step = step
        self.voice = voice
        self.kind = kind      # 'chord' | 'bass' | 'melody' | 'drum'
        self.token = token


class Song:
    def __init__(self):
        self.name = ""
        self.seed = 0
        self.bpm = 160
        self.finetune = 100
        self.patterns = []      # list of dicts with per-voice events
        self.num_patterns = 0

    @property
    def total_steps(self):
        return self.num_patterns * 64


class Generator:
    def __init__(self, seed=None, db=None):
        self.db = db or load_db()
        if seed is None:
            seed = int(time.time()) & 0x7FFFFFFF
        self.seed = seed
        self.rng = Rng(seed)
        self._last = {}

    # --- random helpers mirroring func 0x10861c -----------------------
    def pick(self, category, n, seq):
        """Random index into seq (length n) with simple anti-repeat."""
        if n <= 1:
            return 0
        prev = self._last.get(category, -1)
        for _ in range(8):
            i = self.rng.rand_mod(n)
            if i != prev:
                break
        self._last[category] = i
        return i

    def song_structure(self):
        """Pick one of the 9 arrangement strings (func 0x108794)."""
        groups = len(self.db["song_structures"]) // 3
        g = self.pick("struct", groups, range(groups))
        return self.db["song_structures"][g * 3:(g + 1) * 3]

    def title(self):
        adj = self.db["adjectives"]
        noun = self.db["nouns"]
        tmpl = NAME_TEMPLATES[self.rng.rand_mod(len(NAME_TEMPLATES))]
        n = tmpl.count("%s")
        words = []
        for i in range(n):
            pool = adj if i % 2 == 0 else noun
            words.append(pool[self.rng.rand_mod(len(pool))])
        return tmpl % tuple(words)

    def generate(self, bpm=160, finetune=100):
        s = Song()
        s.seed = self.seed
        s.bpm = bpm
        s.finetune = finetune
        s.name = self.title()

        struct = self.song_structure()
        primary = struct[0]
        s.num_patterns = max(1, len(primary.rstrip()) // 4)

        chords_bank = self.db["song_structs"]
        drums_bank = self.db["drums_a"]
        melody_bank = self.db["melody_a"]
        arp_bank = self.db["arps"]

        for p in range(s.num_patterns):
            patt = {"chord": None, "bass": None, "melody": None, "drums": None}
            # selector character for this pattern block (mirrors structure use)
            sel = primary[p * 4:p * 4 + 1]
            base = ord(sel) - ord("1") if sel and sel.isdigit() else 0
            patt["chord"] = chords_bank[self.pick("chord", len(chords_bank), chords_bank)]
            patt["bass"] = chords_bank[self.pick("bass", len(chords_bank), chords_bank)]
            patt["melody"] = melody_bank[self.pick("melody", len(melody_bank), melody_bank)]
            patt["drums"] = drums_bank[(base + self.pick("drum", len(drums_bank), range(len(drums_bank)))) % len(drums_bank)]
            patt["arp"] = arp_bank[self.pick("arp", len(arp_bank), range(len(arp_bank)))]
            s.patterns.append(patt)
        return s
