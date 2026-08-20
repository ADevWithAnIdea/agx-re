#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent; RAW=HERE/"raw/run01"
ROOT={".gitignore","INTERPRETATION_CORRECTION.md","PRE_REGISTRATION.md","README.md","RESULTS.md","analysis","raw","make_manifest.py","manifest.json","verify.py"}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check_tree():
 if HERE.is_symlink() or {p.name for p in HERE.iterdir()}!=ROOT:raise SystemExit("closed experiment root")
 for name in ROOT-{"analysis","raw"}:
  p=HERE/name
  if p.is_symlink() or not p.is_file():raise SystemExit("root regular file")
 a=HERE/"analysis"
 if a.is_symlink() or not a.is_dir() or {p.name for p in a.iterdir()}!={"audit_falu2i.py"}:raise SystemExit("analysis tree")
 if (a/"audit_falu2i.py").is_symlink() or not (a/"audit_falu2i.py").is_file():raise SystemExit("analysis regular file")
 raw_root=HERE/"raw"
 if raw_root.is_symlink() or not raw_root.is_dir() or {p.name for p in raw_root.iterdir()}!={"run01"}:raise SystemExit("closed raw root")
 if RAW.is_symlink() or not RAW.is_dir() or {p.name for p in RAW.iterdir()}!={"00_inputs.json","result.json"}:raise SystemExit("closed raw tree")
 for p in RAW.iterdir():
  if p.is_symlink() or not p.is_file():raise SystemExit("raw regular file")
check_tree()
(HERE/"manifest.json").write_text(json.dumps({"schema":1,"raw":{"00_inputs.json":sha(RAW/"00_inputs.json"),"result.json":sha(RAW/"result.json")},"result":"structural falu2i semantic subset only"},indent=2,sort_keys=True)+"\n")
