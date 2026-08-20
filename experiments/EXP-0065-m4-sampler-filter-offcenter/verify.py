#!/usr/bin/env python3
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT={".gitignore","PRE_REGISTRATION.md","README.md","RESULTS.md","harness","raw","run.py","verify.py"}
assert not HERE.is_symlink() and {p.name for p in HERE.iterdir()}==ROOT
for n in ROOT-{"harness","raw"}:assert (HERE/n).is_file() and not (HERE/n).is_symlink()
assert not (HERE/"harness").is_symlink() and {p.name for p in (HERE/"harness").iterdir()}=={"probe.m"} and (HERE/"harness/probe.m").is_file() and not (HERE/"harness/probe.m").is_symlink()
assert not (HERE/"raw").is_symlink() and {p.name for p in (HERE/"raw").iterdir()}=={"m4-20260820-run01","m4-20260820-run02"}
for n in ("m4-20260820-run01","m4-20260820-run02"):
 d=HERE/"raw"/n;assert d.is_dir() and not d.is_symlink() and {p.name for p in d.iterdir()}=={"00_inputs.json","01_build.json","02_run.json"} and all(p.is_file() and not p.is_symlink() for p in d.iterdir())
 b=json.loads((d/"01_build.json").read_text());r=json.loads((d/"02_run.json").read_text());assert set(b)==set(r)=={"exit","stdout","stderr"}
 assert b["exit"]==r["exit"]==0
assert "0.5,0.5,0,1" in json.loads((HERE/"raw/m4-20260820-run01/02_run.json").read_text())["stdout"]
print("PASS STOP: public output retained but argv/environment/timeout provenance absent")
