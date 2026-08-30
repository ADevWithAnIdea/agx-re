"""FIXTURE for closure_scan's offline gate -- the CORRECTED form of
`closure_shadow_bad.py`. The mutated buffer gets its own name, so the closure's
read-back size can no longer be rebound underneath it. `mnem` still comes from two
mutually exclusive branches and is still expected to need the allow-list.
"""


def main(argv):
    stage = argv[0]
    nb = 32                       # read-back size in bytes -- assigned exactly once

    if stage == "compute":
        mnem = "device_store"
    else:
        mnem = "tile_read"

    def raw_case(runner, archive):
        return runner.request(archive=archive, grid=64, tg=64, ins={},
                              outs={0: nb, 4: nb}, timeout=8), mnem

    results = [raw_case(None, "baseline.bin")]

    blk0 = b"\x00" * 32
    falsifier_bytes = bytearray(blk0)     # distinct name: nothing shadowed
    results.append((raw_case(None, "falsifier.bin"), len(falsifier_bytes)))
    return results
