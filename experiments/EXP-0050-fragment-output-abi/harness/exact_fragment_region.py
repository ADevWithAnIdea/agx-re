#!/usr/bin/env python3
"""BLOCKED, NON-RUNNABLE draft locator for a possible EXP-0050 clean v2.

DO NOT EXECUTE. Mach-O symbol metadata does not prove an exact `_agc.main`
extent, and the nested fragment-container convention lacks an independently
audited clean provenance basis. This draft is retained only as failed process
history. `main()` exits before opening a target.

This tool has an intentionally narrow clean-room contract:

* it parses only declared fat/Mach-O metadata ranges;
* it selects only ``__TEXT,__fragment`` and the exact ``_agc.main`` symbol;
* ``locate`` never reads executable-section bytes;
* ``extract`` reads only the selected symbol region with ``os.pread``; and
* ``patch`` changes one checked byte with ``os.pwrite`` and re-reads only that
  same selected symbol region.

It never mmaps or reads a whole container, scans a container for magic or byte
patterns, visits another shader stage, materializes a whole ``__text`` section,
or reads a constant/auxiliary program region. Container-wide hashing is also
forbidden because it would require reading regions outside the allowlist.

The format constants and layouts below are public Mach-O container metadata.
The tool must be committed and Git-anchored before it is used on a live archive.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys
from typing import NoReturn


MH_MAGIC_64 = 0xFEEDFACF
MH_CIGAM_64 = 0xCFFAEDFE
FAT_MAGIC = 0xCAFEBABE
FAT_CIGAM = 0xBEBAFECA
FAT_MAGIC_MTL = 0xCBFEBABE
FAT_CIGAM_MTL = 0xBEBAFECB
LC_SEGMENT_64 = 0x19
LC_SYMTAB = 0x02
APPLE_GPU_CPUTYPE = 0x01000013

MACH_HEADER_64_SIZE = 32
SEGMENT_COMMAND_64_SIZE = 72
SECTION_64_SIZE = 80
NLIST_64_SIZE = 16
MAX_FAT_ARCHES = 64
MAX_LOAD_COMMANDS = 4096
MAX_LOAD_COMMAND_BYTES = 16 * 1024 * 1024
MAX_SECTIONS_PER_SEGMENT = 4096
MAX_SYMBOLS = 1_000_000
MAX_STRING_TABLE_BYTES = 16 * 1024 * 1024
MAX_SELECTED_MAIN_BYTES = 1024 * 1024

TARGET_STAGE_SECTION = ("__TEXT", "__fragment")
TARGET_TEXT_SECTION = ("__TEXT", "__text")
TARGET_SYMBOL = "_agc.main"


class CleanRoomError(Exception):
    """A structural or clean-room guard rejected the container."""


def fail(message: str) -> NoReturn:
    raise CleanRoomError(message)


def checked_range(offset: int, size: int, limit: int, purpose: str) -> None:
    if offset < 0 or size < 0 or offset > limit or size > limit - offset:
        fail(f"out-of-range {purpose}: offset={offset} size={size} limit={limit}")


def overlaps(a_offset: int, a_size: int, b_offset: int, b_size: int) -> bool:
    return a_offset < b_offset + b_size and b_offset < a_offset + a_size


def fixed_name(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("ascii", "strict")


class ExactReader:
    """Positional metadata reader with an auditable byte-range transcript."""

    def __init__(self, path: Path, writable: bool):
        self.path = path
        try:
            before = path.lstat()
        except FileNotFoundError:
            fail(f"missing container: {path}")
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
            fail("container must be a non-symlink regular file")
        flags = os.O_RDWR if writable else os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        self.fd = os.open(path, flags)
        self.stat = os.fstat(self.fd)
        if not stat.S_ISREG(self.stat.st_mode):
            os.close(self.fd)
            fail("opened container is not a regular file")
        if (before.st_dev, before.st_ino) != (self.stat.st_dev, self.stat.st_ino):
            os.close(self.fd)
            fail("container changed during safe open")
        fcntl.flock(self.fd, fcntl.LOCK_EX if writable else fcntl.LOCK_SH)
        self.metadata_ranges: list[dict[str, object]] = []
        self._metadata_hash = hashlib.sha256()

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self) -> "ExactReader":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @property
    def size(self) -> int:
        return self.stat.st_size

    def _pread(self, offset: int, size: int, purpose: str) -> bytes:
        checked_range(offset, size, self.size, purpose)
        data = os.pread(self.fd, size, offset)
        if len(data) != size:
            fail(f"short positional read for {purpose}")
        return data

    def metadata(self, offset: int, size: int, purpose: str) -> bytes:
        data = self._pread(offset, size, purpose)
        encoded = purpose.encode("utf-8")
        self._metadata_hash.update(struct.pack("<QQI", offset, size, len(encoded)))
        self._metadata_hash.update(encoded)
        self._metadata_hash.update(data)
        self.metadata_ranges.append({"offset": offset, "bytes": size, "purpose": purpose})
        return data

    def selected_main(self, offset: int, size: int) -> bytes:
        if size <= 0 or size > MAX_SELECTED_MAIN_BYTES:
            fail(f"selected main length outside bound: {size}")
        return self._pread(offset, size, "selected authored fragment _agc.main")

    def pwrite_one(self, offset: int, value: int) -> None:
        checked_range(offset, 1, self.size, "selected-main patch")
        written = os.pwrite(self.fd, bytes([value]), offset)
        if written != 1:
            fail("short selected-main positional write")
        os.fsync(self.fd)

    def metadata_summary(self) -> dict[str, object]:
        return {
            "metadata_bytes_read": sum(int(item["bytes"]) for item in self.metadata_ranges),
            "metadata_read_sha256": self._metadata_hash.hexdigest(),
            "metadata_ranges": self.metadata_ranges,
        }


def u32(raw: bytes, endian: str, offset: int = 0) -> int:
    return struct.unpack_from(endian + "I", raw, offset)[0]


def container_images(reader: ExactReader) -> list[tuple[int, int, str]]:
    magic_raw = reader.metadata(0, 4, "container magic")
    magic_le = struct.unpack("<I", magic_raw)[0]
    if magic_le in (MH_MAGIC_64, MH_CIGAM_64):
        return [(0, reader.size, "standalone-mach-o")]
    if magic_le not in (FAT_MAGIC, FAT_CIGAM, FAT_MAGIC_MTL, FAT_CIGAM_MTL):
        fail(f"unrecognized top-level container magic 0x{magic_le:08x}")

    # The public fat and Metal-fat tables used by these containers are big-endian.
    count = u32(reader.metadata(4, 4, "fat architecture count"), ">")
    if count == 0 or count > MAX_FAT_ARCHES:
        fail(f"fat architecture count outside bound: {count}")
    table = reader.metadata(8, count * 20, "fat architecture table")
    images = []
    for index in range(count):
        cputype, _subtype, offset, size, _align = struct.unpack_from(
            ">IIIII", table, index * 20
        )
        checked_range(offset, size, reader.size, f"fat image {index}")
        if cputype == APPLE_GPU_CPUTYPE:
            if overlaps(0, 8 + count * 20, offset, size):
                fail(f"fat image {index} overlaps container metadata")
            images.append((offset, size, f"fat-apple-gpu-{index}"))
    if not images:
        fail("no declared AppleGPU image")
    return images


def macho_endian(header: bytes) -> str:
    magic_le = struct.unpack_from("<I", header)[0]
    if magic_le == MH_MAGIC_64:
        return "<"
    if magic_le == MH_CIGAM_64:
        return ">"
    fail(f"declared image is not Mach-O 64: 0x{magic_le:08x}")


def parse_macho_metadata(
    reader: ExactReader,
    base: int,
    image_size: int,
    target_section: tuple[str, str],
    purpose_prefix: str,
    require_apple_gpu: bool,
    need_symtab: bool,
) -> tuple[dict[str, int], dict[str, int] | None]:
    checked_range(base, image_size, reader.size, f"{purpose_prefix} image")
    header = reader.metadata(base, MACH_HEADER_64_SIZE, f"{purpose_prefix} Mach-O header")
    endian = macho_endian(header)
    (_magic, cputype_signed, _cpusubtype, _filetype, ncmds, sizeofcmds,
     _flags, _reserved) = struct.unpack(endian + "IiIIIIII", header)
    cputype = cputype_signed & 0xFFFFFFFF
    if require_apple_gpu and cputype != APPLE_GPU_CPUTYPE:
        fail(f"{purpose_prefix} cputype is not AppleGPU: 0x{cputype:08x}")
    if ncmds > MAX_LOAD_COMMANDS or sizeofcmds > MAX_LOAD_COMMAND_BYTES:
        fail(f"{purpose_prefix} load-command bounds exceeded")
    commands_start = base + MACH_HEADER_64_SIZE
    commands_end = commands_start + sizeofcmds
    checked_range(commands_start, sizeofcmds, base + image_size,
                  f"{purpose_prefix} load-command area")

    found_sections: list[dict[str, int]] = []
    symtabs: list[dict[str, int]] = []
    cursor = commands_start
    for index in range(ncmds):
        head = reader.metadata(cursor, 8, f"{purpose_prefix} load command {index} header")
        cmd, cmdsize = struct.unpack(endian + "II", head)
        if cmdsize < 8 or cursor + cmdsize > commands_end:
            fail(f"{purpose_prefix} malformed load command {index}")
        if cmd == LC_SEGMENT_64:
            if cmdsize < SEGMENT_COMMAND_64_SIZE:
                fail(f"{purpose_prefix} short segment command {index}")
            segment = reader.metadata(
                cursor, SEGMENT_COMMAND_64_SIZE,
                f"{purpose_prefix} segment command {index}",
            )
            segment_name = fixed_name(segment[8:24])
            nsects = u32(segment, endian, 64)
            if nsects > MAX_SECTIONS_PER_SEGMENT:
                fail(f"{purpose_prefix} section count outside bound")
            required = SEGMENT_COMMAND_64_SIZE + nsects * SECTION_64_SIZE
            if required > cmdsize:
                fail(f"{purpose_prefix} truncated section table")
            for section_index in range(nsects):
                section_offset = cursor + SEGMENT_COMMAND_64_SIZE + section_index * SECTION_64_SIZE
                section = reader.metadata(
                    section_offset, SECTION_64_SIZE,
                    f"{purpose_prefix} section {index}:{section_index}",
                )
                section_name = fixed_name(section[:16])
                section_segment = fixed_name(section[16:32])
                address, size, file_offset = struct.unpack_from(endian + "QQI", section, 32)
                if (section_segment, section_name) == target_section:
                    if section_segment != segment_name:
                        fail(f"{purpose_prefix} section/segment name mismatch")
                    checked_range(file_offset, size, image_size,
                                  f"{purpose_prefix} selected section")
                    found_sections.append({
                        "address": address,
                        "size": size,
                        "file_offset": file_offset,
                    })
        elif cmd == LC_SYMTAB:
            if cmdsize < 24:
                fail(f"{purpose_prefix} short symtab command")
            symtab = reader.metadata(cursor, 24, f"{purpose_prefix} symtab command")
            symoff, nsyms, stroff, strsize = struct.unpack_from(endian + "IIII", symtab, 8)
            if nsyms > MAX_SYMBOLS or strsize > MAX_STRING_TABLE_BYTES:
                fail(f"{purpose_prefix} symbol metadata bounds exceeded")
            checked_range(symoff, nsyms * NLIST_64_SIZE, image_size,
                          f"{purpose_prefix} nlist table")
            checked_range(stroff, strsize, image_size,
                          f"{purpose_prefix} string table")
            symtabs.append({
                "symoff": symoff,
                "nsyms": nsyms,
                "stroff": stroff,
                "strsize": strsize,
                "endian_little": int(endian == "<"),
            })
        cursor += cmdsize
    if cursor != commands_end:
        fail(f"{purpose_prefix} load-command size mismatch")
    if len(found_sections) != 1:
        fail(f"{purpose_prefix} expected one {target_section}, got {len(found_sections)}")
    if need_symtab and len(symtabs) != 1:
        fail(f"{purpose_prefix} expected one symbol table, got {len(symtabs)}")
    selected = found_sections[0]
    metadata_span = MACH_HEADER_64_SIZE + sizeofcmds
    if overlaps(0, metadata_span, selected["file_offset"], selected["size"]):
        fail(f"{purpose_prefix} selected section overlaps Mach-O metadata")
    for symtab in symtabs:
        if overlaps(symtab["symoff"], symtab["nsyms"] * NLIST_64_SIZE,
                    selected["file_offset"], selected["size"]):
            fail(f"{purpose_prefix} nlist table overlaps selected code section")
        if overlaps(symtab["stroff"], symtab["strsize"],
                    selected["file_offset"], selected["size"]):
            fail(f"{purpose_prefix} string table overlaps selected code section")
    return selected, symtabs[0] if symtabs else None


def symbol_is_exact(
    reader: ExactReader,
    string_base: int,
    string_size: int,
    index: int,
    purpose: str,
) -> bool:
    if index >= string_size:
        fail(f"{purpose} string index outside table")
    expected = TARGET_SYMBOL.encode("ascii") + b"\0"
    if string_size - index < len(expected):
        return False
    # Read only enough symbol-table metadata to test this exact name. We never
    # materialize unrelated symbol strings.
    candidate = reader.metadata(
        string_base + index, len(expected),
        f"{purpose} exact target-symbol name test",
    )
    return candidate == expected


def locate_fragment_main(reader: ExactReader) -> dict[str, object]:
    candidates = []
    for image_base, image_size, image_note in container_images(reader):
        outer, _ = parse_macho_metadata(
            reader, image_base, image_size, TARGET_STAGE_SECTION,
            f"{image_note} outer", True, False,
        )
        nested_base = image_base + outer["file_offset"]
        nested_size = outer["size"]
        text, symtab = parse_macho_metadata(
            reader, nested_base, nested_size, TARGET_TEXT_SECTION,
            f"{image_note} fragment", True, True,
        )
        assert symtab is not None
        endian = "<" if symtab["endian_little"] else ">"
        in_text: list[tuple[int, int]] = []
        text_start = text["address"]
        text_end = text_start + text["size"]
        for index in range(symtab["nsyms"]):
            raw = reader.metadata(
                nested_base + symtab["symoff"] + index * NLIST_64_SIZE,
                NLIST_64_SIZE,
                f"{image_note} fragment nlist {index}",
            )
            name_index, _type, _section, _desc, value = struct.unpack(
                endian + "IBBHQ", raw
            )
            if text_start <= value < text_end:
                in_text.append((name_index, value))

        targets = []
        for name_index, value in in_text:
            if symbol_is_exact(
                reader,
                nested_base + symtab["stroff"], symtab["strsize"], name_index,
                f"{image_note} fragment",
            ):
                targets.append(value)
        if len(targets) != 1:
            fail(f"{image_note}: expected one exact {TARGET_SYMBOL}, got {len(targets)}")
        start_address = targets[0]
        aliases = [value for _name_index, value in in_text if value == start_address]
        if len(aliases) != 1:
            fail(f"{image_note}: selected symbol has an ambiguous same-address alias")
        later = [value for _name_index, value in in_text if value > start_address]
        end_address = min(later) if later else text_end
        length = end_address - start_address
        if length <= 0 or length > MAX_SELECTED_MAIN_BYTES:
            fail(f"{image_note}: selected symbol length outside bound: {length}")
        relative = start_address - text_start
        absolute = nested_base + text["file_offset"] + relative
        checked_range(absolute, length, reader.size, "selected fragment main")
        candidates.append({
            "image": image_note,
            "stage": "fragment",
            "symbol": TARGET_SYMBOL,
            "absolute_offset": absolute,
            "length": length,
            "container_bytes": reader.size,
        })
    if len(candidates) != 1:
        fail(f"expected one selected fragment main across container, got {len(candidates)}")
    return candidates[0]


def extract(reader: ExactReader, region: dict[str, object]) -> dict[str, object]:
    offset = int(region["absolute_offset"])
    length = int(region["length"])
    main = reader.selected_main(offset, length)
    return {
        "status": "EXTRACTED",
        "access_contract": "metadata plus exact selected authored fragment _agc.main only",
        "region": region,
        "main_length": len(main),
        "main_sha256": hashlib.sha256(main).hexdigest(),
        "main_hex": main.hex(),
        **reader.metadata_summary(),
    }


def patch(reader: ExactReader, region: dict[str, object], args: argparse.Namespace) -> dict[str, object]:
    offset = int(region["absolute_offset"])
    length = int(region["length"])
    if length != args.expected_main_length:
        fail(f"selected main length {length} != expected {args.expected_main_length}")
    before = reader.selected_main(offset, length)
    before_hash = hashlib.sha256(before).hexdigest()
    if before_hash != args.expected_main_sha256:
        fail(f"selected main hash {before_hash} != expected {args.expected_main_sha256}")

    signature = bytes.fromhex(args.signature_hex)
    if not signature:
        fail("empty signature")
    span = max(len(signature), args.selector_offset + 1)
    matches = [
        index for index in range(0, len(before) - span + 1)
        if before[index:index + len(signature)] == signature
    ]
    candidates = [
        index for index in matches
        if before[index + args.selector_offset] == args.before_byte
    ]
    if len(candidates) != args.expected_candidates:
        fail(
            f"checked signature candidates {len(candidates)} != expected "
            f"{args.expected_candidates}; signature matches={matches} candidates={candidates}"
        )
    selected = candidates[0]
    changed_relative = selected + args.selector_offset
    expected_diff = [{
        "offset": changed_relative,
        "before": args.before_byte,
        "after": args.after_byte,
    }]
    wrote = False
    try:
        reader.pwrite_one(offset + changed_relative, args.after_byte)
        wrote = True
        after = reader.selected_main(offset, length)
        differences = [
            {"offset": index, "before": old, "after": new}
            for index, (old, new) in enumerate(zip(before, after)) if old != new
        ]
        if differences != expected_diff:
            fail(f"post-write exact-region diff guard failed: {differences}")
    except Exception:
        # Roll back the one intended byte when possible. No other region is read.
        if wrote:
            try:
                reader.pwrite_one(offset + changed_relative, args.before_byte)
            except OSError:
                pass
        raise
    return {
        "status": "PATCHED",
        "access_contract": "metadata plus exact selected authored fragment _agc.main only",
        "region": region,
        "signature_hex": args.signature_hex,
        "signature_offsets": matches,
        "candidate_offsets": candidates,
        "changed_main_offset": changed_relative,
        "change_count": 1,
        "before_byte": args.before_byte,
        "after_byte": args.after_byte,
        "before_main_length": len(before),
        "before_main_sha256": before_hash,
        "before_main_hex": before.hex(),
        "after_main_length": len(after),
        "after_main_sha256": hashlib.sha256(after).hexdigest(),
        "after_main_hex": after.hex(),
        **reader.metadata_summary(),
    }


def byte_value(text: str) -> int:
    value = int(text, 16)
    if not 0 <= value <= 0xFF:
        raise argparse.ArgumentTypeError("byte must be 00..ff")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EXP-0050 exact fragment-main metadata locator/accessor"
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)
    for operation in ("locate", "extract"):
        child = subparsers.add_parser(operation)
        child.add_argument("archive", type=Path)
    child = subparsers.add_parser("patch")
    child.add_argument("archive", type=Path)
    child.add_argument("--expected-main-length", type=int, required=True)
    child.add_argument("--expected-main-sha256", required=True)
    child.add_argument("--signature-hex", default="e70654")
    child.add_argument("--selector-offset", type=int, default=5)
    child.add_argument("--before-byte", type=byte_value, default=0x02)
    child.add_argument("--after-byte", type=byte_value, default=0x04)
    child.add_argument("--expected-candidates", type=int, default=1)
    return parser


def main() -> int:
    raise SystemExit(
        "BLOCKED DRAFT: exact _agc.main extent/container provenance is not established"
    )
    args = build_parser().parse_args()
    writable = args.operation == "patch"
    try:
        with ExactReader(args.archive, writable=writable) as reader:
            region = locate_fragment_main(reader)
            if args.operation == "locate":
                result = {
                    "status": "LOCATED",
                    "access_contract": "container metadata only; no executable bytes read",
                    "region": region,
                    **reader.metadata_summary(),
                }
            elif args.operation == "extract":
                result = extract(reader, region)
            else:
                result = patch(reader, region, args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (CleanRoomError, OSError, UnicodeError, ValueError, struct.error) as error:
        print(json.dumps({"status": "REJECTED", "error": str(error)}, sort_keys=True),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
