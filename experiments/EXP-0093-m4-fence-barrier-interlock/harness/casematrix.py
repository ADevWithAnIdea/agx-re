"""EXP-0093 frozen case matrix. Imported by run.py (executor) and verify.py
(selftest/seqtest). Building the matrix does NOT touch the device or the
filesystem beyond reading this repo's own kernels/ directory listing is NOT
required either -- it is pure data construction, safe to call in any tree
state (selftest requirement).
"""

KERNELS_ROG_TEX_STRONG = "kernels/litmus_rog_tex.metal"
KERNELS_ROG_TEX_WEAK = "kernels/litmus_rog_tex_none.metal"
KERNELS_ROG_BUF_STRONG = "kernels/litmus_rog_buf.metal"
KERNELS_ROG_BUF_WEAK = "kernels/litmus_rog_buf_none.metal"

# ROG index sweep -- generated kernel bodies are produced by run.py from this
# template list (finite-resource mandate: exact range incl. holes/first-alias).
ROG_INDEX_SWEEP = [0, 1, 2, 3, 4, 5, 6, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 255, 256, 65535]

STRUCTURAL_COMPUTE = [
    ("c_barrier_mem_none", "kernels/c_barrier_mem_none.metal", "compute", "k_main"),
    ("c_barrier_mem_device", "kernels/c_barrier_mem_device.metal", "compute", "k_main"),
    ("c_barrier_mem_texture", "kernels/c_barrier_mem_texture.metal", "compute", "k_main"),
    ("c_fence_device_seqcst", "kernels/c_fence_device_seqcst.metal", "compute", "k_main"),
]

STRUCTURAL_FRAGMENT = [
    ("census_rog_tex0", "kernels/census_rog_tex0.metal"),
    ("census_rog_none", "kernels/census_rog_none.metal"),
    ("census_rog_buf0", "kernels/census_rog_buf0.metal"),
    ("census_rog_buf_none", "kernels/census_rog_buf_none.metal"),
]

# --- Family E: compute device-fence message-passing pairs (ATOM-07/ATOM-08) --
DEVFENCE_VARIANTS = ["RR", "FR", "RF", "FF"]
DEVFENCE_PAIRS_SWEEP = [1, 4, 8]
DEVFENCE_ITERATIONS = 50
DEVFENCE_SPIN_BOUND = 500000
DEVFENCE_REPEATS = 2

# --- Family F: barrier convergence (ATOM-09/ATOM-10) -------------------------
# (name, source, prefill_scratch_sentinel, splice_offset_or_None, splice_hex,
#  expect_converge) -- expect_converge is the frozen build-time-probed
# hypothesis: True = 0/256 stale sentinel reads, False = 128/256.
TGDIV_CASES = [
    ("tgdiv_baseline",        "kernels/tgdiv2_baseline.metal",      False, None, None, True),
    ("tgdiv_baseline_none",   "kernels/tgdiv2_baseline_none.metal", False, None, None, False),
    ("tgdiv_mem_none",        "kernels/tgdiv2_mem_none.metal",      False, None, None, True),
    ("tgdiv_dev",             "kernels/tgdiv2_dev.metal",           True,  None, None, True),
    ("tgdiv_dev_none",        "kernels/tgdiv2_dev_none.metal",      True,  None, None, False),
    ("tgdiv_dev_splice_off",  "kernels/tgdiv2_dev.metal",           True,  133, "84", False),
    ("tgdiv_fenceonly",       "kernels/tgdiv2_dev_fenceonly.metal", True,  None, None, False),
    ("tgdiv_fenceonly_splice_on", "kernels/tgdiv2_dev_fenceonly.metal", True, 133, "85", True),
]
TGDIV_REPEATS = 2

ROG_N_SWEEP = [64, 4096, 65536]
ROG_REPEATS = 3

ROG_SPLICE_N_SWEEP = [4096, 65536]
ROG_SPLICE_REPEATS = 2
# (splice_name, splice_offsets, expect_exact) -- offsets relative to fragment
# _agc.main region start, all zero the target byte (neutering splice per
# EXP-0025 precedent: zeroing byte+3 empirically neutralizes a 0x07-family
# fence). expect_exact encodes the pre-registered hypothesis: True = this
# splice is predicted to LEAVE the interlock intact (final == N), False =
# predicted to BREAK it (final < N). Both directions are frozen BEFORE the
# official capture runs from the build-time interactive probing recorded in
# PRE_REGISTRATION.md "Build-time findings".
ROG_TEX_SPLICES = [
    ("identity", [], True),
    ("acq_only", [189], False),
    ("rel_only", [195], False),
    ("both", [189, 195], False),
]
ROG_BUF_SPLICES = [
    ("identity", [], True),
    ("fence_scope_only", [169], True),    # build-time probe: does NOT break
    ("brackets_only", [25, 149], False),  # build-time probe: DOES break
    ("all", [25, 149, 169, 170], False),
]


def build_matrix():
    cases = []

    def add(cid, family, kind, params):
        cases.append({"id": cid, "family": family, "kind": kind, "params": params})

    # Family A: fragment ROG texture RMW-count.
    for src, tag in [(KERNELS_ROG_TEX_STRONG, "strong"), (KERNELS_ROG_TEX_WEAK, "weak")]:
        for n in ROG_N_SWEEP:
            for r in range(ROG_REPEATS):
                add(f"rogtex_{tag}_n{n}_r{r}", "rog_tex", "rog_gpu",
                    {"source": src, "mode": "tex", "instances": n, "repeat": r, "tag": tag})

    # Family B: fragment ROG buffer RMW-count.
    for src, tag in [(KERNELS_ROG_BUF_STRONG, "strong"), (KERNELS_ROG_BUF_WEAK, "weak")]:
        for n in ROG_N_SWEEP:
            for r in range(ROG_REPEATS):
                add(f"rogbuf_{tag}_n{n}_r{r}", "rog_buf", "rog_gpu",
                    {"source": src, "mode": "buf", "instances": n, "repeat": r, "tag": tag})

    # Family C: texture splice controls.
    for sname, offs, expect_exact in ROG_TEX_SPLICES:
        for n in ROG_SPLICE_N_SWEEP:
            for r in range(ROG_SPLICE_REPEATS):
                add(f"rogtex_splice_{sname}_n{n}_r{r}", "rog_tex_splice", "rog_splice_gpu",
                    {"source": KERNELS_ROG_TEX_STRONG, "mode": "tex", "instances": n,
                     "splice_name": sname, "splice_offsets": offs, "expect_exact": expect_exact,
                     "repeat": r})

    # Family D: buffer splice controls.
    for sname, offs, expect_exact in ROG_BUF_SPLICES:
        for n in [4096]:
            for r in range(ROG_SPLICE_REPEATS):
                add(f"rogbuf_splice_{sname}_n{n}_r{r}", "rog_buf_splice", "rog_splice_gpu",
                    {"source": KERNELS_ROG_BUF_STRONG, "mode": "buf", "instances": n,
                     "splice_name": sname, "splice_offsets": offs, "expect_exact": expect_exact,
                     "repeat": r})

    # Family E: compute device-fence pairs. expect_race encodes the frozen
    # hypothesis from build-time probing: FF never races; RR/FR/RF at pairs==1
    # are too small-scale to expose cross-core reordering (matches EXP-0051);
    # RR/FR/RF at pairs>=4 are predicted to show a genuine violation.
    for variant in DEVFENCE_VARIANTS:
        for pairs in DEVFENCE_PAIRS_SWEEP:
            if variant == "FF":
                expect_race = False
            else:
                expect_race = pairs >= 4
            for r in range(DEVFENCE_REPEATS):
                add(f"devfence_{variant}_p{pairs}_r{r}", "devfence_pairs", "devfence_gpu",
                    {"function": f"msg_pairs_{variant}", "pairs": pairs,
                     "iterations": DEVFENCE_ITERATIONS, "spin_bound": DEVFENCE_SPIN_BOUND,
                     "variant": variant, "expect_race": expect_race, "repeat": r})

    # Family F: barrier convergence (plain + spliced).
    for name, src, prefill, off, hexval, expect_converge in TGDIV_CASES:
        for r in range(TGDIV_REPEATS):
            add(f"{name}_r{r}", "tgdiv", "tgdiv_gpu",
                {"source": src, "prefill_scratch": prefill,
                 "splice_offset": off, "splice_hex": hexval,
                 "expect_converge": expect_converge, "repeat": r})

    # Family G: structural census (own-compile only, no GPU dispatch).
    for idx in ROG_INDEX_SWEEP:
        add(f"structural_rogidx_{idx}", "structural", "structural_compile",
            {"kind": "rog_index", "index": idx})
    for cid, src, stage, fn in STRUCTURAL_COMPUTE:
        add(f"structural_{cid}", "structural", "structural_compile",
            {"kind": "compute", "source": src, "stage": stage, "function": fn})
    for cid, src in STRUCTURAL_FRAGMENT:
        add(f"structural_{cid}", "structural", "structural_compile",
            {"kind": "fragment", "source": src})

    return cases


MATRIX = build_matrix()
TOTAL = len(MATRIX)
IDS = [c["id"] for c in MATRIX]


def tgdiv_expected_output():
    """The exact LCG recurrence tgdiv2's kernels compute, independent of the
    GPU: a[gid]=1 for all 256 lanes; lane `lid` iterates
    d = d*1664525+1013904223 (mod 2**32) `(lid+1)*32` times; out[lid] =
    the OTHER lane's (255-lid) final d, so out[lid] uses iters=(256-lid)*32.
    Pure arithmetic -- safe to call with no device/filesystem access."""
    def lcg_iterate(d, n):
        for _ in range(n):
            d = (d * 1664525 + 1013904223) & 0xFFFFFFFF
        return d
    return [lcg_iterate(1, (256 - lid) * 32) for lid in range(256)]


def case_order_sensitive_keys(case):
    """Gated-record 'observed' sub-keys allowed to differ between the two
    capture runs WITHOUT failing the cross-run byte-identity gate, because
    they record concurrently-scheduled race detail (class (d)): the exact
    lost-update count under a genuine, expected race is a legitimate
    scheduling-order artifact, not evidence of a semantic difference. The
    coarse verdict (did the invariant hold: exact-N / mismatch-free) always
    stays in the strict gate for every case, including these.
    """
    fam = case["family"]
    if fam == "rog_tex" and case["params"]["tag"] == "weak":
        return {"final_hex"}
    if fam == "rog_buf" and case["params"]["tag"] == "weak":
        return {"final_hex"}
    if fam in ("rog_tex_splice", "rog_buf_splice") and case["params"]["splice_name"] != "identity":
        return {"final_hex"}
    if fam == "devfence_pairs":
        # mismatch/timeout/completed COUNTS are race-scheduling-order detail;
        # only the coarse pass/fail verdict (mismatch_gt_zero) is gated.
        return {"mismatch", "producer_timeouts", "consumer_timeouts", "completed"}
    return set()
