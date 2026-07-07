# Conformant OpenGL 4.6 on the M1

> Source URL: https://rosenzweig.io/blog/conformant-gl46-on-the-m1.html
> Redirect: https://alyssarosenzweig.ca/blog/conformant-gl46-on-the-m1.html

**14 Feb 2024**

For years, the M1 has only supported OpenGL 4.1. That changes today – with the release of full OpenGL® 4.6 and OpenGL® ES 3.2! Install Fedora for the latest M1/M2-series drivers.

Already installed? Just `dnf upgrade --refresh`.

Unlike the vendor's non-conformant 4.1 drivers, the open source Linux drivers are **conformant** to the latest OpenGL versions, finally promising broad compatibility with modern OpenGL workloads, like Blender.

Conformant 4.6/3.2 drivers must pass over 100,000 tests to ensure correctness. The official list of conformant drivers now includes the OpenGL 4.6 and ES 3.2 implementations.

While the vendor doesn't yet support graphics standards like modern OpenGL, this project does. The goal is to profess support for interoperable open standards, freeing users and developers from lock-in, enabling applications to run anywhere without special ports. Six months ago, the team became the first conformant driver for any standard graphics API for the M1 with OpenGL ES 3.1 drivers. Today, the full 4.6 release is complete… and Vulkan support is well underway.

---

Compared to 4.1, OpenGL 4.6 adds dozens of required features, including:

* Robustness
* SPIR-V
* Clip control
* Cull distance
* Compute shaders
* Upgraded transform feedback

Regrettably, the M1 doesn't map well to any graphics standard newer than OpenGL ES 3.1. While Vulkan makes some of these features optional, the missing features are required to layer DirectX and OpenGL on top. No existing solution on M1 gets past the OpenGL 4.1 feature set.

How do we break the 4.1 barrier? Without hardware support, new features need new tricks. Geometry shaders, tessellation, and transform feedback become compute shaders. Cull distance becomes a transformed interpolated value. Clip control becomes a vertex shader epilogue. The list goes on.

For a taste of the challenges overcome, let's look at **robustness**.

Built for gaming, GPUs traditionally prioritize raw performance over safety. Invalid application code, like a shader that reads a buffer out-of-bounds, can trigger undefined behaviour. Drivers exploit that to maximize performance.

For applications like web browsers, that trade-off is undesirable. Browsers handle untrusted shaders, which they must sanitize to ensure stability and security. Clicking a malicious link should not crash the browser. While some sanitization is necessary as graphics APIs are not security barriers, reducing undefined behaviour in the API can assist "defence in depth".

"Robustness" features can help. Without robustness, out-of-bounds buffer access in a shader can crash. With robustness, the application can opt for defined out-of-bounds behaviour, trading some performance for less attack surface.

All modern cross-vendor APIs include robustness. Many games even (accidentally?) rely on robustness. Strangely, the vendor's proprietary API omits buffer robustness. Better solutions must be provided for conformance, correctness, and compatibility.

Let's first define the problem. Different APIs have different definitions of what an out-of-bounds load returns when robustness is enabled:

* Zero (Direct3D, Vulkan with `robustBufferAccess2`)
* Either zero or some data in the buffer (OpenGL, Vulkan with `robustBufferAccess`)
* Arbitrary values, but can't crash (OpenGL ES)

OpenGL uses the second definition: return zero or data from the buffer. One approach is to return the _last_ element of the buffer for out-of-bounds access. Given the buffer size, we can calculate the last index. Now consider the _minimum_ of the index being accessed and the last index. That equals the index being accessed if it is valid, and some other valid index otherwise. Loading the minimum index is safe and gives a spec-compliant result.

As an example, a uniform buffer load without robustness might look like:

```
load.i32 result, buffer, index
```

Robustness adds a single unsigned minimum (`umin`) instruction:

```
umin idx, index, last
load.i32 result, buffer, idx
```

Is the robust version slower? It can be. The difference should be small percentage-wise, as arithmetic is faster than memory. With thousands of threads running in parallel, the arithmetic cost may even be hidden by the load's latency.

There's another trick that speeds up robust uniform buffers. Like other GPUs, the M1 supports "preambles". The idea is simple: instead of calculating the same value in every thread, it's faster to calculate once and reuse the result. The compiler identifies eligible calculations and moves them to a preamble executed before the main shader. These redundancies are common, so preambles provide a nice speed-up.

We usually move uniform buffer loads to the preamble when every thread loads the same index. Since the size of a uniform buffer is fixed, extra robustness arithmetic is _also_ moved to the preamble. The robustness is "free" for the main shader. For robust storage buffers, the clamping might move to the preamble even if the load or store cannot.

Armed with robust uniform and storage buffers, let's consider robust "vertex buffers". In graphics APIs, the application can set vertex buffers with a base GPU address and a chosen layout of "attributes" within each buffer. Each attribute has an offset and a format, and the buffer has a "stride" indicating the number of bytes per vertex. The vertex shader can then read attributes, implicitly indexing by the vertex. To do so, the shader loads the address:

> Base plus stride times vertex plus offset

Some hardware implements robust vertex fetch natively. Other hardware has bounds-checked buffers to accelerate robust software vertex fetch. Unfortunately, the M1 has neither. We need to implement vertex fetch with raw memory loads.

One instruction set feature helps. In addition to a 64-bit base address, the M1 GPU's memory loads also take an offset in _elements_. The hardware shifts the offset and adds to the 64-bit base to determine the address to fetch. Additionally, the M1 has a combined integer multiply-add instruction `imad`. Together, these features let us implement vertex loads in two instructions. For example, a 32-bit attribute load looks like:

```
imad idx, stride/4, vertex, offset/4
load.i32 result, base, idx
```

The hardware load can perform an additional small shift. Suppose our attribute is a vector of 4 32-bit values, densely packed into a buffer with no offset. We can load that attribute in one instruction:

```
load.v4i32 result, base, vertex << 2
```

…with the hardware calculating the address: Base plus 4 times vertex left shifted 2, which equals Base plus 16 times vertex

What about robustness?

We want to implement robustness with a clamp, like we did for uniform buffers. The problem is that the vertex buffer size is given in bytes, while our optimized load takes an index in "vertices". A single vertex buffer can contain multiple attributes with different formats and offsets, so we can't convert the size in bytes to a size in "vertices".

Let's handle the latter problem. We can rewrite the addressing equation as: Base plus offset, which is the attribute base, plus stride times vertex

That is: one buffer with many attributes at different offsets is equivalent to many buffers with one attribute and no offset. This gives an alternate perspective on the same data layout. Is this an improvement? It avoids an addition in the shader, at the cost of passing more data – addresses are 64-bit while attribute offsets are 16-bit. More importantly, it lets us translate the vertex buffer size in bytes into a size in "vertices" for _each_ vertex attribute. Instead of clamping the offset, we clamp the vertex index. We still make full use of the hardware addressing modes, now with robustness:

```
umin idx, vertex, last valid
load.v4i32 result, base, idx << 2
```

We need to calculate the last valid vertex index ahead-of-time for each attribute. Each attribute has a format with a particular size. Manipulating the addressing equation, we can calculate the last _byte_ accessed in the buffer (plus 1) relative to the base: Offset plus stride times vertex plus format

The load is valid when that value is bounded by the buffer size in bytes. We solve the integer inequality as: Vertex less than or equal to the floor of size minus offset minus format divided by stride

The driver calculates the right-hand side and passes it into the shader.

One last problem: what if a buffer is too small to load _anything_? Clamping won't save us – the code would clamp to a negative index. In that case, the attribute is entirely invalid, so we swap the application's buffer for a small buffer of zeroes. Since we gave each attribute its own base address, this determination is per-attribute. Then clamping the index to zero correctly loads zeroes.

Putting it together, a little driver math gives us robust buffers at the cost of one `umin` instruction.

---

In addition to buffer robustness, we need image robustness. Like its buffer counterpart, image robustness requires that out-of-bounds image loads return zero. That formalizes a guarantee that reasonable hardware already makes.

…But it would be no fun if our hardware was reasonable.

Running the conformance tests for image robustness, there is a single test failure affecting "mipmapping".

For background, mipmapped images contain multiple "levels of detail". The base level is the original image; each successive level is the previous level downscaled. When rendering, the hardware selects the level closest to matching the on-screen size, improving efficiency and visual quality.

With robustness, the specifications all agree that image loads return…

* Zero if the X- or Y-coordinate is out-of-bounds
* Zero if the level is out-of-bounds

Meanwhile, image loads on the M1 GPU return…

* Zero if the X- or Y-coordinate is out-of-bounds
* Values from the last level if the level is out-of-bounds

Uh-oh. Rather than returning zero for out-of-bounds levels, the hardware clamps the level and returns nonzero values. It's a mystery why. The vendor does not document their hardware publicly, forcing us to rely on reverse engineering to build drivers. Without documentation, we don't know if this behaviour is intentional or a hardware bug. Either way, we need a workaround to pass conformance.

The obvious workaround is to never load from an invalid level:

```
if (level <= levels) {
    return imageLoad(x, y, level);
} else {
    return 0;
}
```

That involves branching, which is inefficient. Loading an out-of-bounds level doesn't crash, so we can speculatively load and then use a compare-and-select operation instead of branching:

```
vec4 data = imageLoad(x, y, level);

return (level <= levels) ? data : 0;
```

This workaround is okay, but it could be improved. While the M1 GPU has combined compare-and-select instructions, the instruction set is _scalar_. Each thread processes one value at a time, not a vector of multiple values. However, image loads return a vector of four components (red, green, blue, alpha). While the pseudo-code looks efficient, the resulting assembly is not:

```
image_load R, x, y, level
ulesel R[0], level, levels, R[0], 0
ulesel R[1], level, levels, R[1], 0
ulesel R[2], level, levels, R[2], 0
ulesel R[3], level, levels, R[3], 0
```

Fortunately, the vendor driver has a trick. We know the hardware returns zero if either X or Y is out-of-bounds, so we can _force_ a zero output by _setting_ X or Y out-of-bounds. As the maximum image size is 16384 pixels wide, any X greater than 16384 is out-of-bounds. That justifies an alternate workaround:

```
bool valid = (level <= levels);
int x_ = valid ? x : 20000;

return imageLoad(x_, y, level);
```

Why is this better? We only change a single scalar, not a whole vector, compiling to compact scalar assembly:

```
ulesel x_, level, levels, x, #20000
image_load R, x_, y, level
```

If we preload the constant to a uniform register, the workaround is a single instruction. That's optimal – and it passes conformance.

---

_Blender "Wanderer" demo by Daniel Bystedt, licensed CC BY-SA._
