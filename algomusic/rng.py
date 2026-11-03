"""Exact re-implementation of AlgoMusic's pseudo random generator.

Recovered from the 68000 binary:

    srand(seed):  state = seed - 1
    rand():       u = (state * 0xE5D + 0xE60) & 0x7FFFFFFF
                  state = u - 1
                  return u

The state is a signed 32-bit cell, so we keep it masked to 32 bits.
"""

MASK32 = 0xFFFFFFFF


class Rng:
    def __init__(self, seed=0):
        self.state = (seed - 1) & MASK32

    def srand(self, seed):
        self.state = (seed - 1) & MASK32

    def rand(self):
        u = (self.state * 0xE5D + 0xE60) & 0x7FFFFFFF
        self.state = (u - 1) & MASK32
        return u

    def rand_mod(self, n):
        """Equivalent of the inlined rand() % n used all over the program."""
        if n <= 0:
            return 0
        return self.rand() % n

    def choice(self, seq):
        return seq[self.rand_mod(len(seq))]
