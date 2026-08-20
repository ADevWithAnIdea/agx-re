#!/usr/bin/env python3
"""Semantic EXP-0064 verifier: derives every claim directly from raw records."""
import hashlib,json,subprocess
from pathlib import Path
from make_manifest import check,expected,RUNS,CASES
HERE=Path(__file__).resolve().parent
CAPTURE_REV="1a3160a2df49dcfeaa8558a7db1b8676569b6673"
PREREG_REV="100ec777b09f64958694d43a9ef16320bc28e934"
E={
 "rgba8unorm_edges":("0080ff80",[0,0x3f008081,0x3f800000,0x3f008081]),
 "bgra8unorm_edges":("ff800080",[0,0x3f008081,0x3f800000,0x3f008081]),
 "rgba8srgb_threshold":("0a0abc80",[0x3b400c01,0x3b400c01,0x3f00b80c,0x3f008081]),
 "r16unorm_midpoint":("0080",[0x3f000080,0,0,0x3f800000]),
 "rgba16float_edges":("0080003cff7b5535",[0x80000000,0x3f800000,0x477fe000,0x3eaaa000]),
 "r32uint_exact":("efbeadde",[0xdeadbeef,0,0,1]),}
def req(x,m):
 if not x:raise SystemExit("FAIL "+m)
def sh(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def blob(rel):return subprocess.run(["git","show",f"{CAPTURE_REV}:experiments/EXP-0064-m4-format-conversion-matrix-fixed/{rel}"],cwd=HERE,capture_output=True,check=True).stdout
def anc(a,b):return subprocess.run(["git","merge-base","--is-ancestor",a,b],cwd=HERE).returncode==0
def main():
 check(); req(anc(PREREG_REV,CAPTURE_REV) and anc(CAPTURE_REV,"HEAD"),"capture lineage")
 srcblob=subprocess.run(["git","show",f"{PREREG_REV}:experiments/EXP-0064-m4-format-conversion-matrix-fixed/kernels/format_matrix.metal"],cwd=HERE,capture_output=True,check=True).stdout
 blobsha=hashlib.sha256(srcblob).hexdigest(); runsha=hashlib.sha256(blob("run.py")).hexdigest(); probesha=hashlib.sha256(blob("harness/probe.m")).hexdigest(); preregsha=hashlib.sha256(blob("PRE_REGISTRATION.md")).hexdigest(); req(hashlib.sha256((HERE/"PRE_REGISTRATION.md").read_bytes()).hexdigest()==preregsha,"captured prereg blob"); semantic=[]
 for run in RUNS:
  root=HERE/"raw"/run; env=json.loads((root/"00_environment.json").read_text())
  req(env["git_revision"]==CAPTURE_REV and env["source_sha256"]==blobsha and sh(root/"format_matrix.metal")==blobsha,"environment/source binding "+run)
  for k,cmd in (("sw_vers",["sw_vers"]),("xcode",["xcrun","--version"])):
   z=env[k];req(z["command"]==cmd and z["exit"]==0 and z["timeout"] is False,"environment "+run+k)
  rm=json.loads((root/"run_manifest.json").read_text());req(rm=={"run_id":run,"cases":list(CASES),"fresh_process_per_case":True,"source_sha256":blobsha,"runner_sha256":runsha},"run manifest "+run)
  build=json.loads((root/"01_build.json").read_text());req(build["timeout"] is False and build["exit"]==0 and build["seconds"]<=30 and build["stderr"]=="" and build["command"]==["clang","-fobjc-arc","-framework","Metal","-framework","Foundation","-o",str(HERE/"work"/run/"probe"),str(HERE/"harness/probe.m")],"build "+run)
  one={}
  for case in CASES:
   z=json.loads((root/f"case_{case}.json").read_text()); cmd=z["command"]
   req(z["timeout"] is False and z["exit"]==0 and z["seconds"]<=20 and z["stderr"]=="" and cmd==[str(HERE/"work"/run/"probe"),"--source",str(root/"format_matrix.metal"),"--case",case],"argv/timeout "+run+case)
   p=json.loads(z["stdout"]); req(p["phase"]=="execution" and p["case"]==case and p["device"]=="Apple M4" and p["machine"]=="arm64" and p["os"]=="Version 26.6.2 (Build 25G82)" and p["status"]==4 and p["error"]=="","execution "+run+case)
   req(len(p["render_hex"])==768 and len(p["compute_hex"])==288 and all(c in "0123456789abcdef" for c in p["render_hex"]+p["compute_hex"]),"hex size "+run+case)
   rb,cb=bytes.fromhex(p["render_hex"]),bytes.fromhex(p["compute_hex"]);req(rb[:64]==b"\x5a"*64 and rb[320:]==b"\xa5"*64 and cb[:64]==b"\x5a"*64 and cb[80:]==b"\xa5"*64,"guards "+run+case)
   want,w=E[case]; words=[int.from_bytes(cb[64+i:68+i],"little") for i in range(0,16,4)];req(p["physical_texel_hex"]==want and rb[64:64+len(want)//2].hex()==want and words==p["compute_words_le"]==w,"semantic "+run+case)
   req(all(p[x] is True for x in ("render_prefix_guard","render_suffix_guard","compute_prefix_guard","compute_suffix_guard")),"guard flags "+run+case);one[case]=p
  semantic.append(one)
 req(semantic[0]==semantic[1],"two-run raw equality")
 a=json.loads((HERE/"analysis.json").read_text());req(a["repeat_exact"] is True and a["cases"]=={c:{k:semantic[0][c][k] for k in ("physical_texel_hex","compute_words_le","render_hex","compute_hex")} for c in CASES},"analysis regeneration")
 m=json.loads((HERE/"manifest.json").read_text());req({x["path"] for x in m["artifacts"]}==expected(),"manifest coverage")
 for x in m["artifacts"]:req(sh(HERE/x["path"])==x["sha256"] and (HERE/x["path"]).stat().st_size==x["bytes"],"manifest hash")
 print("PASS raw-semantic runs=2 cases=6 full_render=384 full_compute=144 deviation=build30_outer20")
if __name__=="__main__":main()
