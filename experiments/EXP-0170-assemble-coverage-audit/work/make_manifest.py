#!/usr/bin/env python3
"""EXP-0170 -- build manifest.json: sha256 of every artifact this experiment produced
and of every external input it was pinned to.  Usage: python3 work/make_manifest.py"""
import hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT)


own = {}
for dp, dns, fns in os.walk(EXP):
    dns[:] = [d for d in dns if d != "__pycache__"]
    for fn in sorted(fns):
        p = os.path.join(dp, fn)
        own[os.path.relpath(p, EXP)] = {"sha256": sha(p), "bytes": os.path.getsize(p)}

INPUTS = [
    "tools/agx-isa/db.json", "tools/agx-isa/validation.json", "tools/agx-isa/isadb.py",
    "tools/agx-isa/roundtrip_test.py", "work/merge_verdicts.py",
    "experiments/EXP-0164-inert-audit/analysis/collect_raw.py",
    "experiments/EXP-0164-inert-audit/analysis/audit.py",
    "experiments/EXP-0164-inert-audit/analysis/audit.json",
    "experiments/EXP-0164-inert-audit/analysis/withhold_inert_single.json",
    "experiments/EXP-0164-inert-audit/analysis/withhold_unstable.json",
    "experiments/EXP-0164-inert-audit/analysis/withhold_unverifiable.json",
    "experiments/EXP-0164-inert-audit/work/db.snapshot.json",
    "experiments/EXP-0164-inert-audit/work/validation.snapshot.json",
]
inputs = {}
for r in INPUTS:
    p = os.path.join(ROOT, r)
    inputs[r] = {"sha256": sha(p), "bytes": os.path.getsize(p)} if os.path.exists(p) \
        else {"sha256": None, "note": "absent at manifest time"}

# every raw JSONL Arm B/D read, by experiment (hashing 4.7M lines individually is
# 617 entries; recorded as a per-experiment digest of the sorted (path, sha256) list)
raws = {}
EXPDIR = os.path.join(ROOT, "experiments")
for e in sorted(os.listdir(EXPDIR)):
    raw = os.path.join(EXPDIR, e, "raw")
    if not os.path.isdir(raw):
        continue
    files = []
    for dp, _, fns in os.walk(raw):
        for fn in sorted(fns):
            if fn.endswith(".jsonl"):
                p = os.path.join(dp, fn)
                files.append((rel(p), sha(p)))
    if files:
        files.sort()
        d = hashlib.sha256("\n".join("%s %s" % t for t in files).encode()).hexdigest()
        raws[e] = {"n_jsonl": len(files), "digest_of_sorted_path_sha_list": d}

try:
    rev = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
except Exception:
    rev = None

json.dump({
  "experiment": "EXP-0170-assemble-coverage-audit",
  "title": "assembler under-coverage, round-trip blindness, and disowned-run selection",
  "date": "2026-08-30",
  "target": "NONE -- pure analysis on the repo host. No device, no SSH, no GPU.",
  "git_rev_at_manifest": rev,
  "arms": {"A": "static match/field overlap", "B": "distinct-bytes coverage audit",
           "C": "round-trip idiom census + demonstration",
           "D": "run eligibility + placeholder re-scoring (dated amendment)"},
  "reproduction": [
     "python3 analysis/static_overlap.py",
     "python3 analysis/coverage_index.py",
     "python3 analysis/classify.py",
     "python3 analysis/roundtrip_idiom.py",
     "python3 analysis/roundtrip_blindspot.py",
     "python3 work/collect_raw_D.py",
     "python3 analysis/run_eligibility.py",
     "python3 analysis/rescore_D.py",
     "python3 analysis/emit_wrongly_withdrawn.py"],
  "promotes_anything": False,
  "files_written_outside_this_experiment": [],
  "external_inputs_at_manifest_time": inputs,
  "pinned_snapshots_used_for_all_numbers": {
     "work/db.snapshot.json": own["work/db.snapshot.json"]["sha256"],
     "work/validation.snapshot.json": own["work/validation.snapshot.json"]["sha256"],
     "note": "tools/agx-isa/{db,validation}.json and isadb.py all moved while this "
             "experiment ran (pre-registration 5 confounder 7). All numbers are against "
             "these snapshots; RESULTS.md 7 records the re-check against the live db."},
  "raw_evidence_read_readonly": raws,
  "artifacts": own,
}, open(os.path.join(EXP, "manifest.json"), "w"), indent=1, sort_keys=True)
print("manifest: %d artifacts, %d inputs, %d experiments' raw hashed"
      % (len(own), len(inputs), len(raws)))
