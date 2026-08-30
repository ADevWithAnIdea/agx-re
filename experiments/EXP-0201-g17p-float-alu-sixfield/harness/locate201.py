#!/usr/bin/env python3
"""EXP-0201 instruction location by DESCRIPTOR SIGNATURE, from the PINNED db.

Why signature scanning and not a tokenizer walk. A resync walk makes every
occurrence offset depend on the DB's length rules for every preceding byte, and
those length rules are themselves under revision by sibling experiments. A
signature scan depends only on the `match` constraints of the ONE descriptor
under test, read from THIS experiment's pinned `db.json`, so the located bytes
are the same whatever a sibling experiment does to the tokenizer.

`falu3` and `falu3_ext` share a signature ([0,4,9] + [17,1,1]) and are told apart
only by length, and `falu3_srcmod12`/`falu_srcmod12b` share it with them too. So
every hit is cross-checked against the pinned tokenizer and an occurrence is
admitted for a target mnemonic ONLY if `decode_one` names that mnemonic there.

Every hit is then CROSS-CHECKED by asking the pinned `decode_one` what the bytes
at that offset decode to, and the tokenized mnemonic is recorded on every case.
FIELD-SWEEP-PROTOCOL / dispatch, 2026-08-30: *two fields were withdrawn after
their "movement" turned out to be the sweep encoding a DIFFERENT instruction.*

HARD EXIT if the pinned db.json / isadb.py are absent: `tools/agx-isa/` is
shared and edited by other experiments, and this one must never resolve through
it. Everything here reads the snapshot in `pinned/`.

CLEAN-ROOM: OWN-SHADER. Only our own compiled MSL is scanned.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def pinned_dir():
    for cand in (EXP / "pinned",
                 Path.home() / "agxre" / "EXP-0201" / "pinned"):
        if (cand / "isadb.py").exists() and (cand / "db.json").exists():
            return cand
    sys.stderr.write(
        "FATAL: EXP-0201 pinned isadb.py/db.json not found. This experiment "
        "must NOT resolve through the shared tools/agx-isa; use pinned/.\n")
    raise SystemExit(2)


PINNED = pinned_dir()
sys.path.insert(0, str(PINNED))
import isadb  # noqa: E402  (READ-ONLY use of the pinned snapshot)

if Path(isadb.__file__).resolve() != (PINNED / "isadb.py").resolve():
    sys.stderr.write("FATAL: isadb resolved to %s, not the pinned copy\n"
                     % isadb.__file__)
    raise SystemExit(2)

DB = json.loads((PINNED / "db.json").read_text())
DESC = {d["mnemonic"]: d for d in DB["instructions"]}


def field_span(mnemonic, field):
    d = DESC[mnemonic]
    for f in d["fields"]:
        if f["name"] == field:
            return f["start"], f["width"]
    raise KeyError("%s.%s not in the pinned db" % (mnemonic, field))


def _bits(raw, start, width):
    return (int.from_bytes(raw, "little") >> start) & ((1 << width) - 1)


def find_occurrences(main, mnemonic, step=1):
    """Every offset whose bytes satisfy EVERY `match` constraint of `mnemonic`.

    `step` is 1 (byte granularity) rather than the 2-byte parcel, deliberately:
    a hit that is not parcel-aligned is evidence the descriptor's signature is
    ambiguous, and it is recorded rather than filtered away.
    """
    d = DESC[mnemonic]
    L = d["length"]
    out = []
    for off in range(0, len(main) - L + 1, step):
        raw = bytes(main[off:off + L])
        if all(_bits(raw, s, w) == v for (s, w, v) in d["match"]):
            out.append({"off": off, "len": L, "bytes": raw.hex(),
                        "parcel_aligned": (off % DB.get("parcel_bytes", 2)) == 0})
    return out


def token_at(main, off):
    """What the PINNED tokenizer says the bytes at `off` are. Never a build
    error: a mutated instruction is often deliberately undecodable by OUR
    disassembler, and the hardware is the authority on what the bytes mean."""
    try:
        rec, length = isadb.decode_one(bytes(main), off)
        return {"mnemonic": rec["mnemonic"], "op": rec.get("op_mnemonic"),
                "length": length}
    except Exception as e:                                      # noqa: BLE001
        return {"mnemonic": None, "op": None, "length": None,
                "error": str(e)[:120]}


def compile_carrier(bin_dir, metal_path, func, out_dir):
    """shdump our own MSL -> (archive path, `_agc.main` offset, main bytes)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    arch = out_dir / ("carrier_%s.bin" % func)
    subprocess.run([str(Path(bin_dir) / "shdump"), "-o", str(arch),
                    "--no-fast-math", "-f", func, str(metal_path)],
                   check=True, capture_output=True, timeout=600)
    agxparse = str(PINNED / "agxparse.py")
    off = int(subprocess.check_output(
        [sys.executable, "-B", agxparse, str(arch), "--locate", "_agc.main"],
        text=True, timeout=180).split()[0])
    hexstr = subprocess.check_output(
        [sys.executable, "-B", agxparse, str(arch), "--extract-hex"],
        text=True, timeout=180).strip()
    return str(arch), off, bytes.fromhex(hexstr)


def walk_offsets(main):
    """Tokenize `main` from offset 0 and return {offset: (mnemonic, length)}
    for every TRUE instruction boundary, plus how far the walk got.

    A signature scan alone is not enough. It runs at BYTE granularity on purpose
    (a non-parcel-aligned hit is evidence the descriptor's signature is
    ambiguous, and is recorded rather than filtered away) -- but that means it
    also reports offsets INSIDE another instruction. `f3_two` produced exactly
    that: an `09 80 0a 29 91 35 05 80` at offset 79, three bytes into a real
    6-byte `falu2_uni` at 76, which `decode_one` happily confirms as `falu3`.
    Splicing there would corrupt two real instructions and any resulting
    "movement" would be about neither field.

    So an occurrence is admitted as an ARM only if the walk lands on it. The
    walk's reach is returned too: if it stops short, the caller must say so
    rather than silently treating a signature hit as a boundary.
    """
    out, off, n = {}, 0, len(main)
    while off < n:
        try:
            rec, length = isadb.decode_one(bytes(main), off)
        except Exception:                                       # noqa: BLE001
            return out, off, False
        if not length:
            return out, off, False
        out[off] = (rec["mnemonic"], length)
        off += length
    return out, off, True
