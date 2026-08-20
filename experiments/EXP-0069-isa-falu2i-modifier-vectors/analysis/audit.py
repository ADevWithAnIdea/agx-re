#!/usr/bin/env python3
"""Append-only structural modifier-vector audit for the pinned falu2i codec."""
from __future__ import annotations
import hashlib, itertools, json, subprocess, sys
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
REPO=HERE.parents[1]; TOOL=REPO/"tools/agx-isa"; OUT=HERE/"raw/run01"
INPUTS=(HERE/"PRE_REGISTRATION.md",HERE/"analysis/audit.py",TOOL/"isadb.py",TOOL/"roundtrip_test.py",TOOL/"db.json")
FIXED={"dst":7,"imm_flag":1,"imm_mant":1,"imm_exp":11,"opsel":4,"imm_sign":0,"srcA_size":1,"srcA_reg":31}
DOMAIN={"opflags":range(16),"ctrl_lo":range(128),"mods":range(256)}
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def main()->int:
 if OUT.exists():raise SystemExit("append-only output exists")
 OUT.mkdir(parents=True)
 rev=subprocess.run(["git","rev-parse","HEAD"],cwd=REPO,check=True,capture_output=True,text=True).stdout.strip()
 (OUT/"00_inputs.json").write_text(json.dumps({"schema":1,"revision":rev,"inputs":{str(p.relative_to(REPO)):sha(p) for p in INPUTS}},indent=2,sort_keys=True)+"\n")
 subprocess.run([sys.executable,str(TOOL/"roundtrip_test.py")],cwd=TOOL,check=True,timeout=30,capture_output=True,text=True)
 sys.path.insert(0,str(TOOL));import isadb
 db=json.loads((TOOL/"db.json").read_text());d=next(x for x in db["instructions"] if x["mnemonic"]=="falu2i")
 assert {x["name"] for x in d["fields"]}==set(FIXED)|set(DOMAIN)
 seen=set(); stream=hashlib.sha256();count=0
 for vals in itertools.product(*(DOMAIN[k] for k in DOMAIN)):
  fields={**FIXED,**dict(zip(DOMAIN,vals))};encoded=isadb.assemble("falu2i",fields);decoded,used=isadb.decode_one(encoded,0)
  assert used==6 and decoded["mnemonic"]=="falu2i" and decoded["fields"]==fields and isadb.assemble("falu2i",decoded["fields"])==encoded and encoded not in seen
  seen.add(encoded);stream.update(encoded);count+=1
 assert count==524288
 (OUT/"result.json").write_text(json.dumps({"schema":1,"scope":"falu2i modifier codec only; no hardware claim","fixed_semantic_fields":FIXED,"modifier_domain":{"opflags":16,"ctrl_lo":128,"mods":256},"vectors":count,"unique_encodings":len(seen),"all_round_trip":True,"encoding_sha256":stream.hexdigest()},indent=2,sort_keys=True)+"\n")
 return 0
if __name__=="__main__":raise SystemExit(main())
