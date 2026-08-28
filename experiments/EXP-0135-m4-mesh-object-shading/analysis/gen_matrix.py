#!/usr/bin/env python3
"""EXP-0135 deterministic case matrix.

Produces the FIXED, non-adaptive list of cases both official runs execute, in
the SAME order. The checkpoint ladders below were chosen from build-time
calibration (see PRE_REGISTRATION.md "Build-time findings"): Metal's own
compiler/pipeline-creation error text gave EXACT boundaries for NV (256),
NP (512), and payload bytes (16384) during that pilot, and a bisection during
the same pilot found the AMP_COUNT/indirect-grid silent-zero-output boundary
at exactly 65536. Ladders below bracket each confirmed boundary tightly
(N-1, N, N+1 style) rather than needing a runtime bisector -- keeping both
official runs' case lists identical, static, and simple to gate.

No case here depends on any prior case's outcome (no adaptive bisection at
run time) -- required for the byte-exact cross-run gate.
"""
import copy

SRC_SWEEP = "kernels/mesh_sweep.metal"
SRC_INDIRECT = "kernels/mesh_indirect.metal"
SRC_ICB_GPU = "kernels/mesh_icb_gpu.metal"

NOOBJ = dict(object="__none__", no_object=True, mesh="mesh_main_noobj", fragment="frag_main_noobj")


def case(cid, group, role, params, argv_extra, role_note=""):
    return {"case_id": cid, "group": group, "role": role, "params": params,
            "argv_extra": argv_extra, "role_note": role_note}


def build_matrix():
    cases = []

    # ------------------------------------------------------------------
    # Group R -- re-validation of the A18 (EXP-0030) findings on M4.
    # ------------------------------------------------------------------
    cases.append(case("R-render-baseline", "R", "render",
                       dict(NV=3, NP=1, PAYLOAD_BYTES=16, AMP_COUNT=1),
                       ["--src", SRC_SWEEP, "--define", "NV=3", "--define", "NP=1",
                        "--define", "PAYLOAD_BYTES=16", "--define", "AMP_COUNT=1",
                        "--mode", "direct", "--width", "32", "--height", "32"],
                       "1-triangle object+mesh+fragment pipeline, A18 EXP-0030 shape"))
    cases.append(case("R-render-emit0", "R", "render",
                       dict(NV=3, NP=0, PAYLOAD_BYTES=16, AMP_COUNT=1),
                       ["--src", SRC_SWEEP, "--define", "NV=3", "--define", "NP=0",
                        "--define", "PAYLOAD_BYTES=16", "--define", "AMP_COUNT=1",
                        "--mode", "direct", "--width", "32", "--height", "32"],
                       "primitive_count=0 control, expect COVERED=0"))
    # R-bytes-* and R-datatrace-* are executed by run.py's dedicated static/iotrace
    # path (not mesh_probe argv), but are still recorded as cases in the same
    # ledger for the byte-exact gate -- see run.py's GROUP_R_STATIC/GROUP_R_TRACE.
    for cid, role in [("R-bytes-mesh-baseline", "extract"), ("R-bytes-mesh-emit0", "extract"),
                       ("R-bytes-compute-control", "extract")]:
        cases.append(case(cid, "R", role, {}, [], "static byte extraction, see run.py"))
    for cid in ["R-trace-mesh", "R-trace-draw", "R-trace-compute"]:
        cases.append(case(cid, "R", "iotrace", {}, [], "DATA-TRACE IOKit call histogram, see run.py"))

    # ------------------------------------------------------------------
    # Group B -- object-to-mesh payload size (finite-resource mandate).
    # Ladder brackets the confirmed exact boundary 16384/16385 (PIPELINE_FAIL).
    # ------------------------------------------------------------------
    for pb in [16, 1024, 8192, 16128, 16376, 16383, 16384, 16385, 16400, 20480, 65536]:
        cases.append(case(f"B-payload-{pb}", "B", "payload_size", dict(PAYLOAD_BYTES=pb),
                           ["--src", SRC_SWEEP, "--define", "NV=3", "--define", "NP=1",
                            "--define", f"PAYLOAD_BYTES={pb}", "--define", "AMP_COUNT=1",
                            "--mode", "direct", "--width", "32", "--height", "32"]))
    # payloadMemoryLength explicit override (struct fixed 256B); tests whether
    # Metal validates override>=struct-size (min-adequacy) as well as the max.
    for ov in [-1, 0, 128, 256, 512, 16384, 16385, 1048576]:
        cases.append(case(f"B-override-{ov}", "B", "payload_override", dict(override=ov),
                           ["--src", SRC_SWEEP, "--define", "NV=3", "--define", "NP=1",
                            "--define", "PAYLOAD_BYTES=256", "--define", "AMP_COUNT=1",
                            "--payload-override", str(ov),
                            "--mode", "direct", "--width", "32", "--height", "32"]))

    # ------------------------------------------------------------------
    # Group C -- UVB output sizing: max vertices / max primitives per meshlet.
    # NV ladder brackets confirmed boundary 256/257 (COMPILE_FAIL).
    # NP ladder (NV held at 256, the vertex-addressing ceiling) brackets 512/513.
    # ------------------------------------------------------------------
    for nv in [1, 2, 3, 64, 128, 192, 224, 248, 254, 255, 256, 257, 300, 1024]:
        cases.append(case(f"C-nv-{nv}", "C", "max_vertices", dict(NV=nv),
                           ["--src", SRC_SWEEP, "--define", f"NV={nv}", "--define", "NP=1",
                            "--define", "PAYLOAD_BYTES=16", "--define", "AMP_COUNT=1",
                            "--mode", "direct", "--width", "32", "--height", "32"]))
    for np in [1, 2, 3, 64, 128, 256, 384, 448, 496, 508, 511, 512, 513, 600, 1024]:
        cases.append(case(f"C-np-{np}", "C", "max_primitives", dict(NP=np, NV=256),
                           ["--src", SRC_SWEEP, "--define", "NV=256", "--define", f"NP={np}",
                            "--define", "PAYLOAD_BYTES=16", "--define", "AMP_COUNT=1",
                            "--mode", "direct", "--width", "32", "--height", "32"]))

    # ------------------------------------------------------------------
    # Group D -- allocation ownership + raster linkage: object-stage grid
    # amplification (mesh_grid_properties::set_threadgroups_per_grid), plus
    # iotrace BO-scaling checks (EXP-0120 methodology) at 3 checkpoints.
    # Ladder brackets the confirmed silent-zero-output boundary at 65536.
    # ------------------------------------------------------------------
    for amp in [0, 1, 2, 4, 64, 1000, 65280, 65534, 65535, 65536, 65537, 65600, 1048576]:
        cases.append(case(f"D-amp-{amp}", "D", "grid_amplification", dict(AMP_COUNT=amp),
                           ["--src", SRC_SWEEP, "--define", "NV=3", "--define", "NP=1",
                            "--define", "PAYLOAD_BYTES=16", "--define", f"AMP_COUNT={amp}",
                            "--mode", "direct", "--width", "64", "--height", "64"]))
    for tag, nv, np_, pb, amp in [
        ("small", 3, 1, 16, 1), ("nearmax", 256, 512, 16384, 1), ("highamp", 3, 1, 16, 65535)
    ]:
        cases.append(case(f"D-trace-{tag}", "D", "iotrace_bo_scaling",
                           dict(NV=nv, NP=np_, PAYLOAD_BYTES=pb, AMP_COUNT=amp), [],
                           "DATA-TRACE, see run.py GROUP_D_TRACE"))

    # ------------------------------------------------------------------
    # Group I -- indirect draw + ICB (CPU- and GPU-authored) mesh dispatch.
    # ------------------------------------------------------------------
    for x in [0, 1, 2, 65535, 65536, 1048576, 16777216]:
        cases.append(case(f"I-indirect-x{x}", "I", "indirect_grid", dict(x=x), [
            "--src", SRC_INDIRECT, "--object", NOOBJ["object"], "--no-object",
            "--mesh", NOOBJ["mesh"], "--fragment", NOOBJ["fragment"],
            "--width", "64", "--height", "64", "--mode", "indirect",
            "--indirect-x", str(x), "--indirect-y", "1", "--indirect-z", "1",
            "--indirect-write-offset", "0", "--mesh-tg", "3,1,1",
        ]))
    cases.append(case("I-indirect-misaligned-offset2", "I", "indirect_grid", dict(offset=2), [
        "--src", SRC_INDIRECT, "--object", NOOBJ["object"], "--no-object",
        "--mesh", NOOBJ["mesh"], "--fragment", NOOBJ["fragment"],
        "--width", "64", "--height", "64", "--mode", "indirect",
        "--indirect-x", "1", "--indirect-y", "1", "--indirect-z", "1",
        "--indirect-write-offset", "2", "--indirect-call-offset", "2",
        "--indirect-buffer-bytes", "64", "--mesh-tg", "3,1,1",
    ]))
    cases.append(case("I-indirect-oob-calloffset", "I", "indirect_grid", dict(offset="oob"), [
        "--src", SRC_INDIRECT, "--object", NOOBJ["object"], "--no-object",
        "--mesh", NOOBJ["mesh"], "--fragment", NOOBJ["fragment"],
        "--width", "64", "--height", "64", "--mode", "indirect",
        "--indirect-x", "1", "--indirect-y", "1", "--indirect-z", "1",
        "--indirect-write-offset", "0", "--indirect-call-offset", "4096",
        "--indirect-buffer-bytes", "16", "--mesh-tg", "3,1,1",
    ]))

    def icb_common(mode, icb_max, grid, extra):
        argv = ["--src", SRC_INDIRECT, "--object", NOOBJ["object"], "--no-object",
                "--mesh", NOOBJ["mesh"], "--fragment", NOOBJ["fragment"],
                "--width", "64", "--height", "64", "--mode", mode, "--icb-support", "1",
                "--icb-max", str(icb_max), "--icb-grid", grid, "--mesh-tg", "3,1,1"]
        if mode == "icb_gpu":
            argv += ["--icb-src", SRC_ICB_GPU, "--icb-fn", "icbw_encode_mesh"]
        return argv + extra

    for mode, tag in [("icb_cpu", "cpu"), ("icb_gpu", "gpu")]:
        cases.append(case(f"I-{tag}-baseline", "I", "icb", dict(mode=mode, max=4, grid="1,1,1"),
                           icb_common(mode, 4, "1,1,1", [])))
        cases.append(case(f"I-{tag}-range-baseline", "I", "icb_range",
                           dict(mode=mode, max=8, loc=0, len=8),
                           icb_common(mode, 8, "1,1,1", ["--icb-loc", "0", "--icb-len", "8"])))
        cases.append(case(f"I-{tag}-range-at-max", "I", "icb_range",
                           dict(mode=mode, max=8, loc=8, len=1),
                           icb_common(mode, 8, "1,1,1", ["--icb-loc", "8", "--icb-len", "1"])))
        cases.append(case(f"I-{tag}-range-past-max", "I", "icb_range",
                           dict(mode=mode, max=8, loc=9, len=1),
                           icb_common(mode, 8, "1,1,1", ["--icb-loc", "9", "--icb-len", "1"])))
        cases.append(case(f"I-{tag}-range-oversized-len", "I", "icb_range",
                           dict(mode=mode, max=8, loc=0, len=20),
                           icb_common(mode, 8, "1,1,1", ["--icb-loc", "0", "--icb-len", "20"])))
    for mc in [1024, 65536, 131072, 262144, 524288, 1048576, 2097152, 3145728,
               4194304, 6391319, 6391320, 8388608]:
        cases.append(case(f"I-cpu-maxcount-{mc}", "I", "icb_maxcount", dict(max=mc),
                           icb_common("icb_cpu", mc, "1,1,1", [])))

    return cases


if __name__ == "__main__":
    import json
    import sys
    m = build_matrix()
    print(f"{len(m)} cases", file=sys.stderr)
    print(json.dumps(m, indent=2))
