#!/usr/bin/env python3
"""runner220.py -- EXP-0220 persistent compute-runner driver.

FORKED FROM OUR OWN experiments/EXP-0219-named-dispatches/harness/runner4.py
(itself EXP-0204's, itself EXP-0172's, itself EXP-0163's), keeping BOTH of the
fixes FIELD-SWEEP-PROTOCOL section 3(d) mandates:

  ONE READER THREAD PER CHILD, TAGGED BY OWNER.  The shared `persistrun.py`
  starts a fresh daemon thread per read and abandons it on timeout; the thread
  resolves `self.proc` when it is finally scheduled, so it can attach to the
  REPLACEMENT child and race the foreground reader.  EXP-0178 proved the
  consequence: one benign case poisoned every later request and three
  consecutive cases were recorded `hang` with restarts=99 -- ALL FALSE.  Here
  `_install_pump` starts exactly ONE thread per child and `_readline` discards
  any tuple whose proc is not the current child.

  A MALFORMED RESPONSE IS A MEASUREMENT FAILURE, NOT AN OBSERVATION.  A
  truncated surface line is recorded as MALFORMED with the raw lines kept, and
  is never scored as a hang, a fault, or an inert case.

WHAT IS NEW HERE: multi-buffer requests.  EXP-0220 uploads all three buffers
(poisoned out, mem, imem) on every dispatch and reads all three back, so a store
that lands in the WRONG buffer is caught rather than merely missed.

CLEAN-ROOM: process/protocol plumbing over our own OWN-SHADER runner.
"""
import os
import queue
import signal
import subprocess
import threading
import time

FOREIGN = "InnocentVictim"
MAX_FOREIGN_RETRIES = 8


class _Child(object):
    def __init__(self, cmd, ready_prefix="READY", ready_timeout=120):
        self.cmd = cmd
        self.ready_prefix = ready_prefix
        self.ready_timeout = ready_timeout
        self.proc = None
        self.restarts = 0
        self._q = queue.Queue()
        self._start()

    def _install_pump(self, proc):
        def pump():
            try:
                for line in iter(proc.stdout.readline, ""):
                    self._q.put((proc, line))
            except Exception:                                  # noqa: BLE001
                pass
            self._q.put((proc, None))          # explicit EOF (DEF-0153-2)
        t = threading.Thread(target=pump, daemon=True)
        t.start()
        return t

    def _start(self):
        self.proc = subprocess.Popen(
            self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
        self._pump = self._install_pump(self.proc)
        ln = self._readline(self.ready_timeout)
        if not ln or not ln.startswith(self.ready_prefix):
            err = ""
            try:
                err = self.proc.stderr.read()
            except Exception:                                  # noqa: BLE001
                pass
            raise RuntimeError("child not ready: %r %s" % (ln, err))
        self.device = ln.split(None, 1)[1].strip() if " " in ln else "?"

    def _readline(self, timeout):
        deadline = time.monotonic() + timeout
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            try:
                proc, line = self._q.get(timeout=left)
            except queue.Empty:
                return None
            if proc is not self.proc:
                continue                        # stale child: drop it
            if line is None:
                return None                     # EOF on the current child
            return line

    def kill(self):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            self.proc.wait(timeout=10)
        except Exception:                                      # noqa: BLE001
            pass

    def restart(self):
        self.kill()
        self.restarts += 1
        self._start()

    def close(self):
        try:
            if self.proc and self.proc.stdin:
                self.proc.stdin.close()
            if self.proc:
                self.proc.wait(timeout=10)
        except Exception:                                      # noqa: BLE001
            self.kill()


class ComputeRunner(_Child):
    """tools/agxtest/agxrun_persist protocol, multi-buffer."""

    def __init__(self, exe, source, function, fast_math=False):
        cmd = [exe, "--source", source, "--function", function]
        if not fast_math:
            cmd.append("--no-fast-math")
        self._n = 0
        super(ComputeRunner, self).__init__(cmd)

    def run(self, archive, ins, outs, grid=1, tg=1, timeout=20.0):
        """ins: [(idx, path)]   outs: [(idx, nbytes)]"""
        for attempt in range(MAX_FOREIGN_RETRIES + 1):
            out = self._run1(archive, ins, outs, grid, tg, timeout)
            if not (out.get("status") == "CMDBUF_ERROR"
                    and FOREIGN in out.get("error", "")):
                if attempt:
                    out["foreign_retries"] = attempt
                return out
            time.sleep(0.25 * (attempt + 1))
        out["foreign_retries"] = MAX_FOREIGN_RETRIES
        out["status"] = "FOREIGN_FAULT"
        return out

    def _run1(self, archive, ins, outs, grid, tg, timeout):
        self._n += 1
        rid = "c%d" % self._n
        parts = [rid, archive, str(grid), str(tg), str(len(ins))]
        parts += ["%d:%s" % (i, p) for i, p in ins]
        parts += [str(len(outs))]
        parts += ["%d:%d" % (i, n) for i, n in outs]
        try:
            self.proc.stdin.write(" ".join(parts) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self.restart()
            return {"status": "HANG", "error": "child pipe broken", "restarted": True,
                    "surf": {}}
        out = {"status": "UNKNOWN", "restarted": False, "surf": {}, "raw_lines": []}
        while True:
            ln = self._readline(timeout)
            if ln is None:
                self.restart()
                out["status"] = "HANG"
                out["error"] = "no response within %ss" % timeout
                out["restarted"] = True
                return out
            ln = ln.rstrip("\n")
            if len(ln) < 200:
                out["raw_lines"].append(ln)
            if ln.startswith("STATUS "):
                out["status"] = ln.split(None, 1)[1]
            elif ln.startswith("GPUTIME_NS "):
                out["gputime_ns"] = int(ln.split()[1])
            elif ln.startswith("ERROR "):
                out["error"] = ln.split(None, 1)[1]
            elif ln.startswith("OUT "):
                bits = ln.split(None, 2)
                if len(bits) < 3:
                    out["status"] = "MALFORMED"
                    out["error"] = "truncated OUT line"
                    return out
                try:
                    out["surf"][int(bits[1])] = bytes.fromhex(bits[2])
                except ValueError:
                    out["status"] = "MALFORMED"
                    out["error"] = "unparsable OUT hex for buffer %s" % bits[1]
                    return out
            elif ln.startswith("DONE "):
                out.pop("raw_lines", None)
                return out
