#!/usr/bin/env python3
"""Generate complete, authored MSL sources for EXP-0057.

This writes only sources.  It neither invokes Metal nor opens an archive.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEVELS = {"baseline": 0, "p576": 576, "p1024": 1024, "p2048": 2048,
          "p4096": 4096, "p8192": 8192, "p16384": 16384}


def source(name: str, byte_count: int) -> str:
    words = byte_count // 4
    # The indexed, data-dependent cross-lane recurrence prevents the source from
    # expressing a constant result.  Metadata, not this requested extent, decides
    # whether the compiler actually declares scratch.
    body = "" if words == 0 else f'''\
    thread uint lanes[{words}];
    for (uint i = 0; i < {words}u; ++i)
        lanes[i] = (seed + i * 0x9e3779b9u) ^ ((i + 1u) * 0x85ebca6bu);
    for (uint pass = 0; pass < 3u; ++pass)
        for (uint i = 0; i < {words}u; ++i) {{
            uint j = (i * 13u + pass * 7u + 1u) % {words}u;
            lanes[i] = (lanes[i] ^ lanes[j]) + 0x27d4eb2du + pass;
        }}
    for (uint i = 0; i < {words}u; ++i) {{
        acc = (acc << 5u) | (acc >> 27u);
        acc ^= lanes[i];
    }}
'''
    return f'''// Complete authored source: EXP-0057 {name}, requested={byte_count} bytes.
#include <metal_stdlib>
using namespace metal;

kernel void k_main(device uint *out [[buffer(0)]],
                   device const uint *in [[buffer(1)]],
                   uint gid [[thread_position_in_grid]]) {{
    uint seed = in[gid];
    uint acc = seed ^ 0xa5a5a5a5u;
{body}    out[gid] = acc;
}}
'''


def main() -> None:
    for name, byte_count in LEVELS.items():
        path = HERE / f"{name}.metal"
        path.write_text(source(name, byte_count), encoding="utf-8")
        print(f"wrote {path.name} requested_bytes={byte_count}")


if __name__ == "__main__":
    main()
