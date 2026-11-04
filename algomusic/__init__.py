"""A modern (Linux/Python) re-implementation of the Amiga program AlgoMusic.

The RNG, the musical database (note/drum/speech patterns and the song-name word
lists) and the whole generation RNG stream are recovered from the original
68000 binary.  For a given seed the produced **song name and length match the
original** (verified for 10 seeds by `tools/verify_groundtruth.py`); note-level
audio is still an approximation.

Public API:
    Generator(seed).generate() -> Song
    render(song, "out.wav")
"""
from .rng import Rng
from .song import Generator, Song, load_db
from .render import render, render_samples, render_tables
from .samples import SampleBank, scan_drawers
from . import sequencer

__all__ = ["Rng", "Generator", "Song", "load_db", "render", "render_samples",
           "SampleBank", "scan_drawers", "sequencer"]
__version__ = "0.4.0"
