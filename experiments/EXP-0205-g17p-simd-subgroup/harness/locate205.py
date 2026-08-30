#!/usr/bin/env python3
"""EXP-0205 instruction location by DESCRIPTOR SIGNATURE, from the PINNED db.

Signature scan rather than a tokenizer walk, for the reason EXP-0184 gave: a
resync walk makes every occurrence offset depend on the DB's length rules for
every preceding byte, and sibling experiments edit those rules.  A signature
scan depends only on the `match` constraints of the ONE descriptor under test,
read from THIS experiment's pinned `db.json`.

Every hit is cross-checked by asking the pinned `decode_one` what the bytes at
that offset are, and the tokenized mnemonic of the MUTATED bytes is recorded on
every case -- two fields were withdrawn elsewhere on 2026-08-30 after their
"movement" turned out to be the sweep encoding a DIFFERENT instruction.

HARD EXIT if the pinned db.json / isadb.py are absent: this experiment must
never resolve through `tools/agx-isa`, which other experiments edit.

CLEAN-ROOM: OWN-SHADER.  Only our own compiled MSL is scanned.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def pinned_dir():
    for cand in (EXP / "pinned",
                 Path.home() / "agxre" / "EXP-0205" / "pinned"):
        if (cand / "isadb.py").exists() and (cand / "db.json").exists():
            return cand
    sys.stderr.write("FATAL: EXP-0205 pinned isadb.py/db.json not found.\n")
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
    for f in DESC[mnemonic]["fields"]:
        if f["name"] == field:
            return f["start"], f["width"]
    raise KeyError("%s.%s not in the pinned db" % (mnemonic, field))


def get_bits(raw, start, width):
    return (int.from_bytes(raw, "little") >> start) & ((1 << width) - 1)


def patch_instr(raw, start, width, value):
    """Replace bits [start, start+width) of ONE instruction, little-endian over
    its own byte string -- the same convention isadb uses to decode.  Bytes are
    patched DIRECTLY; the assembler is never used, so the OR-only assemble()
    defect (which cannot clear a bit and silently aliases distinct field values
    onto identical bytes) cannot reach this experiment."""
    v = int.from_bytes(raw, "little")
    mask = ((1 << width) - 1) << start
    v = (v & ~mask) | ((value & ((1 << width) - 1)) << start)
    return v.to_bytes(len(raw), "little")


def find_occurrences(main, mnemonic, step=1):
    """Every offset satisfying EVERY `match` constraint of `mnemonic`.

    step=1 (byte granularity) deliberately: a non-parcel-aligned hit is evidence
    the signature is ambiguous and is RECORDED rather than filtered away."""
    d = DESC[mnemonic]
    L = d["length"]
    out = []
    for off in range(0, len(main) - L + 1, step):
        raw = bytes(main[off:off + L])
        if all(get_bits(raw, s, w) == v for (s, w, v) in d["match"]):
            out.append({"off": off, "len": L, "bytes": raw.hex(),
                        "parcel_aligned": (off % DB.get("parcel_bytes", 2)) == 0})
    return out


def token_at(main, off):
    """What the PINNED tokenizer says the bytes at `off` are.  Never fatal: a
    mutated instruction is often deliberately undecodable by OUR disassembler,
    and the hardware -- not our tokenizer -- is the authority on what bytes
    mean.  (A prior gate counted our own disassembler failing to decode as
    hardware movement; recording the token is how that stays visible.)"""
    try:
        rec, length = isadb.decode_one(bytes(main), off)
        return {"mnemonic": rec["mnemonic"], "op": rec.get("op_mnemonic"),
                "length": length}
    except Exception as e:                                      # noqa: BLE001
        return {"mnemonic": None, "op": None, "length": None,
                "error": str(e)[:120]}


def compile_carrier(bin_dir, metal_path, func, out_dir):
    """shdump our own MSL -> (archive path, `_agc.main` file offset, main bytes)."""
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
