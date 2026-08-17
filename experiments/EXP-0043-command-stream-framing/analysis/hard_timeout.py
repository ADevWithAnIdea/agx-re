#!/usr/bin/env python3
"""Run a command in its own process group and enforce a hard wall timeout."""

import argparse
import os
import signal
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command or args.seconds <= 0:
        parser.error("a command and a positive --seconds value are required")

    proc = subprocess.Popen(command, start_new_session=True)
    try:
        return proc.wait(timeout=args.seconds)
    except subprocess.TimeoutExpired:
        print(f"HARD_TIMEOUT seconds={args.seconds} pid={proc.pid}", file=sys.stderr)
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            return proc.wait(timeout=2.0) or 124
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            return 124


if __name__ == "__main__":
    sys.exit(main())
