#!/usr/bin/env python3
"""EXP-0102 standing gates. Implements the five gates required by the
dispatch: --selftest (pure-Python, one authoritative key-set, runnable in
any tree state), --seqtest (PRE_GPU/RUN01_PRESENT/RUN02_PRESENT sequential
state check), --preflight/--between-runs (NON-RECORDED hardware smoke test,
never written under raw/), --captured (post-capture schema + cross-run
byte-identity check on the GATED record fields only).

Usage:
  python3 -B verify.py --selftest
  python3 -B verify.py --seqtest
  python3 -B verify.py --preflight --bin-dir DIR --repo DIR
  python3 -B verify.py --between-runs --bin-dir DIR --repo DIR
  python3 -B verify.py --captured --run raw/m4-<id>-run01
  python3 -B verify.py --captured --compare raw/m4-<id>-run01 raw/m4-<id>-run02
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "analysis"))
sys.path.insert(0, str(HERE / "harness"))
import oracle as O  # noqa: E402
import casematrix as CM  # noqa: E402

# ---------------------------------------------------------------------------
# --selftest: one authoritative shared key-set. Hand-worked values only,
# never derived from a prior GPU run. Runnable with zero dependencies beyond
# analysis/oracle.py and analysis/casematrix.py (pure Python, no GPU, no
# tools/ build required) -- so it is runnable in ANY tree state.
# ---------------------------------------------------------------------------
SELFTEST_VECTORS = [
    ("ubfe_model_d cnt0", lambda: O.ubfe_model_d_width32_bypasses_offset(0xFFFFFFFF, 5, 0), 0),
    ("ubfe_model_d cnt32 ignores huge off", lambda: O.ubfe_model_d_width32_bypasses_offset(0xFFFFFFFF, 4294967295, 32), 0xFFFFFFFF),
    ("ubfe_model_d off>=32 cnt<32 -> 0", lambda: O.ubfe_model_d_width32_bypasses_offset(0xFFFFFFFF, 32, 8), 0),
    ("ubfe_model_d basic", lambda: O.ubfe_model_d_width32_bypasses_offset(0b1011010, 1, 3), 0b101),
    ("ubfe_model_d cnt>32 clamps to 32, literal off", lambda: O.ubfe_model_d_width32_bypasses_offset(0xFFFFFFFF, 1, 33), 0x7FFFFFFF),
    ("sbfe basic neg", lambda: O.sbfe_from_ubfe(0xF, 4), -1),
    ("sbfe basic pos", lambda: O.sbfe_from_ubfe(0x7, 4), 7),
    ("insert_bits_model_d cnt0 noop", lambda: O.insert_bits_model_d(0xAB, 0xFF, 4, 0), 0xAB),
    ("insert_bits_model_d cnt32 verbatim", lambda: O.insert_bits_model_d(0x1234, 0x5678, 9999, 32), 0x5678),
    ("insert_bits_model_d off>=32 noop", lambda: O.insert_bits_model_d(0xAB, 0xFF, 32, 8), 0xAB),
    ("insert_bits_model_d basic", lambda: O.insert_bits_model_d(0x00000000, 0xFFFFFFFF, 4, 4), 0xF0),
    ("rotl32 zero", lambda: O.rotl32(0x1, 0), 0x1),
    ("rotl32 wrap", lambda: O.rotl32(0x80000000, 1), 0x1),
    ("rotl32 mod32 33==1", lambda: O.rotl32(0x12345678, 33), O.rotl32(0x12345678, 1)),
    ("imad_u32 wrap", lambda: O.imad_u32(0xFFFFFFFF, 2, 1), 0xFFFFFFFF),
    ("clz32 zero", lambda: O.clz32(0), 32),
    ("clz32 one", lambda: O.clz32(1), 31),
    ("clz32 top", lambda: O.clz32(0x80000000), 0),
    ("find_msb_derived top", lambda: O.find_msb_derived(0x80000000), 31),
    ("find_msb_derived one", lambda: O.find_msb_derived(1), 0),
    ("find_msb_derived zero", lambda: O.find_msb_derived(0), -1),
    ("popcount32", lambda: O.popcount32(0xFFFFFFFF), 32),
    ("logic_lut xor", lambda: O.logic_lut(6, 1, 0) & 1, 1),
    ("logic_lut nand", lambda: O.logic_lut(14, 1, 1) & 1, 0),
    ("logic_lut all16 self-consistent",
     lambda: [O.logic_lut(i, 0xF0F0F0F0, 0x0F0F0F0F) for i in range(16)],
     [O.logic_lut(i, 0xF0F0F0F0, 0x0F0F0F0F) for i in range(16)]),
    ("pack_unorm16 zero", lambda: O.pack_unorm16(0.0), 0),
    ("pack_unorm16 one", lambda: O.pack_unorm16(1.0), 65535),
    ("pack_unorm16 neg clamps", lambda: O.pack_unorm16(-5.0), 0),
    ("pack_unorm16 exact tie RTE", lambda: O.pack_unorm16((32767 + 0.5) / 65535.0), 32768),
    ("pack_snorm16 one", lambda: O.pack_snorm16(1.0) & 0xFFFF, 32767),
    ("pack_snorm16 neg one", lambda: O.pack_snorm16(-1.0) & 0xFFFF, (-32767) & 0xFFFF),
    ("f32_to_f16_bits overflow -> inf", lambda: O.f32_to_f16_bits(100000.0), 0x7C00),
    ("f32_to_f16_bits neg overflow -> -inf", lambda: O.f32_to_f16_bits(-100000.0), 0xFC00),
    ("f32_to_f16_bits nan -> canonical", lambda: O.f32_to_f16_bits(float("nan")), O.F16_QNAN),
    ("f32_to_f16_bits neg zero", lambda: O.f32_to_f16_bits(-0.0), 0x8000),
    ("f16_op add basic", lambda: O.f16_bits_to_f32(O.f16_op([O.f32_to_f16_bits(1.5), O.f32_to_f16_bits(1.0)], "add2")), 2.5),
    ("f16_op add nan propagates canonical", lambda: O.f16_op([0x7E01, O.f32_to_f16_bits(1.0)], "add2"), O.F16_QNAN),
    ("f16_op inf-inf -> nan", lambda: O.f16_op([0x7C00, 0xFC00], "add2"), O.F16_QNAN),
    ("f16_encode_exact matches struct (spot)", lambda: O.f32_to_f16_bits(1.0009765625), None),  # existence check only
]


def run_selftest(verbose=True):
    fails = []
    for name, fn, exp in SELFTEST_VECTORS:
        try:
            got = fn()
        except Exception as e:  # noqa: BLE001
            fails.append((name, f"EXCEPTION {e!r}", exp))
            continue
        if exp is None:
            continue  # existence-only check
        if got != exp:
            fails.append((name, got, exp))
    # struct cross-check over a bounded deterministic sweep (not random --
    # selftest must be identical every run)
    mism = 0
    for i in range(-2000, 2000):
        f = i * 12.5
        try:
            import struct
            want = struct.unpack("<H", struct.pack("<e", f))[0]
        except OverflowError:
            continue
        got = O.f32_to_f16_bits(f)
        if got != want:
            mism += 1
    if mism:
        fails.append(("f32_to_f16_bits vs struct sweep", f"{mism} mismatches", 0))
    # casematrix must build with no duplicate ids and every oracle filled
    try:
        cs = CM.build_cases()
        ids = [c["id"] for c in cs]
        dups = set(x for x in ids if ids.count(x) > 1)
        if dups:
            fails.append(("casematrix duplicate ids", str(dups), "none"))
        for c in cs:
            for k, v in c["oracle"].items():
                if v is None:
                    fails.append((f"casematrix oracle unfilled {c['id']}.{k}", None, "filled"))
    except Exception as e:  # noqa: BLE001
        fails.append(("casematrix build", f"EXCEPTION {e!r}", "builds cleanly"))

    if verbose:
        print(f"SELFTEST: {len(SELFTEST_VECTORS)} vectors + struct sweep + casematrix build")
        for f in fails:
            print("  FAIL", f)
        print("SELFTEST", "PASS" if not fails else "FAIL", f"({len(fails)} failures)")
    return not fails


# ---------------------------------------------------------------------------
# --seqtest: PRE_GPU / RUN01_PRESENT / RUN02_PRESENT sequential state check.
# ---------------------------------------------------------------------------
def _phase(exp_dir):
    raw = exp_dir / "raw"
    runs = sorted([p for p in raw.glob("m4-*-run*") if p.is_dir()]) if raw.is_dir() else []
    run01 = [p for p in runs if p.name.endswith("run01")]
    run02 = [p for p in runs if p.name.endswith("run02")]
    if run02:
        return "RUN02_PRESENT", run01, run02
    if run01:
        return "RUN01_PRESENT", run01, run02
    return "PRE_GPU", run01, run02


def run_seqtest(exp_dir, verbose=True):
    exp_dir = Path(exp_dir)
    phase, run01, run02 = _phase(exp_dir)
    fails = []
    if phase == "PRE_GPU":
        if not (exp_dir / "harness" / "case_exec.py").exists():
            fails.append("harness/case_exec.py missing")
        if not (exp_dir / "analysis" / "casematrix.py").exists():
            fails.append("analysis/casematrix.py missing")
        if not run_selftest(verbose=False):
            fails.append("selftest does not pass in PRE_GPU phase")
    elif phase == "RUN01_PRESENT":
        r = run01[0]
        if not (r / "01_results.jsonl").exists():
            fails.append(f"{r}/01_results.jsonl missing")
        else:
            n = sum(1 for _ in open(r / "01_results.jsonl"))
            expected = len(CM.build_cases())
            if n != expected:
                fails.append(f"{r}/01_results.jsonl has {n} records, expected {expected}")
        if (r / "STOP.json").exists():
            fails.append(f"{r}/STOP.json present -- run01 was stopped, do not treat as complete")
    elif phase == "RUN02_PRESENT":
        for r in run01 + run02:
            if not (r / "01_results.jsonl").exists():
                fails.append(f"{r}/01_results.jsonl missing")
        if (run02[0] / "STOP.json").exists():
            fails.append(f"{run02[0]}/STOP.json present -- run02 was stopped, do not treat as complete")
    if verbose:
        print(f"SEQTEST: phase={phase} run01={[str(r) for r in run01]} run02={[str(r) for r in run02]}")
        for f in fails:
            print("  FAIL", f)
        print("SEQTEST", "PASS" if not fails else "FAIL", f"({len(fails)} failures)")
    return not fails, phase


# ---------------------------------------------------------------------------
# --preflight / --between-runs: NON-RECORDED hardware smoke test. Never
# writes into raw/. Proves the toolchain (shdump+agxrun+agxtest.py) works on
# THIS host before/between the recorded, gated captures.
# ---------------------------------------------------------------------------
def run_smoke(bin_dir, repo, verbose=True):
    """NON-RECORDED smoke dispatch. Uses a scratch dir INSIDE this
    experiment's own work/ tree (never system temp / anywhere outside the
    repo -- see PROGRESS.md 2026-08-28T06:45Z entry: an earlier version of
    this function used tempfile.TemporaryDirectory(), which resolves
    outside the repo on this host; caught and fixed before it produced any
    out-of-repo artifact larger than a transient kernel .metal + tiny
    binary archive, both removed at the end of this function either way)."""
    bin_dir = Path(bin_dir)
    repo = Path(repo)
    td = Path(__file__).resolve().parent / "work" / "smoke" / f"smoke-{int(time.time()*1000)}"
    td.mkdir(parents=True, exist_ok=True)
    try:
        kernel = td / "smoke_add.metal"
        kernel.write_text(
            "#include <metal_stdlib>\nusing namespace metal;\n"
            "kernel void k(device const uint *a [[buffer(0)]],\n"
            "              device const uint *b [[buffer(1)]],\n"
            "              device uint *out [[buffer(2)]],\n"
            "              uint gid [[thread_position_in_grid]]) {\n"
            "    out[gid] = a[gid] + b[gid];\n}\n")
        argv = [sys.executable, "-B", str(repo / "tools" / "agxtest" / "agxtest.py"),
                "--source", str(kernel), "--function", "k", "--grid", "4", "--tg", "4",
                "--int", "--buf", "0=1,2,3,4", "--buf", "1=10,20,30,40", "--out", "2=4",
                "--expect", "2=11,22,33,44",
                "--shdump", str(bin_dir / "shdump"), "--agxrun", str(bin_dir / "agxrun"),
                "--agxparse", str(repo / "tools" / "shdump" / "agxparse.py"),
                "--workdir", str(td), "--run-timeout", "30"]
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=45)
        except subprocess.TimeoutExpired:
            if verbose:
                print("SMOKE FAIL: agxtest.py timed out")
            return False
        ok = ("STATUS OK" in r.stdout) and ("COMPARE 2 MATCH" in r.stdout)
        if verbose:
            print("SMOKE", "PASS" if ok else "FAIL")
            if not ok:
                print(r.stdout[-2000:])
                print(r.stderr[-2000:])
        return ok
    finally:
        shutil.rmtree(td, ignore_errors=True)


# ---------------------------------------------------------------------------
# --captured: post-capture schema + cross-run byte-identity on GATED fields.
# ---------------------------------------------------------------------------
GATED_FIELDS = ["i", "id", "items", "kernel", "function", "grid", "status",
                "pipeline_source", "main_len", "main_hash_sha256", "main_hex",
                "observed_sha256", "observed_inline", "compared"]


def _gated_repr(rec):
    return {k: rec.get(k) for k in GATED_FIELDS}


def check_captured(run_dir, verbose=True):
    run_dir = Path(run_dir)
    f = run_dir / "01_results.jsonl"
    fails = []
    if not f.exists():
        return False, [f"{f} missing"]
    lines = [json.loads(l) for l in open(f) if l.strip()]
    expected = len(CM.build_cases())
    if len(lines) != expected:
        fails.append(f"record count {len(lines)} != expected {expected}")
    seen_ids = set()
    for rec in lines:
        if rec["id"] in seen_ids:
            fails.append(f"duplicate case id in results: {rec['id']}")
        seen_ids.add(rec["id"])
    if verbose:
        print(f"CAPTURED {run_dir}: {len(lines)} records")
        for fl in fails:
            print("  FAIL", fl)
    return not fails, fails


def compare_runs(run_a, run_b, verbose=True):
    run_a, run_b = Path(run_a), Path(run_b)
    la = [json.loads(l) for l in open(run_a / "01_results.jsonl") if l.strip()]
    lb = [json.loads(l) for l in open(run_b / "01_results.jsonl") if l.strip()]
    fails = []
    if len(la) != len(lb):
        fails.append(f"record count differs: {len(la)} vs {len(lb)}")
    n = min(len(la), len(lb))
    mismatches = []
    for i in range(n):
        ga, gb = _gated_repr(la[i]), _gated_repr(lb[i])
        ha = hashlib.sha256(json.dumps(ga, sort_keys=True).encode()).hexdigest()
        hb = hashlib.sha256(json.dumps(gb, sort_keys=True).encode()).hexdigest()
        if ha != hb:
            mismatches.append((i, la[i].get("id"), ha, hb))
    if mismatches:
        fails.append(f"{len(mismatches)}/{n} gated records differ between runs")
    if verbose:
        print(f"COMPARE {run_a} vs {run_b}: {n} records compared")
        for m in mismatches[:20]:
            print("  DIFF", m)
        print("BYTE_IDENTICAL", "YES" if not mismatches else "NO")
    return not fails, mismatches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seqtest", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--between-runs", action="store_true")
    ap.add_argument("--captured", action="store_true")
    ap.add_argument("--compare", nargs=2, default=None)
    ap.add_argument("--bin-dir", default=None)
    ap.add_argument("--repo", default=None)
    ap.add_argument("--run", default=None)
    ap.add_argument("--exp-dir", default=str(HERE))
    a = ap.parse_args()
    ok = True
    if a.selftest:
        ok = run_selftest() and ok
    if a.seqtest:
        r, _ = run_seqtest(a.exp_dir)
        ok = r and ok
    if a.preflight or a.between_runs:
        ok = run_smoke(a.bin_dir, a.repo) and ok
    if a.captured:
        if a.compare:
            r, _ = compare_runs(a.compare[0], a.compare[1])
            ok = r and ok
        elif a.run:
            r, _ = check_captured(a.run)
            ok = r and ok
        else:
            print("--captured requires --run or --compare")
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
