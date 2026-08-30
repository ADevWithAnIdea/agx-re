#!/usr/bin/env python3
"""EXP-0184 instruction location by DESCRIPTOR SIGNATURE, from the PINNED db.

Why signature scanning and not a tokenizer walk. Two of the four target
instructions live in intersection_query programs that EXP-0157 measured as NOT
tokenizing end-to-end (a 25 kB `_agc.main` with resync gaps). A resync walk
would make every occurrence offset depend on the DB's length rules for every
preceding byte -- and EXP-0182 is changing those length rules right now. A
signature scan depends only on the `match` constraints of the ONE descriptor
under test, read from THIS experiment's pinned `db.json`, so the located bytes
are the same whatever a sibling experiment does to the tokenizer.

Every hit is then CROSS-CHECKED by asking the pinned `decode_one` what the bytes
at that offset decode to, and the tokenized mnemonic is recorded on every case.
FIELD-SWEEP-PROTOCOL / dispatch, 2026-08-30: *two fields were withdrawn after
their "movement" turned out to be the sweep encoding a DIFFERENT instruction.*

HARD EXIT if the pinned db.json / isadb.py are absent: EXP-0182 owns
`tools/agx-isa/isadb.py` and EXP-0183 owns `tools/agx-isa/db.json`, both are
being edited concurrently, and this experiment must never resolve through them.

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
                 Path.home() / "agxre" / "EXP-0184" / "pinned"):
        if (cand / "isadb.py").exists() and (cand / "db.json").exists():
            return cand
    sys.stderr.write(
        "FATAL: EXP-0184 pinned isadb.py/db.json not found. This experiment "
        "must NOT resolve through tools/agx-isa (EXP-0182 owns isadb.py, "
        "EXP-0183 owns db.json, both are editing).\n")
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
