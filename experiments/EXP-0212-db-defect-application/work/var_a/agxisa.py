#!/usr/bin/env python3
# agxisa.py -- CLI front-end for the clean-room A18 Pro (G17P) AGX ISA database.
#
# Subcommands (all driven by the single table in isadb.py):
#   tokenize <hex>       split a raw _agc.main hex string into instructions
#   disasm   <hex>       decode one instruction (or a stream) to mnemonic+fields
#   asm      <mnem> k=v  assemble one instruction from fields -> hex
#   dumpdb               print the DB summary
#   json                 print the machine-readable DB as JSON
#
# CLEAN-ROOM: operates only on OUR OWN compiled shader bytes / our own table.

import sys
import isadb


def _fmt_fields(fields):
    return " ".join(f"{k}={v:#x}" for k, v in fields.items())


def cmd_tokenize(hexstr):
    buf = bytes.fromhex(hexstr.replace(" ", ""))
    recs, leftover = isadb.disassemble(buf)
    off = 0
    for r in recs:
        if r.get("error"):
            print(f"  +{off:#04x}  <UNKNOWN>  {r['hex']}   ({r['error']})")
            break
        opn = f" [{r['op_mnemonic']}]" if r.get("op_mnemonic") else ""
        print(f"  +{off:#04x}  {r['mnemonic']:12s}{opn:10s} {r['hex']:<20s} "
              f"{_fmt_fields(r['fields'])}")
        off += r["length"]
    if leftover:
        print(f"LEFTOVER {len(leftover)} bytes: {leftover.hex()}  -> NOT CLEAN")
        return 1
    print(f"CLEAN: {len(recs)} instructions, 0 leftover bytes")
    return 0


def cmd_disasm(hexstr):
    buf = bytes.fromhex(hexstr.replace(" ", ""))
    rec, length = isadb.decode_one(buf, 0)
    print(f"mnemonic  : {rec['mnemonic']}")
    if rec.get("op_mnemonic"):
        print(f"op        : {rec['op_mnemonic']}")
    print(f"length    : {rec['length']} bytes")
    print(f"fields    : {_fmt_fields(rec['fields'])}")
    print(f"semantics : {rec['semantics']}")
    print(f"provenance: {rec['provenance']}")
    return 0


def cmd_asm(argv):
    mnem = argv[0]
    fields = {}
    for kv in argv[1:]:
        k, _, v = kv.partition("=")
        fields[k] = int(v, 0)
    # allow assembling by arithmetic op mnemonic too
    if mnem in ("fadd", "fmul", "fma", "fmax", "fmin", "fmov"):
        raw = isadb.assemble_op(mnem, **fields)
    else:
        raw = isadb.assemble(mnem, fields)
    print(raw.hex())
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "tokenize":
        return cmd_tokenize(sys.argv[2])
    if cmd == "disasm":
        return cmd_disasm(sys.argv[2])
    if cmd == "asm":
        return cmd_asm(sys.argv[2:])
    if cmd == "dumpdb":
        import subprocess
        return subprocess.call([sys.executable, "isadb.py"])
    if cmd == "json":
        print(isadb.to_json())
        return 0
    print(f"unknown subcommand {cmd!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
