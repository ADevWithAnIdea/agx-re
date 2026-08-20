#!/usr/bin/env python3
"""Fail-closed static and post-capture verifier for EXP-0070."""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent; REPO=HERE.parents[1]
ROOT={"CAPTURE_CONTRACT.json","PRE_REGISTRATION.md","README.md","RESULTS.md","kernels","harness","run.py","analysis.py","make_manifest.py","verify.py","manifest.json"}
AUTH=("PRE_REGISTRATION.md","README.md","RESULTS.md","CAPTURE_CONTRACT.json","kernels/format_matrix.metal","harness/probe.m","run.py","analysis.py","make_manifest.py","verify.py")
CASES=("rgba8unorm_edges","bgra8unorm_edges","rgba8srgb_threshold","r16unorm_midpoint","rgba16float_finite","r32uint_exact")
def fail(s): raise SystemExit("FAIL "+s)
def req(v,s):
    if not v: fail(s)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def regular(p): return p.is_file() and not p.is_symlink()
def static():
    req(not HERE.is_symlink() and {p.name for p in HERE.iterdir()} == ROOT,"closed root")
    for p in AUTH+("manifest.json",): req(regular(HERE/p),"regular "+p)
    for d,fs in (("kernels",{"format_matrix.metal"}),("harness",{"probe.m"})):
        q=HERE/d;req(q.is_dir() and not q.is_symlink() and {p.name for p in q.iterdir()}==fs and all(regular(x) for x in q.iterdir()),"closed "+d)
    c=json.loads((HERE/"CAPTURE_CONTRACT.json").read_text());req(c["state"]=="PRE_GPU" and tuple(c["cases"])==CASES and tuple(c["required_authored_paths"])==AUTH,"contract core")
    req(c["boundary"]["accesses"]=="in-bounds 1x1 texture reads and writes only" and c["boundary"]["apple_binary_archive_bo_inspection"]=="NONE","boundary")
    req(c["backings"]["render"]["total_bytes"]==384 and c["backings"]["render"]["hex_chars"]==768 and c["backings"]["compute"]["total_bytes"]==144 and c["backings"]["compute"]["hex_chars"]==288,"backing contract")
    h=(HERE/"harness/probe.m").read_text(); k=(HERE/"kernels/format_matrix.metal").read_text();req("uint2(0, 0)" in k and "width:1 height:1" in h and "newTextureWithDescriptor:td offset:64 bytesPerRow:256" in h,"in-bounds geometry")
    req("MTLResourceStorageModeShared" in h and "newBufferWithLength:384" in h and "newBufferWithLength:144" in h,"owned buffers")
    req(not re.search(r"IOKit|objc_msgSend|MTLIO|contents\s*\+\s*[^6]",h),"forbidden inspection token")
    m=json.loads((HERE/"manifest.json").read_text());want={"schema":1,"state":"PRE_GPU","artifacts":[{"path":p,"bytes":(HERE/p).stat().st_size,"sha256":sha(HERE/p)} for p in AUTH]};req(m==want,"manifest")
def captured():
    raw=HERE/"raw"; req(raw.is_dir() and not raw.is_symlink() and {p.name for p in raw.iterdir()}=={"m4-TODO-run01","m4-TODO-run02"},"two exact raw runs")
    compare=[]
    for rid in ("m4-TODO-run01","m4-TODO-run02"):
        d=raw/rid; names={"00_inputs.json","01_host_build.json","run_manifest.json"}|{f"case_{x}.json" for x in CASES};req(d.is_dir() and not d.is_symlink() and {p.name for p in d.iterdir()}==names and all(regular(p) for p in d.iterdir()),"closed raw "+rid)
        i=json.loads((d/"00_inputs.json").read_text()); rev=i.get("git_revision","")
        req(i["schema"]==1 and set(i["authored_sha256"])==set(AUTH) and subprocess.run(["git","cat-file","-e",rev+"^{commit}"],cwd=REPO).returncode==0 and subprocess.run(["git","merge-base","--is-ancestor",rev,"HEAD"],cwd=REPO).returncode==0,"revision "+rid)
        for path,want in i["authored_sha256"].items():
            blob=subprocess.run(["git","show",rev+":experiments/EXP-0070-m4-typed-format-conversion-contract/"+path],cwd=REPO,capture_output=True).stdout
            req(hashlib.sha256(blob).hexdigest()==want,"source binding "+rid+" "+path)
        b=json.loads((d/"01_host_build.json").read_text());req(b["timeout_seconds"]==60 and not b["timed_out"] and b["exit"]==0,"build "+rid)
        rows=[]
        for case in CASES:
            z=json.loads((d/f"case_{case}.json").read_text());req(z["timeout_seconds"]==20 and not z["timed_out"] and z["exit"]==0,"case process "+case);p=json.loads(z["stdout"]);req(set(p)==set(json.loads((HERE/"CAPTURE_CONTRACT.json").read_text())["capture"]["case_record_keys"]),"case schema "+case);req(len(p["render_hex"])==768 and len(p["compute_hex"])==288 and re.fullmatch(r"[0-9a-f]+",p["render_hex"]+p["compute_hex"]) and all(p[x] is True for x in ("render_prefix_guard","render_suffix_guard","compute_prefix_guard","compute_suffix_guard")),"backings "+case);rows.append(p)
        compare.append(rows)
    req(compare[0]==compare[1],"byte-exact repeat")
def main():
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument("--preflight",action="store_true");g.add_argument("--captured",action="store_true");a=ap.parse_args();static()
    if a.preflight: req(not (HERE/"raw").exists() and not (HERE/"work").exists(),"PRE_GPU tree must have no raw/work");print("PASS PRE_GPU contract; no GPU capture")
    else: captured();print("PASS captured public-Metal owned-buffer contract")
if __name__=="__main__": main()
