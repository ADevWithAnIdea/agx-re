# Clip control on the Apple GPU

> Source URL: https://rosenzweig.io/blog/asahi-gpu-part-6.html
> Redirect: https://alyssarosenzweig.ca/blog/asahi-gpu-part-6.html

**22 Aug 2022**

After a year in development, the open source "Asahi" driver for the Apple GPU is running real games. There's more to do, but Neverball is already playable (and a lot of fun!).

Neverball uses legacy "fixed function" OpenGL. Rather than supply programmable shaders like OpenGL 2, old OpenGL 1 applications configure a fixed set of graphics effects like fog and alpha testing. Modern GPUs don't implement these features in hardware. Instead, the driver synthesizes shaders implementing the desired graphics. This translation is complicated, but we get it for "free" as an open source driver in Mesa. If we implement the modern shader pipeline, Mesa will handle fixed function OpenGL for us transparently. That's a win for open source drivers, and a win for GPU acceleration on Asahi Linux.

To implement the modern OpenGL features, we rely on reverse-engineering the behaviour of Apple's Metal driver, as we don't have hardware documentation. Although Metal uses the same shader pipeline as OpenGL, it doesn't support all the OpenGL features that the hardware does, which puts us in a bind. In the past, I've relied on educated guesswork to bridge the gap, but there's another solution… and it's a doozy.

## The Clip Space Problem

For motivation, consider the _clip space_ used in OpenGL. In every other API on the planet, the Z component (depth) of points in the 3D world range from 0 to 1, where 0 is "near" and 1 is "far". In OpenGL, however, Z ranges from _negative 1_ to 1. As Metal uses the 0/1 clip space, implementing OpenGL on Metal requires emulating the -1/1 clip space by inserting extra instructions into the vertex shader to transform the Z coordinate. Although this emulation adds overhead, it works for ANGLE's open source implementation of OpenGL ES on Metal.

Like ANGLE, Apple's OpenGL driver internally translates to Metal. Because Metal uses the 0 to 1 clip space, it should require this emulation code. Curiously, when we disassemble shaders compiled with their OpenGL implementation, we don't see any such emulation. That means Apple's GPU must support -1/1 clip spaces in addition to Metal's preferred 0/1. The problem is figuring out how to use this other clip space.

We expect that there's a bit toggling between these clip spaces. The logical place for such a bit is the viewport packet, but there's no obvious difference between the viewport packets emitted by Metal and OpenGL-on-Metal. Ordinarily, we would identify the bit by toggling the clip space in Metal and comparing memory dumps. However, according to Apple's documentation, there's no way to change the clip space in Metal.

That's an apparent contradiction. There's no way to use the -1/1 clip space with Metal, but Apple's OpenGL-on-Metal translator uses the -1/1 clip space. What gives?

## Two Metals

Here's a little secret: there are two graphics APIs called "Metal". There's the Metal you know, a limited API that Apple documents for App Store developers, an API that lacks useful features supported by OpenGL and Vulkan.

And there's the Metal that Apple uses themselves, an internal API adding back features that Apple doesn't want you using. While ANGLE implements OpenGL ES on the documented Metal, Apple can implement OpenGL on the secret Metal.

Apple does not publish documentation or headers for this richer Metal API, but if we're lucky, we can catch a glimpse behind the curtain. The undocumented classes and methods making up the internal Metal API are still available in the production Metal binaries. To use them, we only need the missing headers. Fortunately, Objective-C symbols contain enough information to reconstruct header files, allowing us to experiment with undocumented methods with "extra" functionality inherited from OpenGL.

Compared to the desktop GPUs found in Intel Macs, Apple's own GPU implements a slim, modern feature set mapping well to Metal. Most of the "extra" functionality is emulated. It is interesting to know the emulation happens in their Metal driver instead of their OpenGL frontend, but that's unsurprising, as it allows their Metal drivers for Intel and AMD GPUs to implement the functionality natively. While this information is fascinating for "macOS hermeneutics", it won't help us with our Apple GPU mystery.

What _will_ help us are the catch-all mystery methods named `setOpenGLModeEnabled`, apparently enabling "OpenGL mode".

Mystery methods named like that just _beg_ to be called.

## Investigating setOpenGLModeEnabled

The render pipeline descriptor has such a method. That descriptor contains state that can change every draw. In some graphics APIs, like OpenGL with `ARB_clip_control` and Vulkan with `VK_EXT_depth_clip_control`, the application can change the clip space every draw. Ideally, the clip space state would be part of this descriptor.

We can test this optimistic guess by augmenting our Metal test bench to call `[MTLRenderPipelineDescriptorInternal setOpenGLModeEnabled: YES]`.

It feels strange to call this hidden method. It's stranger when the code compiles and runs just fine.

We can then compare traces between OpenGL mode and the normal Metal mode. Seemingly, enabling OpenGL mode toggles a plethora of random unknown bits. Even if one of them is what we want, it's a bit unsatisfying that the "real" Metal would lack a proper `[setClipSpace: MTLMinusOneToOne]` method, rather than this blunt hack reconfiguring a pile of loosely related API behaviours.

Alas, for all the random changes in "OpenGL mode", none seem to affect clipping behaviour.

Hope is not yet lost. There's another `setOpenGLModeEnabled` method, this time in the render pass descriptor. Rather than pipeline state that can change every draw, this descriptor's state can only change in between render passes. Changing that state in between draws would require an expensive flush to main memory, similar to the partial renders seen elsewhere with the Apple GPU. Nevertheless, it's worth a shot.

Changing our test bench to call `[MTLRenderPassDescriptorInternal setOpenGLModeEnabled: YES]`, we find another collection of random bits changed. Most of them are in hardware packets, and none of those seem to control clip space, either.

## The Hidden Kernel Bit

One bit does stand out. It's not a hardware bit.

In addition to the packets that the userspace driver prepares for the hardware, userspace passes to the _kernel_ a large block of render pass state describing everything from tile size to the depth/stencil buffers. Such a design is unusual. Ordinarily, GPU kernel drivers are only concerned with memory management and scheduling, remaining oblivious of 3D graphics. By contrast, Apple processes this state in the kernel forwarding the state to the GPU's firmware to configure the actual hardware.

Comparing traces, the render pass "OpenGL mode" sets an unknown bit in this kernel-processed block. If we set the same bit in our OpenGL driver, we find the clip space changes to -1/1. Victory, right?

Almost. Because this bit is render pass state, we can't use it to change the clip space between draws. That's okay for baseline OpenGL and Vulkan, but it prevents us from efficiently implementing the `ARB_clip_control` and `VK_EXT_depth_clip_control` extensions. There _are_ at least three (inefficient) implementations.

## Three Approaches to Clip Control

**The first** is ignoring the hardware support and emulating one of the clip spaces by inserting extra instructions into the vertex shader when the "wrong" clip space is used. In addition to extra overhead, that requires _shader variants_ for the different clip spaces.

Shader variants are terrible.

In new APIs like Vulkan, Metal, and D3D12, everything needed to compile a shader is known up-front as part of a monolithic pipeline. That means pipelines are compiled when they're created, not when they're used, and are never recompiled. By contrast, older APIs like OpenGL and D3D11 allow using the same shader with different API states, requiring some drivers to recompile shaders on the fly. Compiling shaders is slow, so shader variants can cause unpredictable drops in an application's frame rate, familiar to desktop gamers as stuttering. If we use this approach in our OpenGL driver, switching clip modes could cause stuttering due to recompiling shaders.

**The second approach** is _always_ inserting emulation instructions that read the desired clip space at run-time, reserving a uniform (push constant) for the transformation. That way, the same shader is usable with either clip space, eliminating shader variants. However, that has even higher overhead than the first method. If an application frequently changes clip spaces within a render pass, this approach will be the most efficient of the three. If it does not, this approach adds constant overhead to _every_ application. Knowing which approach is better requires the driver to have a magic crystal ball.

**The final option** is _using_ the hardware clip space bit and splitting the render pass when the clip space is changed. Here, the shaders are optimal and do not require variants. However, splitting the render pass wastes tremendous memory bandwidth if the application changes clip spaces frequently. Nevertheless, this approach has some support from the `ARB_clip_control` specification:

> Some [OpenGL] implementations may introduce a flush when changing the clip control state. Hence frequent clip control changes are not recommended.

Each approach has trade-offs. For now, the easiest "option" is sticking our head in the sand and giving up on `ARB_clip_control` altogether. The OpenGL extension is optional until we get to OpenGL 4.5. Apple doesn't implement it in their OpenGL stack. Because `ARB_clip_control` is primarily for porting Direct3D games, native OpenGL games are happy without it. Certainly, Neverball doesn't mind. For now, we can use the hardware bit to use the -1/1 clip space unconditionally in OpenGL and 0/1 unconditionally in Vulkan. That does not require any emulation or flushing, though it prevents us from advertising the extensions.

## Running on macOS vs. Linux

That's enough to run Neverball on macOS, using our userspace OpenGL driver in Mesa, and Apple's proprietary kernel driver. There's a catch: Neverball has to present with the deprecated X11 server on macOS. Years ago, Apple engineers contributed Mesa support for X11 on macOS (XQuartz), allowing us to run X11 applications with our Mesa driver. However, there's no support for Apple's own Cocoa windowing system, meaning native macOS applications won't work with our driver. There's also no easy way to run Linux's newer Wayland display server on macOS. Nevertheless, Neverball does not use Cocoa directly. Instead, it uses the cross-platform SDL2 library to create its window, which internally uses Cocoa, X11, or Wayland as appropriate for the operating system. With enough sweat and tears, we can build an macOS/X11 version of SDL2 and link Neverball with that.

This Neverball/macOS/X11 port was frustrating, especially when the game is one `apt install` away on Linux. That's a job for Asahi Lina, who has been hard at work writing a Linux kernel driver for Apple's GPU. When our work converges, my userspace Mesa driver will run on Linux with her kernel driver to implement a full open source graphics stack for 3D acceleration on Asahi Linux.

## Realistic Expectations

Please temper your expectations: even with hardware documentation, an optimized Vulkan driver stack (with enough features to layer OpenGL 4.6 with Zink) requires many years of full time work. At least for now, nobody is working on this driver full time. Reverse-engineering slows the process considerably. We won't be playing AAA games any time soon.

That said, thanks to the tremendous shared code in Mesa, a basic OpenGL driver is doable by a single person. I'm optimistic that we'll have native OpenGL 2.1 in Asahi Linux by the end of the year. That's enough to accelerate your desktop environment and browser. It's also enough to play older games (like Neverball). Even without fancy features, GPU acceleration means smooth animations and better battery life.

In that light, the Asahi Linux future looks bright.

---

**Footnotes:**

1. This crystal ball is called "Vulkan, Metal, or D3D12", and it has its own problems.

2. Hi Jeremy!

3. I work full-time at Collabora on my baby, the open source Panfrost driver for Mali GPUs.
