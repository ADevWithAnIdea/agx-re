#!/usr/bin/env python3
"""EXP-0097 runner. Executes the frozen case matrix (casematrix.py) and writes
gated/non-gated sibling records under raw/<run_id>/. Single-threaded harness:
one case, one process (capacityprobe or renderprobe), run to completion (or
hard-timed-out) before the next starts. A NON-RECORDED smoke case runs first
(written under work/, never raw/); if it fails, no raw/ artifact is created
for this run at all (standing gate (c)).

Usage:
  python3 run.py --run run01 --out raw/m4_<date>_run01
  python3 run.py --list          # print the frozen case matrix and exit
"""
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(HERE))
import casematrix as CM
import schema as S
import genkernels as G

WORKBIN = EXP / "work" / "bin"
CAPACITYPROBE = WORKBIN / "capacityprobe"
RENDERPROBE = WORKBIN / "renderprobe"
GEN_DIR = EXP / "work" / "gen"

RUN_TIMEOUT_S = 60


def sh(cmd, timeout):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(EXP))
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return -9, (e.stdout or ""), (e.stderr or "") + "\nTIMEOUT", time.time() - t0


def parse_kv_lines(text):
    out = {}
    for line in text.splitlines():
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split(" ", 1)
        key = parts[0]
        val = parts[1] if len(parts) > 1 else ""
        out.setdefault(key, []).append(val)
    return out


def write_gen(name, src):
    GEN_DIR.mkdir(parents=True, exist_ok=True)
    p = GEN_DIR / f"{name}.metal"
    p.write_text(src)
    return str(p)


def nongated(case, out, err, wall, gputime):
    return {"case_id": case["id"], "gputime_ns": gputime, "wall_ms": round(wall * 1000, 3),
            "pid": os.getpid(), "raw_tail": (out[-300:] + err[-300:])}


# ---------------------------------------------------------------------------
# kind: capacity_compile -- families vary_scalar, vary_dce, clip_sweep,
# cull_negative, vary_clip_combo. Dispatches capacityprobe (compile + pipeline
# creation only, no draw -- exactly the "no assembler needed" capacity probe).
# ---------------------------------------------------------------------------
def run_capacity_compile(case):
    p = case["params"]
    fam = case["family"]
    if fam == "vary_scalar":
        src = G.gen_vary_scalar(p["n"], p["n"], p["width"])
    elif fam == "vary_dce":
        src = G.gen_vary_scalar(p["declared"], p["used"], p["width"])
    elif fam == "clip_sweep":
        src = G.gen_clip(p["n"])
    elif fam == "cull_negative":
        src = G.gen_cull()
    elif fam == "vary_clip_combo":
        src = G.gen_vary_clip_combo(p["used"], p["clip_n"])
    else:
        raise RuntimeError(f"unknown family {fam} for capacity_compile")
    path = write_gen(case["id"], src)

    t0 = time.time()
    rc, out, err, wall = sh([str(CAPACITYPROBE), "--source", path, "--vertex", "v_main",
                              "--fragment", "f_main"], RUN_TIMEOUT_S)
    kv = parse_kv_lines(out)
    raw_status = kv.get("STATUS", ["HANG" if rc == -9 else "HARNESS_CRASH"])[0]
    error_text = kv.get("ERROR", [None])[0]
    ok = (raw_status == "PIPELINE_OK")
    status = "OK" if ok else raw_status
    expect_ok = p["expect_ok"]
    if status == "HANG":
        verdict = "TIMEOUT"
    elif status == "HARNESS_CRASH":
        verdict = "FAIL"
    else:
        verdict = "PASS" if ok == expect_ok else "FAIL"
    observed = {"ok": ok, "raw_status": raw_status, "error_text": error_text}
    gated = {"case_id": case["id"], "family": fam, "kind": case["kind"], "params": p,
             "status": status, "verdict": verdict, "observed": observed}
    gt = int(kv["GPUTIME_NS"][0]) if "GPUTIME_NS" in kv else None
    return gated, nongated(case, out, err, wall, gt)


# ---------------------------------------------------------------------------
# kind: render_checksum -- family vary_render_confirm. Real draw + readback;
# confirms the max-legal pipeline EXECUTES correctly (no silent aliasing),
# not merely that it compiles.
# ---------------------------------------------------------------------------
def run_render_checksum(case):
    p = case["params"]
    n, width = p["n"], p["width"]
    src = G.gen_vary_scalar(n, n, width)
    path = write_gen(case["id"], src)
    rc, out, err, wall = sh([str(RENDERPROBE), "--source", path, "--vertex", "v_main",
                              "--fragment", "f_main", "--mode", "render",
                              "--width", "1", "--height", "1"], RUN_TIMEOUT_S)
    kv = parse_kv_lines(out)
    raw_status = kv.get("STATUS", ["HANG" if rc == -9 else "HARNESS_CRASH"])[0]
    error_text = kv.get("ERROR", [None])[0]
    observed_sum = None
    if raw_status == "OK" and "PIXEL 0 0" in out:
        for line in out.splitlines():
            if line.startswith("PIXEL 0 0"):
                rgba = line.split("rgba=")[1]
                observed_sum = float(rgba.split(",")[0])
    expected_sum = sum(i * 0.0001 for i in range(n))
    tol = max(1e-3, abs(expected_sum) * 2e-4)
    match = observed_sum is not None and abs(observed_sum - expected_sum) <= tol
    if raw_status == "HANG":
        status, verdict = "HANG", "TIMEOUT"
    elif raw_status != "OK":
        status, verdict = raw_status, "FAIL"
    else:
        status, verdict = "OK", ("PASS" if match else "FAIL")
    observed = {"observed_sum": observed_sum, "expected_sum": expected_sum,
                "tolerance": tol, "match": match, "error_text": error_text}
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"], "params": p,
             "status": status, "verdict": verdict, "observed": observed}
    gt = int(kv["GPUTIME_NS"][0]) if "GPUTIME_NS" in kv else None
    return gated, nongated(case, out, err, wall, gt)


# ---------------------------------------------------------------------------
# kind: render_fill -- family position_special.
# ---------------------------------------------------------------------------
def run_render_fill(case):
    p = case["params"]
    if p["component"] is None:
        src = G.gen_position_baseline()
    else:
        src = G.gen_position_special(p["component"], p["expr"])
    path = write_gen(case["id"], src)
    rc, out, err, wall = sh([str(RENDERPROBE), "--source", path, "--vertex", "v_main",
                              "--fragment", "f_main", "--mode", "render",
                              "--width", "4", "--height", "4"], RUN_TIMEOUT_S)
    kv = parse_kv_lines(out)
    raw_status = kv.get("STATUS", ["HANG" if rc == -9 else "HARNESS_CRASH"])[0]
    error_text = kv.get("ERROR", [None])[0]
    filled = 0
    total = 0
    if raw_status == "OK":
        for line in out.splitlines():
            if line.startswith("PIXEL"):
                total += 1
                rgba = [float(x) for x in line.split("rgba=")[1].split(",")]
                if all(v > 0.99 for v in rgba):
                    filled += 1
    category = None
    if raw_status == "OK":
        category = "full" if filled == total and total > 0 else ("none" if filled == 0 else "partial")
    if raw_status == "HANG":
        status, verdict = "HANG", "TIMEOUT"
    elif raw_status != "OK":
        status, verdict = raw_status, "FAIL"
    else:
        status = "OK"
        verdict = "PASS" if category == p["expect_category"] else "FAIL"
    observed = {"filled": filled, "total": total, "category": category, "error_text": error_text}
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"], "params": p,
             "status": status, "verdict": verdict, "observed": observed}
    gt = int(kv["GPUTIME_NS"][0]) if "GPUTIME_NS" in kv else None
    return gated, nongated(case, out, err, wall, gt)


# ---------------------------------------------------------------------------
# kind: render_point -- family point_size.
# ---------------------------------------------------------------------------
def classify_point(count, xmin, ymin, xmax, ymax, wh):
    if count == 0:
        return "discard", None
    side_w = xmax - xmin + 1
    side_h = ymax - ymin + 1
    center_ok = abs(((xmin + xmax) / 2.0) - wh / 2.0) <= 2 and abs(((ymin + ymax) / 2.0) - wh / 2.0) <= 2
    if side_w == side_h and count == side_w * side_h and center_ok:
        return "scale", side_w
    return "anomalous", side_w


def run_render_point(case):
    p = case["params"]
    src = G.gen_point_size(p["expr"])
    path = write_gen(case["id"], src)
    wh = p["wh"]
    rc, out, err, wall = sh([str(RENDERPROBE), "--source", path, "--vertex", "v_main",
                              "--fragment", "f_main", "--mode", "point",
                              "--width", str(wh), "--height", str(wh)], RUN_TIMEOUT_S)
    kv = parse_kv_lines(out)
    raw_status = kv.get("STATUS", ["HANG" if rc == -9 else "HARNESS_CRASH"])[0]
    error_text = kv.get("ERROR", [None])[0]
    count = xmin = ymin = xmax = ymax = None
    if raw_status == "OK":
        for line in out.splitlines():
            if line.startswith("BBOX"):
                toks = line.split()
                xmin, ymin, xmax, ymax = int(toks[1]), int(toks[2]), int(toks[3]), int(toks[4])
                count = int(toks[6])
    cat = side = None
    if raw_status == "OK":
        cat, side = classify_point(count, xmin, ymin, xmax, ymax, wh)
    if raw_status == "HANG":
        status, verdict = "HANG", "TIMEOUT"
    elif raw_status != "OK":
        status, verdict = raw_status, "FAIL"
    else:
        status = "OK"
        expect_cat = p["expect_category"]
        if expect_cat == "discard":
            ok = (cat == "discard")
        elif expect_cat == "scale":
            ok = (cat == "scale" and side == p["expect_side"])
        elif expect_cat == "clamp511":
            ok = (cat == "scale" and side == 511)
        elif expect_cat == "anomalous":
            ok = (cat == "anomalous")
        else:
            ok = False
        verdict = "PASS" if ok else "FAIL"
    observed = {"count": count, "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
                "category": cat, "side": side, "error_text": error_text}
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"], "params": p,
             "status": status, "verdict": verdict, "observed": observed}
    gt = int(kv["GPUTIME_NS"][0]) if "GPUTIME_NS" in kv else None
    return gated, nongated(case, out, err, wall, gt)


# ---------------------------------------------------------------------------
# kind: render_layer -- family layer_oob.
# ---------------------------------------------------------------------------
def run_render_layer(case):
    p = case["params"]
    src = G.gen_layer(f'{p["requested"]}u', p["layers"])
    path = write_gen(case["id"], src)
    rc, out, err, wall = sh([str(RENDERPROBE), "--source", path, "--vertex", "v_main",
                              "--fragment", "f_main", "--mode", "layer",
                              "--width", "4", "--height", "4", "--layers", str(p["layers"])],
                             RUN_TIMEOUT_S)
    kv = parse_kv_lines(out)
    raw_status = kv.get("STATUS", ["HANG" if rc == -9 else "HARNESS_CRASH"])[0]
    error_text = kv.get("ERROR", [None])[0]
    landing = []
    if raw_status == "OK":
        for line in out.splitlines():
            if line.startswith("LAYERPIX"):
                toks = line.split()
                layer = int(toks[1])
                rgba = [float(x) for x in toks[2].split("rgba=")[1].split(",")]
                if all(v > 0.99 for v in rgba):
                    landing.append(layer)
    if raw_status == "HANG":
        status, verdict = "HANG", "TIMEOUT"
    elif raw_status != "OK":
        status, verdict = raw_status, "FAIL"
    else:
        status = "OK"
        verdict = "PASS" if landing == [p["expect_landing"]] else "FAIL"
    observed = {"landing": landing, "error_text": error_text}
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"], "params": p,
             "status": status, "verdict": verdict, "observed": observed}
    gt = int(kv["GPUTIME_NS"][0]) if "GPUTIME_NS" in kv else None
    return gated, nongated(case, out, err, wall, gt)


# ---------------------------------------------------------------------------
# kind: render_viewport -- family viewport_oob. Tiles the target into
# `viewports` 4px-wide strips; determines which tile received the fragment.
# ---------------------------------------------------------------------------
def run_render_viewport(case):
    p = case["params"]
    src = G.gen_viewport(f'{p["requested"]}u', p["viewports"])
    path = write_gen(case["id"], src)
    tile = 4
    W = tile * p["viewports"]
    rc, out, err, wall = sh([str(RENDERPROBE), "--source", path, "--vertex", "v_main",
                              "--fragment", "f_main", "--mode", "viewport",
                              "--width", str(W), "--height", "4", "--viewports", str(p["viewports"])],
                             RUN_TIMEOUT_S)
    kv = parse_kv_lines(out)
    raw_status = kv.get("STATUS", ["HANG" if rc == -9 else "HARNESS_CRASH"])[0]
    error_text = kv.get("ERROR", [None])[0]
    landing_tiles = set()
    if raw_status == "OK":
        for line in out.splitlines():
            if line.startswith("PIXEL"):
                toks = line.split()
                x = int(toks[1])
                rgba = [float(v) for v in toks[3].split("rgba=")[1].split(",")]
                if all(v > 0.99 for v in rgba):
                    landing_tiles.add(x // tile)
    landing = sorted(landing_tiles)
    if raw_status == "HANG":
        status, verdict = "HANG", "TIMEOUT"
    elif raw_status != "OK":
        status, verdict = raw_status, "FAIL"
    else:
        status = "OK"
        verdict = "PASS" if landing == [p["expect_landing"]] else "FAIL"
    observed = {"landing": landing, "error_text": error_text}
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"], "params": p,
             "status": status, "verdict": verdict, "observed": observed}
    gt = int(kv["GPUTIME_NS"][0]) if "GPUTIME_NS" in kv else None
    return gated, nongated(case, out, err, wall, gt)


# ---------------------------------------------------------------------------
# kind: render_provoking -- family provoking.
# ---------------------------------------------------------------------------
COLOR_NAMES = {
    (1.0, 0.0, 0.0, 1.0): "red",
    (0.0, 1.0, 0.0, 1.0): "green",
    (0.0, 0.0, 1.0, 1.0): "blue",
    (1.0, 1.0, 0.0, 1.0): "yellow",
}


def classify_color(rgba):
    best, bestd = None, 1e9
    for k, name in COLOR_NAMES.items():
        d = sum((a - b) ** 2 for a, b in zip(k, rgba))
        if d < bestd:
            best, bestd = name, d
    return best if bestd < 0.01 else f"unknown{tuple(round(v,3) for v in rgba)}"


def run_render_provoking(case):
    p = case["params"]
    src = G.gen_provoking(p["gen_topology"])
    path = write_gen(case["id"], src)
    cmd = [str(RENDERPROBE), "--source", path, "--vertex", "v_main", "--fragment", "f_main",
           "--mode", "render", "--width", str(p["width"]), "--height", str(p["height"]),
           "--topology", p["probe_topology"], "--vcount", str(p["vcount"])]
    if p["icount"] > 0:
        cmd += ["--icount", str(p["icount"])]
    rc, out, err, wall = sh(cmd, RUN_TIMEOUT_S)
    kv = parse_kv_lines(out)
    raw_status = kv.get("STATUS", ["HANG" if rc == -9 else "HARNESS_CRASH"])[0]
    error_text = kv.get("ERROR", [None])[0]
    pixels = {}
    if raw_status == "OK":
        for line in out.splitlines():
            if line.startswith("PIXEL"):
                toks = line.split()
                x, y = int(toks[1]), int(toks[2])
                rgba = tuple(float(v) for v in toks[3].split("rgba=")[1].split(","))
                pixels[(x, y)] = rgba
    observed_samples = []
    all_match = True
    if raw_status == "OK":
        for (sx, sy, expect_name) in p["samples"]:
            rgba = pixels.get((sx, sy))
            name = classify_color(rgba) if rgba else None
            observed_samples.append({"x": sx, "y": sy, "color": name, "expect": expect_name})
            if name != expect_name:
                all_match = False
    if raw_status == "HANG":
        status, verdict = "HANG", "TIMEOUT"
    elif raw_status != "OK":
        status, verdict = raw_status, "FAIL"
    else:
        status = "OK"
        verdict = "PASS" if all_match else "FAIL"
    observed = {"samples": observed_samples, "error_text": error_text}
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"], "params": p,
             "status": status, "verdict": verdict, "observed": observed}
    gt = int(kv["GPUTIME_NS"][0]) if "GPUTIME_NS" in kv else None
    return gated, nongated(case, out, err, wall, gt)


DISPATCH = {
    "capacity_compile": run_capacity_compile,
    "render_checksum": run_render_checksum,
    "render_fill": run_render_fill,
    "render_point": run_render_point,
    "render_layer": run_render_layer,
    "render_viewport": run_render_viewport,
    "render_provoking": run_render_provoking,
}


def run_smoke():
    """NON-RECORDED smoke gate. A tiny, fast, known-good real GPU pipeline
    creation + a real draw+readback. Written to work/, NEVER to raw/
    (standing gate (c))."""
    src = G.gen_clip(8)
    path = write_gen("_smoke_clip8", src)
    rc, out, err, wall = sh([str(CAPACITYPROBE), "--source", path, "--vertex", "v_main",
                              "--fragment", "f_main"], 30)
    kv = parse_kv_lines(out)
    ok1 = (kv.get("STATUS", [None])[0] == "PIPELINE_OK")

    src2 = G.gen_position_baseline()
    path2 = write_gen("_smoke_render", src2)
    rc2, out2, err2, wall2 = sh([str(RENDERPROBE), "--source", path2, "--vertex", "v_main",
                                  "--fragment", "f_main", "--mode", "render",
                                  "--width", "2", "--height", "2"], 30)
    ok2 = ("STATUS OK" in out2) and out2.count("1.000000,1.000000,1.000000,1.000000") == 4
    ok = ok1 and ok2
    return ok, {"clip8": {"cmd": "capacityprobe", "rc": rc, "stdout": out, "stderr": err, "ok": ok1},
                "render": {"cmd": "renderprobe", "rc": rc2, "stdout": out2, "stderr": err2, "ok": ok2}}


def git_revision():
    rc, out, err, _ = sh(["git", "rev-parse", "HEAD"], 10)
    rev = out.strip() if rc == 0 else None
    rc2, out2, _, _ = sh(["git", "status", "--porcelain"], 10)
    dirty_tracked = any(line[:2].strip() and line[1] != "?" for line in out2.splitlines() if line.strip())
    return rev, dirty_tracked


def sha256_file(path):
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def authored_files():
    return ["harness/schema.py", "harness/casematrix.py", "harness/run.py",
            "harness/verify.py", "harness/genkernels.py",
            "harness/capacityprobe.m", "harness/renderprobe.m"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--out")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for c in CM.MATRIX:
            print(c["id"], c["family"], c["kind"])
        print(f"TOTAL {CM.TOTAL}")
        return

    if not args.run or not args.out:
        print("need --run and --out (or --list)", file=sys.stderr)
        sys.exit(2)

    out_dir = Path(args.out)
    if out_dir.exists():
        print(f"FAIL: raw dir already exists: {out_dir}", file=sys.stderr)
        sys.exit(2)

    work_dir = EXP / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    smoke_ok, smoke_receipt = run_smoke()
    (work_dir / f"{args.run}_smoke.json").write_text(json.dumps(smoke_receipt, indent=2))
    if not smoke_ok:
        print("FAIL: smoke gate failed, no raw/ artifact written", file=sys.stderr)
        sys.exit(1)
    print("SMOKE OK")

    rev, dirty = git_revision()
    inputs = {
        "run_id": args.run,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_revision_pinned": rev,
        "git_dirty_tracked": dirty,
        "authored_file_hashes": {f: sha256_file(EXP / f) for f in authored_files()},
        "total_cases": CM.TOTAL,
    }
    out_dir.mkdir(parents=True)
    (out_dir / "00_inputs.json").write_text(json.dumps(inputs, indent=2))

    gated_f = open(out_dir / "02_gated.jsonl", "a")
    nongated_f = open(out_dir / "03_nongated.jsonl", "a")
    counts = {"PASS": 0, "FAIL": 0, "TIMEOUT": 0, "N/A": 0}
    for i, case in enumerate(CM.MATRIX):
        fn = DISPATCH[case["kind"]]
        try:
            gated, ng = fn(case)
        except Exception as e:
            gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
                      "params": case["params"], "status": "HARNESS_CRASH", "verdict": "FAIL",
                      "observed": {}}
            ng = {"case_id": case["id"], "gputime_ns": None, "wall_ms": None,
                  "pid": os.getpid(), "raw_tail": repr(e)[:400]}
        ok, msg = S.validate_gated(gated)
        if not ok:
            raise RuntimeError(f"schema violation for case {case['id']}: {msg}")
        ok2, msg2 = S.validate_nongated(ng)
        if not ok2:
            raise RuntimeError(f"schema violation (nongated) for case {case['id']}: {msg2}")
        gated_f.write(json.dumps(gated, sort_keys=True) + "\n"); gated_f.flush(); os.fsync(gated_f.fileno())
        nongated_f.write(json.dumps(ng, sort_keys=True) + "\n"); nongated_f.flush(); os.fsync(nongated_f.fileno())
        counts[gated["verdict"]] = counts.get(gated["verdict"], 0) + 1
        print(f"[{i+1}/{CM.TOTAL}] {case['id']}: status={gated['status']} verdict={gated['verdict']}")
    gated_f.close(); nongated_f.close()

    manifest = {"run_id": args.run, "cases_planned": CM.TOTAL,
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "verdict_counts": counts}
    (out_dir / "04_manifest.json").write_text(json.dumps(manifest, indent=2))
    print("DONE", counts)


if __name__ == "__main__":
    main()
