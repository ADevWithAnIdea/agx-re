#!/usr/bin/env python3
# EXP-0035 helper: given a compiled archive, list every symbol region, print its
# hex, and tokenize it with the current agx-isa DB (to show recognized ops + the
# novel call/return groups). CLEAN-ROOM: only parses OUR OWN compiled archive.
import sys, subprocess, json, os
HERE = os.path.dirname(os.path.abspath(__file__))

def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()

def main():
    binf = sys.argv[1]
    stage = sys.argv[2] if len(sys.argv) > 2 else "compute"
    rep = json.loads(sh(["python3", os.path.join(HERE,"agxparse.py"), binf, "--json"]))
    st = rep.get("stages", {}).get(stage)
    if not st:
        print("no stage", stage); return
    for (name, start, end, length) in st["regions"]:
        hexs = sh(["python3", os.path.join(HERE,"agxparse.py"), binf,
                   "--stage", stage, "--symbol", name, "--extract-hex"])
        # strip trailing 0600.. padding for readability but keep raw too
        print(f"\n##### region {name}  [{start}:{end}] ({length} B)")
        print("HEX:", hexs)
        tok = sh(["python3", os.path.join(HERE,"agxisa.py"), "tokenize", hexs])
        print(tok)

if __name__ == "__main__":
    main()
