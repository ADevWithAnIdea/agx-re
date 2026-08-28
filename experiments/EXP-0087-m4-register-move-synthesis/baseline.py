#!/usr/bin/env python3
"""EXP-0087 baseline derivation (single source of truth for the probe anchors
and the census artifacts).

Deterministically re-derives, from the frozen kernel sources and the
read-only tools, two things:

  1. `kernels/synth_move.metal` function `k` compiled to `_agc.main`, and the
     exact byte offsets of the two probe instructions the case matrix splices:
       probe_src = the FIRST compact move (offset 0x00; feeds out[0] via the
                   first vector store) -- the src/byte+2/op_desc sweep site.
       probe_dst = the LAST compact move before the first device_store
                   (offset 0x3C; originally feeds out[15] via the fourth
                   vector store) -- the dst-register sweep site (nothing
                   later in program order can overwrite whatever it writes).
  2. `kernels/census.metal`'s four functions compiled and disassembled,
     recorded verbatim (including any leftover/undecoded tail) as the
     compiler-emitted-move census evidence.

Everything is done with OUR OWN tools on OUR OWN compiled MSL: `shdump`
(public-API runtime compile + archive serialization), `agxparse` (our
container parser) and `tools/agx-isa` (our instruction DB codec). No Apple
binary is inspected; the only machine code touched is the compiled form of
our own MSL.

CLI (used by run.py as a receipt-producing subprocess):
  python3 baseline.py --bin-dir DIR --out FILE.json
    compiles synth_move.metal + census.metal with DIR/shdump into DIR,
    derives the anchors and the census, checks the synth_move anchors
    against the frozen expectations below, writes JSON.
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

SYNTH_KERNEL = "kernels/synth_move.metal"
CENSUS_KERNEL = "kernels/census.metal"
CENSUS_FUNCTIONS = ("k_passthrough", "k_swap", "k_loop_phi", "k_call_marshal")

# Frozen anchors (authored-stage derivation on this M4, macOS 26.6.2 / 25G82,
# clang 21, `--no-fast-math`). run.py re-derives at capture time and STOPs if
# any anchor differs: the frozen perturbation matrix is expressed over THESE
# bytes, so a different compiler output must not be silently swept.
FROZEN = {
    "main_len": 124,
    "main_hex": ("cb080108db0a0108eb0c0108fb0e01088b1001089b120108ab140108bb1601084b18"
                 "01085b1a01086b1c01087b1e01080b2001081b2201082b2401083b260108e700541"
                 "800000000170000900000e700541000000000178000900000e70054080000000017"
                 "0001900000e7005400000000001780019000000e000000"),
    "probe_src_offset": 0x00,
    "probe_src_hex": "cb080108",
    "probe_src_fields": {"dst": 12, "usrc": 8},
    "probe_dst_offset": 0x3C,
    "probe_dst_hex": "3b260108",
    "probe_dst_fields": {"dst": 3, "usrc": 0x26},
}


def compile_kernel(bin_dir, src_path, fn, out_path):
    """Compile OUR MSL with OUR shdump. Returns (argv, exit, stderr)."""
    argv = [str(Path(bin_dir) / "shdump"), "-o", str(out_path), "-f", fn,
            "--no-fast-math", str(src_path)]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    return argv, p.returncode, p.stderr


def derive_synth(bin_dir):
    """Derive the synth_move probe anchors from a fresh compile."""
    arch = Path(bin_dir) / "synth_move.bin"
    argv, rc, err = compile_kernel(bin_dir, HERE / SYNTH_KERNEL, "k", arch)
    if rc != 0 or not arch.exists():
        raise SystemExit("baseline: shdump failed for synth_move (exit %d): %s" % (rc, err))
    buf = arch.read_bytes()
    pieces_ok, pieces = agxparse.extract_agx(buf)
    main = pieces.get("_agc.main") if pieces_ok else None
    if main is None:
        raise SystemExit("baseline: no _agc.main for synth_move")
    recs, leftover = isadb.disassemble(main)
    if leftover:
        raise SystemExit("baseline: synth_move main does not tokenize cleanly "
                         "(leftover %s)" % leftover.hex())
    off = 0
    moves = []
    for r in recs:
        if isadb.assemble(r["mnemonic"], r["fields"]) != bytes.fromhex(r["hex"]):
            raise SystemExit("baseline: synth_move round-trip failure at +0x%x" % off)
        if r["mnemonic"] in ("uniform_mov", "reg_move_c0", "reg_move_c1", "reg_move_c9",
                             "reg_move_cb", "reg_move_c2var"):
            moves.append((off, r))
        off += r["length"]
    if len(moves) != 16:
        raise SystemExit("baseline: synth_move expected 16 compact moves, found %d"
                         % len(moves))
    src_off, src_rec = moves[0]
    dst_off, dst_rec = moves[-1]
    return {
        "source": SYNTH_KERNEL,
        "source_sha256": hashlib.sha256((HERE / SYNTH_KERNEL).read_bytes()).hexdigest(),
        "archive_sha256": hashlib.sha256(buf).hexdigest(),
        "main_len": len(main),
        "main_hex": main.hex(),
        "main_sha256": hashlib.sha256(main).hexdigest(),
        "probe_src_offset": src_off,
        "probe_src_hex": src_rec["hex"],
        "probe_src_fields": {"dst": src_rec["fields"]["dst"], "usrc": src_rec["fields"]["usrc"]},
        "probe_dst_offset": dst_off,
        "probe_dst_hex": dst_rec["hex"],
        "probe_dst_fields": {"dst": dst_rec["fields"]["dst"], "usrc": dst_rec["fields"]["usrc"]},
        "all_move_offsets": [o for o, _ in moves],
    }


def derive_census(bin_dir):
    """Compile + disassemble every census.metal function. Tolerant of a
    non-clean tokenization (recorded as `leftover_hex`, not an error): the
    census is descriptive evidence, not a splice target."""
    out = {}
    for fn in CENSUS_FUNCTIONS:
        arch = Path(bin_dir) / ("census_%s.bin" % fn)
        argv, rc, err = compile_kernel(bin_dir, HERE / CENSUS_KERNEL, fn, arch)
        if rc != 0 or not arch.exists():
            raise SystemExit("baseline: shdump failed for %s (exit %d): %s" % (fn, rc, err))
        buf = arch.read_bytes()
        pieces_ok, pieces = agxparse.extract_agx(buf)
        main = pieces.get("_agc.main") if pieces_ok else None
        if main is None:
            raise SystemExit("baseline: no _agc.main for %s" % fn)
        recs, leftover = isadb.disassemble(main)
        instrs = [{"offset": sum(x["length"] for x in recs[:i]), "mnemonic": r["mnemonic"],
                   "hex": r["hex"], "fields": r.get("fields", {})}
                  for i, r in enumerate(recs)]
        out[fn] = {
            "source_sha256": hashlib.sha256((HERE / CENSUS_KERNEL).read_bytes()).hexdigest(),
            "main_len": len(main), "main_hex": main.hex(),
            "main_sha256": hashlib.sha256(main).hexdigest(),
            "clean_tokenize": leftover == b"",
            "leftover_hex": leftover.hex(),
            "instructions": instrs,
        }
    return out


def derive(bin_dir):
    return {"schema": 1, "synth_move": derive_synth(bin_dir), "census": derive_census(bin_dir)}


def check_frozen(d):
    """Compare the synth_move derivation against the frozen anchors."""
    diffs = []
    got = d["synth_move"]
    for f in ("main_len", "main_hex", "probe_src_offset", "probe_src_hex", "probe_src_fields",
              "probe_dst_offset", "probe_dst_hex", "probe_dst_fields"):
        if got[f] != FROZEN[f]:
            diffs.append("synth_move.%s: got %r want %r" % (f, got[f], FROZEN[f]))
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
