#!/usr/bin/env python3
# agxparse.py — clean-room parser for Metal binary-archive / metallib containers.
#
# Part of the A18 Pro GPU clean-room RE project. Given a container produced by
# our own shdump tool (from OUR OWN MSL source), this walks the *public* Mach-O
# container format with our own code and isolates the raw AGX machine-code bytes
# the GPU actually executes.
#
# CLEAN-ROOM NOTE: This is pure container parsing (Mach-O is a public, documented
# file format). It reads a section/symbol table and slices out the bytes of a
# shader WE compiled from OUR OWN source. It never disassembles any Apple binary.
# The structure was informed by the public/MIT applegpu metal-archive-extractor,
# but this is our own independent implementation using standard format constants.
#
# Usage:
#   python3 agxparse.py <container>                 # structural report
#   python3 agxparse.py <container> --extract-hex   # print AGX bytes as hex
#   python3 agxparse.py <container> --extract-bin OUT.bin
#   python3 agxparse.py <container> --json          # machine-readable report
#
# Exit status is 0 on a clean AGX extraction, 2 if only AIR/bitcode was found.

import sys
import struct
import json
import argparse

# --- public Mach-O / Metal fat format constants -----------------------------
MH_MAGIC_64   = 0xFEEDFACF
MH_CIGAM_64   = 0xCFFAEDFE
FAT_MAGIC     = 0xCAFEBABE          # standard fat
FAT_CIGAM     = 0xBEBAFECA
FAT_MAGIC_MTL = 0xCBFEBABE          # Metal fat variant
FAT_CIGAM_MTL = 0xBEBAFECB
BITCODE_MAGIC = b"BC\xC0\xDE"       # LLVM bitcode wrapper => AIR, NOT machine code

LC_SEGMENT_64 = 0x19
LC_SYMTAB     = 0x02

# GPU machine (cputype) values Metal uses for its embedded targets.
CPUTYPE_NAMES = {
    0x1000013: "AppleGPU",   # native AGX machine code  <-- what we want
    0x1000014: "AMDGPU",
    0x1000015: "IntelGPU",
    0x1000017: "AIR64",      # AIR / LLVM bitcode        <-- NOT machine code
}
APPLE_GPU_CPUTYPE = 0x1000013
AIR64_CPUTYPE     = 0x1000017

SHADER_SECTIONS = ("__compute", "__vertex", "__fragment")
AGX_MAIN_SYMBOLS = ("_agc.main", "_agc.main.constant_program")


class MachO:
    """Parse one Mach-O image out of a bytes buffer (offset relative to buf)."""

    def __init__(self, buf, base=0):
        self.buf = buf
        self.base = base
        magic = struct.unpack_from("<I", buf, base)[0]
        if magic == MH_MAGIC_64:
            self.le = True
        elif magic == MH_CIGAM_64:
            self.le = False
        else:
            raise ValueError(f"not a mach-o 64 image (magic={magic:#010x})")
        e = "<" if self.le else ">"
        (self.magic, self.cputype, self.cpusubtype, self.filetype,
         self.ncmds, self.sizeofcmds, self.flags, _res) = struct.unpack_from(e + "IiIIIIII", buf, base)
        self.endian = e
        self.segments = []   # list of dicts: name, fileoff, filesize, sections[]
        self.sections = []   # flat list of dicts: seg, sect, offset, size, addr
        self.symbols = []    # list of dicts: name, value, sect
        self._parse_load_commands()

    def _parse_load_commands(self):
        e = self.endian
        p = self.base + 32  # sizeof mach_header_64
        for _ in range(self.ncmds):
            cmd, cmdsize = struct.unpack_from(e + "II", self.buf, p)
            if cmd == LC_SEGMENT_64:
                segname = self.buf[p + 8:p + 24].split(b"\0")[0].decode("ascii", "replace")
                (vmaddr, vmsize, fileoff, filesize, maxprot, initprot,
                 nsects, flags) = struct.unpack_from(e + "QQQQiiII", self.buf, p + 24)
                seg = {"name": segname, "fileoff": fileoff, "filesize": filesize,
                       "vmaddr": vmaddr, "sections": []}
                sp = p + 72  # sizeof segment_command_64
                for _s in range(nsects):
                    sectname = self.buf[sp:sp + 16].split(b"\0")[0].decode("ascii", "replace")
                    segn = self.buf[sp + 16:sp + 32].split(b"\0")[0].decode("ascii", "replace")
                    (addr, size, offset, align, reloff, nreloc, sflags,
                     r1, r2, r3) = struct.unpack_from(e + "QQIIIIIIII", self.buf, sp + 32)
                    sect = {"seg": segn, "sect": sectname, "addr": addr, "size": size,
                            "offset": offset, "flags": sflags}
                    seg["sections"].append(sect)
                    self.sections.append(sect)
                    sp += 80  # sizeof section_64
                self.segments.append(seg)
            elif cmd == LC_SYMTAB:
                symoff, nsyms, stroff, strsize = struct.unpack_from(e + "IIII", self.buf, p + 8)
                strtab = self.buf[self.base + stroff: self.base + stroff + strsize]
                for i in range(nsyms):
                    o = self.base + symoff + i * 16
                    n_strx, n_type, n_sect, n_desc, n_value = struct.unpack_from(e + "IBBHQ", self.buf, o)
                    name = strtab[n_strx:].split(b"\0")[0].decode("ascii", "replace")
                    self.symbols.append({"name": name, "value": n_value, "sect": n_sect})
            p += cmdsize

    def find_section(self, seg, sect):
        for s in self.sections:
            if s["seg"] == seg and s["sect"] == sect:
                return s
        return None

    def section_bytes(self, sect):
        off = self.base + sect["offset"]
        return self.buf[off:off + sect["size"]]

    def cputype_name(self):
        return CPUTYPE_NAMES.get(self.cputype, f"unknown({self.cputype:#x})")


def iter_gpu_images(buf):
    """Yield (offset, size, note) for each embedded Mach-O image in a container.

    Handles a standalone Mach-O, a standard fat, and the Metal fat variant.
    """
    if len(buf) < 8:
        return
    magic = struct.unpack_from("<I", buf, 0)[0]
    if magic in (MH_MAGIC_64, MH_CIGAM_64):
        yield (0, len(buf), "top-level mach-o")
        return
    if magic in (FAT_MAGIC, FAT_MAGIC_MTL):
        be = ">"
    elif magic in (FAT_CIGAM, FAT_CIGAM_MTL):
        be = ">"  # fat headers are stored big-endian regardless
    else:
        # Not a recognised container top; still try to treat as mach-o later.
        yield (0, len(buf), "unrecognised-top")
        return
    nfat = struct.unpack_from(be + "I", buf, 4)[0]
    p = 8
    for i in range(nfat):
        cputype, cpusub, offset, size, align = struct.unpack_from(be + "IIIII", buf, p)
        yield (offset, size, f"fat-arch[{i}] cputype={CPUTYPE_NAMES.get(cputype, hex(cputype))}")
        p += 20


def extract_agx(buf):
    """Return (report, pieces).

    Strategy: find the GPU (AppleGPU) image; inside it the shader section
    (__TEXT,__compute/__vertex/__fragment) is itself a nested Mach-O whose
    __TEXT,__text holds the AGX code, carved into named regions by the symbol
    table (_agc.main = the main program, _agc.main.constant_program = prolog).

    `pieces` is a dict of name -> bytes, always including the synthetic key
    "__whole_text__" (the entire nested __text). The default extraction target
    is "_agc.main". Returns (report, None) if no AppleGPU code was found.
    """
    report = {
        "container_magic": f"{struct.unpack_from('<I', buf, 0)[0]:#010x}",
        "images": [],
        "bitcode_magic_present": (BITCODE_MAGIC in buf),
        "agx": None,
        "air_present": False,
    }
    pieces = None

    for (off, size, note) in iter_gpu_images(buf):
        try:
            mo = MachO(buf, off)
        except ValueError as ex:
            report["images"].append({"note": note, "offset": off, "error": str(ex)})
            continue
        img = {
            "note": note, "offset": off, "cputype": mo.cputype_name(),
            "filetype": mo.filetype,
            "sections": [f'{s["seg"]},{s["sect"]}(off={s["offset"]},size={s["size"]})'
                         for s in mo.sections],
        }
        report["images"].append(img)
        if mo.cputype == AIR64_CPUTYPE:
            report["air_present"] = True

        if mo.cputype != APPLE_GPU_CPUTYPE:
            continue

        # Look for a shader container section and parse it as a nested mach-o.
        for shsecname in SHADER_SECTIONS:
            shsec = mo.find_section("__TEXT", shsecname)
            if not shsec or shsec["size"] == 0:
                continue
            try:
                nested = MachO(buf, off + shsec["offset"])
            except ValueError:
                # Section is raw code, not a nested container; take it whole.
                data = mo.section_bytes(shsec)
                pieces = {"__whole_text__": data}
                report["agx"] = {"kind": "raw-section", "section": f"__TEXT,{shsecname}",
                                 "length": len(data)}
                break

            text = nested.find_section("__TEXT", "__text")
            if not text:
                continue
            text_all = nested.section_bytes(text)

            # Symbols whose value lies inside __text, sorted by address.
            insyms = sorted(
                [s for s in nested.symbols
                 if text["addr"] <= s["value"] < text["addr"] + text["size"]],
                key=lambda s: s["value"])
            # Carve each symbol region [this_sym, next_sym) within __text.
            pieces = {"__whole_text__": text_all}
            region_meta = []
            for i, s in enumerate(insyms):
                start = s["value"] - text["addr"]
                end = (insyms[i + 1]["value"] - text["addr"]) if i + 1 < len(insyms) else text["size"]
                pieces[s["name"]] = text_all[start:end]
                region_meta.append((s["name"], start, end, end - start))

            main_len = len(pieces.get("_agc.main", b""))
            report["agx"] = {
                "kind": "nested-mach-o",
                "outer_section": f"__TEXT,{shsecname}",
                "nested_cputype": nested.cputype_name(),
                "text_section_size": text["size"],
                "regions": region_meta,           # (name, start, end, length)
                "main_length": main_len,
                "whole_text_length": len(text_all),
            }
            break
        if pieces is not None:
            break

    return report, pieces


def locate_region(buf, symbol="_agc.main"):
    """Return (abs_offset, length) of a symbol region within the container FILE.

    Unlike extract_agx (which returns the *bytes*), this returns the absolute
    byte offset of the region inside `buf`, so a caller can splice replacement
    bytes in place without disturbing the surrounding container. Returns None if
    the symbol / AGX code is not found.
    """
    for (off, size, note) in iter_gpu_images(buf):
        try:
            mo = MachO(buf, off)
        except ValueError:
            continue
        if mo.cputype != APPLE_GPU_CPUTYPE:
            continue
        for shsecname in SHADER_SECTIONS:
            shsec = mo.find_section("__TEXT", shsecname)
            if not shsec or shsec["size"] == 0:
                continue
            nested_base = off + shsec["offset"]
            try:
                nested = MachO(buf, nested_base)
            except ValueError:
                continue
            text = nested.find_section("__TEXT", "__text")
            if not text:
                continue
            text_abs = nested.base + text["offset"]   # abs file offset of __text
            insyms = sorted(
                [s for s in nested.symbols
                 if text["addr"] <= s["value"] < text["addr"] + text["size"]],
                key=lambda s: s["value"])
            for i, s in enumerate(insyms):
                if s["name"] != symbol:
                    continue
                start = s["value"] - text["addr"]
                end = (insyms[i + 1]["value"] - text["addr"]) if i + 1 < len(insyms) else text["size"]
                return (text_abs + start, end - start)
    return None


def default_target(pieces):
    """The bytes a caller most likely wants: the main program, else whole text."""
    if pieces is None:
        return None
    if "_agc.main" in pieces:
        return pieces["_agc.main"]
    return pieces.get("__whole_text__")


def main():
    ap = argparse.ArgumentParser(description="clean-room AGX container parser")
    ap.add_argument("container")
    ap.add_argument("--extract-hex", action="store_true",
                    help="print bytes of the target region as hex")
    ap.add_argument("--extract-bin", metavar="OUT",
                    help="write bytes of the target region to a file")
    ap.add_argument("--symbol", metavar="NAME", default="_agc.main",
                    help="which region to extract (default _agc.main; "
                         "use __whole_text__ for the entire nested __text)")
    ap.add_argument("--whole-text", action="store_true",
                    help="target the whole nested __text (both prolog + main)")
    ap.add_argument("--locate", metavar="SYMBOL", nargs="?", const="_agc.main",
                    help="print 'ABS_OFFSET LENGTH' of a symbol region within the "
                         "container file (for in-place splicing); default _agc.main")
    ap.add_argument("--json", action="store_true", help="print JSON report")
    args = ap.parse_args()

    with open(args.container, "rb") as f:
        buf = f.read()

    if args.locate is not None:
        loc = locate_region(buf, args.locate)
        if loc is None:
            sys.stderr.write(f"agxparse: could not locate region '{args.locate}'\n")
            sys.exit(2)
        print(f"{loc[0]} {loc[1]}")
        sys.exit(0)

    report, pieces = extract_agx(buf)

    def pick():
        if pieces is None:
            return None
        key = "__whole_text__" if args.whole_text else args.symbol
        return pieces.get(key)

    if args.extract_hex or args.extract_bin:
        data = pick()
        if data is None:
            sys.stderr.write(f"agxparse: no bytes for target '{args.symbol}'\n")
            sys.exit(2)
        if args.extract_hex:
            print(data.hex())
        if args.extract_bin:
            with open(args.extract_bin, "wb") as of:
                of.write(data)
            sys.stderr.write(f"agxparse: wrote {len(data)} bytes to {args.extract_bin}\n")
        sys.exit(0)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"container magic : {report['container_magic']}")
        print(f"bitcode (BC\\xC0\\xDE) present : {report['bitcode_magic_present']}")
        print(f"AIR64 image present         : {report['air_present']}")
        for img in report["images"]:
            print(f"\nimage @ {img.get('offset')}: {img.get('note')}")
            if "error" in img:
                print(f"  error: {img['error']}")
                continue
            print(f"  cputype : {img.get('cputype')}  filetype={img.get('filetype')}")
            for s in img.get("sections", []):
                print(f"    section {s}")
        if report["agx"]:
            a = report["agx"]
            print(f"\nAGX extraction ({a['kind']}) from {a.get('outer_section')}:")
            print(f"  nested cputype   : {a.get('nested_cputype')}")
            print(f"  __text size      : {a.get('whole_text_length')}")
            print(f"  _agc.main length : {a.get('main_length')}")
            for (name, start, end, length) in a.get("regions", []):
                print(f"  region {name}: [{start}:{end}] ({length} bytes)")
        else:
            print("\nAGX extraction: NONE")

    sys.exit(0 if report["agx"] else 2)


if __name__ == "__main__":
    main()
