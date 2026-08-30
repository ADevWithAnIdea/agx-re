#!/usr/bin/env python3
"""EXP-0148 -- run the frozen roundtrip_test.py against a chosen variant tree
without mutating sys.path for the live tools/agx-isa/ copy."""
import os, sys, runpy
d = os.path.abspath(sys.argv[1])
sys.path.insert(0, d)
sys.argv = [os.path.join(d, "roundtrip_test.py")]
runpy.run_path(sys.argv[0], run_name="__main__")
