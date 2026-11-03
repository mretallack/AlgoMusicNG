#!/usr/bin/env python3
"""Patch the locally installed `amitools` (vamos) to implement DOS `ExAll`.

AlgoMusic's sample loader (FUN_001092ca / FUN_00109c72 / FUN_00109bfa) uses
`ExAll()` together with `AllocDosObject(DOS_EXALLCONTROL, ...)`.  Both were
unimplemented in amitools 0.8.1, so the emulated program saw every sample
drawer as empty, concluded "Nothing matching pattern", and exited before the
play loop ever ran -- meaning it never emitted the `LOG=` ground-truth line.

This script adds:

  * `ExAllDataStruct` + `ExAllControlStruct` to amitools/vamos/libstructs/dos.py
  * `DOS_EXALLCONTROL` support in `AllocDosObject`
  * a real `ExAll()` in amitools/vamos/lib/DosLibrary.py

It is idempotent: running it more than once is harmless.  The `ExAll` symbol is
already present in amitools' `dos_lib.fd` (LVO -390), so no .fd edit is needed
-- the library scanner picks the new method up automatically.

Usage:
    python3 tools/patch_vamos_exall.py
"""
import io
import os
import sys


def find_amitools():
    try:
        import amitools
    except ImportError:
        sys.exit("amitools is not importable; install it first")
    return os.path.dirname(amitools.__file__)


STRUCTS_BLOCK = '''
@AmigaStructDef
class ExAllDataStruct(AmigaStruct):
    _format = [
        (APTR_SELF, "ed_Next"),
        (APTR_VOID, "ed_Name"),
        (LONG, "ed_Type"),
        (ULONG, "ed_Size"),
        (ULONG, "ed_Prot"),
        (ULONG, "ed_Days"),
        (ULONG, "ed_Mins"),
        (ULONG, "ed_Ticks"),
        (APTR_VOID, "ed_Comment"),
        (UWORD, "ed_OwnerUID"),
        (UWORD, "ed_OwnerGID"),
    ]


@AmigaStructDef
class ExAllControlStruct(AmigaStruct):
    _format = [
        (ULONG, "eac_Entries"),
        (APTR_VOID, "eac_LastKey"),
        (APTR_VOID, "eac_MatchString"),
        (APTR_VOID, "eac_MatchFunc"),
    ]


'''

EXALL_METHOD = '''    def _exall_dir_entries(self, lock):
        """collect directory entries (AmigaDOS style, no . / ..) for a lock"""
        entries = []
        try:
            names = os.listdir(lock.sys_path)
        except OSError:
            return entries
        for name in names:
            if name in (".", ".."):
                continue
            path = os.path.join(lock.sys_path, name)
            is_dir = os.path.isdir(path)
            try:
                st = os.stat(path)
            except OSError:
                continue
            entries.append(
                {
                    "name": name,
                    "is_dir": is_dir,
                    "size": 0 if is_dir else st.st_size,
                    "prot": 0,
                    "mtime": st.st_mtime,
                }
            )
        entries.sort(key=lambda e: e["name"])
        return entries

    def ExAll(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        buf_ptr = ctx.cpu.r_reg(REG_D2)
        buf_size = ctx.cpu.r_reg(REG_D3)
        data = ctx.cpu.r_reg(REG_D4)
        control_ptr = ctx.cpu.r_reg(REG_D5)

        lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
        if lock is None:
            log_dos.warning("ExAll: invalid lock %08x", lock_b_addr)
            self.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
            return self.DOSFALSE

        entries = self._exall_dir_entries(lock)

        idx = 0
        ctrl = None
        match_pat = None
        if control_ptr != 0:
            ctrl = AccessStruct(ctx.mem, ExAllControlStruct, struct_addr=control_ptr)
            if ctrl.r_s("eac_LastKey") != 0:
                idx = self.exall_state.get(control_ptr, 0)
            pat_ptr = ctrl.r_s("eac_MatchString")
            if pat_ptr != 0:
                pat_str = ctx.mem.r_cstr(pat_ptr)
                if len(pat_str) > 0:
                    match_pat = Pattern(None, pat_str, True, True)

        if match_pat is not None:
            entries = [e for e in entries if pattern_match(match_pat, e["name"])]

        struct_size = ExAllDataStruct.get_size()
        addr = buf_ptr
        buf_end = buf_ptr + buf_size
        prev_ea = None
        count = 0
        last_addr = 0
        while idx < len(entries):
            ent = entries[idx]
            ent_size = (struct_size + len(ent["name"]) + 1 + 3) & ~3
            if addr + ent_size > buf_end:
                break
            ea = AccessStruct(ctx.mem, ExAllDataStruct, struct_addr=addr)
            ea.w_s("ed_Next", 0)
            name_addr = addr + struct_size
            ctx.mem.w_cstr(name_addr, ent["name"])
            ea.w_s("ed_Name", name_addr)
            ea.w_s("ed_Type", 2 if ent["is_dir"] else -3)
            ea.w_s("ed_Size", ent["size"] & 0xFFFFFFFF)
            ea.w_s("ed_Prot", ent["prot"])
            at = sys_to_ami_time(ent["mtime"])
            ea.w_s("ed_Days", at.tday)
            ea.w_s("ed_Mins", at.tmin)
            ea.w_s("ed_Ticks", at.tick)
            ea.w_s("ed_Comment", 0)
            ea.w_s("ed_OwnerUID", 0)
            ea.w_s("ed_OwnerGID", 0)
            if prev_ea is not None:
                prev_ea.w_s("ed_Next", addr)
            prev_ea = ea
            last_addr = addr
            addr += ent_size
            count += 1
            idx += 1

        if ctrl is not None:
            ctrl.w_s("eac_Entries", count)
            ctrl.w_s("eac_LastKey", last_addr)
            self.exall_state[control_ptr] = idx

        done = idx >= len(entries)
        log_dos.info(
            "ExAll: lock=%s buf=%08x size=%d data=%d ctrl=%08x -> entries=%d done=%s",
            lock,
            buf_ptr,
            buf_size,
            data,
            control_ptr,
            count,
            done,
        )
        if done:
            self.setioerr(ctx, ERROR_NO_MORE_ENTRIES)
            return self.DOSFALSE
        else:
            self.setioerr(ctx, NO_ERROR)
            return self.DOSTRUE

'''


def patch_structs(path):
    src = open(path).read()
    if "ExAllDataStruct" in src:
        print("libstructs/dos.py: already patched")
        return
    anchor = "@AmigaStructDef\nclass DosPacketStruct(AmigaStruct):"
    assert anchor in src, "DosPacketStruct anchor not found"
    src = src.replace(anchor, STRUCTS_BLOCK.lstrip("\n") + anchor, 1)
    open(path, "w").write(src)
    print("libstructs/dos.py: added ExAllDataStruct/ExAllControlStruct")


def patch_doslib(path):
    src = open(path).read()
    changed = False

    if "ExAllDataStruct,\n    ExAllControlStruct," not in src:
        src = src.replace(
            "    FileInfoBlockStruct,\n    InfoDataStruct,",
            "    FileInfoBlockStruct,\n    ExAllDataStruct,\n    ExAllControlStruct,\n    InfoDataStruct,",
            1,
        )
        changed = True

    if 'structure type=1/DOS_EXALLCONTROL' in src or "struct_def = None\n        elif obj_type == 2" in src:
        src = src.replace(
            'elif obj_type == 1:  # DOS_EXALLCONTROL\n            name = "DOS_EXALLCONTROL"\n            struct_def = None',
            'elif obj_type == 1:  # DOS_EXALLCONTROL\n            name = "DOS_EXALLCONTROL"\n            struct_def = ExAllControlStruct',
            1,
        )
        changed = True

    if "self.exall_state = {}" not in src:
        src = src.replace(
            "        self.dos_objs = {}\n        self.errstrings = {}",
            "        self.dos_objs = {}\n        self.exall_state = {}\n        self.errstrings = {}",
            1,
        )
        changed = True

    if "def ExAll(self, ctx):" not in src:
        anchor = "    def ParentDir(self, ctx):\n        lock_b_addr = ctx.cpu.r_reg(REG_D1)"
        assert anchor in src, "ParentDir anchor not found"
        src = src.replace(anchor, EXALL_METHOD + anchor, 1)
        changed = True

    if "self.exall_state.pop(ptr, 0)" not in src:
        src = src.replace(
            "            # free struct\n            ctx.alloc.free_struct(entry[0])\n        else:",
            "            # free struct\n            ctx.alloc.free_struct(entry[0])\n            if obj_type == 1:\n                self.exall_state.pop(ptr, 0)\n        else:",
            1,
        )
        changed = True

    if changed:
        open(path, "w").write(src)
        print("lib/DosLibrary.py: patched")
    else:
        print("lib/DosLibrary.py: already patched")


def main():
    root = find_amitools()
    print("amitools at", root)
    patch_structs(os.path.join(root, "vamos", "libstructs", "dos.py"))
    patch_doslib(os.path.join(root, "vamos", "lib", "DosLibrary.py"))
    print("done -- re-run the AlgoMusic binary under vamos")


if __name__ == "__main__":
    main()
