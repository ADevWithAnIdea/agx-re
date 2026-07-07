# Dissecting the Apple M1 GPU, part IV

> Source URL: https://rosenzweig.io/blog/asahi-gpu-part-4.html
> Redirect: https://alyssarosenzweig.ca/blog/asahi-gpu-part-4.html

**2 May 2021**

After beginning a compiler for the Apple M1 GPU, the next step is to develop a graphics driver exercising the compiler. Since the last post two weeks ago, I've begun a Gallium driver for the M1, implementing much of the OpenGL 2.1 and ES 2.0 specifications. With the compiler and driver together, we're now able to run OpenGL workloads like glxgears and scenes from glmark2 on the M1 with an open source stack. We are passing about 75% of the OpenGL ES 2.0 tests in the drawElements Quality Program used to establish Khronos conformance. To top it off, the compiler and driver are now upstreamed in Mesa!

Gallium is a driver framework inside Mesa. It splits drivers into frontends, like OpenGL and OpenCL, and backends, like Intel and AMD. In between, Gallium has a common caching system for graphics and compute state, reducing the CPU overhead of every Gallium driver. The code sharing, central to Gallium's design, allows high-performance drivers to be written at a low cost. For us, that means we can focus on writing a Gallium backend for Apple's GPU and pick up OpenGL and OpenCL support "for free".

More sharing is possible. A key responsibility of the Gallium backend is to translate Gallium's state objects into hardware packets, so we need a good representation of hardware packets. While packed bitfields can work, C's bitfields have performance and safety (overflow) concerns. Hand-coded C structures lack pretty-printing needed for efficient debugging. Finally, while reverse-engineering, hand-coded C structures tend to accumulate random magic numbers in driver code, which is undesirable. These issues are not new; systems like Intel's GenXML and Nouveau's envytools solve them by allowing the hardware packets to be described as XML while all necessary C code is auto-generated. For Asahi, I've opted to use GenXML, providing a concise description of my reverse-engineering results and an ergonomic API for the driver.

The XML contains recently reverse-engineered packets, like those describing textures and samplers. Fortunately, these packets map closely to both Metal and Gallium, allowing a natural translation. Coupled with Dougall Johnson's latest notes on texture instructions, adding texture support to the Gallium driver and NIR compiler was a cinch.

The resulting XML is somewhat smaller than that of other reverse-engineered drivers of similar maturity. As discussed in the previous post, Apple relies on shader code in lieu of fixed-function graphics hardware for tasks like vertex attribute fetch and blending. Apple's design reduces the hardware surface area, in turn reducing the number of packets in the XML at the expense of extra driver code to produce the needed shader variants. Here is yet another win for code sharing: the most complex code needed is for blending and logic operations, for which Mesa already has lowering code. Mali (Panfrost) needs some blending lowered to shader code, and all Mesa drivers need advanced blending equations lowered (modes like overlay, colour dodge, and screen). As a result, it will be a simple task to wire in the "load tilebuffer to register" instruction and Mesa's blending code and see a thousand more tests pass.

Although Apple culled a great deal of legacy functionality from their GPU, some features are retained to support older APIs like compatibility contexts of desktop OpenGL, even when the features are inaccessible from Metal. Index buffers and primitive types exhibit this phenomenon. In Metal, an application can draw using a 16-bit or 32-bit index buffer, selecting primitives like triangles and triangle strips, with primitive restart always enabled. Most graphics developers want to use this fast path; by only supporting the fast path, Metal prevents a game developer from accidentally introducing slow code. However, this limits our ability to implement Khronos APIs like OpenGL and Vulkan on top of the Apple hardware… or does it?

In addition to the subset supported by Metal, the Khronos APIs also support 8-bit index buffers, additional primitive types like triangle fans, and an option to disable primitive restart. True, some of this functionality is unnecessary. Real geometry usually requires more than 256 vertices, so 8-bit index buffers are a theoretical curiosity. Primitives like triangle fans can bring a hardware penalty relative to triangle strips due to poor cache locality while offering no generality over indexed triangles. Well-written apps generally require primitive restart, and it's almost free for apps that don't need it. Even so, real applications (and the Khronos conformance tests) do use these features, so we need to support them in our OpenGL and Vulkan drivers. The issue does not only affect us – drivers layered on top of Metal like MoltenVK struggle with these exact gaps.

If Apple left these features in the hardware but never wired them into Metal, we'd like to know. But clean room reverse-engineering the hardware requires observing the output of the proprietary driver and looking for patterns, so if the proprietary (Metal) driver doesn't use the functionality, how can we ever know it exists?

This is a case for an underappreciated reverse-engineering technique: guesswork. Hardware designers are logical engineers. If we can understand how Apple approached the hardware design, we can figure out where these hidden features should be in the command stream. We're looking for conspicuous gaps in our understanding of the hardware, like looking for black holes by observing the absence of light.

Consider index buffers, which are configured by an indexed draw packet with a field describing the size. After trying many indexed draws in Metal, I was left with the following reverse-engineered fragment:

```
<enum name="Index size">
  <value name="U16" value="1"/>
  <value name="U32" value="2"/>
</enum>

<struct name="Indexed draw" size="32">
...
  <field name="Index size" size="2" start="2:17" type="Index size"/>
...
</struct>
```

If the hardware only supported what Metal supports, this fragment would be unusual. Note 16-bit and 32-bit index buffers are encoded as 1 and 2. In binary, that's 01 and 10, occupying two different bits, so we know the index size is at least 2 bits wide. That leaves 00 (0) and 11 (3) as possible unidentified index sizes. Now observe index sizes are multiples of 8 bits and powers of two, so there is a natural encoding as the base-2 logarithm of the index size in bytes. This matches our XML fragment, since `log2(16 / 8) = 1` and `log2(32 / 8) = 2`. From here, we make our leap of faith: if the hardware supports 8-bit index buffers, it should be encoded with value `log2(8 / 8) = 0`. Sure enough, if we try out this guess, we'll find it passes the relevant OpenGL tests. Success.

Finding the missing primitive types works the same way. The primitive type field is 4-bits in the hardware, allowing for 16 primitive types to be encoded, while Metal only uses 5, leaving only 11 to brute force with the tests in hand. Likewise, few bits vary between an indexed draw of triangles (no primitive restart) and an indexed draw of triangle strips (with primitive restart), giving us a natural candidate for a primitive restart enable bit. Our understanding of the hardware is coming together.

One outstanding difficulty is ironically specific to macOS: the IOGPU interface with the kernel. Traditionally, open source drivers on Linux use simple kernel space drivers together with complex userspace drivers. The userspace (Mesa) handles all 3D state, and the kernel simply handles memory management and scheduling. However, macOS does not follow this model; the IOGPU kernel extension, common to all GPUs on macOS, is made aware of graphics state like surface dimensions and even details about mipmapping. Many of these mechanisms can be ignored in Mesa, but there is still an uncomfortably large volume of "magic" to interface with the kernel, like the memory mapping descriptors. The good news is many of these elements can be simplified when we write a Linux kernel driver. The bad news is that they do need to be reverse-engineered and implemented in Mesa if we would like native Vulkan support on Macs. Still, we know enough to drive the GPU from macOS… and hey, soon enough, we'll all be running Linux on our M1 machines anyway :-)
