#!/usr/bin/env python3
"""EXP-0084 shared decode library -- ONE authoritative implementation of:
  (1) compile our own MSL to a binary-archive container (tools/shdump,
      read-only, built into this experiment's own work/bin at capture time);
  (2) extract + tokenize the AGX bytes of a named region with tools/agx-isa
      (read-only; imported as a library, not shelled out to, so this script
      gets the SAME structured field values agxisa.py's CLI prints, without
      re-parsing text);
  (3) the FROZEN structural identification algorithm for the splice target
      (pre-registered in PRE_REGISTRATION.md "Splice identification
      algorithm" -- this function IS that algorithm; do not duplicate it).

Imported by analysis/decode_case.py (report-only) AND analysis/splice_case.py
(identification + splice). Never reimplemented in either caller.

Clean-room: every byte inspected here is the compiled form of our own
`kernels/probes.metal`; the decoder is `tools/agx-isa` (our own DB, read
unmodified). No Apple binary is disassembled or introspected.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from procutil import rec  # noqa: E402

AGXPARSE = REPO / "tools" / "shdump" / "agxparse.py"


def build_archive(shdump_bin, source_path, function, out_path, timeout):
    """shdump -o out_path -f function source_path. Returns the receipt."""
    return rec([shdump_bin, "-o", out_path, "-f", function, source_path], timeout, Path(shdump_bin).parent)


def extract_hex(archive_path, symbol, timeout):
    """agxparse.py --extract-hex --symbol NAME --stage compute ARCHIVE.
    Returns (hex_string_or_None, receipt). None (not a raise) means the
    symbol/region is absent from the archive -- a valid, expected outcome
    for `_agc.main.constant_program` when the compiler emitted no preamble."""
    z = rec([sys.executable, "-B", AGXPARSE, archive_path, "--stage", "compute",
             "--symbol", symbol, "--extract-hex"], timeout, AGXPARSE.parent)
    if z["exit"] == 0 and not z["timed_out"] and z["exception"] is None:
        h = z["stdout"].strip()
        return (h if h else None), z
    return None, z


def locate(archive_path, symbol, timeout):
    """agxparse.py --locate SYMBOL ARCHIVE -> (abs_off, length) or (None, receipt)."""
    z = rec([sys.executable, "-B", AGXPARSE, archive_path, "--stage", "compute",
             "--locate", symbol], timeout, AGXPARSE.parent)
    if z["exit"] == 0 and not z["timed_out"] and z["exception"] is None:
        parts = z["stdout"].split()
        if len(parts) == 2:
            return (int(parts[0]), int(parts[1])), z
    return None, z


def tokenize_region(hexstr):
    """Tokenize a hex string with tools/agx-isa's own disassemble(); annotate
    each record with its cumulative byte offset WITHIN this region. Returns
    (records, leftover_hex)."""
    if not hexstr:
        return [], ""
    buf = bytes.fromhex(hexstr)
    recs, leftover = isadb.disassemble(buf)
    out = []
    off = 0
    for r in recs:
        r2 = dict(r)
        r2["offset"] = off
        out.append(r2)
        if r.get("length"):
            off += r["length"]
        else:
            break
    return out, leftover.hex()


def dst_reg(fields):
    return fields.get("dst_lo", 0) | (fields.get("dst_ext9", 0) << 2)


def identify(main_recs, preamble_recs):
    """FROZEN identification algorithm (pre-registered; see
    PRE_REGISTRATION.md 'Splice identification algorithm'). Locates the last
    two `device_load` instructions in the MAIN region (the per-lane, gid-
    dependent dereferences `vA=pA[gid]` / `vB=pB[gid]` in `splice_target` --
    these cannot be hoisted to the preamble because they depend on the
    thread-varying `gid`, unlike the two OUTER pointer-value loads which may
    or may not be hoisted). Returns a dict; `confirmation_ok` is the
    pre-registered refuter check (distinct index_reg values on l1/l2, i.e.
    something to actually swap)."""
    main_dl = [r for r in main_recs if r.get("mnemonic") == "device_load"]
    pre_dl = [r for r in preamble_recs if r.get("mnemonic") == "device_load"]
    result = {"n_device_load_main": len(main_dl), "n_device_load_preamble": len(pre_dl),
              "l1": None, "l2": None, "confirmation_ok": False}
    if len(main_dl) >= 2:
        l1, l2 = main_dl[-2], main_dl[-1]
        for key, r in (("l1", l1), ("l2", l2)):
            f = r["fields"]
            result[key] = {"offset": r["offset"], "hex": r["hex"], "length": r["length"],
                           "base_slot": f.get("base_slot"), "index_reg": f.get("index_reg"),
                           "addr_mode": f.get("addr_mode"), "idx_off": f.get("idx_off"),
                           "dst_reg": dst_reg(f)}
        result["confirmation_ok"] = (result["l1"]["index_reg"] != result["l2"]["index_reg"])
    return result


def full_decode(shdump_bin, source_path, function, work_archive, timeouts):
    """End-to-end: build -> extract main + preamble -> tokenize both ->
    identify. Returns a dict with every intermediate artifact (receipts
    included) for provenance, plus the `identify()` result under `ident`."""
    build = build_archive(shdump_bin, source_path, function, work_archive, timeouts["build"])
    if build["exit"] != 0 or build["timed_out"] or build["exception"] is not None:
        return {"build": build, "main_hex": None, "preamble_hex": None,
                "main_recs": [], "preamble_recs": [], "ident": None}
    main_hex, main_extract = extract_hex(work_archive, "_agc.main", timeouts["extract"])
    pre_hex, pre_extract = extract_hex(work_archive, "_agc.main.constant_program", timeouts["extract"])
    main_recs, main_leftover = tokenize_region(main_hex or "")
    pre_recs, pre_leftover = tokenize_region(pre_hex or "")
    ident = identify(main_recs, pre_recs)
    return {"build": build, "main_extract": main_extract, "preamble_extract": pre_extract,
            "main_hex": main_hex, "preamble_hex": pre_hex,
            "main_leftover": main_leftover, "preamble_leftover": pre_leftover,
            "main_recs": main_recs, "preamble_recs": pre_recs, "ident": ident}
