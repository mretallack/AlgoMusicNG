#!/usr/bin/env python3
"""Convert an Amiga hunk executable into a flat relocated binary + reloc list.

Uses amitools' hunk-based relocator (HunkRelocate), which handles the
absreloc32 delta values correctly.

Produces:
  <out>.bin      raw image, segments laid out from BASE
  <out>.relocs   text: "<image_offset> <absolute_target_addr>" per 32-bit reloc
  <out>.meta     BASE, total size, segment table
"""
import sys, struct, ctypes
from amitools.binfmt.hunk import Hunk
from amitools.binfmt.hunk.HunkReader import HunkReader
from amitools.binfmt.hunk.HunkRelocate import HunkRelocate


def main(path, out, base=0x100000):
    hf = HunkReader()
    hf.read_file_obj(path, open(path, "rb"))
    hf.build_segments()
    rel = HunkRelocate(hf)
    sizes = rel.get_sizes()
    addrs = rel.get_seq_addrs(base)
    datas = rel.relocate(addrs)

    total = base + sum(sizes)
    image = bytearray()
    cur = base
    for s, a, d in zip(sizes, addrs, datas):
        image.extend(b"\x00" * (a - cur))
        image.extend(d[:s])
        cur = a + s
    assert cur == total, (hex(cur), hex(total))

    with open(out + ".bin", "wb") as f:
        f.write(image)

    # relocation entries: compute final pointer value already present in image
    relocs = []
    for seg in hf.segments:
        main = seg[0]
        hunk_no = main["hunk_no"]
        seg_base = addrs[hunk_no]
        for hunk in seg[1:]:
            if hunk["type"] == Hunk.HUNK_ABSRELOC32:
                for hunk_num in hunk["reloc"]:
                    for offset in hunk["reloc"][hunk_num]:
                        abs_addr = seg_base + offset
                        img_off = abs_addr - base
                        target = struct.unpack_from(">i", image, img_off)[0]
                        relocs.append((img_off, target))

    with open(out + ".relocs", "w") as f:
        for off, tgt in relocs:
            f.write("%08x %08x\n" % (off, tgt))

    with open(out + ".meta", "w") as f:
        f.write("BASE %08x\nTOTAL %08x\nSEGMENTS\n" % (base, total))
        for i, (s, a) in enumerate(zip(sizes, addrs)):
            f.write("%d %08x %08x\n" % (i, a, s))

    print("base %08x total %08x" % (base, total))
    for i, (s, a) in enumerate(zip(sizes, addrs)):
        print("  seg %d @ %08x size %08x" % (i, a, s))
    print("relocs: %d" % len(relocs))


if __name__ == "__main__":
    path, out = sys.argv[1], sys.argv[2]
    base = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x100000
    main(path, out, base)
