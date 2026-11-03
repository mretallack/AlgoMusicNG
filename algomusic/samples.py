"""Loading of the original AlgoMusic 8SVX sample bank.

The Amiga package ships its instrument bank as IFF/8SVX files spread across
Acid/, Bass/, Chords/, Melody/, Rhythm/ and Speech/.  Most are proper IFF files
(FORM .... 8SVX VHDR ... BODY), but a few (notably some Chords/*) are stored as
raw headerless signed-8bit PCM.  We accept both.

The loader returns normalised float samples (-1..1), which the renderer then
plays back on a virtual Paula, resampling to the requested note frequency.
"""
import os
import struct

HERE = os.path.dirname(__file__)
REPO = os.path.dirname(HERE)
DEFAULT_ROOT = os.path.join(REPO, "full", "AlgoMusic")

# Amiga PAL Paula clock
PAL_CLOCK = 3546895.0


def _iter_chunks(d):
    off = 12
    n = len(d)
    while off + 8 <= n:
        cid = d[off:off + 4]
        sz = struct.unpack_from(">I", d, off + 4)[0]
        body = d[off + 8:off + 8 + sz]
        yield cid, body
        off += 8 + sz + (sz & 1)


def load_8svx(path):
    """Return (samples[float], sample_rate[int], loop_start[int], loop_len[int])."""
    with open(path, "rb") as f:
        d = f.read()
    if len(d) >= 4 and d[:4] == b"FORM" and b"8SVX" in d[:16]:
        rate = 8363
        loop_start = loop_len = 0
        body = b""
        for cid, c in _iter_chunks(d):
            if cid == b"VHDR" and len(c) >= 20:
                oh, rh, spc, sps, octv, comp, vol = struct.unpack(">IIIHBBL", c[:20])
                rate = sps or 8363
                loop_start = oh
                loop_len = rh
            elif cid == b"BODY":
                body = c
        raw = body
    else:
        # headerless: treat entire file as signed 8-bit PCM
        raw = d
        rate = 8363
        loop_start = loop_len = 0
    # signed 8-bit -> float
    smp = [(b - 256 if b > 127 else b) / 128.0 for b in raw]
    return smp, rate, loop_start, loop_len


# The drawer scan performed by FUN_001094b4: (category, drawer, AmigaDOS
# pattern).  FUN_001095ea then calls FUN_00109bfa for each category in this
# order to *pick* one entry -- each pick consumes RNG, and the number of
# drawer entries matching the pattern is the modulus.  Keeping these exact is
# essential for a byte-identical RNG stream (and hence song title).
DRAWERS = [
    (0, "Bass", "~(.Readme)"),
    (3, "Chords", "#?Maj"),
    (2, "Acid", "~(.Readme)"),
    (1, "Melody", "~(.Readme)"),
    (4, "Rhythm", "Base-#?"),
    (5, "Rhythm", "Clap-#?"),
    (6, "Rhythm", "Hihat-#?"),
    (7, "Rhythm", "Snare-#?"),
    (8, "Rhythm", "BreakBeat-#?"),
]

# order in which FUN_001095ea draws one sample per category
SAMPLE_PICK_ORDER = [3, 1, 2, 0, 8, 4, 5, 6, 7]


def scan_drawers(root=DEFAULT_ROOT):
    """Return ``{cat: [names]}`` exactly as FUN_001094b4's ExAll scan sees it.

    Entries are filtered by the AmigaDOS pattern with case folded
    (ParsePatternNoCase); ``.``/``..`` are not real FFS entries so they are
    excluded.  The ordering is deterministic (sorted) rather than the Amiga's
    on-disk hash order -- the *count* is what drives the RNG, the order only
    selects which concrete sample is used.
    """
    from .amigapattern import pattern_parse, pattern_match

    res = {}
    for cat, drawer, pat in DRAWERS:
        d = os.path.join(root, drawer)
        try:
            names = [
                n
                for n in os.listdir(d)
                if n not in (".", "..") and os.path.isfile(os.path.join(d, n))
            ]
        except OSError:
            names = []
        pat_obj = pattern_parse(pat, ignore_case=True)
        res[cat] = sorted(n for n in names if pattern_match(pat_obj, n))
    return res


class SampleBank:
    """A small, deterministic selection of real AlgoMusic instruments."""

    def __init__(self, root=DEFAULT_ROOT):
        self.root = root
        self.cache = {}
        self.chords = {}
        self.bass = None
        self.melody = None
        self.drums = {}
        self._load()

    def _get(self, rel):
        if rel not in self.cache:
            p = os.path.join(self.root, rel)
            try:
                self.cache[rel] = load_8svx(p)
            except OSError:
                self.cache[rel] = ([0.0], 8363, 0, 0)
        return self.cache[rel]

    def _listdir(self, sub):
        p = os.path.join(self.root, sub)
        try:
            return sorted(x for x in os.listdir(p)
                          if not x.startswith(".") and os.path.isfile(os.path.join(p, x)))
        except OSError:
            return []

    def _load(self):
        # chords: keep the "C-" family (already in C) for straightforward pitch
        for name in self._listdir("Chords"):
            self.chords[name] = self._get("Chords/" + name)

        b = self._listdir("Bass")
        self.bass = self._get("Bass/" + b[0]) if b else ([0.0], 8363, 0, 0)
        m = self._listdir("Melody")
        self.melody = self._get("Melody/" + m[0]) if m else ([0.0], 8363, 0, 0)

        # rhythm: first file of each family
        fam = {"kick": "Base", "snare": "Snare", "hat": "Hihat", "clap": "Clap"}
        for key, prefix in fam.items():
            for name in self._listdir("Rhythm"):
                if name.lower().startswith(prefix.lower()):
                    self.drums[key] = self._get("Rhythm/" + name)
                    break

    # ---- helpers -------------------------------------------------------
    def chord_sample(self, token):
        """Pick a chord sample matching the token's root letter / quality."""
        if not token:
            return self.chords.get("C-Maj")
        letter = token[0].upper()
        mid = token[1] if len(token) > 1 else "-"
        want_min = letter.islower()
        qual = "Min" if want_min else "Maj"
        if mid == "4":
            qual += "4"
        elif mid == "6":
            qual += "6"
        key = "C-%s" % qual
        return self.chords.get(key) or self.chords.get("C-Maj")
