#!/usr/bin/env python3
"""Closed property-vector audit for falu2i's declared semantic sub-schema."""
from __future__ import annotations
import hashlib, itertools, json, subprocess, sys
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
REPO=HERE.parents[1]; TOOL=REPO/"tools/agx-isa"
OUT=HERE/"raw/run01"
DOMAIN={"dst":(0,1,7,15),"srcA_size":(0,1),"srcA_reg":(0,1,31,63,95),"opsel":(4,5),"imm_mant":(0,1,7),"imm_exp":(8,11,15),"imm_sign":(0,1)}
SEMANTIC=("dst","srcA_size","srcA_reg","opsel","imm_flag","imm_mant","imm_exp","imm_sign")
EXCLUDED=("opflags","ctrl_lo","mods")
EXPECTED_COUNT=1440
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def load():
 sys.path.insert(0,str(TOOL)); import isadb
 return isadb
def main()->int:
 out=OUT/"result.json"
 if OUT.exists():raise SystemExit("append-only output exists")
 OUT.mkdir(parents=True)
 inputs=(HERE/"PRE_REGISTRATION.md",HERE/"analysis/audit_falu2i.py",TOOL/"isadb.py",TOOL/"roundtrip_test.py",TOOL/"db.json")
 revision=subprocess.run(["git","rev-parse","HEAD"],cwd=REPO,check=True,capture_output=True,text=True).stdout.strip()
 (OUT/"00_inputs.json").write_text(json.dumps({"schema":1,"revision":revision,"inputs":{str(p.relative_to(REPO)):sha(p) for p in inputs},"pre_registration_sha256":sha(HERE/"PRE_REGISTRATION.md")},indent=2,sort_keys=True)+"\n")
 subprocess.run([sys.executable,str(TOOL/"roundtrip_test.py")],cwd=TOOL,check=True,timeout=30,capture_output=True,text=True)
 isadb=load(); db=json.loads((TOOL/"db.json").read_text()); desc=next(x for x in db["instructions"] if x["mnemonic"]=="falu2i")
 assert {x["name"] for x in desc["fields"]}==set(SEMANTIC)|set(EXCLUDED)
 assert not any(x["type"]=="raw" for x in desc["fields"])
 cases=[]; encodings=set()
 for values in itertools.product(*(DOMAIN[key] for key in DOMAIN)):
  v=dict(zip(DOMAIN,values)); fields={**v,"imm_flag":1,"opflags":0,"ctrl_lo":0,"mods":0}
  encoded=isadb.assemble("falu2i",fields); decoded,used=isadb.decode_one(encoded,0)
  assert used==6 and decoded["mnemonic"]=="falu2i" and isadb.assemble("falu2i",decoded["fields"])==encoded
  assert all(decoded["fields"][key]==fields[key] for key in SEMANTIC)
  assert all(decoded["fields"][key]==0 for key in EXCLUDED)
  assert encoded not in encodings; encodings.add(encoded)
  cases.append(encoded.hex())
 assert len(cases)==EXPECTED_COUNT
 report={"schema":1,"scope":"falu2i semantic sub-schema only; no hardware claim","descriptor":"falu2i","semantic_fields":SEMANTIC,"excluded_nonsemantic_fields":EXCLUDED,"domain":DOMAIN,"expected_vectors":EXPECTED_COUNT,"unique_encodings":len(encodings),"all_round_trip":True,"encoding_sha256":hashlib.sha256("".join(cases).encode()).hexdigest()}
 out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(json.dumps(report,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
