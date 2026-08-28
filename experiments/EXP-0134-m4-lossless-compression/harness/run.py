#!/usr/bin/env python3
"""EXP-0134 runner. Executes the frozen 82-case matrix (casematrix.py), ONE case
per process (SAFETY: illegal/edge-case texture configs -- memoryless+ShaderRead
bind, tiny suballocated heaps, CPU-visible splices -- are exactly the kind of
thing that can fault a GPU context; one case per process isolates that per the
dispatch instructions), under the READ-ONLY tools/iotrace interposer (built
unmodified into work/iotrace.dylib -- never edited by this experiment). A
NON-RECORDED smoke case runs first (written under work/, never raw/); if it
fails, no raw/ artifact is created at all (standing gate (c)).

For each case, cprobe(1) creates the resource + writes the pattern + performs any
CPU-op + SIGUSR1-dumps every registered BO (once, or twice for "descriptor2"
cases via IOTRACE_DUMP_PERSIG). harness/auxdecode.py then locates the sampled
texture descriptor in the dump and decodes the compression flags + aux bytes.
Results split into a gated record (case_id, family, kind, params, status,
verdict, observed -- no raw timestamps) and a non-gated sibling (case_id,
wall_ms, pid, raw_tail, raw_ticks).

Usage:
  python3 run.py --run m4_<date>_run01 --out raw/m4_<date>_run01
  python3 run.py --list
"""
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import casematrix as CM
import schema as S
import auxdecode as AD

CPROBE = EXP / "work" / "bin" / "cprobe"
IOTRACE_DYLIB = EXP / "work" / "iotrace.dylib"
CASE_TIMEOUT_S = 30

# case id -> texture-type token (auxdecode.TYPECODE key) used to locate its descriptor
_TYPE_FOR_CASE = {}
for _c in CM.MATRIX:
    t = _c["params"].get("type", "2d")
    if _c["params"].get("linear"):
        t = "2d"
    _TYPE_FOR_CASE[_c["id"]] = t if t in AD.TYPECODE else "2d"


def sh(cmd, env, timeout):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(EXP), env=env)
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return -9, (e.stdout or ""), (e.stderr or "") + "\nTIMEOUT", time.time() - t0


def parse_stdout(out):
    """cprobe's protocol: 'KEY value...' lines and 'STATUS x' / 'DEVICE x' /
    'CONFIG k=v k=v...'. Returns (status, fields dict of scalar KEY->value)."""
    status = None
    fields = {}
    for line in out.splitlines():
        if line.startswith("STATUS "):
            status = line[len("STATUS "):].strip()
        elif line.startswith("CONFIG ") or line.startswith("DEVICE "):
            continue
        else:
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0].isupper():
                fields[parts[0]] = parts[1].strip()
            elif len(parts) == 1 and parts[0].isupper():
                fields[parts[0]] = ""
    return status, fields


def coerce(v):
    if v in ("0", "1"):
        return int(v)
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


def run_cprobe(binary_kind, params, dump_dir):
    p2 = dict(params)
    p2["dump"] = bool(params.get("dump", True))
    env = dict(os.environ)
    env["DYLD_INSERT_LIBRARIES"] = str(IOTRACE_DYLIB)
    env["IOTRACE_LOG"] = str(dump_dir / "iotrace.log")
    env["IOTRACE_DUMP_DIR"] = str(dump_dir)
    env["IOTRACE_DUMP_PERSIG"] = "1"
    cmd = [str(CPROBE), binary_kind, json.dumps(p2)]
    rc, out, err, wall = sh(cmd, env, CASE_TIMEOUT_S)
    status, fields = parse_stdout(out)
    if status is None:
        status = "HANG" if rc == -9 else "HARNESS_CRASH"
    return status, fields, out, err, wall, rc


def _dump_subdirs(dump_dir):
    return sorted([d for d in dump_dir.iterdir() if d.is_dir() and d.name.startswith("dump")])


def _short_hex(h, n=64):
    return h[:n] + (f"...(+{len(h)-n}B)" if len(h) > n else "")


def decode_descriptor_case(case, dump_dir, is_pair=False):
    w, h = case["params"]["w"], case["params"]["h"]
    typ = _TYPE_FOR_CASE[case["id"]]
    subs = _dump_subdirs(dump_dir)
    if not subs:
        return {"decode_error": "no dump subdirectories captured"}
    targets = [subs[0], subs[-1]] if is_pair else [subs[-1]]
    out = {}
    labels = ["before", "after"] if is_pair else ["main"]
    for label, d in zip(labels, targets):
        bos = AD.load_bos(str(d))
        cands = AD.find_descriptors(bos, w, h, AD.TYPECODE[typ])
        if not cands:
            out[f"{label}_decode_error"] = "descriptor not found"
            continue
        dec = AD.decode_descriptor(cands[0]["words"], bos)
        aux_hex = dec.pop("_aux_hex_full", None)
        prefix = "" if not is_pair else f"{label}_"
        out[f"{prefix}compressed"] = dec["compression_flag_word1_b27"]
        out[f"{prefix}aux_layout"] = dec["aux_layout_flag_word3_b31"]
        out[f"{prefix}secondary_va_present"] = dec["secondary_va"] is not None
        out[f"{prefix}main_bytes"] = dec.get("main_image_bytes_measured")
        out[f"{prefix}aux_bytes"] = dec.get("aux_bytes_measured")
        out[f"{prefix}aux_head_hex"] = _short_hex(aux_hex) if aux_hex else None
        out[f"{prefix}n_descriptors_found"] = len(cands)
    return out


def decode_replicate_case(case, dump_dir):
    w, h = case["params"]["w"], case["params"]["h"]
    subs = _dump_subdirs(dump_dir)
    if not subs:
        return {"decode_error": "no dump subdirectories captured"}
    bos = AD.load_bos(str(subs[-1]))
    cands = AD.find_descriptors(bos, w, h, AD.TYPECODE["2d"])
    bvas = sorted(set(c["base_va"] for c in cands))
    if len(bvas) < 2:
        return {"n_found": len(bvas), "deltas_equal": None, "footprint_bytes": None}
    deltas = [bvas[i + 1] - bvas[i] for i in range(len(bvas) - 1)]
    sec = None
    for c in cands:
        wv = c["words"]
        s = (wv[4] | ((wv[5] & 0xfff) << 32)) << 4
        if s:
            sec = s - c["base_va"]
            break
    return {
        "n_found": len(bvas),
        "deltas_equal": len(set(deltas)) == 1,
        "footprint_bytes": deltas[0] if len(set(deltas)) == 1 else None,
        "all_deltas": [hex(d) for d in deltas] if len(set(deltas)) != 1 else None,
        "main_bytes_from_secondary_va": sec,
    }


def expected_aux_bpp(bpp, w, h, samples=1):
    # Valid for tile-aligned sizes only (this experiment's aux_bpp_size / aux_msaa_ratio
    # cases use 64/256 -- both exact tile multiples for every tested bpp, so the
    # sub-tile / column-granule padding rules never engage; see PRE_REGISTRATION.
    return (w * h * samples) // 32


def default_verdict(case, status, fields, decoded):
    kind = case["kind"]
    if status != "OK":
        # texture-creation rejection is a legitimate negative result for elig_storage
        # (memoryless) probes, not a harness failure.
        if kind == "elig_storage" and fields.get("TEX_CREATE_OK") == "0":
            return "N/A"
        return "FAIL"
    if kind in ("elig_usage", "elig_storage", "elig_type", "elig_linear", "elig_boundary"):
        if fields.get("TEX_CREATE_OK") != "1":
            return "N/A"
        if fields.get("BIND_OK") == "0" or fields.get("BIND_STATUS") not in (None, "4") or "decode_error" in decoded:
            # bind/descriptor-capture failed (e.g. memoryless resource rejected by a
            # standalone compute-kernel read) -- a legitimate negative result, not a
            # harness defect, but distinct from a clean PASS observation.
            return "N/A"
        return "PASS"
    if kind == "aux_bpp_size":
        bpp_map = {"r8unorm":1,"r16float":2,"rgba8unorm":4,"r32uint":4,"rgba8uint":4,
                   "rgba16float":8,"rgba32float":16}
        bpp = bpp_map[case["params"]["fmt"]]
        exp = expected_aux_bpp(bpp, case["params"]["w"], case["params"]["h"])
        got = decoded.get("aux_bytes")
        return "PASS" if got == exp else "FAIL"
    if kind == "aux_msaa_ratio":
        n = case["params"].get("samples", 1)
        exp = expected_aux_bpp(4 if case["params"]["fmt"] == "rgba8unorm" else 2,
                                case["params"]["w"], case["params"]["h"], n)
        got = decoded.get("aux_bytes")
        return "PASS" if got == exp else "FAIL"
    if kind == "aux_alloc_floor":
        return "PASS" if decoded.get("deltas_equal") else "FAIL"
    if kind == "aux_mip":
        return "PASS" if decoded.get("compressed") == 1 else "FAIL"
    if kind in ("state_pattern", "state_format_repeat"):
        return "PASS" if decoded.get("compressed") == 1 else "FAIL"
    if kind == "cpu_replace":
        return "PASS" if fields.get("CPU_OP_OK") == "1" else "FAIL"
    if kind == "cpu_getbytes":
        ok = fields.get("CPU_OP_OK") == "1"
        if "GETBYTES_TEXEL00_MATCH" in fields:
            ok = ok and fields["GETBYTES_TEXEL00_MATCH"] == "1"
        return "PASS" if ok else "FAIL"
    if kind == "cpu_blit":
        return "PASS" if fields.get("CPU_OP_OK") == "1" else "FAIL"
    if kind == "cpu_storeaction":
        return "PASS" if status == "OK" else "FAIL"
    return "PASS"


def run_case(case, run_dumps_dir):
    dump_dir = run_dumps_dir / case["id"]
    dump_dir.mkdir(parents=True, exist_ok=True)
    status, fields, out, err, wall, rc = run_cprobe(case["binary_kind"], case["params"], dump_dir)

    decoded = {}
    if status == "OK":
        if case["decode"] == "descriptor":
            # is_pair=False -> decode_descriptor_case already returns unprefixed keys
            # (compressed, aux_layout, secondary_va_present, main_bytes, aux_bytes, ...).
            decoded = decode_descriptor_case(case, dump_dir, is_pair=False)
        elif case["decode"] == "descriptor2":
            decoded = decode_descriptor_case(case, dump_dir, is_pair=True)
        elif case["decode"] == "replicate":
            decoded = decode_replicate_case(case, dump_dir)
        elif case["decode"] == "stdout":
            decoded = {}

    observed = {"fields": {k: coerce(v) for k, v in fields.items()}, "decoded": decoded}
    verdict = default_verdict(case, status, fields, decoded)
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
             "params": case["params"], "status": status, "verdict": verdict, "observed": observed}
    ok, msg = S.validate_gated(gated)
    if not ok:
        raise RuntimeError(f"schema violation for {case['id']}: {msg}")
    ngated = {"case_id": case["id"], "wall_ms": round(wall * 1000, 3), "pid": os.getpid(),
              "raw_tail": (out[-500:] + err[-300:]), "raw_ticks": {}}
    return gated, ngated


def run_smoke():
    """NON-RECORDED smoke gate: one trivial real GPU probe, checked BEFORE any
    raw/ directory is created (standing gate (c))."""
    receipt = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    env = dict(os.environ)
    env["DYLD_INSERT_LIBRARIES"] = str(IOTRACE_DYLIB)
    env["IOTRACE_DUMP_DIR"] = str(EXP / "work" / "_smoke_dump")
    env["IOTRACE_DUMP_PERSIG"] = "1"
    rc, out, err, w = sh([str(CPROBE), "probe",
                          json.dumps({"fmt": "rgba8unorm", "w": 32, "h": 32, "usage": "read",
                                      "pattern": "gradient", "dump": True})], env, 20)
    ok = (rc == 0 and "STATUS OK" in out)
    receipt.update({"rc": rc, "ok": ok, "tail": out[-500:], "err_tail": err[-300:]})
    return ok, receipt


def git_revision():
    try:
        rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              cwd=str(EXP)).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True,
                                cwd=str(EXP)).stdout.strip() != ""
        return rev, dirty
    except Exception:
        return None, None


def sha256_file(path):
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def authored_files():
    return ["harness/schema.py", "harness/casematrix.py", "harness/run.py", "harness/verify.py",
            "harness/auxdecode.py", "harness/cprobe.m"]


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

    if not CPROBE.exists() or not IOTRACE_DYLIB.exists():
        print(f"FAIL: build work/bin/cprobe and work/iotrace.dylib first (see README.md)", file=sys.stderr)
        sys.exit(2)

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
    run_dumps_dir = work_dir / "dumps" / args.run
    run_dumps_dir.mkdir(parents=True, exist_ok=True)

    gated_f = open(out_dir / "02_gated.jsonl", "a")
    nongated_f = open(out_dir / "03_nongated.jsonl", "a")
    counts = {"PASS": 0, "FAIL": 0, "N/A": 0}
    for i, case in enumerate(CM.MATRIX):
        try:
            gated, ngated = run_case(case, run_dumps_dir)
        except Exception as e:
            gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
                      "params": case["params"], "status": "HARNESS_CRASH", "verdict": "FAIL",
                      "observed": {}}
            ngated = {"case_id": case["id"], "wall_ms": None, "pid": os.getpid(),
                      "raw_tail": repr(e)[:600], "raw_ticks": {}}
        gated_f.write(json.dumps(gated, sort_keys=True) + "\n"); gated_f.flush()
        nongated_f.write(json.dumps(ngated, sort_keys=True) + "\n"); nongated_f.flush()
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
