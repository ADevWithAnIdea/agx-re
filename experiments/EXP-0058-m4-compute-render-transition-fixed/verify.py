#!/usr/bin/env python3
"""Verify EXP-0058's exact metadata-only stop; never open/hash a .bin."""
from __future__ import annotations
import hashlib,json,re,subprocess
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
AUTHORED_FILES=("PRE_REGISTRATION.md","README.md","run.py","harness/probe.m","harness/allowtrace.c","audit.py","make_manifest.py","verify.py")
CAPTURE_HASHES={"PRE_REGISTRATION.md":PRE_HASH,"run.py":"889b6f4e9c6a0a95fcaf4ecfe09d092cea9e4ce04073d95d3d28c8e7bbfd907e","harness/probe.m":"85e3f8b83171ad8a284a69f0e270abd8d65d2b90f9d525c9544bab4806ea99eb","harness/allowtrace.c":"f3ee66cff3d0ccfcfc4081d7dfc60959786900fa95e13221535ff6ed49883286"}
def check_tree() -> None:
    # Closed tree check is path/type only and precedes all artifact stat-listing.
    assert not RAW.is_symlink() and RAW.is_dir()
    assert {p.name for p in RAW.iterdir()} == ROOT_FILES|{"trials"}
    for name in ROOT_FILES:
        p=RAW/name; assert not p.is_symlink() and p.is_file()
    trials=RAW/"trials"; assert not trials.is_symlink() and trials.is_dir()
    assert {p.name for p in trials.iterdir()}==set(TRIALS)
    for name,expected in TRIALS.items():
        trial=trials/name; assert not trial.is_symlink() and trial.is_dir()
        assert {p.name for p in trial.iterdir()}=={"run.json","trace.log","state"}
        for leaf in (trial/"run.json",trial/"trace.log"): assert not leaf.is_symlink() and leaf.is_file()
        state=trial/"state"; assert not state.is_symlink() and state.is_dir()
        assert {p.name for p in state.iterdir()}==expected
        for leaf in state.iterdir(): assert not leaf.is_symlink() and leaf.is_file()
m=json.loads((HERE/"manifest.json").read_text())
assert set(m)=={"schema","status","capture_revision","pre_registration_commit","pre_registration_blob","pre_registration_sha256","raw_inventory","authored_source_sha256","payload_policy"}
assert (m["schema"],m["status"],m["capture_revision"],m["pre_registration_commit"],m["pre_registration_blob"],m["pre_registration_sha256"])==(2,"STOPPED_BEFORE_ANY_PAYLOAD_OPEN",CAPTURE_REVISION,CAPTURE_REVISION,PRE_BLOB,PRE_HASH)
assert m["payload_policy"]=="Every .bin is listed from path/stat metadata only; no payload is opened or hashed by this tool or verifier."
assert set(m["authored_source_sha256"])==set(AUTHORED_FILES)
actual=[]
check_tree()
for p in sorted(RAW.rglob("*")):
    if p.is_dir(): continue
    assert p.is_file() and not p.is_symlink()
    actual.append({"path":str(p.relative_to(HERE)),"bytes":p.stat().st_size,
                   "content_opened":False,"kind":"opaque-payload" if p.suffix==".bin" else "metadata-or-log"})
assert actual==m["raw_inventory"]
assert any(x["kind"]=="opaque-payload" for x in actual)
assert all(not x["content_opened"] for x in actual)
for rel,want in m["authored_source_sha256"].items():
    # Authored sources only: not raw evidence or payloads.
    assert hashlib.sha256((HERE/rel).read_bytes()).hexdigest()==want
failure=json.loads((HERE/"raw/m4-20260819-transition02/analysis_failure.json").read_text())
assert failure=={"error":"AssertionError(\"required mappings absent: ['va_100000b8000']\")"}
inputs=json.loads((RAW/"00_inputs.json").read_text())
assert inputs=={"authored_inputs":CAPTURE_HASHES,"pre_registration_sha256":PRE_HASH,"revision":CAPTURE_REVISION}
assert subprocess.run(["git","cat-file","-e",f"{CAPTURE_REVISION}^{{commit}}"],capture_output=True).returncode==0
assert subprocess.run(["git","merge-base","--is-ancestor",CAPTURE_REVISION,"HEAD"],capture_output=True).returncode==0
assert subprocess.run(["git","rev-parse",f"{CAPTURE_REVISION}:experiments/EXP-0058-m4-compute-render-transition-fixed/PRE_REGISTRATION.md"],capture_output=True,text=True,check=True).stdout.strip()==PRE_BLOB
for rel,want in inputs["authored_inputs"].items():
    blob=subprocess.run(["git","show",f"{CAPTURE_REVISION}:experiments/EXP-0058-m4-compute-render-transition-fixed/{rel}"],capture_output=True,check=True).stdout
    assert hashlib.sha256(blob).hexdigest()==want
build_root=HERE/"work/m4-20260819-transition02"
expected_builds={
 "02_build_allowtrace.json":["xcrun","clang","-arch","arm64e","-dynamiclib","-o",str(build_root/"allowtrace.dylib"),str(HERE/"harness/allowtrace.c"),"-framework","IOKit","-framework","CoreFoundation"],
 "03_build_probe.json":["xcrun","clang","-arch","arm64e","-fobjc-arc","-o",str(build_root/"probe"),str(HERE/"harness/probe.m"),"-framework","Metal","-framework","Foundation"],
}
for name,argv in expected_builds.items():
    record=json.loads((RAW/name).read_text())
    assert set(record)=={"argv","exit","started_utc","stderr","stdout","timeout_seconds"}
    assert record["argv"]==argv and record["exit"]==0 and record["timeout_seconds"]==60 and record["stdout"]==record["stderr"]==""
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT.*\+00:00",record["started_utc"])
for trial in sorted((RAW/"trials").iterdir()):
    run=json.loads((trial/"run.json").read_text())
    schedule,variant=trial.name.split("_",1)
    argv=[str(build_root/"probe"),"--variant",variant,"--dump"]+(["--pad64k"] if schedule=="pad64k" else [])
    assert set(run)=={"argv","exit","started_utc","stderr","stdout","timeout_seconds"}
    assert run["argv"]==argv and run["exit"]==0 and run["timeout_seconds"]==45 and run["stderr"]==""
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT.*\+00:00",run["started_utc"])
    expected="READBACK scene=0.25,0.5,0.75" if variant=="compute-only" else "READBACK center=bf8040ff fnv=4e6294d9841a3583"
    assert expected in run["stdout"] and f"VARIANT name={variant} schedule={schedule}" in run["stdout"] and "COMMAND status=4 error=none" in run["stdout"] and "RESULT ok=1" in run["stdout"]
assert not (RAW/"trials/plain_compute-only/state/va_100000b8000.bin").exists()
print(f"PASS inventory={len(actual)} raw artifacts; payloads=opaque/unopened")
