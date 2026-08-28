#!/usr/bin/env python3
"""Scan each localization fragment main for byte0==0x57,byte2==0x54 occurrences
(candidate kill/mask-submit op) and byte0==0x07,byte2==0x54 occurrences (frag
epilog/fence family), with 6 bytes of context each way. Pure byte scan -- no
semantic assumption about instruction boundaries, so it cannot be fooled by a
tokenizer mis-length. Read-only analysis of our own compiled bytes."""
import sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
HEXDIR = HERE.parent / "work" / "hex"

def scan(name, buf):
    hits57 = []
    hits07 = []
    for i in range(len(buf) - 2):
        if buf[i] == 0x57 and buf[i+2] == 0x54:
            hits57.append(i)
        if buf[i] == 0x07 and buf[i+2] == 0x54:
            hits07.append(i)
    print(f"=== {name} (len={len(buf)}) ===")
    for i in hits57:
        ctx = buf[max(0,i-2):i+10]
        print(f"  0x57@{i:#04x}: window[-2:+10]={ctx.hex()}  exact6={buf[i:i+6].hex()}")
    for i in hits07:
        ctx = buf[max(0,i-2):i+10]
        print(f"  0x07@{i:#04x}: window[-2:+10]={ctx.hex()}  exact6={buf[i:i+6].hex()}")
    if not hits57:
        print("  (no 0x57/../0x54 occurrence)")
    print()

for name in ["loc_base", "loc_if_nodiscard", "loc_if_discard", "loc_samplemask", "loc_samplemask_discard"]:
    hexstr = (HEXDIR / f"{name}.frag.hex").read_text().strip()
    buf = bytes.fromhex(hexstr)
    scan(name, buf)
