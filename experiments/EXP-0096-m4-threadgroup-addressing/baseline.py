#!/usr/bin/env python3
"""EXP-0096 baseline derivation (single source of truth for the probe
anchors), mirroring ../EXP-0082-m4-mem-offset-semantics/baseline.py.

Deterministically re-derives, from the frozen kernel sources and the
read-only tools, the compiled `_agc.main` bytes of all three probe kernels
and the location + decoded fields of each probe instruction:

  * kernels/tga.metal          -> the unique tg_addr_compute instruction.
  * kernels/tg_ld.metal        -> the unique device_load with the threadgroup
                                    space bit set (space & 0x02).
  * kernels/tg_st.metal        -> the unique device_store with the
                                    threadgroup space bit set, occurring AFTER
                                    the first threadgroup_barrier (disambiguates
                                    it from the four compiler-unrolled
                                    zero-fill stores that precede the barrier).

OUR OWN tools only: shdump (public-API runtime compile + archive
serialization), agxparse (our container parser), tools/agx-isa (our
instruction DB codec). No Apple binary is inspected; the only machine code
touched is the compiled form of our own MSL.
"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SHDUMP_TOOLS = REPO / "tools" / "shdump"
ISA_TOOLS = REPO / "tools" / "agx-isa"
sys.path.insert(0, str(SHDUMP_TOOLS))
sys.path.insert(0, str(ISA_TOOLS))
import agxparse          # noqa: E402  (our own parser)
import isadb             # noqa: E402  (our own instruction DB)

KERNELS = {"tga": "kernels/tga.metal", "tg_ld": "kernels/tg_ld.metal",
           "tg_st": "kernels/tg_st.metal"}

# Frozen anchors (authored-stage derivation on this M4, macOS 26.6.2 / 25G82,
# clang toolchain, `--no-fast-math`). run.py re-derives at capture time and
# STOPs if any anchor differs.
FROZEN = {
    "tga": {
        "main_len": 134,
        "probe_main_offset": 0x2e,
        "probe_hex": "1c0200000000",
        "probe_fields": {"b3": 0, "b4": 0, "b5": 0},
    },
    "tg_ld": {
        "main_len": 278,
        "probe_main_offset": 0xca,
        "probe_hex": "6702540210000000440d00c00800",
        "probe_fields": {"space": 2, "addr_mode": 84, "extmode": 2, "base_slot": 16,
                         "index_reg": 0, "access_desc": 0, "reserved7": 0,
                         "ld_format": 4, "dst_lo": 1, "dst_ext9": 13, "idx_off": 0,
                         "ldform_hi11": 48, "elem_size": 8, "reserved13": 0},
    },
    "tg_st": {
        "main_len": 414,
        "probe_main_offset": 0xaa,
        "probe_hex": "e702540e0c000000440300300200",
        "probe_fields": {"space": 2, "addr_mode": 84, "extmode": 14, "base_slot": 12,
                         "index_reg": 0, "access_desc": 0, "reserved7": 0,
                         "st_format": 68, "st_format_ext": 3, "idx_off": 0,
                         "st_desc_hi": 12, "elem_size": 2, "reserved13": 0},
    },
}


def compile_kernel(bin_dir, kernel_key, out_path):
    argv = [str(Path(bin_dir) / "shdump"), "-o", str(out_path), "-f", "k",
            "--no-fast-math", str(HERE / KERNELS[kernel_key])]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    return argv, p.returncode, p.stderr


def locate_probe(key, recs):
    """Kernel-specific structural locator. Returns (offset, record); raises
    SystemExit with a diagnostic if the rule does not match exactly one
    instruction (a STOP, never a silent pick-first)."""
    off = 0
    hits = []
    first_barrier = None
    all_recs = []
    for r in recs:
        all_recs.append((off, r))
        if r["mnemonic"] == "threadgroup_barrier" and first_barrier is None:
            first_barrier = off
        off += r["length"]
    if key == "tga":
        hits = [(o, r) for o, r in all_recs if r["mnemonic"] == "tg_addr_compute"]
    elif key == "tg_ld":
        hits = [(o, r) for o, r in all_recs
                if r["mnemonic"] == "device_load" and (r["fields"].get("space", 0) & 0x02)]
    elif key == "tg_st":
        hits = [(o, r) for o, r in all_recs
                if r["mnemonic"] == "device_store" and (r["fields"].get("space", 0) & 0x02)
                and first_barrier is not None and o > first_barrier]
    else:
        raise SystemExit("baseline: unknown kernel key %s" % key)
    if len(hits) != 1:
        raise SystemExit("baseline: %s probe locator matched %d instructions (want 1): %s"
                         % (key, len(hits), hits))
    return hits[0]


def derive(bin_dir):
    out = {"schema": 1, "kernels": {}}
    for key in ("tga", "tg_ld", "tg_st"):
        arch = Path(bin_dir) / ("%s.bin" % key)
        argv, rc, err = compile_kernel(bin_dir, key, arch)
        if rc != 0 or not arch.exists():
            raise SystemExit("baseline: shdump failed for %s (exit %d): %s" % (key, rc, err))
        buf = arch.read_bytes()
        pieces_ok, pieces = agxparse.extract_agx(buf)
        main = pieces.get("_agc.main") if pieces_ok else None
        if main is None:
            raise SystemExit("baseline: no _agc.main for %s" % key)
        recs, leftover = isadb.disassemble(main)
        if leftover:
            raise SystemExit("baseline: %s main does not tokenize cleanly "
                             "(leftover %s)" % (key, leftover.hex()))
        off = 0
        for r in recs:
            if isadb.assemble(r["mnemonic"], r["fields"]) != bytes.fromhex(r["hex"]):
                raise SystemExit("baseline: %s round-trip failure at +0x%x" % (key, off))
            off += r["length"]
        poff, prec = locate_probe(key, recs)
        out["kernels"][key] = {
            "source": KERNELS[key],
            "source_sha256": hashlib.sha256((HERE / KERNELS[key]).read_bytes()).hexdigest(),
            "archive_sha256": hashlib.sha256(buf).hexdigest(),
            "main_len": len(main),
            "main_hex": main.hex(),
            "main_sha256": hashlib.sha256(main).hexdigest(),
            "probe_main_offset": poff,
            "probe_hex": prec["hex"],
            "probe_fields": prec["fields"],
        }
    return out


def check_frozen(d):
    diffs = []
    for key in ("tga", "tg_ld", "tg_st"):
        got, want = d["kernels"][key], FROZEN[key]
        for f in ("main_len", "probe_main_offset", "probe_hex", "probe_fields"):
            if got[f] != want[f]:
                diffs.append("%s.%s: got %r want %r" % (key, f, got[f], want[f]))
    return diffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    d = derive(a.bin_dir)
    d["frozen_anchor_diffs"] = check_frozen(d)
    txt = json.dumps(d, indent=2, sort_keys=True) + "\n"
    if a.out:
        Path(a.out).write_text(txt)
    sys.stdout.write(txt)
    return 1 if d["frozen_anchor_diffs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
