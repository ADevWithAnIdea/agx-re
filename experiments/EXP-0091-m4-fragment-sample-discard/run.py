#!/usr/bin/env python3
"""EXP-0091 runner. Executes the full frozen case matrix (GLFS-A01/A02/A03/A05/A06/
A07 + OPT-09) and writes gated/non-gated sibling records under raw/<run_id>/.

Two case kinds:
  compile_scan -- host-side OWN-SHADER compile (tools/shdump) + our own byte-offset
                  scan for the located 0x57/../0x54 and 0x07/02/54 fragment-mask
                  submission op family, plus a tools/agx-isa tokenize check. No GPU
                  dispatch; fully deterministic given the frozen kernel source.
  gpu_render    -- one fresh `fsrun` process per case (single-threaded harness: one
                  case, one process, run to completion before the next starts).
                  Hard per-case timeout. A fault/timeout is recorded as a result,
                  never silently dropped.

Usage:
  python3 run.py --run run01 --out raw/m4_<date>_run01
  python3 run.py --run run02 --out raw/m4_<date>_run02
  python3 run.py --list                # print the frozen case matrix and exit (no I/O)
"""
import argparse, hashlib, json, os, subprocess, sys, time
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
HEX_DIR = HERE / "work" / "hex"
KERNELS = HERE / "kernels"

RUN_TIMEOUT_S = 60      # hard per-case GPU dispatch timeout (well under the 300s cap)
COMPILE_TIMEOUT_S = 120


def sh(cmd, timeout):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(HERE))
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return -9, e.stdout or "", (e.stderr or "") + "\nTIMEOUT", time.time() - t0


def parse_fsrun_stdout(text):
    pixels, depth, buffers = [], [], {}
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
        elif line.startswith("PIXEL "):
            parts = line.split()
            x, y = int(parts[1]), int(parts[2])
            bgra = parts[3].split("=")[1]
            pixels.append({"x": x, "y": y, "bgra": bgra})
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
    pixels.sort(key=lambda p: (p["y"], p["x"]))
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
        result = {"device": None, "pipeline_source": None, "size": None, "pixels": [],
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


def compile_and_locate(name):
    """Compile kernels/<name>.metal to a render archive, extract the fragment main
    hex. Returns (archive_path, hex_string)."""
    src = KERNELS / f"{name}.metal"
    arch = ARCH_DIR / f"{name}.bin"
    if not arch.exists():
        rc, out, err, _ = sh([str(SHDUMP), "-o", str(arch), "--render", "--vertex", "v_main",
                               "--fragment", "f_main", str(src)], COMPILE_TIMEOUT_S)
        if rc != 0:
            raise RuntimeError(f"shdump failed for {name}: {err}")
    rc, out, err, _ = sh(["python3", str(AGXPARSE), str(arch), "--stage", "fragment",
                           "--extract-hex"], COMPILE_TIMEOUT_S)
    if rc != 0:
        raise RuntimeError(f"agxparse extract-hex failed for {name}: {err}")
    return arch, out.strip()


def run_scan_case(case):
    name = case["kernel"]
    arch, hexstr = compile_and_locate(name)
    buf = bytes.fromhex(hexstr)
    hits57, hits07 = [], []
    for i in range(len(buf) - 2):
        if buf[i] == 0x57 and buf[i + 2] == 0x54:
            hits57.append({"offset": i, "exact6": buf[i:i + 6].hex()})
        if buf[i] == 0x07 and buf[i + 2] == 0x54:
            hits07.append({"offset": i, "exact6": buf[i:i + 6].hex()})
    rc, out, err, _ = sh(["python3", str(AGXISA), "tokenize", hexstr], COMPILE_TIMEOUT_S)
    clean = "CLEAN:" in out
    leftover = 0
    for line in out.splitlines():
        if line.startswith("LEFTOVER "):
            leftover = int(line.split()[1])
    result = {
        "frag_main_hex": hexstr, "frag_main_len": len(buf),
        "hits_0x57": hits57, "hits_0x07": hits07,
        "tokenize_clean": clean, "tokenize_leftover": leftover,
    }
    gated = {"case_id": case["id"], "group": case["group"], "kind": "compile_scan",
             "params": case["params"], "status": "SCANNED", "result": result}
    nongated = {"case_id": case["id"], "gputime_ns": None, "wall_ms": None,
                "pid": os.getpid(), "started_at": None}
    return gated, nongated


# ----------------------------------------------------------------------------
# Frozen case matrix
# ----------------------------------------------------------------------------

def build_cases():
    cases = []

    def add_scan(cid, kernel):
        cases.append({"id": cid, "group": "loc", "kernel": kernel,
                      "params": {"kernel": kernel, "vertex": "v_main", "fragment": "f_main"},
                      "run": run_scan_case})

    for k in ["loc_base", "loc_if_nodiscard", "loc_if_discard", "loc_samplemask",
              "loc_samplemask_discard", "loc_discard_unconditional", "loc_mask_const_zero",
              "loc_mask_const_full", "loc_mask_const_A"]:
        add_scan(f"loc_{k}", k)

    def add_gpu(cid, group, source, fragment="f_main", vertex="v_main", extra=None, base=None):
        args = ["--source", str(KERNELS / f"{source}.metal"), "--vertex", vertex,
                "--fragment", fragment]
        if base:
            args = list(base)
        args += extra or []
        cases.append({"id": cid, "group": group,
                      "params": {"source": source, "vertex": vertex, "fragment": fragment,
                                 "extra": extra or []},
                      "fsrun_args": args, "run": run_gpu_case})

    # --- splice group: baseline + byte sweep on s_kill_probe -----------------
    S_ARCH = str(ARCH_DIR / "s_kill_probe.bin")
    common_splice = ["--source", str(KERNELS / "s_kill_probe.metal"), "--vertex", "v_main",
                      "--fragment", "f_main", "--archive", S_ARCH,
                      "--width", "2", "--height", "2", "--depth", "--depth-clear", "0.5",
                      "--depth-compare", "7", "--occlusion"]

    def add_splice(cid, mask, splice_off=None, splice_hex=None):
        args = list(common_splice) + ["--buf-u32", f"0={mask}"]
        if splice_off is not None:
            args += ["--splice", f"{splice_off}={splice_hex}"]
        cases.append({"id": cid, "group": "splice",
                      "params": {"mask": mask, "splice_off": splice_off, "splice_hex": splice_hex},
                      "fsrun_args": args, "run": run_gpu_case})

    add_splice("splice_baseline_archive_m1", 1)
    add_splice("splice_baseline_archive_m0", 0)
    for m in (0, 1):
        add_splice(f"splice_own_b3_01_m{m}", m, 13801, "01")
        add_splice(f"splice_companion_b3_0c_m{m}", m, 13807, "0c")
        add_splice(f"splice_own_byte1_1c_m{m}", m, 13799, "1c")
    add_splice("splice_posctrl_color_m1", 1, 13820, "00")
    for v in ["01", "02", "04", "08", "10", "20", "40", "80", "fe", "ff", "00"]:
        add_splice(f"splice_B4own_{v}_m1", 1, 13802, v)
    add_splice("splice_B5own_00_m1", 1, 13803, "00")
    add_splice("splice_B4comp_ff_m1", 1, 13808, "ff")
    add_splice("splice_B5comp_ff_m1", 1, 13809, "ff")
    # plain (non-archive) baseline for cross-check
    add_gpu("splice_plain_m1", "splice", "s_kill_probe",
            extra=["--width", "2", "--height", "2", "--depth", "--depth-clear", "0.5",
                   "--depth-compare", "7", "--occlusion", "--buf-u32", "0=1"])
    add_gpu("splice_plain_m0", "splice", "s_kill_probe",
            extra=["--width", "2", "--height", "2", "--depth", "--depth-clear", "0.5",
                   "--depth-compare", "7", "--occlusion", "--buf-u32", "0=0"])

    # --- msaa width/hole sweep ------------------------------------------------
    msaa_masks = {
        4: [0, 1, 5, 10, 15, 16, 32, 240, 255, 65535, 4294967295, 2147483648],
        2: [0, 1, 2, 3, 4, 12],
        1: [0, 1, 2, 3],
    }
    for n, masks in msaa_masks.items():
        for m in masks:
            extra = ["--width", "1", "--height", "1", "--samples", str(n), "--buf-u32", f"0={m}"]
            if n > 1:
                extra += ["--resolve"]
            add_gpu(f"msaa_N{n}_mask{m}", "msaa", "f_persample_mask_resolve", extra=extra)

    # --- demote / helper-status group ----------------------------------------
    dims = ["--buf-u32", "1=4,4"]
    # Rec is 4 x uint32 = 16 bytes; W=4,H=4 = 16 pixels -> 256 bytes required.
    for name in ["d_control_nodiscard", "d_demote_before", "d_demote_after"]:
        add_gpu(name, "demote", name,
                extra=["--width", "4", "--height", "4", "--buf", "0=256,00"] + dims)
    add_gpu("d_orig_helper", "demote", "d_orig_helper",
            extra=["--width", "4", "--height", "4", "--buf", "0=256,00"] + dims)
    for name in ["d_tex_implicit_lod", "d_control_tex"]:
        add_gpu(name, "demote", name,
                extra=["--width", "4", "--height", "4", "--buf", "0=256,00"] + dims +
                      ["--tex-checker", "0", "--tex-w", "8", "--tex-h", "8", "--tex-mip"])
    add_gpu("d_quad_shuffle", "demote", "d_quad_shuffle",
            extra=["--width", "4", "--height", "4", "--buf", "0=256,00"] + dims)

    # --- depth ordering group -------------------------------------------------
    for name in ["e_late_nodiscard", "e_early_nodiscard", "e_late_discard", "e_early_discard",
                 "e_shaderdepth_nodiscard", "e_shaderdepth_discard"]:
        add_gpu(name, "depth", name,
                extra=["--width", "8", "--height", "8", "--depth", "--depth-clear", "0.5",
                       "--depth-compare", "1", "--occlusion",
                       "--buf", "0=256,00", "--buf", "1=1024,cc", "--buf-u32", "2=8,8"])

    # --- suppression matrix ----------------------------------------------------
    for name in ["g6_suppress", "g6_suppress_control"]:
        add_gpu(name, "suppress", name,
                extra=["--width", "4", "--height", "4", "--depth", "--depth-clear", "0.9",
                       "--depth-compare", "7",
                       "--buf", "0=64,ee", "--buf", "1=4,00", "--buf-u32", "2=4,4"])

    # --- sample-shading invocation model ---------------------------------------
    for n in (1, 2, 4):
        add_gpu(f"f_persample_count_N{n}", "sampleshading", "f_persample_count",
                extra=["--width", "2", "--height", "2", "--samples", str(n),
                       "--buf", "0=64,00", "--buf-u32", "1=2,2,%d" % n])
        add_gpu(f"f_perpixel_count_N{n}", "sampleshading", "f_perpixel_count",
                extra=["--width", "2", "--height", "2", "--samples", str(n),
                       "--buf", "0=64,00", "--buf-u32", "1=2,2,%d" % n])
    add_gpu("f_persample_discard_N4", "sampleshading", "f_persample_discard",
            extra=["--width", "2", "--height", "2", "--samples", "4",
                   "--buf", "0=64,00", "--buf", "1=64,00", "--buf-u32", "2=2,2,4"])

    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="run id, e.g. run01")
    ap.add_argument("--out", help="output dir for this run's raw records")
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
        print(f"CASE {c['id']:40s} status={gated['status']}")
    print(f"DONE {len(cases)} cases -> {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
