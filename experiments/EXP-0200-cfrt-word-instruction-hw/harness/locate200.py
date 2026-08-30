#!/usr/bin/env python3
"""EXP-0200 instruction location, compilation and tokenization, from the PINNED
snapshot only.

The pinned snapshot is EXP-0187's, carried into `t1/pinned/` VERBATIM (every
hash re-checked against EXP-0187's own `CAPTURE_CONTRACT.json`), because this
experiment's target 1 is EXP-0187's frozen contract honoured unchanged and both
targets must read the same descriptor set. Sibling experiments own
`tools/agx-isa/*`; nothing here may resolve through them, and it is a HARD EXIT
if the pinned copies are absent.

Derived from EXP-0187 harness/locate187.py (our own code, cited); the changes
are the pinned path, `walk_boundaries()` and `find_runs()`.

CLEAN-ROOM: OWN-SHADER. Only our own compiled MSL is scanned.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def pinned_dir():
    for cand in (EXP / "t1" / "pinned",
                 Path.home() / "agxre" / "EXP-0200" / "t1" / "pinned"):
        if (cand / "isadb.py").exists() and (cand / "db.json").exists():
            return cand
    sys.stderr.write("FATAL: pinned isadb.py/db.json not found under t1/pinned. "
                     "This experiment must NOT resolve through tools/agx-isa.\n")
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
PARCEL = DB.get("parcel_bytes", 2)


def _bits(raw, start, width):
    return (int.from_bytes(raw, "little") >> start) & ((1 << width) - 1)


def descriptor_bytes(mnemonic, overrides=None):
    """Re-derive an instruction's fixed bytes from its own `match` constraints.

    Used by analysis/contract200.py to FAIL LOUD if the hand-written encodings
    in harness/words200.py ever drift from the pinned descriptors, instead of
    trusting a transcribed constant. `overrides` supplies the free bits."""
    d = DESC[mnemonic]
    v = 0
    for (s, w, val) in d["match"]:
        v |= (val & ((1 << w) - 1)) << s
    for (s, w, val) in (overrides or []):
        v &= ~(((1 << w) - 1) << s)
        v |= (val & ((1 << w) - 1)) << s
    return v.to_bytes(d["length"], "little")


def find_occurrences(main, mnemonic, step=1):
    """Every offset whose bytes satisfy EVERY `match` constraint of `mnemonic`.
    Byte granularity deliberately: a non-parcel-aligned hit is evidence the
    signature is ambiguous and is recorded, not filtered away."""
    d = DESC[mnemonic]
    L = d["length"]
    out = []
    for off in range(0, len(main) - L + 1, step):
        raw = bytes(main[off:off + L])
        if all(_bits(raw, s, w) == v for (s, w, v) in d["match"]):
            out.append({"off": off, "len": L, "bytes": raw.hex(),
                        "parcel_aligned": (off % PARCEL) == 0})
    return out


def token_at(main, off):
    """What the PINNED tokenizer says the bytes at `off` are. Never raises: a
    mutated instruction is often deliberately undecodable by OUR disassembler,
    and the hardware, not our tokenizer, is the authority on what bytes mean."""
    try:
        rec, length = isadb.decode_one(bytes(main), off)
        return {"mnemonic": rec["mnemonic"], "op": rec.get("op_mnemonic"),
                "length": length}
    except Exception as e:                                      # noqa: BLE001
        return {"mnemonic": None, "op": None, "length": None,
                "error": str(e)[:120]}


def walk_boundaries(main):
    """Tokenize from offset 0 -> (list of (off, len, mnemonic), leftover_hex).

    A walk that stops early can only UNDERCOUNT, so `leftover` is reported and
    never hidden. Every hole this experiment uses starts and ends on a boundary
    this walk produced, so a hole never straddles an instruction the tokenizer
    could not name."""
    recs, leftover = isadb.disassemble(bytes(main))
    off = 0
    out = []
    for r in recs:
        L = r.get("length")
        if not L:
            break
        out.append((off, L, r["mnemonic"]))
        off += L
    return out, leftover.hex()[:400]


def find_runs(bounds, total_bytes, want_len, lo_frac=0.0, hi_frac=1.0):
    """Runs of consecutive walked instructions whose lengths sum to exactly
    `want_len`. These are the RULER HOLES: overwriting one replaces whole
    instructions, never half of one, so a `stop` planted inside it is at a
    genuine instruction boundary of the ORIGINAL program too."""
    out = []
    for i, (off, _L, _m) in enumerate(bounds):
        if not (lo_frac * total_bytes <= off <= hi_frac * total_bytes):
            continue
        acc, j, mns = 0, i, []
        while j < len(bounds) and acc < want_len:
            acc += bounds[j][1]
            mns.append(bounds[j][2])
            j += 1
        if acc == want_len:
            out.append({"off": off, "len": want_len, "covers": mns,
                        "n_instr": len(mns)})
    return out


def find_occurrence_holes(bounds, want_len, mnemonics):
    """Walked tokens of exactly `want_len` bytes whose mnemonic is in
    `mnemonics` -- the NATURAL holes used by the transparency arm."""
    return [{"off": off, "len": L, "mnemonic": m}
            for (off, L, m) in bounds if L == want_len and m in mnemonics]


def compile_carrier(bin_dir, metal_path, func, out_dir):
    """shdump our own MSL -> (archive path, `_agc.main` offset, main bytes)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    arch = out_dir / ("carrier_%s.bin" % func)
    cmd = [str(Path(bin_dir) / "shdump"), "-o", str(arch),
           "--no-fast-math", "-f", func, str(metal_path)]
    subprocess.run(cmd, check=True, capture_output=True, timeout=600)
    parser = str(PINNED / "agxparse.py")
    off = int(subprocess.check_output(
        [sys.executable, "-B", parser, str(arch), "--locate", "_agc.main"],
        text=True, timeout=180).split()[0])
    hexstr = subprocess.check_output(
        [sys.executable, "-B", parser, str(arch), "--extract-hex"],
        text=True, timeout=180).strip()
    return str(arch), off, bytes.fromhex(hexstr)
