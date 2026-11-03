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
        self.picks = {}         # {cat: (index, sample name)} from FUN_00109bfa
        self.transpose = 0      # global transpose (rand()%6-3)
        self.arrangement = 0    # perm9() result (0..8)
        self.arrangement_phrases = []
        self.phrase_index = 0   # perm70() result (0..69)
        self.step_period = 16   # local_30
        self.timing = 0         # local_90

    @property
    def total_steps(self):
        return self.num_patterns * 64

    @property
    def duration(self):
        """Song length in seconds, as the original's LOG= line reports it.

        ``num_patterns * 64 steps`` at a 16th-note step (``60/bpm/4`` s).
        """
        return self.total_steps * 60.0 / self.bpm / 4.0


class Selectors:
    """Faithful port of the selector helpers from the 68000 binary.

    * category selector  -- func 0x10861c  (DAT_0010e778/0x10e786 tables)
    * permutation picker -- func 0x108710 (70 slots) and 0x108794 (9 slots)

    The exact rand() call order is reproduced, including the "sticky"
    behaviour where a category keeps returning its previous value until a
    reroll condition fires.
    """

    NCAT = 7

    def __init__(self, rng):
        self.rng = rng
        self.last = [0xFFFF] * self.NCAT      # DAT_0010e778 init (-1)
        self.count = [9999] * self.NCAT       # DAT_0010e786 init
        self.perm_slots = None                # DAT_0010ff48 (70)
        self.perm_n = 0
        self.perm_prev = -1                   # DAT_0010e976
        self.perm9_slots = None               # DAT_0010ff8e (9)
        self.perm9_n = 0
        self.perm9_prev = -1                  # DAT_0010e97a

    # func 0x1086dc
    def reset_selectors(self):
        self.last = [0xFFFF] * self.NCAT
        self.count = [9999] * self.NCAT

    # func 0x10861c
    def sel(self, cat, n):
        r = self.rng.rand()
        if (((r & 3) == 1) and (self.count[cat] > 5)) or (self.last[cat] == 0xFFFF):
            while True:
                v = self.rng.rand() % n
                if n == 1:
                    break
                if v != self.last[cat]:
                    break
            self.last[cat] = v
            self.count[cat] = 0
            return v
        else:
            self.count[cat] += 1
            return self.last[cat]

    # func 0x108710  (choose an unused index in 0..n-1, != previous)
    def perm(self, n):
        if self.perm_slots is None:
            self.perm_slots = [0] * n
        if self.perm_n == n:
            self.perm_slots = [0] * n
            self.perm_n = 0
        while True:
            while True:
                v = self.rng.rand() % n
                if self.perm_slots[v] == 0:
                    break
            if v != self.perm_prev:
                break
        self.perm_slots[v] = 1
        self.perm_n += 1
        self.perm_prev = v
        return v

    # func 0x108794  (choose an unused index in 0..8)
    def perm9(self):
        if self.perm9_slots is None:
            self.perm9_slots = [0] * 9
        if self.perm9_n == 9:
            self.perm9_slots = [0] * 9
            self.perm9_n = 0
        while True:
            while True:
                v = self.rng.rand() % 9
                if self.perm9_slots[v] == 0:
                    break
            if v != self.perm9_prev:
                break
        self.perm9_slots[v] = 1
        self.perm9_n += 1
        self.perm9_prev = v
        return v


class Generator:
    def __init__(self, seed=None, db=None):
        self.db = db or load_db()
        if seed is None:
            seed = int(time.time()) & 0x7FFFFFFF
        self.seed = seed
        self.rng = Rng(seed)
        self.sel = Selectors(self.rng)

    def song_structure(self):
        """Pick one of the 9 arrangement strings (func 0x108794)."""
        g = self.sel.perm9()
        return self.db["song_structures"][g * 3:(g + 1) * 3]

    def title(self):
        """Faithful port of the title builder 0x108816.

        Rolls adjective, noun, then one of 14 templates.  Templates 3/10/11/12/13
        capitalise the adjective (the binary mutates the table entry in place;
        only the comparison is by pointer, so index comparison is equivalent).
        Extra noun/adjective rolls use the binary's retry loop verbatim: roll,
        and if it repeats the avoided index retry while a counter < 20 -- i.e. at
        most 21 rolls.  Template 1 falls through into 2 in the binary, so it too
        produces "Another %s %s".
        """
        adjs = self.db["adjectives"]
        nouns = self.db["nouns"]
        rng = self.rng

        ai = rng.rand() % len(adjs)
        ni = rng.rand() % len(nouns)
        t = rng.rand() % 14
        adj, noun = adjs[ai], nouns[ni]

        def cap(s):
            return s[:1].upper() + s[1:]

        def roll(tab, avoid, max_extra=20):
            u = 0
            while True:
                i = rng.rand() % len(tab)
                if i not in avoid:
                    return i
                more = u < max_extra
                u += 1
                if not more:
                    return i

        if t == 0:
            return "The %s %s" % (adj, noun)
        if t in (1, 2):
            return "Another %s %s" % (adj, noun)
        if t == 3:
            return "%s %s" % (cap(adj), noun)
        if t == 4:
            return "Where's that %s %s?" % (adj, noun)
        if t == 5:
            return "Meet the %s %s" % (adj, noun)
        if t == 6:
            return "The %s %s in my house" % (adj, noun)
        if t == 7:
            return "Follow the %s %s" % (adj, noun)
        if t == 8:
            return "My %s is your %s" % (noun, nouns[rng.rand() % len(nouns)])
        if t == 9:
            n2 = roll(nouns, (ni,))
            a2 = roll(adjs, (ai,))
            return "The %s %s and the %s %s" % (adj, noun, adjs[a2], nouns[n2])
        if t == 10:
            return "%s %s in space" % (cap(adj), noun)
        if t == 11:
            return "%s and %s" % (cap(adj), adjs[roll(adjs, (ai,))])
        if t == 12:
            return "%s %s strikes back" % (cap(adj), noun)
        if t == 13:
            a2 = roll(adjs, (ai,))
            a3 = roll(adjs, (ai, a2))
            return "%s, %s and %s" % (cap(adj), adjs[a2], adjs[a3])
        return "The %s %s" % (adj, noun)

    # ---- FUN_001095ea : sample-bank pick (consumes RNG) ----------------
    def sample_pick(self, drawers=None):
        """Replay FUN_00109bfa for every category, in call order.

        Each pick draws ``rand() % count`` and retries while the result equals
        the previous pick for that category (unless count == 1).  Returns the
        dict ``{cat: (index, name)}``.
        """
        from .samples import scan_drawers, SAMPLE_PICK_ORDER

        if drawers is None:
            drawers = scan_drawers()
        last = {}
        picks = {}
        for cat in SAMPLE_PICK_ORDER:
            names = drawers.get(cat, [])
            n = len(names)
            if n == 0:
                picks[cat] = (None, None)
                continue
            while True:
                v = self.rng.rand() % n
                if n == 1:
                    break
                if last.get(cat, 0) != v + 1:
                    break
            last[cat] = v + 1
            picks[cat] = (v, names[v])
        return picks

    def generate(self, bpm=160, finetune=100, speech=False, drawers=None):
        s = Song()
        s.seed = self.seed
        s.bpm = bpm
        s.finetune = finetune

        # === FUN_001095ea : sample-bank pick, *before* the generator ======
        # (called from FUN_00105caa, after srand(), before the play loop)
        s.picks = self.sample_pick(drawers)

        # === FUN_00106256 : the sequencer ================================
        rng = self.rng

        # global transpose: rand() % 6 - 3                        (0x10625e)
        s.transpose = rng.rand() % 6 - 3

        # FUN_001086dc resets the sticky selectors                 (0x106286)
        self.sel.reset_selectors()

        # per-voice init (0x113180 is all zero in a default run, so no RNG)
        # arrangement + phrase selection                          (0x10634a)
        g = self.sel.perm9()                       # FUN_00108794 -> 0..8
        phrase_idx = self.sel.perm(                # FUN_00108710 -> 0..69
            len(self.db["song_structs"]))
        phrase = self.db["song_structs"][phrase_idx]
        s.phrase_index = phrase_idx
        s.arrangement = g
        s.arrangement_phrases = self.db["song_structures"][g * 3:g * 3 + 3]

        # step period = two leading digits of the phrase; number of patterns
        # is the quadruple count of the arrangement string       (0x1063d6)
        step = 10 * (ord(phrase[0]) - 0x30) + (ord(phrase[1]) - 0x30)
        s.num_patterns = len(s.arrangement_phrases[0]) >> 2

        # optional halve/double of the step period                (0x106426)
        if 4 < step < 0x40:
            v = rng.rand() & 7
            if v in (1, 2):
                step >>= 1
            elif v == 5:
                step *= 2

        # timing divider from phrase length and step             (0x106464)
        timing = (len(phrase) >> 2) * step
        while timing <= 0x20:
            timing <<= 1
        timing <<= 1
        if timing < 0x100 and (rng.rand() & 1):
            timing <<= 1
        s.step_period = step
        s.timing = timing

        # echo and rhythm-mix selectors                           (0x1064e8)
        s.echo = self.sel.sel(6, len(self.db["echo"]))
        s.rhythm_mix = self.sel.sel(5, len(self.db["rhythm_mix"]))

        # ---- per-pattern selectors (outer loop) -------------------------
        drums_a = self.db["drums_a"]
        drums_b = self.db["drums_b"]
        melody_bank = self.db["melody_a"] if not speech else self.db["melody_b"]
        arp_bank = self.db["arps"]

        for _p in range(s.num_patterns):
            drum_a = self.sel.sel(0, 0x11)     # FUN_0010861c(0,0x11)
            drum_b = self.sel.sel(1, 0x0E)     # FUN_0010861c(1,0x0e)
            mel = self.sel.sel(3, 0x18)        # FUN_0010861c(3,0x18)
            arp = self.sel.sel(4, 0x27)        # FUN_0010861c(4,0x27)
            s.patterns.append({
                "chord": phrase,
                "bass": phrase,
                "melody": melody_bank[mel % len(melody_bank)],
                "drums": drums_a[drum_a],
                "drums_b": drums_b[drum_b],
                "arp": arp_bank[arp],
                "echo": self.db["echo"][s.echo],
                "rmix": self.db["rhythm_mix"][s.rhythm_mix],
            })

        # FUN_00108816 runs *after* 0x106256 (inside the play routine
        # 0x1073e6) on the same RNG stream, so the name is rolled last.
        s.name = self.title()
        return s
