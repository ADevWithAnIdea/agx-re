#!/usr/bin/env python3
"""Write an exact EXP-0058 inventory without opening any raw payload byte."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
RAW=HERE/"raw/m4-20260819-transition02"
TRIALS={
 "plain_compute-only":set(),
 "plain_cpu-render":{"va_18000.bin","va_18000.meta"},
 "plain_compute-render":{"va_18000.bin","va_18000.meta"},
 "pad64k_compute-only":{"va_100000b8000.bin","va_100000b8000.meta"},
 "pad64k_cpu-render":{"va_18000.bin","va_18000.meta"},
 "pad64k_compute-render":{"va_100000b8000.bin","va_100000b8000.meta","va_18000.bin","va_18000.meta"},
}
ROOT_FILES={"00_inputs.json","01_environment.json","02_build_allowtrace.json","03_build_probe.json","analysis_failure.json"}
CAPTURE_REVISION="18567cd4da5c46f94c6b8dd839df8702bc5c18db"
PRE_BLOB="49b6301a3131015bda4183c9913e77dbd6b9a0dc"
PRE_HASH="bbe4610c094f7223718e311efec986cb94d14b6d54220cceec3a5e6a8e574181"
CAPTURE_INPUTS=("PRE_REGISTRATION.md","run.py","harness/probe.m","harness/allowtrace.c")
def check_tree() -> None:
    # Names/types only: this runs before any artifact is stat-listed or opened.
    if RAW.is_symlink() or not RAW.is_dir(): raise SystemExit("raw root type")
    if {p.name for p in RAW.iterdir()} != ROOT_FILES|{"trials"}: raise SystemExit("raw root entries")
    for name in ROOT_FILES:
        p=RAW/name
        if p.is_symlink() or not p.is_file(): raise SystemExit(f"raw root regular {name}")
    trials=RAW/"trials"
    if trials.is_symlink() or not trials.is_dir() or {p.name for p in trials.iterdir()}!=set(TRIALS): raise SystemExit("trial matrix")
    for name,expected in TRIALS.items():
        trial=trials/name
        if trial.is_symlink() or not trial.is_dir() or {p.name for p in trial.iterdir()}!={"run.json","trace.log","state"}: raise SystemExit(f"trial entries {name}")
        for leaf in (trial/"run.json",trial/"trace.log"):
            if leaf.is_symlink() or not leaf.is_file(): raise SystemExit(f"trial regular {name}")
        state=trial/"state"
        if state.is_symlink() or not state.is_dir() or {p.name for p in state.iterdir()}!=expected: raise SystemExit(f"exact state entries {name}")
        for leaf in state.iterdir():
            if leaf.is_symlink() or not leaf.is_file(): raise SystemExit(f"state regular {name}")
def sha_source(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()
entries=[]
check_tree()
for p in sorted(RAW.rglob("*")):
    if p.is_dir(): continue
    if p.is_symlink() or not p.is_file(): raise SystemExit(f"non-regular artifact: {p}")
    # stat()/name only for every raw artifact, especially all .bin payloads.
    entries.append({"path":str(p.relative_to(HERE)),"bytes":p.stat().st_size,
                    "content_opened":False,"kind":"opaque-payload" if p.suffix==".bin" else "metadata-or-log"})
manifest={
 "schema":2,"status":"STOPPED_BEFORE_ANY_PAYLOAD_OPEN",
 "capture_revision":CAPTURE_REVISION,
 "pre_registration_commit":CAPTURE_REVISION,"pre_registration_blob":PRE_BLOB,
 "pre_registration_sha256":PRE_HASH,
 "raw_inventory":entries,
 "authored_source_sha256":{str(p.relative_to(HERE)):sha_source(p) for p in [HERE/"PRE_REGISTRATION.md",HERE/"README.md",HERE/"run.py",HERE/"harness/probe.m",HERE/"harness/allowtrace.c",HERE/"audit.py",HERE/"make_manifest.py",HERE/"verify.py"]},
 "payload_policy":"Every .bin is listed from path/stat metadata only; no payload is opened or hashed by this tool or verifier."
}
(HERE/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
