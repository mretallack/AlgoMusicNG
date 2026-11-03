#!/usr/bin/env python3
import re, json, sys

base = 0x100000
d = open('/home/mark/git/AlgoMusic/work/algomusic.bin', 'rb').read()
LO, HI = 0x1009c0, 0x10dfec

items = []
off = LO - base
while off < HI - base:
    j = d.find(b'\x00', off)
    if j < 0:
        break
    s = d[off:j]
    if len(s) > 0:
        items.append((base + off, s.decode('latin1')))
    off = j + 1

note_re = re.compile(r'^\d\d( [A-Ga-g][-#+]\d){2,}')
drum_re = re.compile(r'^[1-4\-]+$')
word_re = re.compile(r"^[a-zA-Z][a-zA-Z .']*$")

groups = {'note': [], 'drum': [], 'word': [], 'other': []}
for addr, t in items:
    if note_re.match(t):
        groups['note'].append((addr, t))
    elif drum_re.match(t) and len(t) >= 8:
        groups['drum'].append((addr, t))
    elif word_re.match(t) and len(t) > 2:
        groups['word'].append((addr, t))
    else:
        groups['other'].append((addr, t))

out = {k: [{'addr': '0x%08x' % a, 'text': t} for a, t in v] for k, v in groups.items()}
json.dump(out, open('/home/mark/git/AlgoMusic/work/tables.json', 'w'), indent=1)

for k, v in groups.items():
    print("== %s: %d ==" % (k, len(v)))
    for a, t in v[:5]:
        print("   %08x %r" % (a, t[:70]))
