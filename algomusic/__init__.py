"""A modern (Linux/Python) re-implementation of the Amiga program AlgoMusic.

The RNG and the musical database (note/drum/speech patterns and the song-name
word lists) are recovered from the original 68000 binary; the generation flow
is reconstructed from the decompiled control flow.

Public API:
    Generator(seed).generate() -> Song
    render(song, "out.wav")
"""
from .rng import Rng
from .song import Generator, Song, load_db
from .render import render, render_samples
from .samples import SampleBank

__all__ = ["Rng", "Generator", "Song", "load_db", "render", "render_samples",
           "SampleBank"]
__version__ = "0.2.0"
