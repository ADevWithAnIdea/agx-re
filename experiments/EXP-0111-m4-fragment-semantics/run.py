#!/usr/bin/env python3
"""EXP-0111 runner. Executes the full frozen case matrix (FS-01..FS-12 + the two
EXP-0091 anomaly resolutions) and writes gated/non-gated sibling records under
raw/<run_id>/. Pattern follows EXP-0091's run.py.

Three case kinds:
  compile_scan    -- host-side OWN-SHADER compile (tools/shdump) + our own byte-offset
                     scan of the extracted fragment main + a tools/agx-isa tokenize
                     check. No GPU dispatch; fully deterministic given the frozen kernel
                     source.
  compile_attempt -- host-side OWN-SHADER compile attempt only, recording whether it
                     succeeded or the exact rejection (used for the FS-11 negative probe).
  gpu_render       -- one fresh `fsrun` process per case (single-threaded harness: one
                     case, one process, run to completion before the next starts). Hard
                     per-case timeout. A fault/timeout is recorded as a result, never
                     silently dropped.

Usage:
  python3 run.py --run run01 --out raw/m4_<date>_run01
  python3 run.py --run run02 --out raw/m4_<date>_run02
  python3 run.py --list                # print the frozen case matrix and exit (no I/O)
"""
import argparse, json, os, struct, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import schema as S

BIN = HERE / "work" / "bin"
FSRUN = BIN / "fsrun"
SHDUMP = BIN / "shdump"
AGXPARSE = REPO / "tools" / "shdump" / "agxparse.py"
AGXISA = REPO / "tools" / "agx-isa" / "agxisa.py"
ARCH_DIR = HERE / "work" / "archives"
KERNELS = HERE / "kernels"

RUN_TIMEOUT_S = 60
COMPILE_TIMEOUT_S = 120


def sh(cmd, timeout):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(HERE))
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return -9, e.stdout or "", (e.stderr or "") + "\nTIMEOUT", time.time() - t0


def f2hex(x):
    return format(struct.unpack("<I", struct.pack("<f", x))[0], "#010x")


def parse_fsrun_stdout(text):
    pixels = {}
    depth = []
    buffers = {}
    device = None; pipeline_source = None; size = None
    occlusion = None; gputime = None; status = None; error = None
    for line in text.splitlines():
        line = line.rstrip("\n")
        if line.startswith("DEVICE "):
            device = line[len("DEVICE "):]
        elif line.startswith("PIPELINE_SOURCE "):
            pipeline_source = line.split()[1]
        elif line.startswith("GPUTIME_NS "):
            gputime = int(line.split()[1])
        elif line.startswith("SIZE "):
            parts = line.split()
            size = [int(parts[1]), int(parts[2]), int(parts[4])]
        elif line.startswith("PIXEL") and not line.startswith("PIXEL_UNAVAILABLE") and "_UNAVAILABLE" not in line.split()[0]:
            # "PIXEL<rt> x y bgra=.... rgba_unorm=...."
            head, rest = line.split(" ", 1)
            rt = head[len("PIXEL"):]
            parts = rest.split()
            x, y = int(parts[0]), int(parts[1])
            bgra = parts[2].split("=")[1]
            pixels.setdefault(rt, []).append({"x": x, "y": y, "bgra": bgra})
        elif line.startswith("DEPTH "):
            parts = line.split()
            x, y = int(parts[1]), int(parts[2])
            val = float(parts[3].split("=")[1])
            depth.append({"x": x, "y": y, "value": val})
        elif line.startswith("OCCLUSION_COUNT "):
            occlusion = int(line.split()[1])
        elif line.startswith("BUFFER "):
            parts = line.split(" ", 2)
            idx = int(parts[1])
            hexval = parts[2].split("=", 1)[1]
            buffers[str(idx)] = hexval
        elif line.startswith("STATUS "):
            status = line.split()[1]
        elif line.startswith("ERROR "):
            error = line[len("ERROR "):]
    for rt in pixels:
        pixels[rt].sort(key=lambda p: (p["y"], p["x"]))
    depth.sort(key=lambda p: (p["y"], p["x"]))
    return {
        "device": device, "pipeline_source": pipeline_source, "size": size,
        "pixels": pixels, "depth": (depth if depth else None),
        "occlusion": occlusion, "buffers": buffers, "error": error,
    }, status, gputime


def run_gpu_case(case):
    args = [str(FSRUN)] + case["fsrun_args"]
    rc, out, err, wall = sh(args, RUN_TIMEOUT_S)
    if rc == -9:
        result = {"device": None, "pipeline_source": None, "size": None, "pixels": {},
                  "depth": None, "occlusion": None, "buffers": {}, "error": "TIMEOUT"}
        status = "HANG"
        gputime = None
    else:
        result, status, gputime = parse_fsrun_stdout(out)
        if status is None:
            status = "HARNESS_CRASH"
            result["error"] = (result.get("error") or "") + " | stderr=" + err[:500]
    gated = {
        "case_id": case["id"], "group": case["group"], "kind": "gpu_render",
        "params": case["params"], "status": status, "result": result,
    }
    nongated = {"case_id": case["id"], "gputime_ns": gputime, "wall_ms": round(wall * 1000, 3),
                "pid": os.getpid(), "started_at": None}
    return gated, nongated


def compile_and_locate(name, vertex="v_main", fragment="f_main"):
    src = KERNELS / f"{name}.metal"
    arch = ARCH_DIR / f"{name}_{vertex}_{fragment}.bin"
    if not arch.exists():
        rc, out, err, _ = sh([str(SHDUMP), "-o", str(arch), "--render", "--vertex", vertex,
                               "--fragment", fragment, str(src)], COMPILE_TIMEOUT_S)
        if rc != 0:
            raise RuntimeError(f"shdump failed for {name}: {err}")
    rc, out, err, _ = sh(["python3", str(AGXPARSE), str(arch), "--stage", "fragment",
                           "--extract-hex"], COMPILE_TIMEOUT_S)
    if rc != 0:
        raise RuntimeError(f"agxparse extract-hex failed for {name}: {err}")
    rc2, base_out, err2, _ = sh(["python3", str(AGXPARSE), str(arch), "--stage", "fragment",
                                  "--locate", "_agc.main"], COMPILE_TIMEOUT_S)
    base = int(base_out.split()[0]) if rc2 == 0 else None
    return arch, out.strip(), base


def scan_leader6(buf, byte0_set, byte2):
    """Generic scan for a family of 6-byte-leader ops: byte0 in byte0_set, byte+2==byte2.
    Returns list of (offset, 6-byte-hex)."""
    hits = []
    for i in range(len(buf) - 2):
        if buf[i] in byte0_set and buf[i + 2] == byte2:
            hits.append((i, buf[i:i + 6].hex()))
    return hits


def run_scan_case(case):
    name = case["kernel"]
    vertex = case.get("vertex", "v_main")
    fragment = case.get("fragment", "f_main")
    arch, hexstr, base = compile_and_locate(name, vertex, fragment)
    buf = bytes.fromhex(hexstr)
    counts = case["count_fn"](buf)
    rc, out, err, _ = sh(["python3", str(AGXISA), "tokenize", hexstr], COMPILE_TIMEOUT_S)
    clean = "CLEAN:" in out
    leftover = 0
    for line in out.splitlines():
        if line.startswith("LEFTOVER "):
            leftover = int(line.split()[1])
    result = {
        "frag_main_hex": hexstr, "frag_main_len": len(buf),
        "tokenize_clean": clean, "tokenize_leftover": leftover, "counts": counts,
    }
    gated = {"case_id": case["id"], "group": case["group"], "kind": "compile_scan",
             "params": case["params"], "status": "SCANNED", "result": result}
    nongated = {"case_id": case["id"], "gputime_ns": None, "wall_ms": None,
                "pid": os.getpid(), "started_at": None}
    return gated, nongated


def run_attempt_case(case):
    name = case["kernel"]
    vertex = case.get("vertex", "v_main")
    fragment = case.get("fragment", "f_main")
    src = KERNELS / f"{name}.metal"
    arch = ARCH_DIR / f"{name}_attempt_{vertex}_{fragment}.bin"
    rc, out, err, _ = sh([str(SHDUMP), "-o", str(arch), "--render", "--vertex", vertex,
                           "--fragment", fragment, str(src)], COMPILE_TIMEOUT_S)
    compiled = (rc == 0)
    result = {"compiled": compiled, "error_text": (None if compiled else (out + err)[:800])}
    gated = {"case_id": case["id"], "group": case["group"], "kind": "compile_attempt",
             "params": case["params"], "status": ("ACCEPTED" if compiled else "REJECTED"),
             "result": result}
    nongated = {"case_id": case["id"], "gputime_ns": None, "wall_ms": None,
                "pid": os.getpid(), "started_at": None}
    return gated, nongated


# ----------------------------------------------------------------------------
# byte-scan helper functions (count_fn) per compile_scan case
# ----------------------------------------------------------------------------

def count_get_sr_position(buf):
    hits = []
    for i in range(len(buf) - 4):
        if (buf[i] & 0x07) == 0x04 and buf[i + 1] in (0xa0, 0xa1):
            hits.append((i, buf[i + 1]))
    return {"get_sr_0xa0": sum(1 for _, sr in hits if sr == 0xa0),
            "get_sr_0xa1": sum(1 for _, sr in hits if sr == 0xa1),
            "offsets": [o for o, _ in hits]}


def count_deriv_axis(buf):
    hits = []
    for i in range(len(buf) - 2):
        if buf[i] == 0x37 and buf[i + 2] == 0x54:
            hits.append(buf[i + 6])
    return {"total": len(hits), "axis_0x92": hits.count(0x92), "axis_0x90": hits.count(0x90),
            "other": len(hits) - hits.count(0x92) - hits.count(0x90)}


def count_iter_family(buf):
    i = 0; iters = 0; flats = 0
    slots = []
    while i < len(buf) - 2:
        if buf[i] in (0x2f, 0xaf) and buf[i + 2] == 0x54 and i + 10 <= len(buf):
            iters += 1; slots.append(buf[i + 5]); i += 10
        elif buf[i] == 0x1f and buf[i + 2] == 0x54 and i + 6 <= len(buf):
            flats += 1; i += 6
        else:
            i += 1
    return {"iter": iters, "iter_flat": flats, "iter_slots_raw": slots}


def count_frag_color_store(buf):
    hits = []
    for i in range(len(buf) - 5):
        if buf[i] == 0xe7 and buf[i + 1] == 0x06 and buf[i + 2] == 0x54:
            hits.append(buf[i + 5])
    return {"store_count": len(hits), "rt_index_bytes": hits}


# ----------------------------------------------------------------------------
# Frozen case matrix
# ----------------------------------------------------------------------------

def build_cases():
    cases = []

    def add_gpu(cid, group, source, extra, vertex="v_main", fragment="f_main", base=None, archive=None):
        args = ["--source", str(KERNELS / f"{source}.metal"), "--vertex", vertex, "--fragment", fragment]
        if archive:
            args = ["--archive", str(archive), "--source", str(KERNELS / f"{source}.metal"),
                    "--vertex", vertex, "--fragment", fragment]
        args += extra
        cases.append({"id": cid, "group": group,
                      "params": {"source": source, "vertex": vertex, "fragment": fragment, "extra": extra},
                      "fsrun_args": args, "run": run_gpu_case})

    def add_scan(cid, group, kernel, count_fn, vertex="v_main", fragment="f_main"):
        cases.append({"id": cid, "group": group, "kernel": kernel, "vertex": vertex, "fragment": fragment,
                      "params": {"kernel": kernel, "vertex": vertex, "fragment": fragment},
                      "count_fn": count_fn, "run": run_scan_case})

    def add_attempt(cid, group, kernel, vertex="v_main", fragment="f_main"):
        cases.append({"id": cid, "group": group, "kernel": kernel, "vertex": vertex, "fragment": fragment,
                      "params": {"kernel": kernel, "vertex": vertex, "fragment": fragment},
                      "run": run_attempt_case})

    # ============================= poscoord (FS-01/02/03) ===================
    add_scan("poscoord_scan", "poscoord", "poscoord_scan", count_get_sr_position)
    add_gpu("poscoord_grid_w4h3", "poscoord", "poscoord_grid",
            ["--width", "4", "--height", "3", "--buf", "0=96,00", "--buf-u32", "1=4,3"])
    add_gpu("poscoord_yhalf_w4h4", "poscoord", "poscoord_yhalf", ["--width", "4", "--height", "4"])
    add_gpu("poscoord_xhalf_w4h4", "poscoord", "poscoord_xhalf", ["--width", "4", "--height", "4"])
    add_gpu("poscoord_msaa_stability_N2", "poscoord", "poscoord_msaa_stability",
            ["--width", "2", "--height", "2", "--samples", "2", "--buf", "0=64,00", "--buf-u32", "1=2,2,2"])
    add_gpu("poscoord_msaa_stability_N4", "poscoord", "poscoord_msaa_stability",
            ["--width", "2", "--height", "2", "--samples", "4", "--buf", "0=128,00", "--buf-u32", "1=2,2,4"])

    # splice group: compile the corner kernel fresh, locate the two get_sr ops by our own
    # byte scan (not a hardcoded offset), then dispatch baseline/spliced pairs.
    corner_arch, corner_hex, corner_base = compile_and_locate("poscoord_splice_corner")
    corner_buf = bytes.fromhex(corner_hex)
    sr_hits = [(i, corner_buf[i + 1]) for i in range(len(corner_buf) - 4)
               if (corner_buf[i] & 0x07) == 0x04 and corner_buf[i + 1] in (0xa0, 0xa1)]
    assert len(sr_hits) == 2, f"expected exactly 2 get_sr(0xa0/0xa1) in poscoord_splice_corner, found {sr_hits}"
    x_off, x_sr = sr_hits[0]; y_off, y_sr = sr_hits[1]
    assert x_sr == 0xa0 and y_sr == 0xa1, f"unexpected SR order {sr_hits}"
    x_abs = corner_base + x_off + 1  # absolute file offset of the SR-select byte
    y_abs = corner_base + y_off + 1
    common_corner = ["--archive", str(corner_arch), "--source", str(KERNELS / "poscoord_splice_corner.metal"),
                      "--vertex", "v_main", "--fragment", "f_main", "--width", "3", "--height", "2",
                      "--buf", "0=16,00"]
    cases.append({"id": "poscoord_splice_baseline", "group": "poscoord",
                  "params": {"archive_base": corner_base, "x_abs": x_abs, "y_abs": y_abs, "splice": None},
                  "fsrun_args": list(common_corner), "run": run_gpu_case})
    cases.append({"id": "poscoord_splice_x_to_y", "group": "poscoord",
                  "params": {"archive_base": corner_base, "x_abs": x_abs, "y_abs": y_abs, "splice": "x->a1"},
                  "fsrun_args": list(common_corner) + ["--splice", f"{x_abs}=a1"], "run": run_gpu_case})
    cases.append({"id": "poscoord_splice_y_to_x", "group": "poscoord",
                  "params": {"archive_base": corner_base, "x_abs": x_abs, "y_abs": y_abs, "splice": "y->a0"},
                  "fsrun_args": list(common_corner) + ["--splice", f"{y_abs}=a0"], "run": run_gpu_case})

    # ============================= deriv_quad (FS-04) ========================
    for axis, axis_name in ((0, "x"), (1, "y")):
        for thresh, thresh_name, hexval in ((1.0, "within", f2hex(1.0)), (2.0, "between", f2hex(2.0))):
            add_gpu(f"deriv_quadbound_axis{axis_name}_{thresh_name}", "deriv_quad", "deriv_quadbound",
                    ["--width", "4", "--height", "4", "--buf", "0=64,00",
                     "--buf-u32", f"1={axis},{hexval}", "--buf-u32", "2=4,4"])

    # ============================= deriv_scalar (FS-07) ======================
    add_scan("deriv_scalar_f1_scan", "deriv_scalar", "deriv_scalar_f1", count_deriv_axis)
    add_scan("deriv_scalar_f2_scan", "deriv_scalar", "deriv_scalar_f2", count_deriv_axis)
    add_scan("deriv_scalar_f3_scan", "deriv_scalar", "deriv_scalar_f3", count_deriv_axis)
    add_scan("deriv_scalar_f4_scan", "deriv_scalar", "deriv_scalar_f4", count_deriv_axis)
    add_scan("deriv_scalar_f4_both_scan", "deriv_scalar", "deriv_scalar_f4_both", count_deriv_axis)
    add_scan("deriv_scalar_plain_scan", "deriv_scalar", "deriv_scalar_plain", count_deriv_axis)
    add_gpu("deriv_axis_check", "deriv_scalar", "deriv_axis_check",
            ["--width", "2", "--height", "2", "--buf", "0=16,00"])

    # ============================= deriv_helper (FS-02/06) ===================
    add_gpu("helper_orig_relay", "deriv_helper", "helper_orig_relay",
            ["--width", "4", "--height", "4", "--buf", "0=128,00", "--buf-u32", "1=4,4"])

    # ============================= interp_mode (FS-08) =======================
    add_gpu("interp_centroid_extrap", "interp_mode", "interp_centroid_extrap",
            ["--width", "1", "--height", "1", "--samples", "4", "--resolve", "--buf", "0=8,00"])
    add_gpu("interp_offset_anchor", "interp_mode", "interp_offset_anchor",
            ["--width", "1", "--height", "1", "--buf", "0=12,00"])
    offset_x_vals = [0.0, 0.25, -0.25, 0.4, -0.4, 0.5, -0.5, 0.6, 0.9, -0.9]
    for v in offset_x_vals:
        tag = ("m" if v < 0 else "") + str(abs(v)).replace(".", "p")
        add_gpu(f"interp_offset_x_{tag}", "interp_mode", "interp_offset_sweep",
                ["--width", "1", "--height", "1", "--buf", "0=4,00",
                 "--buf-u32", f"1={f2hex(v)},{f2hex(0.0)}"])
    offset_y_vals = [0.0, 0.25, -0.25, 0.5]
    for v in offset_y_vals:
        tag = ("m" if v < 0 else "") + str(abs(v)).replace(".", "p")
        add_gpu(f"interp_offset_y_{tag}", "interp_mode", "interp_offset_y",
                ["--width", "1", "--height", "1", "--buf", "0=4,00",
                 "--buf-u32", f"1={f2hex(0.0)},{f2hex(v)}"])
    offset_xy_vals = [(0.2, 0.1), (-0.3, 0.4), (0.45, -0.45)]
    for dx, dy in offset_xy_vals:
        tag = f"{str(dx).replace('.', 'p').replace('-', 'm')}_{str(dy).replace('.', 'p').replace('-', 'm')}"
        add_gpu(f"interp_offset_xy_{tag}", "interp_mode", "interp_offset_xy",
                ["--width", "1", "--height", "1", "--buf", "0=4,00",
                 "--buf-u32", f"1={f2hex(dx)},{f2hex(dy)}"])

    # ============================= interp_convergent (FS-09) =================
    configs = [
        ("A", 1.0, 2.0, 3.0, 0.1),
        ("B", 1.0, 5.0, 20.0, 0.1 + 1.0/3.0),
        ("C", 1.0, 2.0, 3.0, 1.0/3.0),
        ("D", 2.0, 2.0, 2.0, 0.1),
        ("E", 1.0, 1000.0, 1.0, 0.1),
    ]
    for tag, w0, w1, w2, attr in configs:
        vals = ",".join(f2hex(v) for v in (w0, w1, w2, attr))
        add_gpu(f"interp_convergent_{tag}", "interp_convergent", "interp_convergent",
                ["--width", "4", "--height", "4", "--buf", "0=192,00", "--buf-u32", "1=4,4",
                 "--buf-u32", f"2={vals}"])

    # ============================= dynidx_in (FS-10) ==========================
    add_scan("dynidx_in_select_scan", "dynidx_in", "dynidx_in_select", count_iter_family)
    add_scan("dynidx_in_control_scan", "dynidx_in", "dynidx_in_control", count_iter_family)
    add_gpu("dynidx_in_select_render", "dynidx_in", "dynidx_in_select",
            ["--width", "4", "--height", "1", "--buf", "0=16,00", "--buf-u32", "1=4,1"])

    # ============================= dynidx_out (FS-11) ==========================
    add_attempt("dynidx_out_reject_attempt", "dynidx_out", "dynidx_out_reject")
    add_scan("dynidx_out_unroll_scan", "dynidx_out", "dynidx_out_unroll", count_frag_color_store)
    add_gpu("dynidx_out_unroll_render", "dynidx_out", "dynidx_out_unroll",
            ["--width", "2", "--height", "1", "--rt-count", "2"])

    # ============================= fs12_samplemask (FS-12) =====================
    add_gpu("fs12_samplemask_control", "fs12_samplemask", "fs12_samplemask_demote",
            ["--width", "2", "--height", "1", "--samples", "4", "--resolve"], fragment="f_control")
    add_gpu("fs12_samplemask_discard", "fs12_samplemask", "fs12_samplemask_demote",
            ["--width", "2", "--height", "1", "--samples", "4", "--resolve"], fragment="f_main")

    # ============================= anomaly_helper_pre (a) =======================
    add_gpu("anomaly_helper_pre_direct", "anomaly_helper_pre", "anomaly_helper_pre_direct",
            ["--width", "4", "--height", "4", "--buf", "0=64,ee", "--buf-u32", "1=4,4"])

    # ============================= anomaly_persample (b) =========================
    add_gpu("anomaly_persample_control", "anomaly_persample", "anomaly_persample_resolve",
            ["--width", "2", "--height", "2", "--samples", "4", "--resolve"], fragment="f_control")
    add_gpu("anomaly_persample_discard", "anomaly_persample", "anomaly_persample_resolve",
            ["--width", "2", "--height", "2", "--samples", "4", "--resolve"], fragment="f_main")

    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--out")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    cases = build_cases()
    if args.list:
        for c in cases:
            print(c["group"], c["id"])
        print(f"TOTAL {len(cases)} cases")
        return 0

    if not args.run or not args.out:
        print("need --run and --out (or --list)", file=sys.stderr)
        return 2

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    for c in cases:
        gated, nongated = c["run"](c)
        assert set(gated.keys()) == S.GATED_KEYS, f"{c['id']}: gated key mismatch {set(gated.keys())}"
        assert set(nongated.keys()) == S.NONGATED_KEYS, f"{c['id']}: nongated key mismatch"
        (outdir / f"{c['id']}.gated.json").write_text(json.dumps(gated, indent=2, sort_keys=True) + "\n")
        (outdir / f"{c['id']}.nongated.json").write_text(json.dumps(nongated, indent=2, sort_keys=True) + "\n")
        print(f"CASE {c['id']:36s} status={gated['status']}")
    print(f"DONE {len(cases)} cases -> {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
