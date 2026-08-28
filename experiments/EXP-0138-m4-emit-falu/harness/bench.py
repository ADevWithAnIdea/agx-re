#!/usr/bin/env python3
"""EXP-0138 hardware bench: one persistent M4 device, many spliced programs.

Wraps `tools/agxtest/persistrun.py` (READ-ONLY, unmodified) so a dense field
sweep is ONE process launch instead of one per case, per
`experiments/FIELD-SWEEP-PROTOCOL.md` section 2. Each case writes a spliced
copy of a base archive (compiled from OUR OWN MSL by `tools/shdump`) and
issues one request with a hard per-request watchdog; a wedge kills and
restarts the child, and the case is recorded as `hang`.

CLEAN-ROOM: pure process/file plumbing over our own tools. No Apple binary is
disassembled or introspected.
"""
import importlib.util
import os
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "shdump"))
import agxparse  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


PersistRunner = _load("persistrun", str(REPO / "tools" / "agxtest" / "persistrun.py")).PersistRunner


class Bench:
    def __init__(self, source, function, bin_dir, workdir, fast_math=False,
                 timeout=10.0):
        self.source = str(source)
        self.function = function
        self.bin_dir = Path(bin_dir)
        self.work = Path(workdir)
        self.work.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.fast_math = fast_math
        self.hangs = 0
        self.victim_retries = 0
        base = self.work / ("base_%s.bin" % function)
        cmd = [str(self.bin_dir / "shdump"), "-o", str(base), "-f", function]
        if not fast_math:
            cmd.append("--no-fast-math")
        cmd.append(self.source)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0 or not base.exists():
            raise RuntimeError("shdump failed for %s: %s" % (function, r.stderr))
        self.basebuf = base.read_bytes()
        loc = agxparse.locate_region(self.basebuf, "_agc.main")
        if loc is None:
            raise RuntimeError("could not locate _agc.main in %s" % base)
        self.region_off, self.region_len = loc
        _, pieces = agxparse.extract_agx(self.basebuf)
        self.main_bytes = pieces["_agc.main"]
        assert len(self.main_bytes) == self.region_len, (len(self.main_bytes), self.region_len)
        self.runner = PersistRunner(source=self.source, function=function,
                                    fast_math=fast_math,
                                    agxrun_persist=str(self.bin_dir / "agxrun_persist"))
        self.device = self.runner.device
        self._n = 0

    # -- input/output plumbing -------------------------------------------
    def write_in(self, idx, values, fmt="<f"):
        p = self.work / ("in%d.bin" % idx)
        p.write_bytes(b"".join(struct.pack(fmt, v) for v in values))
        return str(p)

    def splice(self, pairs):
        """pairs: [(offset_within_main, bytes)] -> path to spliced archive."""
        buf = bytearray(self.basebuf)
        for off, data in pairs:
            if off + len(data) > self.region_len:
                raise ValueError("splice %d+%d exceeds region %d" % (off, len(data), self.region_len))
            buf[self.region_off + off: self.region_off + off + len(data)] = data
        self._n += 1
        p = self.work / ("sp.bin")
        p.write_bytes(bytes(buf))
        return str(p)

    # A command buffer can be reported "Discarded (victim of GPU error/
    # recovery)" when an UNRELATED process on the same GPU faults -- this host
    # runs several concurrent RE experiments, each deliberately submitting
    # illegal encodings. That status carries NO information about our own
    # bytes (the buffer never executed), so it is retried rather than
    # recorded as a result. Every retry is counted and reported.
    VICTIM_MARKERS = ("Discarded", "victim of GPU error")

    def _is_victim(self, resp):
        e = resp.get("error") or ""
        return resp["status"] != "OK" and any(m in e for m in self.VICTIM_MARKERS)

    def run(self, pairs, ins, outs, grid=1, tg=1, max_retries=6):
        arch = self.splice(pairs)
        retries = 0
        while True:
            resp = self.runner.request(archive=arch, grid=grid, tg=tg, ins=ins,
                                       outs=outs, timeout=self.timeout)
            if resp["status"] == "HANG":
                self.hangs += 1
            if retries < max_retries and self._is_victim(resp):
                retries += 1
                self.victim_retries += 1
                continue
            resp["retries"] = retries
            return resp

    def close(self):
        try:
            self.runner.close()
        except Exception:
            pass


def words_f32(raw, n):
    return [struct.unpack_from("<f", raw, 4 * i)[0] for i in range(min(n, len(raw) // 4))]


def words_u32(raw, n):
    return [struct.unpack_from("<I", raw, 4 * i)[0] for i in range(min(n, len(raw) // 4))]


def halfs(raw, n):
    return [struct.unpack_from("<e", raw, 2 * i)[0] for i in range(min(n, len(raw) // 2))]
