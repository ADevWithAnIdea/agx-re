#!/usr/bin/env python3
"""Regenerate CAPTURE_CONTRACT.json from the authored blobs actually on disk.

Run on the REPO HOST (the M4), never on the neo. It hashes every authored input
so a capture is valid iff those hashes match -- repo HEAD moving because a
sibling experiment landed is NOT contamination (SUBAGENT_BRIEF).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*a):
    return subprocess.run(["git"] + list(a), cwd=str(EXP), stdout=subprocess.PIPE
                          ).stdout.decode().strip()


blobs = {}
for pat in ("harness/*.py", "harness/*.m", "harness/sync.sh", "kernels/*.metal",
            "kernels/census/*.metal", "analysis/*.py",
            "work/frozen/db.json", "work/frozen/isadb.py"):
    for p in sorted(EXP.glob(pat)):
        blobs[str(p.relative_to(EXP))] = sha(p)

try:
    import cases as CM
    add = json.loads((EXP / "work" / "addendum.json").read_text())
    cs = CM.build_cases(add)
    matrix = {"generator": "harness/cases.py build_cases()",
              "n_cases": len(cs), "sha256": CM.matrix_sha256(cs),
              "arms": CM.summarize(cs),
              "addendum_used": {k: v for k, v in add.items()
                                if not k.startswith("_")},
              "addendum_provisional": "_PROVISIONAL" in add}
except Exception as e:
    matrix = {"error": repr(e)}

contract = {
 "experiment": "EXP-0179-g17p-call",
 "question": ("Can this ISA make a NON-INLINED CALL, and can we EMIT one -- generate a "
              "call, a callee and a return from the rules, with zero bytes copied from "
              "any compiled shader, and have the hardware execute and return? Then: what "
              "do call.b3/.b5/.b6/.tail and ret.scoreboard actually do?"),
 "gap": ("docs/P0-P1-CLOSURE.md P0.8 ranked blocker #2 (EXP-0177 analysis/p08_gaps.md G2): "
         "call.{b3,b5,b6,tail} are tokenization-only and ret.scoreboard was declined in "
         "advance, so NO CALL CAN BE EMITTED -- which blocks EXP-0137's split-epilog "
         "contract, every out-of-line helper, and non-leaf frames."),
 "frozen_utc": None,
 "authored_blobs": blobs,
 "case_matrix": matrix,
 "clean_room": {
   "provenance": "OWN-SHADER + HW-PROBE",
   "apple_binary_introspection": "NONE",
   "instruction_under_test": ("GENERATED from the pinned db.json's declared bit geometry "
                              "by isa_helpers.call_bytes()/ret_bytes(); ZERO bytes copied "
                              "from any compiled shader. Arm S additionally mutates a REAL "
                              "compiler-emitted call inside OUR OWN compiled program, as an "
                              "independent second method, labelled as such."),
   "declared_boundary": ("Apple's inlining heuristic is a DECLARED CLEAN-ROOM BOUNDARY "
                         "(docs/P0-P1-CLOSURE.md P0.8) and is NOT characterised. The census "
                         "authors OUR OWN MSL until the instruction appears and reports "
                         "per-construct outcomes only -- no threshold, no interpolation, no "
                         "claim about why anything inlined, and no Apple binary inspected."),
 },
 "environment": {
   "grid": 1, "threadgroup": 1, "fast_math": False,
   "poison": "0xDEADBEEF over all 104 output words before every dispatch",
   "seed_method": ("mov_imm immediates ONLY. device_load is FORBIDDEN on every verdict path "
                   "(DEF-0169-1: device_load is ASYNCHRONOUS on G17P and fabricates "
                   "movement); it appears only in arm O, where that asynchrony is the "
                   "instrument and promotion is pre-declined."),
   "baseline_use": ("The unmutated program is re-run periodically for RUN INTEGRITY only. "
                    "NO case is scored against it -- every oracle is host-computed from "
                    "isa_helpers.SEED_I and the frozen layout."),
 },
 "observable": {
   "dump": "16 GPR stores in a FIXED order, byte-identical in every case of every arm",
   "sentinels": "PRE (written before the call) and POST (written after it returns)",
   "breadcrumb": ("W_CALLEE -- a store made INSIDE the callee, so 'ran but never returned' "
                  "survives a caller-side dump that never executes"),
   "landing_ladder": ("4 x 2-byte mov_imm rungs before the callee entry; the lowest rung "
                      "that fired localises a mis-targeted branch to 2 bytes"),
   "tail_poison": "28 words never stored to; any change is invalid_sentinel",
   "rule_3a": ("STRUCTURAL, not careful: neither `call` nor `ret` declares a register-typed "
               "field, so no swept value can name the read-back index register, any store's "
               "data register, the sentinel registers, or the callee register."),
 },
 "gate": {
   "runs": ["run01 forward", "run02 reverse"],
   "carriers_for_hardware_run": 2,
   "carrier_dimension": ("execution-mask stack depth at the call (flat vs one if_push deep) "
                         "-- the dimension H4 says these fields control. Two carriers "
                         "differing only in the register plan would be ONE carrier."),
   "cross_run_agreement_min": 0.99,
   "movement_over_disagreement_min": 2.0,
   "cases_counted": "validity == 'valid' only",
   "falsifiers_must_fire_every_run": True,
   "rt_ok": "RECORDED AND USED FOR NOTHING (FIELD-SWEEP-PROTOCOL 3b)",
 },
 "pinned_toolchain": {
   "path": "work/frozen/",
   "db.json": sha(EXP / "work" / "frozen" / "db.json"),
   "isadb.py": sha(EXP / "work" / "frozen" / "isadb.py"),
   "resolution": ("isa_helpers._find_isadb() has EXACTLY ONE candidate and NO path-search "
                  "fallback; it raises if the pin is absent. The neo's shared "
                  "~/agxre/tools/agx-isa/db.json is STALE and silently resolved for another "
                  "experiment on 2026-08-30."),
 },
 "calibration": {
   "phase": "PRE-FREEZE, raw/prefreeze/**, NEVER EVIDENCE",
   "closed_list": ["extmode_or", "marker", "reconverge", "region_len", "jumpover_ok"],
   "written_to": "work/addendum.json",
   "note": ("These five are the ONLY parameters calibration may decide "
            "(PRE_REGISTRATION section 8). run.py REFUSES to dispatch while the "
            "placeholder addendum is present."),
 },
 "raw_schema": {
   "raw/prefreeze/census_<id>/00_meta.json": "census environment + kernel hashes",
   "raw/prefreeze/census_<id>/census.jsonl": "one record per authored MSL construct",
   "raw/prefreeze/calib_<id>/00_env.json": "device identity + measured region geometry",
   "raw/prefreeze/calib_<id>/calib.jsonl": "every calibration dispatch",
   "raw/prefreeze/calib_<id>/01_calibration.json": "the five calibrated parameters",
   "raw/<run>/00_env.json": ("device identity, region geometry, every authored blob hash, "
                             "the plans, the seed table, the marker values, the word layout"),
   "raw/<run>/01_gpuwatch_start.json": "concurrent GPU/compiler process sample at run start",
   "raw/<run>/02_gpuwatch_end.json": "the same at run end",
   "raw/<run>/03_summary.json": "case count, hangs, stopped arms, dispatch count, elapsed",
   "raw/<run>/baseline.jsonl": "unmutated-program dumps -- RUN INTEGRITY ONLY, never an oracle",
   "raw/<run>/sweep.jsonl": "one FIELD-SWEEP-PROTOCOL section-4 record per case, append-only, flushed+fsynced",
 },
 "timeouts": {"per_request_s": 8.0, "retries_majority_of": 3,
              "hang_cooldown_s": 2.0, "max_hangs_per_arm": 2,
              "shdump_s": 300, "ssh_alarm_s": "120-1800 per sync.sh verb"},
 "safety": {
   "hang_budget": ("2 per arm -> the arm STOPS and is reported PARTIAL. Arms N (depth-2, no "
                   "link save) and the positive half of arm T are DECLARED HANG CANDIDATES "
                   "and are announced in PROGRESS.md before they run."),
   "contiguous_hazard": ("FIELD-SWEEP-PROTOCOL 3(c): a per-value budget CANNOT characterise a "
                         "contiguous hazard. If adjacent values hang, a NAMED non-gated "
                         "mapping pass (`--hang-tolerant`, run id containing MAPPING_) is "
                         "dispatched over the whole range and reported separately."),
   "if_the_neo_stops_answering": "STOP and report BLOCKED. No scanning. No macvdmtool.",
 },
 "target": {
   "name": "users-MacBook-Neo.local", "soc": "T8140",
   "gpu": "G17P / AGXAcceleratorG17P", "arch": "applegpu_g17p",
   "note": ("device identity is READ FROM THE LIVE DEVICE into 00_env.json on every run and "
            "is never taken from this literal"),
 },
 "repo_revision_at_freeze": {
   "head": git("rev-parse", "HEAD"),
   "dirty": bool(git("status", "--porcelain")),
   "note": ("A capture is valid if the AUTHORED BLOB HASHES above match. HEAD moving because "
            "a sibling experiment landed is NOT contamination (SUBAGENT_BRIEF)."),
 },
}
# Amendments and calibration outcomes are APPEND-ONLY: a regeneration must never
# silently drop them. Anything not in the generated key set is carried forward.
out = EXP / "CAPTURE_CONTRACT.json"
if out.exists():
    prev = json.loads(out.read_text())
    for k, v in prev.items():
        if k not in contract:
            contract[k] = v
try:
    contract["calibration"]["outcome"] = json.loads(
        (EXP / "work" / "addendum.json").read_text())
except Exception:
    pass
out.write_text(json.dumps(contract, indent=1, sort_keys=True))
print("wrote", out, "blobs:", len(blobs), "cases:", matrix.get("n_cases"))
