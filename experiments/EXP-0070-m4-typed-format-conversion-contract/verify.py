#!/usr/bin/env python3
"""Fail-closed static and post-capture verifier for EXP-0070."""
import argparse, datetime, hashlib, json, re, subprocess
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
REC_KEYS={"argv","cwd","timeout_seconds","started_utc","timed_out","exit","stdout","stderr","exception"}
CASE_KEYS={"case","command_buffer_status","device","error","machine","os","physical_texel_hex","render_hex","compute_hex","compute_words_le","render_prefix_guard","render_suffix_guard","compute_prefix_guard","compute_suffix_guard"}
def receipt(z, argv, cwd, timeout, label):
    req(set(z)==REC_KEYS and z["argv"]==[str(x) for x in argv] and z["cwd"]==str(cwd) and z["timeout_seconds"]==timeout and z["timed_out"] is False and z["exit"]==0 and z["exception"] is None and isinstance(z["stdout"],str) and isinstance(z["stderr"],str),label)
    try: req(datetime.datetime.fromisoformat(z["started_utc"]).utcoffset()==datetime.timedelta(),label+" timestamp")
    except (TypeError,ValueError): fail(label+" timestamp")
def bpp(case): return 2 if case=="r16unorm_midpoint" else 8 if case=="rgba16float_finite" else 4
def backing(case,p):
    req(set(p)==CASE_KEYS and p["case"]==case and p["command_buffer_status"]==4 and p["device"]=="Apple M4" and p["machine"]=="arm64" and isinstance(p["os"],str) and p["os"] and p["error"]=="","status/device/error "+case)
    req(isinstance(p["compute_words_le"],list) and len(p["compute_words_le"])==4 and all(type(x) is int and 0<=x<2**32 for x in p["compute_words_le"]),"word grammar "+case)
    req(isinstance(p["physical_texel_hex"],str) and len(p["physical_texel_hex"])==2*bpp(case) and re.fullmatch(r"[0-9a-f]+",p["physical_texel_hex"]) and isinstance(p["render_hex"],str) and len(p["render_hex"])==768 and isinstance(p["compute_hex"],str) and len(p["compute_hex"])==288 and re.fullmatch(r"[0-9a-f]+",p["render_hex"]+p["compute_hex"]),"hex grammar "+case)
    r,c=bytes.fromhex(p["render_hex"]),bytes.fromhex(p["compute_hex"]); words=[int.from_bytes(c[64+i:68+i],"little") for i in range(0,16,4)]
    req(p["physical_texel_hex"]==r[64:64+bpp(case)].hex() and p["compute_words_le"]==words,"derived texel/words "+case)
    req(p["render_prefix_guard"]==(r[:64]==b"\x5a"*64) and p["render_suffix_guard"]==(r[320:]==b"\xa5"*64) and p["compute_prefix_guard"]==(c[:64]==b"\x5a"*64) and p["compute_suffix_guard"]==(c[80:]==b"\xa5"*64),"derived guard flags "+case)
    req(all(p[x] is True for x in ("render_prefix_guard","render_suffix_guard","compute_prefix_guard","compute_suffix_guard")),"guard mutation "+case)
def static(capture=False):
    names={p.name for p in HERE.iterdir()}; allowed=ROOT|({"raw"} if capture else set())|({"work"} if "work" in names else set()); req(not HERE.is_symlink() and names == allowed,"closed root")
    if "work" in names: req((HERE/"work").is_dir() and not (HERE/"work").is_symlink() and not any((HERE/"work").iterdir()),"work absent or empty")
    for p in AUTH+("manifest.json",): req(regular(HERE/p),"regular "+p)
    for d,fs in (("kernels",{"format_matrix.metal"}),("harness",{"probe.m"})):
        q=HERE/d;req(q.is_dir() and not q.is_symlink() and {p.name for p in q.iterdir()}==fs and all(regular(x) for x in q.iterdir()),"closed "+d)
    c=json.loads((HERE/"CAPTURE_CONTRACT.json").read_text());req(c["state"]=="PRE_GPU" and tuple(c["cases"])==CASES and tuple(c["required_authored_paths"])==AUTH and set(c["capture"]["receipt_keys"])==REC_KEYS and set(c["capture"]["case_record_keys"])==CASE_KEYS and c["capture"]["run_manifest_keys"]==["schema","run_id","cases","fresh_process_per_case","runner_sha256","harness_sha256","kernel_sha256"],"contract core")
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
        req(set(i)=={"schema","git_revision","authored_sha256","sw_vers","xcrun_version","machine","boundary"} and i["schema"]==1 and i["machine"]=="arm64" and i["boundary"]=="public Metal; owned in-bounds buffers; no binary/archive/BO inspection" and set(i["authored_sha256"])==set(AUTH) and subprocess.run(["git","cat-file","-e",rev+"^{commit}"],cwd=REPO).returncode==0 and subprocess.run(["git","merge-base","--is-ancestor",rev,"HEAD"],cwd=REPO).returncode==0,"revision "+rid)
        for path,want in i["authored_sha256"].items():
            blob=subprocess.run(["git","show",rev+":experiments/EXP-0070-m4-typed-format-conversion-contract/"+path],cwd=REPO,capture_output=True).stdout
            req(hashlib.sha256(blob).hexdigest()==want,"source binding "+rid+" "+path)
        captured_cwd=i["sw_vers"].get("cwd"); req(isinstance(captured_cwd,str),"captured root type "+rid); captured_root=Path(captured_cwd); req(captured_root.is_absolute() and i["xcrun_version"].get("cwd")==str(captured_root),"captured root "+rid)
        receipt(i["sw_vers"],["sw_vers"],captured_root,5,"sw_vers "+rid);receipt(i["xcrun_version"],["xcrun","--version"],captured_root,5,"xcrun "+rid)
        probe=captured_root/"work"/rid/"probe"; b=json.loads((d/"01_host_build.json").read_text());receipt(b,["xcrun","clang","-fobjc-arc","-o",probe,captured_root/"harness/probe.m","-framework","Metal","-framework","Foundation"],captured_root,60,"build "+rid)
        rm=json.loads((d/"run_manifest.json").read_text());req(rm=={"schema":1,"run_id":rid,"cases":list(CASES),"fresh_process_per_case":True,"runner_sha256":i["authored_sha256"]["run.py"],"harness_sha256":i["authored_sha256"]["harness/probe.m"],"kernel_sha256":i["authored_sha256"]["kernels/format_matrix.metal"]},"run manifest "+rid)
        rows=[]
        for case in CASES:
            z=json.loads((d/f"case_{case}.json").read_text());receipt(z,[probe,"--source",captured_root/"kernels/format_matrix.metal","--case",case],captured_root,20,"case process "+case);p=json.loads(z["stdout"]);backing(case,p);rows.append(p)
        compare.append(rows)
    req(compare[0]==compare[1],"byte-exact repeat")
def main():
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument("--preflight",action="store_true");g.add_argument("--captured",action="store_true");a=ap.parse_args()
    if a.preflight: static(); req(not (HERE/"raw").exists(),"PRE_GPU tree must have no raw");print("PASS PRE_GPU contract; no GPU capture")
    else: static(capture=True);captured();print("PASS captured public-Metal owned-buffer contract")
if __name__=="__main__": main()
