"""FIXTURE for closure_scan's offline gate -- NOT a runnable harness.

Reproduces, in miniature, the defect that lost EXP-0178's `raw/g17p_20260830_run01`:
a closure reads `nb` (a read-back SIZE) that a later statement in the SAME enclosing
scope rebinds to a `bytearray`. `mnem` is the expected FALSE POSITIVE: it is assigned
in two mutually exclusive branches of one if/else, which is safe, and exists here so
the gate can prove the allow-list works.
"""


def main(argv):
    stage = argv[0]
    nb = 32                       # read-back size in bytes

    if stage == "compute":        # mutually exclusive branches: safe
        mnem = "device_store"
    else:
        mnem = "tile_read"

    def raw_case(runner, archive):
        return runner.request(archive=archive, grid=64, tg=64, ins={},
                              outs={0: nb, 4: nb}, timeout=8), mnem

    results = [raw_case(None, "baseline.bin")]

    blk0 = b"\x00" * 32
    nb = bytearray(blk0)          # <-- the rebind; every later raw_case() is broken
    results.append(raw_case(None, "falsifier.bin"))
    return results
