#!/usr/bin/env python3
from __future__ import annotations
import hashlib,itertools,json,subprocess,types
from pathlib import Path
HERE=Path(__file__).resolve().parent; REPO=HERE.parents[1]; RAW=HERE/"raw/run01"
INPUT_KEYS={"experiments/EXP-0060-isa-falu2i-bound-vectors/PRE_REGISTRATION.md","experiments/EXP-0060-isa-falu2i-bound-vectors/analysis/audit_falu2i.py","tools/agx-isa/isadb.py","tools/agx-isa/roundtrip_test.py","tools/agx-isa/db.json"}
ROOT={".gitignore","INTERPRETATION_CORRECTION.md","PRE_REGISTRATION.md","README.md","RESULTS.md","analysis","raw","make_manifest.py","manifest.json","verify.py"}
DOMAIN={"dst":[0,1,7,15],"imm_exp":[8,11,15],"imm_mant":[0,1,7],"imm_sign":[0,1],"opsel":[4,5],"srcA_reg":[0,1,31,63,95],"srcA_size":[0,1]}
VECTOR_DOMAIN={"dst":[0,1,7,15],"srcA_size":[0,1],"srcA_reg":[0,1,31,63,95],"opsel":[4,5],"imm_mant":[0,1,7],"imm_exp":[8,11,15],"imm_sign":[0,1]}
SEMANTIC=["dst","srcA_size","srcA_reg","opsel","imm_flag","imm_mant","imm_exp","imm_sign"]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check_tree():
 assert not HERE.is_symlink() and {p.name for p in HERE.iterdir()}==ROOT
 for name in ROOT-{"analysis","raw"}:
  p=HERE/name;assert p.is_file() and not p.is_symlink()
 a=HERE/"analysis";assert a.is_dir() and not a.is_symlink() and {p.name for p in a.iterdir()}=={"audit_falu2i.py"}
 assert (a/"audit_falu2i.py").is_file() and not (a/"audit_falu2i.py").is_symlink()
 raw_root=HERE/"raw";assert not raw_root.is_symlink() and raw_root.is_dir() and {p.name for p in raw_root.iterdir()}=={"run01"}
 assert not RAW.is_symlink() and RAW.is_dir() and {p.name for p in RAW.iterdir()}=={"00_inputs.json","result.json"}
 assert all(p.is_file() and not p.is_symlink() for p in RAW.iterdir())
check_tree()
m=json.loads((HERE/"manifest.json").read_text());assert m=={"schema":1,"raw":{"00_inputs.json":sha(RAW/"00_inputs.json"),"result.json":sha(RAW/"result.json")},"result":"structural falu2i semantic subset only"}
i=json.loads((RAW/"00_inputs.json").read_text());assert set(i)=={"schema","revision","inputs","pre_registration_sha256"} and i["schema"]==1 and set(i["inputs"])==INPUT_KEYS
assert i["pre_registration_sha256"]==i["inputs"]["experiments/EXP-0060-isa-falu2i-bound-vectors/PRE_REGISTRATION.md"]
assert subprocess.run(["git","cat-file","-e",i["revision"]+"^{commit}"],cwd=REPO).returncode==0
assert subprocess.run(["git","merge-base","--is-ancestor",i["revision"],"HEAD"],cwd=REPO).returncode==0
blobs={}
for rel,want in i["inputs"].items():
 blob=subprocess.run(["git","show",i["revision"]+":"+rel],cwd=REPO,capture_output=True,check=True).stdout;assert hashlib.sha256(blob).hexdigest()==want
 blobs[rel]=blob
r=json.loads((RAW/"result.json").read_text())
assert set(r)=={"schema","scope","descriptor","semantic_fields","excluded_nonsemantic_fields","domain","expected_vectors","unique_encodings","all_round_trip","encoding_sha256"}
assert r["schema"]==1 and r["scope"]=="falu2i semantic sub-schema only; no hardware claim" and r["descriptor"]=="falu2i" and r["semantic_fields"]==SEMANTIC and r["excluded_nonsemantic_fields"]==["opflags","ctrl_lo","mods"] and r["domain"]==DOMAIN and r["expected_vectors"]==r["unique_encodings"]==1440 and r["all_round_trip"] is True
correction=(HERE/"INTERPRETATION_CORRECTION.md").read_text()
assert "not established by EXP-0060" in correction and "no positive claim about Apple hardware execution" in correction
isadb=types.ModuleType("captured_isadb");exec(compile(blobs["tools/agx-isa/isadb.py"],"captured-isadb.py","exec"),isadb.__dict__)
encodings=set(); cases=[]
for values in itertools.product(*(VECTOR_DOMAIN[key] for key in VECTOR_DOMAIN)):
 fields=dict(zip(VECTOR_DOMAIN,values));fields.update(imm_flag=1,opflags=0,ctrl_lo=0,mods=0)
 encoded=isadb.assemble("falu2i",fields);decoded,used=isadb.decode_one(encoded,0)
 assert used==6 and decoded["mnemonic"]=="falu2i" and isadb.assemble("falu2i",decoded["fields"])==encoded and all(decoded["fields"][k]==fields[k] for k in SEMANTIC) and all(decoded["fields"][k]==0 for k in ("opflags","ctrl_lo","mods")) and encoded not in encodings
 encodings.add(encoded);cases.append(encoded.hex())
assert len(cases)==1440 and hashlib.sha256("".join(cases).encode()).hexdigest()==r["encoding_sha256"]
print("PASS bound 1440-vector structural falu2i subset; no hardware claim")
