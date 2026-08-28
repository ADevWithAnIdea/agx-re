#!/usr/bin/env python3
"""tmo.py -- hard-timeout process wrapper (this host has no coreutils `timeout`).
Usage: tmo.py SECONDS CMD...   -> exits 124 on timeout, else the child's status."""
import os, signal, subprocess, sys
sec = float(sys.argv[1])
p = subprocess.Popen(sys.argv[2:], start_new_session=True)
try:
    sys.exit(p.wait(timeout=sec))
except subprocess.TimeoutExpired:
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except ProcessLookupError:
        pass
    sys.stderr.write(f"TIMEOUT after {sec}s\n")
    sys.exit(124)
