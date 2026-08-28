## What the lifetime fields mean

Apple9 ALU instructions carry state describing what happens to each source operand after the instruction consumes it.

For:

```text
dst = op(src0, src1)
```

the instruction independently says:

```text
retain src0 after this instruction?
retain src1 after this instruction?
```

This is not the lifetime of `dst`. It describes whether each input remains available to later instructions.

That distinction matters because an instruction may compute its own result correctly while prematurely releasing one of its inputs. The failure only appears when a later instruction tries to consume that input again. Empirically, this does not necessarily fault or hang the GPU: the command retires, but later arithmetic receives incorrect data.

Bit numbering below starts at the least-significant bit of byte 0.

### Extended logic encoding

For the tested 10-byte `and/or/xor` form:

| Meaning | Required encoding |
|---|---|
| Retain source 0 | bit 15 = 1, bit 19 = 0 |
| Retain source 1 | bit 31 = 1, bit 20 = 0, bit 21 = 1 |
| Retain either source | bit 63 = 0 |

The complementary fields matter. “Retain source 0” is the correlated transition `(bit15, bit19) = (1,0)`, not simply setting bit 15.

### Compact two-source float encoding

For the tested six-byte `fadd/fsub/fmul` form:

| Meaning | Required encoding |
|---|---|
| Destination publication state | bit 21 = 1 |
| Retain source 0 | bit 15 = 1, bit 19 = 0 |
| Retain source 1 | bit 31 = 1, bit 20 = 0 |
| Consumer route | bits 45–47 |

Float min/max uses the same source-retention transitions in the tested compact form.

For the eight-byte FMA form, source 0 and source 1 use those same fields, while source 2 uses:

```text
retain source 2: bit 47 = 1, bit 39 = 0
consumer route:  bits 61–63
```

The destination-publication and consumer-route fields are distinct from source lifetime:

- Source-lifetime fields decide whether an operand is released after this use.
- Destination state controls how the new result is published.
- Consumer route identifies the kind of producer from which the operands arrive.

The following examples specifically reproduce source-lifetime failures.

## Example 1: integer select DAG

```glsl
#version 310 es
layout(local_size_x = 256) in;

layout(std430, binding = 0) buffer Output {
    uint v[];
} output0;

void main()
{
    uint gid = gl_GlobalInvocationID.x;

    output0.v[gid] =
        ((gid + 3u) < (gid * 2u))
            ? (gid ^ 0x55u)
            : (gid + 100u);
}
```

The relevant dataflow is:

```text
                         ┌── XOR 0x55 ─── true value
gid ─────────────────────┼── ADD 100  ─── false value
                         ├── ADD 3    ─── comparison left
                         └── MUL 2    ─── comparison right
```

A legal schedule begins by calculating the true value:

```text
true = gid XOR 0x55
```

That is not the final use of `gid`: the false branch and comparison still need it. Therefore the XOR must retain source 0.

The tested XOR bytes were:

```text
Correct — source 0 retained:

4b 85 16 07 02 08 00 00 00 00
```

```text
Incorrect — both sources released:

4b 05 1e 07 02 08 00 80 00 00
```

The important differences are:

```text
              incorrect   correct
bit 15             0          1
bit 19             1          0
bit 63             1          0
```

Nothing about the XOR opcode, registers, or destination changes. Only the source-lifetime state changes.

With the correct encoding, all 16,384 invocations produced exact results.

With the incorrect encoding, the command completed, but the first detected mismatch was:

```text
gid       = 1
actual    = 0x00000064
expected  = 0x00000065
```

Many sampled invocations returned `0x64`. The specific corrupt value may vary with scheduling and register assignment; the meaningful observation is that prematurely releasing `gid` corrupts its later consumers without causing a submission failure.

A CPU reference is:

```c
uint32_t expected(uint32_t gid)
{
    return (gid + 3u) < (gid * 2u)
        ? (gid ^ 0x55u)
        : (gid + 100u);
}
```

## Example 2: float fanout DAG

```glsl
#version 310 es
layout(local_size_x = 256) in;

layout(std430, binding = 0) buffer Output {
    uint v[];
} output0;

void main()
{
    uint gid = gl_GlobalInvocationID.x;
    float x = uintBitsToFloat(gid | 0x3f800000u);

    float a = x * 2.0 + 0.25;
    float b = x * 0.5 + 0.125;

    float c = a + b;
    float d = a - b;
    float e = a * b;

    float f = max(c, e);
    float g = min(d + 2.0, e * 0.5);

    output0.v[gid] = floatBitsToUint((f + g) * d);
}
```

This deliberately has several fanout points:

```text
x ──┬──> a
    └──> b

a ──┬──> c
    ├──> d
    └──> e

b ──┬──> c
    ├──> d
    └──> e

e ──┬──> f
    └──> g

d ──┬──> g
    └──> final multiply
```

Representative source-lifetime states from the working shader were:

| Instruction | Lifetime mask | Meaning |
|---|---:|---|
| `x * 2.0` | `0x3` | Retain both inputs |
| `x * 0.5` | `0x2` | Release `x`, retain `0.5` |
| `a + b` | `0x3` | Retain both `a` and `b` |
| `a * b` | `0x3` | Retain both for later subtraction |
| `max(c,e)` | `0x2` | Release `c`, retain `e` |
| `d + 2.0` | `0x1` | Retain `d`, release `2.0` |

For the first multiply, the tested bytes were:

```text
Correct — both sources retained:

39 89 25 85 00 00
```

```text
Incorrect — both sources released:

39 09 3d 05 00 00
```

The lifetime transitions are visible directly:

```text
              incorrect   correct
bit 15             0          1     src0 keep
bit 19             1          0     src0 complement
bit 31             0          1     src1 keep
bit 20             1          0     src1 complement
```

The destination state and route remain unchanged.

With correct lifetime fields, all 16,384 results matched. For `gid=0`:

```text
x        = 1.0
a        = 2.25
b        = 0.625
c        = 2.875
d        = 1.625
e        = 1.40625
f        = 2.875
g        = 0.703125
result   = 5.814453125
bits     = 0x40ba1000
```

When the float source-retention fields were forced into their all-dead state, the command still completed, but every sampled output was zero:

```text
gid       = 0
actual    = 0x00000000
expected  = 0x40ba1000
```

The earliest damaging release is the first `x * 2.0`: that instruction is allowed to release `x`, even though `x` is subsequently needed for `x * 0.5`. The resulting corruption then propagates through most of the graph.

## Consumer-route qualification

The float encodings also contain a three-bit consumer route, but the float fanout shader is entirely ALU-produced. In our testing, forcing its route through all values `0–7` did not change the output.

Therefore:

- The two shaders above are strong source-lifetime reproducers.
- The float fanout shader is not a reliable consumer-route reproducer.
- Testing route selection requires mixing producer classes, such as a memory load feeding a float ALU instruction.

A suitable route-oriented shader shape would be:

```glsl
#version 310 es
layout(local_size_x = 256) in;

layout(std430, binding = 0) readonly buffer Input {
    float v[];
} input0;

layout(std430, binding = 1) writeonly buffer Output {
    uint v[];
} output0;

void main()
{
    uint gid = gl_GlobalInvocationID.x;
    float loaded = input0.v[gid];
    float result = loaded * 2.0 + 0.25;

    output0.v[gid] = floatBitsToUint(result);
}
```

That distinguishes a load-produced operand from an ALU-produced operand and is the appropriate shape for investigating the route field. The two complete shaders above isolate the separate—and independently demonstrated—source-retention contract.
