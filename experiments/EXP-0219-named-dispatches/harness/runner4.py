#!/usr/bin/env python3
"""runner4.py -- EXP-0204 persistent-runner drivers.

FORKED FROM OUR OWN experiments/EXP-0172-g17p-onefield-tail/harness/runner2.py
(itself EXP-0163's, itself EXP-0155's, itself EXP-0143's), with TWO changes,
both mandated by FIELD-SWEEP-PROTOCOL sec.3(d):

  CHANGE 1 -- ONE READER THREAD PER CHILD, TAGGED BY OWNER.  runner2.py starts a
  FRESH daemon thread per read and abandons it on timeout; the thread resolves
  `self.proc` when it is finally scheduled, so it can attach to the REPLACEMENT
  child and race the foreground reader.  EXP-0178 proved the consequence: ONE
  benign case poisoned every later request, and three consecutive cases were
  recorded `hang` with restarts=99 -- ALL FALSE.  Section 3(d) was widened the
  same day: a mere WATCHDOG TIMEOUT is enough to start the cascade, no real hang
  required.  The fix here is EXP-0178's saferunner.py shape: `_install_pump()`
  starts exactly ONE thread per child in `_start()`, pushing `(proc, line)` onto
  a queue, and `_read_line` DISCARDS any tuple whose proc is not the current
  child.  EOF pushes an explicit `(proc, None)` so DEF-0153-2 (a dead child's
  `""` read forever, spinning at 100 % CPU) stays fixed.

  CHANGE 2 -- A MALFORMED RESPONSE IS A MEASUREMENT FAILURE, NOT AN OBSERVATION.
  A truncated surface line is recorded as status MALFORMED with the raw lines
  kept, and is never scored as a hang, a fault or an inert case.

Plus the plumbing EXP-0204's own carriers need: the EXP-0204 surface tags
(TEXWM<level>, TEXWC<face>, TEXWB, TEXWR, TEXWG), a mipmapped sampled texture,
and MULTIPLE numbered buffers rather than only buffer 0.

CLEAN-ROOM: process/protocol plumbing over our own OWN-SHADER runners.
"""
import os
import queue
import signal
import subprocess
import threading
import time

FOREIGN = "InnocentVictim"
MAX_FOREIGN_RETRIES = 8

# Every response-line prefix that carries a raw byte surface.
_HEXTAGS = ("PIX", "DEPTH", "TEXW", "OUTBUF", "OUT ")


class _Child:
    def __init__(self, cmd, ready_prefix="READY", ready_timeout=90):
        self.cmd = cmd
        self.ready_prefix = ready_prefix
        self.ready_timeout = ready_timeout
        self.proc = None
        self.restarts = 0
        self._q = queue.Queue()
        self._start()

    # -- CHANGE 1: one pump thread per child, tagged by the child it read from --
    def _install_pump(self, proc):
        def pump():
            try:
                for line in iter(proc.stdout.readline, ""):
                    self._q.put((proc, line))
            except Exception:
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
            except Exception:
                pass
            raise RuntimeError(f"child not ready: {ln!r} {err}")
        self.device = ln.split(None, 1)[1].strip() if " " in ln else "?"

    def _readline(self, timeout):
        """One line from the CURRENT child, or None on timeout/EOF.

        Lines produced by a previous child are discarded rather than handed to
        the wrong request -- that is the whole point of the tag.
        """
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
        except Exception:
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
        except Exception:
            self.kill()


def render_cmd(frun, source, cfg, archive=None, scratch=None, build=None,
               bufs=None, vname="v_main", fname="f_main"):
    """The EXACT command line for a carrier, used for BOTH --build-archive and
    the persistent run, so MTLPipelineOptionFailOnBinaryArchiveMiss can never
    miss on a descriptor mismatch."""
    cmd = [frun, "--source", source, "--vertex", vname, "--fragment", fname,
           "--color-format", str(cfg["color_format"]),
           "--width", str(cfg["width"]), "--height", str(cfg["height"]),
           "--samples", str(cfg.get("samples", 1)),
           "--rt-count", str(cfg.get("rt_count", 1))]
    if build:
        cmd += ["--build-archive", build]
    else:
        cmd += ["--archive", archive, "--scratch", scratch, "--persist"]
    if cfg.get("depth"):
        cmd.append("--depth")
    if cfg.get("resolve"):
        cmd.append("--resolve")
    if cfg.get("rt_array"):
        cmd += ["--rt-array", str(cfg["rt_array"])]
    if cfg.get("tex_sample"):
        cmd += ["--tex-sample", "%d,%d" % cfg["tex_sample"]]
    if cfg.get("tex_write"):
        cmd += ["--tex-write", "%d,%d" % cfg["tex_write"]]
    if cfg.get("tex_depth"):
        cmd += ["--tex-depth", "%d,%d" % cfg["tex_depth"]]
    if cfg.get("tex_extra"):
        cmd.append("--tex-extra")
    if cfg.get("tex_write_arr"):
        cmd += ["--tex-write-arr", "%d,%d,%d" % cfg["tex_write_arr"]]
    if cfg.get("tex_write_3d"):
        cmd += ["--tex-write-3d", "%d,%d,%d" % cfg["tex_write_3d"]]
    if cfg.get("tex_write_half"):
        cmd += ["--tex-write-half", "%d,%d" % cfg["tex_write_half"]]
    if cfg.get("tex_write_uint"):
        cmd += ["--tex-write-uint", "%d,%d" % cfg["tex_write_uint"]]
    # ---- EXP-0204 surfaces ----
    if cfg.get("tex_mip"):
        cmd += ["--tex-mip", "%d,%d,%d" % cfg["tex_mip"]]
    if cfg.get("tex_write_mip"):
        cmd += ["--tex-write-mip", "%d,%d,%d" % cfg["tex_write_mip"]]
    if cfg.get("tex_write_cube"):
        cmd += ["--tex-write-cube", str(cfg["tex_write_cube"])]
    if cfg.get("tex_write_buf"):
        cmd += ["--tex-write-buf", str(cfg["tex_write_buf"])]
    if cfg.get("tex_write_r32"):
        cmd += ["--tex-write-r32", "%d,%d" % cfg["tex_write_r32"]]
    if cfg.get("tex_write_rg32"):
        cmd += ["--tex-write-rg32", "%d,%d" % cfg["tex_write_rg32"]]
    if cfg.get("clear"):
        cmd += ["--clear", ",".join(str(v) for v in cfg["clear"])]
    if cfg.get("out_buf"):
        cmd += ["--out-buf", "%d=%d" % cfg["out_buf"]]
    for idx, words in sorted((bufs or {}).items()):
        cmd += ["--buf-u32", "%d=" % idx + ",".join(str(v) for v in words)]
    return cmd


class RenderRunner(_Child):
    def __init__(self, frun, source, archive, scratch, cfg, bufs=None):
        self._n = 0
        super().__init__(render_cmd(frun, source, cfg, archive=archive,
                                    scratch=scratch, bufs=bufs))

    def render(self, splices, timeout=15.0):
        for attempt in range(MAX_FOREIGN_RETRIES + 1):
            out = self._render1(splices, timeout)
            if not (out.get("status") == "CMDBUF_ERROR"
                    and FOREIGN in out.get("error", "")):
                if attempt:
                    out["foreign_retries"] = attempt
                return out
            time.sleep(0.25 * (attempt + 1))
        out["foreign_retries"] = MAX_FOREIGN_RETRIES
        out["status"] = "FOREIGN_FAULT"
        return out

    def _render1(self, splices, timeout=15.0):
        self._n += 1
        rid = f"r{self._n}"
        parts = [rid, str(len(splices))] + [f"{o}={h}" for o, h in splices]
        try:
            self.proc.stdin.write(" ".join(parts) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self.restart()
            return {"status": "HANG", "error": "child pipe broken", "restarted": True}
        out = {"status": "UNKNOWN", "restarted": False, "surf": {}, "missing": [],
               "raw_lines": []}
        while True:
            ln = self._readline(timeout)
            if ln is None:
                self.restart()
                out["status"] = "HANG"
                out["error"] = f"no response within {timeout}s"
                out["restarted"] = True
                return out
            ln = ln.rstrip("\n")
            out["raw_lines"].append(ln[:80])
            if ln.startswith("STATUS "):
                out["status"] = ln.split(None, 1)[1]
            elif ln.startswith("SENTINEL "):
                out["sentinel"] = ln.split(None, 1)[1]
            elif ln.startswith("ACTUAL "):
                out["actual"] = ln.split(None, 1)[1]
            elif ln.startswith("PROGHASH "):
                out["proghash"] = ln.split(None, 1)[1]
            elif ln.startswith("ERRDOM "):
                out["errdom"] = ln.split(None, 1)[1]
            elif ln.startswith("ERROR "):
                out["error"] = ln.split(None, 1)[1]
            elif ln.startswith("OCC "):
                out["occ"] = int(ln.split()[1])
            elif ln.startswith("DONE "):
                out.pop("raw_lines", None)
                return out
            elif any(ln.startswith(t) for t in _HEXTAGS):
                tag, _, rest = ln.partition(" ")
                if tag.endswith("_UNAVAILABLE"):
                    out["missing"].append(tag)
                    continue
                try:
                    out["surf"][tag] = bytes.fromhex(rest)
                except ValueError:
                    # CHANGE 2: a truncated surface line is a MEASUREMENT
                    # FAILURE, kept with its raw text, never scored.
                    out["status"] = "MALFORMED"
                    out["error"] = f"unparsable surface line for {tag}"
                    return out


class ComputeRunner(_Child):
    """tools/agxtest/agxrun_persist protocol (our own EXP-0005 tool)."""

    def __init__(self, exe, source, function, in_file, out_bytes, grid, tg):
        self.in_file = in_file
        self.out_bytes = out_bytes
        self.grid = grid
        self.tg = tg
        self._n = 0
        super().__init__([exe, "--source", source, "--function", function])

    def run(self, archive, timeout=15.0):
        for attempt in range(MAX_FOREIGN_RETRIES + 1):
            out = self._run1(archive, timeout)
            if not (out.get("status") == "CMDBUF_ERROR"
                    and FOREIGN in out.get("error", "")):
                if attempt:
                    out["foreign_retries"] = attempt
                return out
            time.sleep(0.25 * (attempt + 1))
        out["foreign_retries"] = MAX_FOREIGN_RETRIES
        out["status"] = "FOREIGN_FAULT"
        return out

    def _run1(self, archive, timeout=15.0):
        self._n += 1
        rid = f"c{self._n}"
        line = f"{rid} {archive} {self.grid} {self.tg} 1 1:{self.in_file} 1 0:{self.out_bytes}\n"
        try:
            self.proc.stdin.write(line)
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self.restart()
            return {"status": "HANG", "error": "child pipe broken", "restarted": True}
        out = {"status": "UNKNOWN", "restarted": False, "surf": {}, "missing": []}
        while True:
            ln = self._readline(timeout)
            if ln is None:
                self.restart()
                out["status"] = "HANG"
                out["error"] = f"no response within {timeout}s"
                out["restarted"] = True
                return out
            ln = ln.rstrip("\n")
            if ln.startswith("STATUS "):
                out["status"] = ln.split(None, 1)[1]
            elif ln.startswith("OUT "):
                bits = ln.split(None, 2)
                if len(bits) < 3:
                    out["status"] = "MALFORMED"
                    out["error"] = "truncated OUT line"
                    return out
                out["surf"]["OUT"] = bytes.fromhex(bits[2])
            elif ln.startswith("ERROR "):
                out["error"] = ln.split(None, 1)[1]
            elif ln.startswith("DONE "):
                return out
