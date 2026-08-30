#!/usr/bin/env python3
"""EXP-0200 freeze/refresh of CAPTURE_CONTRACT.json, plus the ENCODING RE-DERIVATION.

  python3 analysis/contract200.py freeze     # write the contract
  python3 analysis/contract200.py check      # re-hash; non-zero on any drift
  python3 analysis/contract200.py encodings  # re-derive words200's byte constants

`encodings` exists because a hand-transcribed opcode is exactly the kind of
constant that drifts silently: it re-derives every fixed encoding in
`harness/words200.py` from the PINNED descriptor's own `match` constraints and
FAILS LOUD on a mismatch, rather than trusting the transcription. It also
asserts that every fill in the frozen catalogue is a DISTINCT byte string --
the aliased-sweep trap, where `match`-pinned bits the assembler cannot clear
make nominally different values assemble to identical bytes and the oracle then
describes a program that never ran.

The contract records the repo revision AT PRE-REGISTRATION TIME and captures are
compared against THAT recorded value, not against live `HEAD`: the orchestrator
commits sibling experiments continuously and a gate written as "HEAD must not
move" aborts mid-sequence through no fault of this experiment (EXP-0082).
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))

FILES = ["PRE_REGISTRATION.md", "README.md", "run200.py",
         "harness/carriers200.py", "harness/locate200.py",
         "harness/words200.py", "harness/sync200.sh",
         "harness/verify_remote200.py", "harness/arms200.json",
         "analysis/census200.py", "analysis/gen_arms200.py",
         "analysis/verdicts200.py", "analysis/contract200.py",
         "analysis/ledger200.py", "analysis/reverse_arms.py",
         "harness/arms187_reversed.json",
         "kernels/k_w200.metal"]
# Target 1 is EXP-0187's apparatus carried in VERBATIM. Every one of these is
# hashed here as well, and `harness/verify_remote200.py` additionally checks
# them against EXP-0187's OWN CAPTURE_CONTRACT.json -- if they differ, this is
# not that contract honoured unchanged and must not be reported as such.
T1 = ["t1/run.py", "t1/PRE_REGISTRATION.md", "t1/README.md",
      "t1/CAPTURE_CONTRACT.json",
      "t1/harness/carriers187.py", "t1/harness/locate187.py",
      "t1/harness/saferunner187.py", "t1/harness/sync.sh",
      "t1/harness/verify_remote.py", "t1/harness/agxrun_persist_as.m",
      "t1/harness/arms187.json",
      "t1/analysis/census.py", "t1/analysis/census2.py",
      "t1/analysis/gen_arms.py", "t1/analysis/verdicts.py",
      "t1/analysis/contract.py", "t1/analysis/single_run_summary.py",
      "t1/kernels/k_rq187.metal", "t1/kernels/k_cube187.metal",
      "t1/kernels/k_cf187.metal", "t1/kernels/k_mesh187.metal",
      "t1/pinned/db.json", "t1/pinned/isadb.py", "t1/pinned/agxparse.py",
      "t1/pinned/persistrun.py", "t1/pinned/saferunner.py",
      "t1/pinned/shdump.m", "t1/pinned/shdump_mesh.m",
      "t1/pinned/mesh_extract.py"]

V1 = EXP / "raw" / "prefreeze" / "CAPTURE_CONTRACT.v1.json"


def sha(p):
    q = EXP / p
    return hashlib.sha256(q.read_bytes()).hexdigest() if q.exists() else "ABSENT"


def build():
    rev = subprocess.check_output(["git", "-C", str(EXP), "rev-parse", "HEAD"],
                                  text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(EXP), "status",
                                     "--porcelain"], text=True).strip()
    prereg_rev, prereg_dirty = rev, len(dirty.splitlines())
    if V1.exists():
        v1 = json.loads(V1.read_text())
        prereg_rev = v1["repo_revision_at_pre_registration"]
        prereg_dirty = v1["repo_dirty_paths_at_pre_registration"]
    return {
        "experiment": "EXP-0200-cfrt-word-instruction-hw",
        "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo_revision_at_last_freeze": rev,
        "repo_dirty_paths_at_last_freeze": len(dirty.splitlines()),
        "repo_revision_at_pre_registration": prereg_rev,
        "repo_dirty_paths_at_pre_registration": prereg_dirty,
        "gate_note": "captures are compared against the RECORDED revision "
                     "above, never against live HEAD (SUBAGENT_BRIEF / EXP-0082)",
        "authored_sha256": {f: sha(f) for f in FILES + T1},
        "target1_is_exp0187_contract_unchanged": True,
        "target": {"device": "Apple A18 Pro / G17P", "arch": "applegpu_g17p",
                   "cores": 5, "family": "Apple9", "os": "macOS 26.6",
                   "host": "users-MacBook-Neo.local", "ip": "192.168.170.254"},
        "remote_workdir": "~/agxre/EXP-0200",
        "timeouts_s": {"request_compute": 8.0, "request_rt": 10.0,
                       "shdump": 600, "ssh_connect": 15,
                       "run_wall_clock_watchdog": 3600},
        "gate": {
            "gated_runs": 2,
            "per_value_cross_run_agreement_min_pct": 99.0,
            "movement_rule": "moved >= 2 * disagree AND moved >= 1",
            "movement_rule_note": "NOT `moved >= 2 * max(disagree,1)`: that form "
                                  "silently cannot promote any width-1 field "
                                  "(protocol 5b).",
            "measurement_failure_max_pct": 1.0,
            "hang_budget": None,
            "hang_budget_note": "DELIBERATELY ABSENT. FIELD-SWEEP-PROTOCOL 3(c): "
                                "a per-field hang budget cannot characterise a "
                                "CONTIGUOUS hazard -- it guarantees the region "
                                "is never mapped. Every fill is dispatched.",
        },
        "raw_schema": ["carrier", "arm", "instr", "field", "value", "fill_id",
                       "bytes", "hole_off", "hole_len", "token", "observed",
                       "oracle", "predict", "match", "outcome", "status",
                       "statuses", "fault_classes", "innocent_retries", "role",
                       "note", "ts"],
        "outcomes": ["ok", "not_written", "silent_zero", "wrong_value", "fault",
                     "hang", "invalid_run", "nondeterministic",
                     "measurement_failure", "carrier_ready",
                     "carrier_start_failed"],
    }


def encodings():
    import locate200 as L
    import words200 as W
    bad = []

    def cmp(name, mnemonic, got, overrides=None):
        try:
            want = L.descriptor_bytes(mnemonic, overrides)
        except KeyError:
            bad.append("%s: %s not in the pinned db" % (name, mnemonic))
            return
        if bytes(got) != want:
            bad.append("%s: words200 has %s, pinned descriptor gives %s"
                       % (name, bytes(got).hex(), want.hex()))
        else:
            print("  OK %-14s %-14s %s" % (name, mnemonic, want.hex()))

    cmp("STOP4", "stop", W.STOP4)
    cmp("MOV2", "mov_imm", W.MOV2, [(8, 7, 0x20)])        # dst=r0, imm7=32
    cmp("PAD2", "pad_operand", W.PAD2)
    cmp("IFPUSH4", "if_push", W.IFPUSH4, [(16, 8, 0x00), (24, 8, 0x54)])
    cmp("RTQ_PRED", "rtq_pred", W.RTQ_PRED)
    for mn, enc in sorted(W.TARGETS_2B.items()):
        cmp("TARGETS_2B[%s]" % mn, mn, enc)
    cmp("n4_cf(0)", "n4_cf_word", W.n4_cf(0x00), [(24, 8, 0x00)])
    cmp("n4_rt(0x42)", "n4_rt_word", W.n4_rt(0x42), [(8, 8, 0x42)])
    # ICMP2 is the 2-byte HEAD of a 6-byte icmp_pred, not a whole instruction:
    # check only that it satisfies the descriptor's leading match constraint.
    d = L.DESC["icmp_pred"]
    for (s, w, v) in d["match"]:
        if s + w <= 16 and ((int.from_bytes(W.ICMP2, "little") >> s) & ((1 << w) - 1)) != v:
            bad.append("ICMP2 %s violates icmp_pred match (%d,%d,%d)"
                       % (W.ICMP2.hex(), s, w, v))
    print("  OK %-14s %-14s %s (6-byte word; head only)"
          % ("ICMP2", "icmp_pred", W.ICMP2.hex()))

    # ---- aliasing: every fill in the frozen catalogue must be distinct ------
    arms = EXP / "harness" / "arms200.json"
    if arms.exists():
        doc = json.loads(arms.read_text())
        for a in doc["arms"]:
            seen = {}
            for f in a["fills"]:
                if f["hex"] in seen:
                    bad.append("ALIASED fills in %s: %s and %s are byte-identical"
                               " (%s)" % (a["arm"], seen[f["hex"]], f["fid"],
                                          f["hex"]))
                seen[f["hex"]] = f["fid"]
        print("  aliasing check: %d arms, all fills distinct within each arm"
              % len(doc["arms"]) if not bad else "  ALIASING FAILURES")
    else:
        print("  (arms200.json not frozen yet; aliasing check deferred)")
    for b in bad:
        print("FAIL " + b)
    return 1 if bad else 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "encodings":
        return encodings()
    p = EXP / "CAPTURE_CONTRACT.json"
    doc = build()
    if cmd == "freeze":
        p.write_text(json.dumps(doc, indent=1, sort_keys=True))
        print("froze", p, "-", len(doc["authored_sha256"]), "blobs")
        return 0
    old = json.loads(p.read_text())
    bad = [k for k, v in doc["authored_sha256"].items()
           if old["authored_sha256"].get(k) != v]
    for k in bad:
        print("DRIFT %s: contract %s, on disk %s"
              % (k, old["authored_sha256"].get(k), doc["authored_sha256"][k]))
    print("check: %d/%d blobs match"
          % (len(doc["authored_sha256"]) - len(bad), len(doc["authored_sha256"])))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
