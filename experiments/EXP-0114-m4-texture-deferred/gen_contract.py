#!/usr/bin/env python3
"""Generates CAPTURE_CONTRACT.json for EXP-0114 from this file's own literal
case tables (RECORDED REALITY: every splice offset/value and every expected
outcome below was derived from an actual pre-registration-phase compile or
compile+dispatch on this M4, recorded in PROGRESS.md and work/precompute/,
not invented). Re-run to regenerate deterministically; the committed
CAPTURE_CONTRACT.json is the frozen, reviewed artifact.
"""
import hashlib, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GIT_REVISION_PINNED = "0cd13aee2b04b6c0f7dc9c6ae2e2c39c7f7c9b0a"  # placeholder; overwritten below from git

def sha(p):
    return hashlib.sha256((HERE / p).read_bytes()).hexdigest()

# ---------------------------------------------------------------- diff family
DIFF_CASES = [
    ("diff_n2",   "kernels/read_n2.metal",   2,   {"bundle_count": 2,  "distinct_nibbles": [0, 8],             "lownibble_all_zero": True, "op4_sequence": [0, 128]}),
    ("diff_n4",   "kernels/read_n4.metal",   4,   {"bundle_count": 4,  "distinct_nibbles": [0, 8],             "lownibble_all_zero": True, "op4_sequence": [0, 128, 0, 128]}),
    ("diff_n8",   "kernels/read_n8.metal",   8,   {"bundle_count": 8,  "distinct_nibbles": [0, 8],             "lownibble_all_zero": True, "op4_sequence": None}),
    ("diff_n16",  "kernels/read_n16.metal",  16,  {"bundle_count": 16, "distinct_nibbles": [0, 8],             "lownibble_all_zero": True, "op4_sequence": None}),
    ("diff_n32",  "kernels/read_n32.metal",  32,  {"bundle_count": 32, "distinct_nibbles": [0, 8],             "lownibble_all_zero": True, "op4_sequence": None}),
    ("diff_n64",  "kernels/read_n64.metal",  64,  {"bundle_count": 32, "distinct_nibbles": [0, 1, 8, 9],       "lownibble_all_zero": True, "op4_sequence": None}),
    ("diff_n127", "kernels/read_n127.metal", 127, {"bundle_count": 84, "distinct_nibbles": [0, 1, 2, 3, 8, 9, 10, 11], "lownibble_all_zero": True, "op4_sequence": None}),
    ("diff_sparse3", "kernels/read_sparse3.metal", 128, {"bundle_count": 3, "distinct_nibbles": [0, 8], "lownibble_all_zero": True, "op4_sequence": [0, 128, 0]}),
]

def diff_cases():
    out = []
    for case, kfile, n, expect in DIFF_CASES:
        out.append({
            "case": case, "family": "diff", "kernel_file": kfile, "n_declared": n,
            "args": {"kernel_file": kfile, "case": case, "n_declared": n},
            "expect": expect,
            "timeout_seconds": 90,
            "rule_note": "own-shader-diff: compile-only census of the AGX texture-read bundle's op+4 byte across N declared/used textures (TEX-15/16 selector-field census)."
        })
    return out

# ---------------------------------------------------------- splice_tex family
TEX_BASELINE = {"baseline_id": "read_n2", "kernel_file": "kernels/read_n2.metal", "function": "kread_n2",
                "tex0_hex": "11111111", "tex1_hex": "22222222"}
B1_OFF, B2_OFF = 20, 34   # rel offsets of bundle1/bundle2 op+4, from PRE_REGISTRATION.md sec exploration
T0, T1_T0, T0_T0, T1 = "11111111", "22222222", "22222222", "33333333"  # not used directly; expect values below

def tex_expect_for_nibble(nib):
    if nib == 0x0:
        return "22222222"  # t0+t0
    if nib == 0x8:
        return "33333333"  # t0+t1 (native)
    return "11111111"      # silent zero: t0+0

def splice_tex_cases():
    out = []
    def mk(case, splices, expect, note):
        out.append({
            "case": case, "family": "splice_tex", **TEX_BASELINE,
            "args": {**TEX_BASELINE, "case": case, "splices": splices,
                     "gpu_timeout_seconds": 15},
            "splices": splices, "expect": {"status": "ok", "out_word_hex": expect},
            "timeout_seconds": 40, "rule_note": note,
        })

    mk("tex_native", [], T1, "positive control / pre-capture smoke case: unmodified baseline, t0.read()+t1.read().")
    mk("tex_flip_b2_to_t0", [{"rel_offset": B2_OFF, "value": 0x00}], T0_T0,
       "reproduces EXP-0016's t1->t0 splice with our own freshly authored kernel: bundle2 op+4 0x80->0x00.")
    mk("tex_flip_b1_to_t1", [{"rel_offset": B1_OFF, "value": 0x80}], "44444444",
       "bidirectional control: bundle1 op+4 0x00->0x80, expect t1+t1.")
    for nib in range(16):
        v = nib << 4
        mk(f"tex_nibble_{nib:x}", [{"rel_offset": B2_OFF, "value": v}], tex_expect_for_nibble(nib),
           f"full upper-nibble construction sweep on bundle2 op+4 (byte={v:#04x}); finite-resource min/max/hole/failure-mode test.")
    for v in (0x00, 0x01, 0x02, 0x04, 0x08, 0x0F):
        mk(f"tex_lownib_slot0_{v:02x}", [{"rel_offset": B2_OFF, "value": v}], T0_T0,
           "low-nibble-invariance construction test on the populated nibble-0 slot (t0).")
    for v in (0x80, 0x81, 0x82, 0x84, 0x88, 0x8F):
        mk(f"tex_lownib_slot1_{v:02x}", [{"rel_offset": B2_OFF, "value": v}], T1,
           "low-nibble-invariance construction test on the populated nibble-8 slot (t1).")
    return out

# --------------------------------------------------------- splice_grad family
GRAD1 = {"baseline_id": "gradpair_A", "kernel_file": "kernels/gradpair_A.metal", "vertex": "vmain", "fragment": "fmain",
         "params": [0.001, 0, 0, 0.001, 10, 0, 0, 10]}
GRAD2 = {"baseline_id": "gradpair2_A", "kernel_file": "kernels/gradpair2_A.metal", "vertex": "vmain", "fragment": "fmain",
         "params": [0.001, 0, 0, 0.001, 10, 0, 0, 10, 0, 0, 0, 0]}
PAIR1_DIFFS = [(33,0xa),(43,0xe),(53,0xc),(63,0x10),(73,0x5),(81,0x6),(89,0x7),(97,0x8),
               (133,0x4),(153,0x2),(163,0x6),(173,0x8),(183,0x1),(191,0x2),(199,0x3),(211,0x4)]

def splice_grad_cases():
    out = []
    def mk(case, base, splices, expect_rg, note):
        out.append({
            "case": case, "family": "splice_grad", **base,
            "args": {**base, "case": case, "splices": splices, "gpu_timeout_seconds": 15},
            "splices": splices, "expect": {"status": "ok", "rg": expect_rg},
            "timeout_seconds": 40, "rule_note": note,
        })

    mk("g1_native", GRAD1, [], "red", "pair1 baseline: gradient2d(gA) with gA tiny -> level0 (red).")
    mk("g1_off33", GRAD1, [{"rel_offset": 33, "value": 0xa}], "green",
       "single-byte causal test: fragment-relative offset 33 alone, A-native->B-native value.")
    mk("g1_off63", GRAD1, [{"rel_offset": 63, "value": 0x10}], "green",
       "single-byte causal test: fragment-relative offset 63 alone.")
    mk("g1_off43_negctrl", GRAD1, [{"rel_offset": 43, "value": 0xe}], "red",
       "negative control: offset 43 alone (one of the 16 differing bytes) does NOT flip the outcome.")
    mk("g1_both_33_63", GRAD1, [{"rel_offset": 33, "value": 0xa}, {"rel_offset": 63, "value": 0x10}], "green",
       "consistency check: both causal offsets together, still green.")
    mk("g1_all16", GRAD1, [{"rel_offset": o, "value": v} for o, v in PAIR1_DIFFS], "green",
       "consistency check: all 16 A/B-differing bytes spliced together should reproduce B-native (green) exactly.")

    mk("g2_native", GRAD2, [], "red", "pair2 baseline (different register assignment: extra filler varying).")
    mk("g2_off33", GRAD2, [{"rel_offset": 33, "value": 0x12}], "green",
       "pair2 single-byte causal test at the SAME relative offset 33 -- tests stability across register assignments.")
    mk("g2_off63", GRAD2, [{"rel_offset": 63, "value": 0x18}], "green",
       "pair2 single-byte causal test at the SAME relative offset 63.")
    mk("g2_off43_negctrl", GRAD2, [{"rel_offset": 43, "value": 0x16}], "red",
       "pair2 negative control at offset 43.")
    return out


def main():
    cases = diff_cases() + splice_tex_cases() + splice_grad_cases()
    ids = [c["case"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case id"

    # README.md / RESULTS.md / PROGRESS.md are deliberately EXCLUDED: they are written/updated
    # AFTER capture (RESULTS.md in particular reports the capture's own outcome) and must not be
    # hash-pinned into capture-time provenance. PRE_REGISTRATION.md IS pinned -- it is frozen
    # before any capture by design. verify.py's static() still requires all three to exist as
    # regular files; it just does not hash-bind them.
    EXCLUDE_FROM_BLOBS = {"README.md", "RESULTS.md", "PROGRESS.md"}
    auth_relpaths = sorted(str(p.relative_to(HERE)) for p in HERE.rglob("*")
                            if p.is_file() and p.name not in ("CAPTURE_CONTRACT.json",)
                            and str(p.relative_to(HERE)) not in EXCLUDE_FROM_BLOBS
                            and p.suffix in (".py", ".metal", ".md", ".m")
                            and "work" not in p.parts and "raw" not in p.parts and "quarantine" not in str(p).lower())
    blob_sha256 = {p: sha(p) for p in auth_relpaths}

    import subprocess
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()

    contract = {
        "schema": 1, "state": "PRE_GPU", "experiment": "EXP-0114-m4-texture-deferred",
        "pinned_git_revision": rev,
        "boundary": "OWN-SHADER + public Mach-O/Metal-fat container parsing (agxparse.py) on our own compiled+spliced AGX bytes; public Metal API dispatch only; no Apple binary inspected",
        "cases": cases,
        "blob_sha256": blob_sha256,
        "capture": {"runs": ["m4-20260828f-run01", "m4-20260828f-run02"],
                    "pre_capture_smoke": {"case": "tex_native", "family": "splice_tex"}},
    }
    (HERE / "CAPTURE_CONTRACT.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    print(f"wrote CAPTURE_CONTRACT.json: {len(cases)} cases, {len(blob_sha256)} authored blobs, revision {rev}")


if __name__ == "__main__":
    main()
