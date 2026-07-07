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

# stage name -> the __TEXT section that carries that stage's AGX code.
# Insertion order matters: it is the default search order for the
# backward-compatible (stage=None) code paths (compute first).
STAGE_SECTIONS = {"compute": "__compute", "vertex": "__vertex", "fragment": "__fragment"}
SECTION_STAGE = {v: k for k, v in STAGE_SECTIONS.items()}


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


def _carve_shader_section(buf, image_off, shsec, shsecname):
    """Carve one shader section (a nested Mach-O) into {symbol: bytes} pieces.

    The section's __TEXT,__text holds the AGX code, split into named regions by
    the symbol table (_agc.main = main program, _agc.main.constant_program =
    prolog). Returns (pieces, meta). `pieces` always includes "__whole_text__".
    For a section that is NOT a nested Mach-O, returns the raw bytes whole.
    """
    try:
        nested = MachO(buf, image_off + shsec["offset"])
    except ValueError:
        # Section is raw code, not a nested container; take it whole.
        off = image_off + shsec["offset"]
        data = buf[off:off + shsec["size"]]
        return ({"__whole_text__": data},
                {"kind": "raw-section", "outer_section": f"__TEXT,{shsecname}",
                 "length": len(data), "whole_text_length": len(data), "regions": []})

    text = nested.find_section("__TEXT", "__text")
    if not text:
        return None, {"kind": "no-text", "outer_section": f"__TEXT,{shsecname}"}
    text_all = nested.section_bytes(text)

    # Symbols whose value lies inside __text, sorted by address.
    insyms = sorted(
        [s for s in nested.symbols
         if text["addr"] <= s["value"] < text["addr"] + text["size"]],
        key=lambda s: s["value"])
    pieces = {"__whole_text__": text_all}
    region_meta = []
    for i, s in enumerate(insyms):
        start = s["value"] - text["addr"]
        end = (insyms[i + 1]["value"] - text["addr"]) if i + 1 < len(insyms) else text["size"]
        pieces[s["name"]] = text_all[start:end]
        region_meta.append((s["name"], start, end, end - start))

    meta = {
        "kind": "nested-mach-o",
        "outer_section": f"__TEXT,{shsecname}",
        "nested_cputype": nested.cputype_name(),
        "text_section_size": text["size"],
        "regions": region_meta,               # (name, start, end, length)
        "main_length": len(pieces.get("_agc.main", b"")),
        "whole_text_length": len(text_all),
    }
    return pieces, meta


def extract_all_stages(buf):
    """Return (report, stages).

    Walk every AppleGPU image and carve *all* shader stages present (compute,
    vertex, fragment) — a render pipeline archive carries __vertex and
    __fragment as two separate __TEXT sections in one AppleGPU image (EXP-0008),
    directly analogous to the compute path's __compute section.

    `stages` is {stage_name: pieces}, where pieces is {symbol: bytes} (always
    including "__whole_text__"). report["stages"][stage] holds the per-stage
    carve metadata; report["agx"] mirrors the compute (else first) stage for
    backward-compatible callers.
    """
    report = {
        "container_magic": f"{struct.unpack_from('<I', buf, 0)[0]:#010x}",
        "images": [],
        "bitcode_magic_present": (BITCODE_MAGIC in buf),
        "agx": None,
        "stages": {},
        "air_present": False,
    }
    stages = {}

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

        for stage_name, shsecname in STAGE_SECTIONS.items():
            if stage_name in stages:
                continue
            shsec = mo.find_section("__TEXT", shsecname)
            if not shsec or shsec["size"] == 0:
                continue
            pieces, meta = _carve_shader_section(buf, off, shsec, shsecname)
            if pieces is None:
                continue
            stages[stage_name] = pieces
            report["stages"][stage_name] = meta

    # Backward-compatible single-stage view: compute if present, else first found.
    for s in STAGE_SECTIONS:
        if s in report["stages"]:
            report["agx"] = report["stages"][s]
            break
    return report, stages


def extract_agx(buf, stage=None):
    """Return (report, pieces) — backward-compatible single-stage extractor.

    `pieces` is a dict of name -> bytes, always including "__whole_text__"; the
    default extraction target is "_agc.main". When `stage` is None, returns the
    compute stage if present, else the first stage found (compute, vertex,
    fragment order) — preserving the historical behaviour for compute archives.
    When `stage` is given ("compute"|"vertex"|"fragment"), returns that stage.
    Returns (report, None) if the requested code was not found.
    """
    report, stages = extract_all_stages(buf)
    if not stages:
        return report, None
    if stage is not None:
        report["agx"] = report["stages"].get(stage)
        return report, stages.get(stage)
    for s in STAGE_SECTIONS:            # compute, vertex, fragment
        if s in stages:
            report["agx"] = report["stages"][s]
            return report, stages[s]
    return report, None


def locate_region(buf, symbol="_agc.main", stage=None):
    """Return (abs_offset, length) of a symbol region within the container FILE.

    Unlike extract_agx (which returns the *bytes*), this returns the absolute
    byte offset of the region inside `buf`, so a caller can splice replacement
    bytes in place without disturbing the surrounding container. Returns None if
    the symbol / AGX code is not found.

    `stage` ("compute"|"vertex"|"fragment") restricts the search to one shader
    stage — needed for render archives, which carry a `_agc.main` in BOTH the
    __vertex and __fragment sections. With stage=None the search order is
    compute, vertex, fragment (first match wins) — backward compatible.
    """
    for (off, size, note) in iter_gpu_images(buf):
        try:
            mo = MachO(buf, off)
        except ValueError:
            continue
        if mo.cputype != APPLE_GPU_CPUTYPE:
            continue
        for stage_name, shsecname in STAGE_SECTIONS.items():
            if stage is not None and stage_name != stage:
                continue
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
    ap.add_argument("--stage", choices=("compute", "vertex", "fragment"),
                    default=None,
                    help="which shader stage to extract/locate. A render archive "
                         "carries both 'vertex' and 'fragment'; default is compute "
                         "(else the first stage found).")
    ap.add_argument("--locate", metavar="SYMBOL", nargs="?", const="_agc.main",
                    help="print 'ABS_OFFSET LENGTH' of a symbol region within the "
                         "container file (for in-place splicing); default _agc.main")
    ap.add_argument("--json", action="store_true", help="print JSON report")
    args = ap.parse_args()

    with open(args.container, "rb") as f:
        buf = f.read()

    if args.locate is not None:
        loc = locate_region(buf, args.locate, stage=args.stage)
        if loc is None:
            sys.stderr.write(f"agxparse: could not locate region '{args.locate}'"
                             f"{f' in stage {args.stage}' if args.stage else ''}\n")
            sys.exit(2)
        print(f"{loc[0]} {loc[1]}")
        sys.exit(0)

    report, pieces = extract_agx(buf, stage=args.stage)

    def pick():
        if pieces is None:
            return None
        key = "__whole_text__" if args.whole_text else args.symbol
        return pieces.get(key)

    if args.extract_hex or args.extract_bin:
        data = pick()
        if data is None:
            sys.stderr.write(f"agxparse: no bytes for target '{args.symbol}'"
                             f"{f' in stage {args.stage}' if args.stage else ''}\n")
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
        stages = report.get("stages", {})
        if stages:
            print(f"\nstages present: {', '.join(stages)}")
            for stage_name, a in stages.items():
                print(f"\nAGX extraction [{stage_name}] ({a['kind']}) "
                      f"from {a.get('outer_section')}:")
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
