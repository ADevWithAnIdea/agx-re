#!/usr/bin/env python3
"""EXP-0158 whole-tree artifact manifest and frozen capture contract.

--check     pre-GPU: every authored file present and hashed.
--write     post-capture: adds the raw/ tree hashes.
--contract  writes CAPTURE_CONTRACT.json -- the frozen contract, including the
            PINNED ISA snapshot hashes and the frozen-pilot evidence hash.

Architecture from EXP-0112's own make_manifest.py (our own code).
"""
import argparse, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as RUN  # noqa: E402


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


ALL_AUTH = None


def build(include_raw):
    m = {"schema": 2, "target": "G17P",
         "authored_code_sha256": {f: sha(HERE / f) for f in RUN.AUTH_CODE},
         "authored_kernel_sha256": {f: sha(HERE / f) for f in RUN.AUTH_KERNELS},
         "authored_doc_sha256": {f: sha(HERE / f) for f in RUN.AUTH_DOC},
         "pinned_isa_sha256": {f: sha(HERE / f) for f in RUN.AUTH_PINNED}}
    if include_raw:
        raw = {}
        for rid in RUN.RUNS:
            d = HERE / "raw" / rid
            if d.exists():
                raw[rid] = {p.name: sha(p) for p in sorted(d.glob("*")) if p.is_file()}
        m["raw_sha256"] = raw
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--contract", action="store_true")
    a = ap.parse_args()
    if a.check:
        m = build(include_raw=False)
        missing = [f for f in RUN.AUTH_CODE + RUN.AUTH_KERNELS + RUN.AUTH_DOC + RUN.AUTH_PINNED
                   if not (HERE / f).exists()]
        if missing:
            print("MISSING:", missing)
            sys.exit(1)
        print("manifest --check: PASS (%d authored files present)" %
              (len(RUN.AUTH_CODE) + len(RUN.AUTH_KERNELS) + len(RUN.AUTH_DOC)
               + len(RUN.AUTH_PINNED)))
        return
    if a.contract:
        import casematrix as CM
        import frozen_pilot as FP
        m = build(include_raw=False)
        m.update({
            "experiment": "EXP-0158-g17p-generator-synthesis",
            "target": {"soc": "T8140", "gpu": "G17P / AGXAcceleratorG17P",
                       "arch": "applegpu_g17p", "cores": 5, "os": "macOS 26.6",
                       "metal_family": "Apple9", "host": "192.168.10.243"},
            "run_ids_append_only": list(RUN.RUNS),
            "n_cases": len(CM.build_cases()),
            "timeouts_seconds": {"agxrun_dispatch": 20, "agxtest_invocation": 45,
                                 "case_exec_subprocess": RUN.CASE_TIMEOUT,
                                 "gate": 900},
            "cascade_witness_every_n_cases": RUN.CASCADE_EVERY,
            "revalidation_extra_attempts": RUN.REVALIDATE_EXTRA,
            "revalidated_outcomes": list(RUN.REVALIDATE_OUTCOMES),
            "frozen_pilot": {"frozen": FP.FROZEN, "run_id": FP.PILOT_RUN_ID,
                             "jsonl_sha256": FP.PILOT_JSONL_SHA256,
                             "INLINE_NEG0_SIGN": FP.INLINE_NEG0_SIGN,
                             "INLINE_NEG_WORKS": FP.INLINE_NEG_WORKS,
                             "FALU2_MODHI_OK_ALU": FP.FALU2_MODHI_OK_ALU,
                             "FALU2_MODHI_OK_LOAD": FP.FALU2_MODHI_OK_LOAD},
            "raw_schema": ["00_env.json", "01_results.jsonl", "01_timing.jsonl",
                           "02_dispatch.json", "03_cascade.jsonl", "04_revalidate.jsonl"],
            "gate": ["frozen_pilot.FROZEN", "verify.py --selftest",
                     "verify.py --seqtest", "verify.py --preflight|--between-runs",
                     "baseline.py", "non-recorded smoke case",
                     "01_results.jsonl byte-identical across both runs"],
            "clean_room": {"category": ["OWN-SHADER", "HW-PROBE"],
                           "apple_binary_introspection": "NONE",
                           "boundary": RUN.BOUNDARY}})
        (HERE / "CAPTURE_CONTRACT.json").write_text(
            json.dumps(m, indent=2, sort_keys=True) + "\n")
        print("wrote CAPTURE_CONTRACT.json")
        return
    m = build(include_raw=True)
    (HERE / "manifest.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    print("wrote manifest.json")


if __name__ == "__main__":
    main()
