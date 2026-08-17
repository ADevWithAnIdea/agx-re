#!/usr/bin/env python3
"""Verify frozen inputs, raw runs, semantic analysis, and manifest coverage."""
from __future__ import annotations
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path,PurePosixPath
HERE=Path(__file__).resolve().parent
PREREG="941eb45f744f6a08b19037cfd147810954fb7365466355f50e1ad652da0d2cec"
RUNS=["m4_20260817_run01","m4_20260817_run02"]
RUN_FILES={"00_preflight.json","01_sw_vers.json","02_uname.json","03_clang.json",
  "04_build.json","05_runner_hash.json","06_suite.json","failures.json","SHA256SUMS"}
INPUTS={"PRE_REGISTRATION.md","run.py","harness/litmus.m","kernels/litmus.metal",
  "kernels/compile_probes/atomic_load_acquire_store_release.metal",
  "kernels/compile_probes/atomic_rmw_acq_rel.metal",
  "kernels/compile_probes/atomic_rmw_relaxed.metal",
  "kernels/compile_probes/fence_release_device.metal",
  "kernels/compile_probes/fence_seq_cst_device.metal"}
RUNNER=(70392,"839fb7ae55cce23b7768e016cfd58a2e07c59f4fa4385013678c9ed675ba4f2e")
STATIC_ARTIFACTS={".gitignore","PRE_REGISTRATION.md","README.md","RESULTS.md",
  "run.py","make_manifest.py","verify.py","analysis/analyze.py","analysis/summary.json",
  "analysis/report.txt","harness/litmus.m",*INPUTS-{"PRE_REGISTRATION.md","run.py","harness/litmus.m"}}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(c,m):
    if not c:raise AssertionError(m)
def inventory(path):
    result={}
    for number,line in enumerate(path.read_text().splitlines(),1):
        parts=line.split("  ")
        require(len(parts)==2 and len(parts[0])==64,f"malformed inventory {path}:{number}")
        want,rel=parts;pure=PurePosixPath(rel)
        require(not pure.is_absolute() and ".." not in pure.parts,f"unsafe raw path {rel}")
        require(rel not in result,f"duplicate raw path {rel}")
        try:int(want,16)
        except ValueError:raise AssertionError(f"nonhex inventory digest {path}:{number}")
        result[rel]=want
    return result
def main():
    require(digest(HERE/"PRE_REGISTRATION.md")==PREREG,"pre-registration changed")
    require({p.name for p in (HERE/"raw").iterdir() if p.is_dir()}==set(RUNS),"raw run set")
    runner=[];inputs=[]
    for name in RUNS:
        d=HERE/"raw"/name
        require(d.is_dir() and not d.is_symlink(),f"raw directory {name}")
        entries=list(d.rglob("*"))
        require(all(p.is_file() and not p.is_symlink() and p.parent==d for p in entries),
          f"raw nested/special entry {name}")
        files={p.name for p in entries}
        require(files==RUN_FILES,f"raw file set {name}")
        sums=inventory(d/"SHA256SUMS")
        require(set(sums)==RUN_FILES-{"SHA256SUMS"},f"raw inventory coverage {name}")
        for rel,want in sums.items():
            require(digest(d/rel)==want,f"raw hash mismatch {name}/{rel}")
        require(not json.loads((d/"failures.json").read_text()),f"formal failure {name}")
        pre=json.loads((d/"00_preflight.json").read_text());inputs.append(pre["exact_input_hashes"])
        require(pre["preregistration_sha256"]==PREREG and pre["verified_before_build_and_hardware"],f"preflight {name}")
        require(pre["target"]=="local Apple M4 only",f"target {name}")
        require(pre["clean_room"]=={
          "apple_auxiliary_code_inspection":False,"apple_binary_introspection":False,
          "command_bo_capture":False,"generic_bo_scan":False,"pointer_following":False,
          "observations":"authored MSL compile result and own shared-buffer live outputs only"},f"clean-room record {name}")
        require(set(pre["exact_input_hashes"])==INPUTS,f"input path set {name}")
        for rel,want in pre["exact_input_hashes"].items():
            require(digest(HERE/rel)==want,f"authored input changed {name}/{rel}")
        runner.append(json.loads((d/"05_runner_hash.json").read_text()))
        env_commands={"01_sw_vers.json":(["sw_vers"],10),
          "02_uname.json":(["uname","-a"],10),"03_clang.json":(["clang","--version"],10)}
        for filename,(argv,timeout) in env_commands.items():
            record=json.loads((d/filename).read_text())
            require(record["command"]==argv and record["timeout_seconds"]==timeout and
              record["exit"]==0 and not record.get("timeout",False) and record["stderr"]=="",
              f"environment command {name}/{filename}")
        executable=HERE/"work"/name/"litmus"
        build=json.loads((d/"04_build.json").read_text())
        require(build["command"]==["clang","-fobjc-arc","-o",str(executable),
          str(HERE/"harness/litmus.m"),"-framework","Metal","-framework","Foundation"] and
          build["timeout_seconds"]==30 and build["exit"]==0 and not build.get("timeout",False) and
          build["stdout"]=="" and build["stderr"]=="",f"build command {name}")
        suite=json.loads((d/"06_suite.json").read_text())
        require(suite["command"]==[str(executable),"--source",str(HERE/"kernels/litmus.metal"),
          "--probe-dir",str(HERE/"kernels/compile_probes"),"--api-trials","128",
          "--message-tg-iters","256","--message-cross-iters","8192"] and
          suite["timeout_seconds"]==180 and suite["exit"]==0 and
          not suite.get("timeout",False) and suite["stderr"]=="",f"suite command {name}")
    require(inputs[0]==inputs[1],"run input identity mismatch")
    require(all((item["bytes"],item["sha256"])==RUNNER for item in runner),"runner identity mismatch")
    with tempfile.TemporaryDirectory(prefix="exp0051-verify-") as tmp:
        summary=Path(tmp)/"summary.json";report=Path(tmp)/"report.txt"
        cp=subprocess.run([sys.executable,HERE/"analysis/analyze.py","--json",summary,"--report",report],capture_output=True,text=True,timeout=30)
        require(cp.returncode==0,f"analysis failed: {cp.stderr}")
        require(summary.read_bytes()==(HERE/"analysis/summary.json").read_bytes(),"stale analysis/summary.json")
        require(report.read_bytes()==(HERE/"analysis/report.txt").read_bytes(),"stale analysis/report.txt")
    m=json.loads((HERE/"manifest.json").read_text());listed={x["path"]:x for x in m["artifacts"]}
    require(len(listed)==len(m["artifacts"]),"duplicate manifest path")
    require(m["experiment"]=="EXP-0051-m4-synchronization-litmus","manifest experiment")
    require(m["pre_registration"]=={"path":"PRE_REGISTRATION.md","sha256":PREREG},"manifest preregistration")
    require(m["repository"]["head_at_manifest"]=="cad2132bcac680ecb482c04fa57a515f60b9bcb4","manifest head")
    require(m["runner_binary"]=={"bytes":RUNNER[0],"same_in_both_runs":True,"sha256":RUNNER[1]},"manifest runner")
    require(m["provenance"]=={
      "categories":["HW-PROBE","OWN-SHADER"],
      "observed":["authored MSL compile acceptance/diagnostics","live Metal completion","process-owned shared-buffer bytes"],
      "apple_binary_introspection":"NONE","apple_auxiliary_or_helper_code_inspection":"NONE",
      "command_or_bo_scan":"NONE","pointer_following":"NONE","compiled_shader_bytes_inspected":"NONE"},
      "manifest clean-room")
    require(m["target"]=={"gpu":"Apple M4 / G16G","model":"Mac16,10",
      "qualification":"M4 Metal-path observation only; no A18 Pro validation","soc":"Apple M4"},"manifest target")
    require(m["runs"]==["raw/m4_20260817_run01","raw/m4_20260817_run02"],"manifest runs")
    actual={str(p.relative_to(HERE)):p for p in HERE.rglob("*") if p.is_file() and p.name!="manifest.json" and "work" not in p.parts and "__pycache__" not in p.parts}
    expected_artifacts=STATIC_ARTIFACTS|{f"raw/{run}/{name}" for run in RUNS for name in RUN_FILES}
    require(set(actual)==expected_artifacts,
      f"committable artifact allowlist extra={sorted(set(actual)-expected_artifacts)} missing={sorted(expected_artifacts-set(actual))}")
    require(set(listed)==set(actual),f"manifest coverage missing={sorted(set(actual)-set(listed))} extra={sorted(set(listed)-set(actual))}")
    for rel,p in actual.items():
        pure=PurePosixPath(rel)
        require(not pure.is_absolute() and ".." not in pure.parts,f"unsafe manifest path {rel}")
        require(p.is_file() and not p.is_symlink(),f"unsafe artifact {rel}")
        require(listed[rel]["bytes"]==p.stat().st_size and listed[rel]["sha256"]==digest(p),f"manifest mismatch {rel}")
    print(f"PASS prereg=1 raw_runs=2 inputs_identical=1 runner_identical=1 analysis=PASS manifest_artifacts={len(listed)}")
    return 0
if __name__=="__main__":raise SystemExit(main())
