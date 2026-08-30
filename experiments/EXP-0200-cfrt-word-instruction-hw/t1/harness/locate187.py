#!/usr/bin/env python3
"""EXP-0187 instruction location by DESCRIPTOR SIGNATURE + a tokenizer walk,
both from the PINNED db.

Why BOTH, and why they are reported separately.

* A **signature scan** (every offset whose bytes satisfy every `match`
  constraint of one descriptor) depends only on that one descriptor, so the
  located bytes do not move when a sibling experiment changes a length rule
  elsewhere. It is an UPPER BOUND: a hit may be another op's operand tail.
* A **tokenizer walk** from offset 0 answers the question the target-2 census
  actually asks -- *does the compiler emit this opcode* -- because an opcode
  whose signature only ever appears INTERIOR to a longer token is not emitted in
  any sense an emitter cares about. `cubearray_coord_const` is exactly that case
  on M4 (EXP-0148: 0 firings in 1080 files; its `f0 c0 04` sits inside a 12-byte
  `tex_addr_setup`), so a census that reported only signature hits would report a
  carrier that does not exist.

Every sweep hit is CROSS-CHECKED by asking the pinned `decode_one` what the
bytes at that offset decode to, and the tokenized mnemonic is recorded on every
case: three fields were withdrawn on 2026-08-30 after their "movement" turned
out to be the sweep encoding a DIFFERENT instruction.

HARD EXIT if the pinned db.json / isadb.py are absent. Sibling experiments own
`tools/agx-isa/*`; nothing here may resolve through them.

Derived from EXP-0184 harness/locate184.py (our own code, cited).
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
                 Path.home() / "agxre" / "EXP-0187" / "pinned"):
        if (cand / "isadb.py").exists() and (cand / "db.json").exists():
            return cand
    sys.stderr.write(
        "FATAL: EXP-0187 pinned isadb.py/db.json not found. This experiment "
        "must NOT resolve through tools/agx-isa.\n")
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

    `step` is 1 (byte granularity) deliberately: a hit that is not
    parcel-aligned is evidence the descriptor's signature is ambiguous, and it
    is recorded rather than filtered away."""
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


def walk(main):
    """Tokenize from offset 0 with the pinned tokenizer.

    Returns (offsets_by_mnemonic, n_tokens, leftover_hex). `leftover` non-empty
    means the walk did not reach the end -- reported, never hidden, because a
    walk that stops early can only UNDERCOUNT."""
    recs, leftover = isadb.disassemble(bytes(main))
    off = 0
    by = {}
    n = 0
    for r in recs:
        L = r.get("length")
        if L is None:
            break
        by.setdefault(r["mnemonic"], []).append(off)
        off += L
        n += 1
    return by, n, leftover.hex()[:200]


def compile_carrier(bin_dir, metal_path, func, out_dir, tool="shdump",
                    extra=(), stage=None):
    """shdump our own MSL -> (archive path, `_agc.main` offset, main bytes).

    `tool`/`stage` select the MESH pipeline path (pinned/shdump_mesh.m +
    pinned/mesh_extract.py, EXP-0135's own tools) for mesh-stage carriers: the
    compute path cannot see that stage at all, which is why every previous
    `mesh_out_src` census read 0 occurrences."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    arch = out_dir / ("carrier_%s.bin" % func)
    if tool == "shdump":
        cmd = [str(Path(bin_dir) / "shdump"), "-o", str(arch),
               "--no-fast-math", "-f", func, str(metal_path)]
        parser = str(PINNED / "agxparse.py")
        pargs = []
    else:
        cmd = [str(Path(bin_dir) / "shdump_mesh"), "-o", str(arch)] + list(extra) \
            + [str(metal_path)]
        parser = str(PINNED / "mesh_extract.py")
        pargs = ["--stage", stage or "mesh"]
    subprocess.run(cmd, check=True, capture_output=True, timeout=600)
    off = int(subprocess.check_output(
        [sys.executable, "-B", parser, str(arch)] + pargs + ["--locate", "_agc.main"],
        text=True, timeout=180).split()[0])
    hexstr = subprocess.check_output(
        [sys.executable, "-B", parser, str(arch)] + pargs + ["--extract-hex"],
        text=True, timeout=180).strip()
    return str(arch), off, bytes.fromhex(hexstr)
