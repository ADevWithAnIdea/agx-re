#!/usr/bin/env python3
"""runner2.py -- EXP-0163 persistent-runner drivers with per-request watchdogs.

Derived from OUR OWN experiments/EXP-0155-g17p-emit-tex-frag/harness/runner.py
(itself from our EXP-0143 runner.py).  EXP-0163's additions are only the extra
observation surfaces its carriers need:

  * the layered colour attachment's per-slice read-backs   (PIX<rt>_S<slice>)
  * the array / 3D / half / uint writable textures         (TEXWA<n>, TEXW3,
                                                            TEXWH, TEXWU)
  * OUTBUF, the device buffer a render carrier writes, which is the PRIMARY
    observation for the multisampled per-sample arm
  * `PIX<n>_UNAVAILABLE`, which the EXP-0155 reader would have tried to parse
    as hex; it is now recorded as an explicit missing surface.

Everything else -- the watchdog, the dead-child EOF fix (EXP-0153), the
InnocentVictim retry policy (FIELD-SWEEP-PROTOCOL sec.7.2) -- is unchanged.

CLEAN-ROOM: process/protocol plumbing over our own OWN-SHADER runners.
"""
import os
import signal
import subprocess
import threading
import time

FOREIGN = "InnocentVictim"
MAX_FOREIGN_RETRIES = 8

# Every response line prefix that carries a raw byte surface.
_HEXTAGS = ("PIX", "DEPTH", "TEXW", "OUTBUF")


class _Child:
    def __init__(self, cmd, ready_prefix="READY", ready_timeout=90):
        self.cmd = cmd
        self.ready_prefix = ready_prefix
        self.ready_timeout = ready_timeout
        self.proc = None
        self.restarts = 0
        self._start()

    def _start(self):
        self.proc = subprocess.Popen(
            self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
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
        """One line, or None on timeout OR on a dead child (EXP-0153 fix: a
        closed stdout returns '' forever and must read as None, or the caller
        spins at 100% CPU with no timeout)."""
        box = [None]

        def rd():
            try:
                box[0] = self.proc.stdout.readline()
            except Exception:
                box[0] = None
        t = threading.Thread(target=rd, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            return None
        if not box[0]:
            return None
        return box[0]

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
               buf0=None, vname="v_main", fname="f_main"):
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
    if cfg.get("clear"):
        cmd += ["--clear", ",".join(str(v) for v in cfg["clear"])]
    if cfg.get("out_buf"):
        cmd += ["--out-buf", "%d=%d" % cfg["out_buf"]]
    if buf0:
        cmd += ["--buf-u32", "0=" + ",".join(str(v) for v in buf0)]
    return cmd


class RenderRunner(_Child):
    def __init__(self, frun, source, archive, scratch, cfg, buf0=None):
        self._n = 0
        super().__init__(render_cmd(frun, source, cfg, archive=archive,
                                    scratch=scratch, buf0=buf0))

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
            elif ln.startswith("SENTINEL "):
                out["sentinel"] = ln.split(None, 1)[1]
            elif ln.startswith("ERRDOM "):
                out["errdom"] = ln.split(None, 1)[1]
            elif ln.startswith("ERROR "):
                out["error"] = ln.split(None, 1)[1]
            elif ln.startswith("OCC "):
                out["occ"] = int(ln.split()[1])
            elif ln.startswith("DONE "):
                return out
            elif any(ln.startswith(t) for t in _HEXTAGS):
                tag, _, rest = ln.partition(" ")
                if tag.endswith("_UNAVAILABLE"):
                    out["missing"].append(tag)
                    continue
                try:
                    out["surf"][tag] = bytes.fromhex(rest)
                except ValueError:
                    out["missing"].append(tag)


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
                _, idx, hexs = ln.split(None, 2)
                out["surf"]["OUT"] = bytes.fromhex(hexs)
            elif ln.startswith("ERROR "):
                out["error"] = ln.split(None, 1)[1]
            elif ln.startswith("DONE "):
                return out
