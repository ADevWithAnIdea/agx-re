#!/usr/bin/env python3
# Host-side ssh-with-hard-timeout wrapper. Runs a remote command; if it does not
# finish in TIMEOUT seconds (e.g. wedged GPU stalling SSH), kills the ssh process
# and prints TIMEOUT so the caller knows to reboot the device.
import subprocess, sys, signal, os

timeout = float(sys.argv[1])
remote_cmd = sys.argv[2]
ssh = ["sshpass", "-p", "Password_1", "ssh",
       "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=15",
       "user@192.168.170.254", remote_cmd]
p = subprocess.Popen(ssh, start_new_session=True)
try:
    p.wait(timeout=timeout)
    print(f"\n[sshto] exit={p.returncode}")
except subprocess.TimeoutExpired:
    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    print(f"\n[sshto] TIMEOUT after {timeout}s -- remote command killed (GPU likely wedged)")
    sys.exit(124)
