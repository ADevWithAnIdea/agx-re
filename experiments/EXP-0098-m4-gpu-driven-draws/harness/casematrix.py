"""EXP-0098 frozen case matrix. Imported by run.py (executor) and verify.py
(selftest/seqtest). Building the matrix does NOT touch the device or the
filesystem -- pure data construction, safe to call in any tree state
(selftest requirement).

Calibration (build-time, recorded in PRE_REGISTRATION.md "Build-time
findings"): h_sync uses n=65536 vertices with a spinIters=100000 per-thread
sequential-dependency busy-loop in the producer kernel -- this combination
reliably (a) leaves encoder_order/fence_sym/cpu_baseline at 0 stale reads
across repeated trials, and (b) reliably exposes genuine data staleness in
unsync_split/asym_producer/asym_consumer, while completing in well under 1s
per case. xfb_sync uses numPrimitives=4096 with spinIters=500000 (heavier
per-primitive kernel body: atomics + a 16-byte byte-copy loop) -- this
combination did NOT reproduce h_sync's data-staleness signature in any
build-time trial, but DID reproduce a large (~15.5s), highly consistent
completion-latency penalty specific to the two-command-buffer sync variants
(unsync_split/asym_producer/asym_consumer) that encoder_order/fence_sym never
show -- recorded as its own first-class (negative-for-corruption,
positive-for-latency-penalty) finding, not assumed to generalize from h_sync.
"""

# ---------------------------------------------------------------------------
# Family: h_sync
H_SYNC_N = 65536
H_SYNC_SPIN = 100000
H_SYNC_SAFE_MODES = ["cpu_baseline", "encoder_order", "fence_sym"]
H_SYNC_UNSAFE_MODES = ["unsync_split", "asym_producer", "asym_consumer"]
H_SYNC_SAFE_REPEATS = 2
H_SYNC_UNSAFE_REPEATS = 4

# ---------------------------------------------------------------------------
# Family: h_fields -- baseline + single-variable perturbations (change-one-
# variable-at-a-time from CODEX 3, not a full cross product).
# (id, indexed, cap, vc, ic, vs, bi, bv, idxbits, idxbase, restartAt, ioff)
NO_RESTART = 0xFFFFFFFF
H_FIELDS_CASES = [
    ("baseline_nonindexed",       0, 32, 8, 1, 0, 0,  0, 32, 0, NO_RESTART, 0),
    ("vc_zero",                   0, 32, 0, 1, 0, 0,  0, 32, 0, NO_RESTART, 0),
    ("vc_one",                    0, 32, 1, 1, 0, 0,  0, 32, 0, NO_RESTART, 0),
    ("vc_full_capacity",          0, 32, 32, 1, 0, 0, 0, 32, 0, NO_RESTART, 0),
    ("ic_zero",                   0, 32, 8, 0, 0, 0,  0, 32, 0, NO_RESTART, 0),
    ("ic_four",                   0, 32, 8, 4, 0, 0,  0, 32, 0, NO_RESTART, 0),
    ("baseinstance5_ic3",         0, 32, 8, 3, 0, 5,  0, 32, 0, NO_RESTART, 0),
    ("vertexstart10",             0, 32, 8, 1, 10, 0, 0, 32, 0, NO_RESTART, 0),
    ("indirect_offset_misaligned",0, 32, 8, 1, 0, 0,  0, 32, 0, NO_RESTART, 2),
    ("indexed_baseline32",        1, 32, 8, 1, 0, 0,  0, 32, 0, NO_RESTART, 0),
    ("indexed_restart_sentinel",  1, 32, 8, 1, 0, 0,  0, 32, 0, 4,          0),
    ("indexed_16bit",             1, 32, 8, 1, 0, 0,  0, 16, 0, NO_RESTART, 0),
    ("indexed_negative_basevertex",1,32, 8, 1, 0, 0, -3, 32, 3, NO_RESTART, 0),
    ("indexed_vc_zero",           1, 32, 0, 1, 0, 0,  0, 32, 0, NO_RESTART, 0),
    ("indexed_ic_four",           1, 32, 8, 4, 0, 0,  0, 32, 0, NO_RESTART, 0),
    ("indexed_offset_misaligned", 1, 32, 8, 1, 0, 0,  0, 32, 0, NO_RESTART, 2),
]

# ---------------------------------------------------------------------------
# Family: h_icbrange -- fixed maxCount=8 ICB; the {location,length} record is
# written by producer_icbrange (a compute kernel), consumed by
# executeCommandsInBuffer:indirectBuffer:indirectBufferOffset:.
H_ICBRANGE_MAXCOUNT = 8
# (id, wloc, wlen)
H_ICBRANGE_CASES = [
    ("len_zero",        0, 0),
    ("full",             0, 8),
    ("prefix",           0, 4),
    ("suffix",            4, 4),
    ("middle",            2, 4),
    ("oversized_length",  0, 20),
    ("loc_at_max_len0",   8, 0),
    ("loc_at_max_len1",   8, 1),
    ("loc_past_max",     10, 3),
]
# Build-time finding: a range whose `location` is STRICTLY GREATER than
# maxCommandCount (not merely equal to it -- "loc_at_max_len1" above is safe
# and executes 0 commands) causes a real GPU-side command-buffer fault
# (kIOGPUCommandBufferCallbackErrorPageFault), reproduced twice, both
# fault-contained (command-buffer-level only; host/GPU confirmed responsive
# immediately after). Recorded as an EXPECTED fault, not an unexplained FAIL.
H_ICBRANGE_EXPECT_FAULT = {"loc_past_max"}

# ---------------------------------------------------------------------------
# Family: h_icbmax -- allocation-only census (no dispatch). 8388608 is a
# build-time-confirmed CPU-side crash boundary (SIGSEGV inside the calling
# process during newIndirectCommandBufferWithDescriptor: itself) -- included
# deliberately as the finite-resource mandate's "first illegal value";
# process-isolated (one case, one process) so a crash there cannot affect any
# other case or the run.py orchestrator.
H_ICBMAX_TRYCOUNTS = [1024, 65536, 1048576, 4194304, 8388608]

# ---------------------------------------------------------------------------
# Family: xfb_capacity -- (id, numprim, maskmode, vppa, vppb, cap0, cap1,
# stride0, stride1, off0, off1, interleave)
XFB_CAP_CASES = [
    ("cap_exact_fit",       64, 1, 3, 0, 192,  0, 16, 16, 0, 0, 0),
    ("cap_one_short",       64, 1, 3, 0, 191,  0, 16, 16, 0, 0, 0),
    ("cap_way_under",       64, 1, 3, 0, 10,   0, 16, 16, 0, 0, 0),
    ("cap_zero",            64, 1, 3, 0, 0,    0, 16, 16, 0, 0, 0),
    ("cap_huge",            64, 1, 3, 0, 1000, 0, 16, 16, 0, 0, 0),
    ("vpp1_cap_exact",      50, 1, 1, 0, 50,   0, 16, 16, 0, 0, 0),
    ("vpp1_cap_one_short",  50, 1, 1, 0, 49,   0, 16, 16, 0, 0, 0),
    ("interleaved_2attr",   20, 2, 3, 0, 100, 100, 32, 32, 0, 16, 1),
    ("misaligned_stride_off",20,1, 3, 0, 100,  0, 17, 16, 3, 0, 0),
]
XFB_CAP_REPEATS = 2

# ---------------------------------------------------------------------------
# Family: xfb_multistream -- (id, numprim, maskmode, vppa, vppb, cap, replay)
XFB_MULTI_CASES = [
    ("all4_active",       32, 0, 3, 0, 200, 0),
    ("alternate_pairs",   32, 2, 3, 0, 200, 0),
    ("gsshaped_replay0",  32, 3, 3, 1, 200, 0),
    ("gsshaped_replay1",  32, 3, 3, 1, 200, 1),
    ("passthrough_vpp1",  32, 1, 1, 0, 200, 0),
]
XFB_MULTI_REPEATS = 2

# ---------------------------------------------------------------------------
# Family: xfb_discard -- (id, discard)
XFB_DISCARD_CASES = [("discard_off", 0), ("discard_on", 1)]
XFB_DISCARD_REPEATS = 2

# ---------------------------------------------------------------------------
# Family: xfb_sync
XFB_SYNC_NUMPRIM = 4096
XFB_SYNC_SPIN = 500000
XFB_SYNC_CAP0 = 20000
XFB_SYNC_SAFE_MODES = ["encoder_order", "fence_sym"]
XFB_SYNC_UNSAFE_MODES = ["unsync_split", "asym_producer", "asym_consumer"]
XFB_SYNC_SAFE_REPEATS = 2
XFB_SYNC_UNSAFE_REPEATS = 3


def build_matrix():
    cases = []

    def add(cid, family, kind, params):
        cases.append({"id": cid, "family": family, "kind": kind, "params": params})

    # h_sync
    for indexed in (0, 1):
        tag = "indexed" if indexed else "nonindexed"
        for mode in H_SYNC_SAFE_MODES:
            for r in range(H_SYNC_SAFE_REPEATS):
                add(f"hsync_{tag}_{mode}_r{r}", "h_sync", "h_sync",
                    {"indexed": indexed, "sync": mode, "n": H_SYNC_N, "spin": H_SYNC_SPIN, "repeat": r})
        for mode in H_SYNC_UNSAFE_MODES:
            for r in range(H_SYNC_UNSAFE_REPEATS):
                add(f"hsync_{tag}_{mode}_r{r}", "h_sync", "h_sync",
                    {"indexed": indexed, "sync": mode, "n": H_SYNC_N, "spin": H_SYNC_SPIN, "repeat": r})

    # h_fields
    for (cid, indexed, cap, vc, ic, vs, bi, bv, idxbits, idxbase, restartAt, ioff) in H_FIELDS_CASES:
        add(f"hfields_{cid}", "h_fields", "h_fields",
            {"indexed": indexed, "cap": cap, "vc": vc, "ic": ic, "vs": vs, "bi": bi, "bv": bv,
             "idxbits": idxbits, "idxbase": idxbase, "restartAt": restartAt, "ioff": ioff})

    # h_icbrange
    for (cid, wloc, wlen) in H_ICBRANGE_CASES:
        add(f"hicbrange_{cid}", "h_icbrange", "h_icbrange",
            {"maxcount": H_ICBRANGE_MAXCOUNT, "wloc": wloc, "wlen": wlen,
             "expect_fault": cid in H_ICBRANGE_EXPECT_FAULT})

    # h_icbmax
    for tc in H_ICBMAX_TRYCOUNTS:
        add(f"hicbmax_{tc}", "h_icbmax", "h_icbmax", {"trycount": tc})

    # xfb_capacity
    for (cid, numprim, maskmode, vppa, vppb, cap0, cap1, stride0, stride1, off0, off1, interleave) in XFB_CAP_CASES:
        for r in range(XFB_CAP_REPEATS):
            add(f"xfbcap_{cid}_r{r}", "xfb_capacity", "xfb_capacity",
                {"numprim": numprim, "maskmode": maskmode, "vppa": vppa, "vppb": vppb,
                 "cap0": cap0, "cap1": cap1, "stride0": stride0, "stride1": stride1,
                 "off0": off0, "off1": off1, "interleave": interleave, "replay": 0, "repeat": r})

    # xfb_multistream
    for (cid, numprim, maskmode, vppa, vppb, cap, replay) in XFB_MULTI_CASES:
        for r in range(XFB_MULTI_REPEATS):
            add(f"xfbmulti_{cid}_r{r}", "xfb_multistream", "xfb_multistream",
                {"numprim": numprim, "maskmode": maskmode, "vppa": vppa, "vppb": vppb,
                 "cap0": cap, "cap1": cap, "replay": replay, "repeat": r})

    # xfb_discard
    for (cid, discard) in XFB_DISCARD_CASES:
        for r in range(XFB_DISCARD_REPEATS):
            add(f"xfbdiscard_{cid}_r{r}", "xfb_discard", "xfb_discard",
                {"numprim": 16, "maskmode": 1, "vppa": 3, "cap0": 100, "discard": discard, "repeat": r})

    # xfb_sync
    for mode in XFB_SYNC_SAFE_MODES:
        for r in range(XFB_SYNC_SAFE_REPEATS):
            add(f"xfbsync_{mode}_r{r}", "xfb_sync", "xfb_sync",
                {"sync": mode, "numprim": XFB_SYNC_NUMPRIM, "spin": XFB_SYNC_SPIN,
                 "cap0": XFB_SYNC_CAP0, "repeat": r})
    for mode in XFB_SYNC_UNSAFE_MODES:
        for r in range(XFB_SYNC_UNSAFE_REPEATS):
            add(f"xfbsync_{mode}_r{r}", "xfb_sync", "xfb_sync",
                {"sync": mode, "numprim": XFB_SYNC_NUMPRIM, "spin": XFB_SYNC_SPIN,
                 "cap0": XFB_SYNC_CAP0, "repeat": r})

    return cases


MATRIX = build_matrix()
TOTAL = len(MATRIX)
IDS = [c["id"] for c in MATRIX]


def case_order_sensitive_keys(case):
    """Gated-record 'observed' sub-keys allowed to differ between the two
    capture runs WITHOUT failing the cross-run byte-identity gate, because
    they record concurrently-scheduled race detail (class (d)): under a
    genuine, expected race the exact corruption magnitude is a legitimate
    scheduling-order artifact, not evidence of a semantic difference. The
    coarse verdict (did the sync contract hold: PASS/FAIL) always stays in
    the strict gate for every case, including these.
    """
    fam = case["family"]
    if fam == "h_sync" and case["params"]["sync"] in ("unsync_split", "asym_producer", "asym_consumer"):
        return {"n_correct", "n_stale", "n_other", "n_z_wrong"}
    if fam == "xfb_sync" and case["params"]["sync"] in ("unsync_split", "asym_producer", "asym_consumer"):
        # gen0/res0/wr0 are pure producer-side atomics, unaffected by the
        # consumer's (racy) read timing, and stay in the strict gate;
        # replay_vertexCount/n_invoked/n_correct/n_stale depend on what the
        # racy consumer actually observed and are excluded.
        return {"replay_vertexCount", "n_invoked", "n_correct", "n_stale"}
    return set()
