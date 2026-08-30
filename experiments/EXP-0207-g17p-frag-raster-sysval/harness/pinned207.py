#!/usr/bin/env python3
"""EXP-0207 PINNED toolchain resolver.

The neo's shared `~/agxre/tools/agx-isa/db.json` is stale and a path-search
fallback has silently resolved it for another experiment before.  A harness must
FAIL when its pinned toolchain is absent, not quietly resolve something else --
so this module never searches, never falls back, and exits non-zero if a pinned
blob is missing or its sha256 does not match the value frozen at
pre-registration.

`isadb.py` loads `db.json` from ITS OWN directory, so pinning means pinning the
PAIR into `pinned/` and importing `pinned/isadb.py` by absolute path.

(Structure follows our own EXP-0178 harness/pinned_isa.py.)
"""
import hashlib
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
PINNED = os.path.join(EXP, "pinned")

EXPECT = {
    "isadb.py":        "500db91a6077cd1968570dd1f7c08ae22a63bbfb39e688168ce711397375aa9f",
    "db.json":         "2412eac1cad4449eb385702062abd03e5c926d04f7d384e6bf3684c9c4c7c6c4",
    "agxparse.py":     "72911ee524fa1e327914445a0b38837b4a71e8525565a03f2cb7f520733c6a0f",
    "mesh_extract.py": "4a48fd421f03c5c341d48ad2ec869d71de145c90cf97a04ec2c17919ee242e13",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def verify():
    out = {}
    for name, want in EXPECT.items():
        p = os.path.join(PINNED, name)
        if not os.path.exists(p):
            sys.stderr.write("FATAL: pinned toolchain blob missing: %s\n"
                             "       This harness does NOT fall back to a path search.\n" % p)
            raise SystemExit(4)
        got = sha256(p)
        if got != want:
            sys.stderr.write("FATAL: pinned toolchain blob CHANGED: %s\n"
                             "       expected %s\n       actual   %s\n" % (p, want, got))
            raise SystemExit(4)
        out[name] = (p, got)
    return out


def load_isadb():
    verify()
    spec = importlib.util.spec_from_file_location(
        "exp0207_pinned_isadb", os.path.join(PINNED, "isadb.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    doc = json.load(open(os.path.join(PINNED, "db.json")))
    assert len(mod.DB) == len(doc["instructions"]), "isadb bound to a foreign db.json"
    return mod


def agxparse_path():
    verify()
    return os.path.join(PINNED, "agxparse.py")


def mesh_extract_path():
    verify()
    return os.path.join(PINNED, "mesh_extract.py")


def field_geometry(mnemonic, field):
    doc = json.load(open(os.path.join(PINNED, "db.json")))
    for i in doc["instructions"]:
        if i["mnemonic"] == mnemonic:
            for f in i["fields"]:
                if f["name"] == field:
                    return f["start"], f["width"], 1 << f["width"]
            raise KeyError("%s has no field %s in the pinned db" % (mnemonic, field))
    raise KeyError("no instruction %s in the pinned db" % mnemonic)


if __name__ == "__main__":
    r = verify()
    for k, (p, s) in sorted(r.items()):
        print("%-16s %s  %s" % (k, s, p))
    m = load_isadb()
    print("pinned isadb OK: %d instructions" % len(m.DB))
