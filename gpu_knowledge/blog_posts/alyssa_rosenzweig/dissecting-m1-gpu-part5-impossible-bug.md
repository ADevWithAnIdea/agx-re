# The Apple GPU and the Impossible Bug

> Source URL: https://rosenzweig.io/blog/asahi-gpu-part-5.html
> Redirect: https://alyssarosenzweig.ca/blog/asahi-gpu-part-5.html

**13 May 2022**

In late 2020, Apple debuted the M1 with Apple's GPU architecture, AGX, rumoured to be derived from Imagination's PowerVR series. Since then, we've been reverse-engineering AGX and building open source graphics drivers. Last January, I rendered a triangle with my own code, but there has since been a heinous bug lurking:

**The driver fails to render large amounts of geometry.**

Spinning a cube is fine, low polygon geometry is okay, but detailed models won't render. Instead, the GPU renders only part of the model and then faults.

It's hard to pinpoint how much we can render without faults. It's not just the geometry complexity that matters. The same geometry can render with simple shaders but fault with complex ones.

That suggests rendering detailed geometry with a complex shader "takes too long", and the GPU is timing out. Maybe it renders only the parts it finished in time.

Given the hardware architecture, this explanation is unlikely.

## Testing the Timeout Hypothesis

This hypothesis is easy to test, because we can control for timing with a shader that takes as long as we like:

```
for (int i = 0; i < LARGE_NUMBER; ++i) {
    /* some work to prevent the optimizer from removing the loop */
}
```

After experimenting with such a shader, we learn…

*   If shaders have a time limit to protect against infinite loops, it's astronomically high. There's no way our bunny hits that limit.
*   The symptoms of timing out differ from the symptoms of our driver rendering too much geometry.

That theory is out.

## Finding the Real Culprit

Let's experiment more. Modifying the shader and seeing where it breaks, we find the only part of the shader contributing to the bug: the amount of data interpolated per vertex. Modern graphics APIs allow specifying "varying" data for each vertex, like the colour or the surface normal. Then, for each triangle the hardware renders, these "varyings" are interpolated across the triangle to provide smooth inputs to the fragment shader, allowing efficient implementation of common graphics techniques like Blinn-Phong shading.

Putting the pieces together, what matters is the _product_ of the number of vertices (geometry complexity) _times_ amount of data per vertex ("shading" complexity). That product is "total amount of per-vertex data". The GPU faults if we use too much _total_ per-vertex data.

## Why?

When the hardware processes each vertex, the vertex shader produces per-vertex data. That data has to _go_ somewhere. How this works depends on the hardware architecture. Let's consider common GPU architectures.

### Immediate Mode Renderers vs. Tilers

Traditional **immediate mode renderers** render directly into the framebuffer. They first run the vertex shader for each vertex of a triangle, then run the fragment shader for each pixel in the triangle. Per-vertex "varying" data is passed almost directly between the shaders, so immediate mode renderers are efficient for complex scenes.

There is a drawback: rendering directly into the framebuffer requires tremendous amounts of memory access to constantly write the results of the fragment shader and to read out back results when blending. Immediate mode renderers are suited to discrete, power-hungry desktop GPUs with dedicated video RAM.

By contrast, **tile-based deferred renderers** split rendering into two passes. First, the hardware runs all vertex shaders for the entire frame, not just for a single model. Then the framebuffer is divided into small tiles, and dedicated hardware called a _tiler_ determines which triangles are in each tile. Finally, for each tile, the hardware runs all relevant fragment shaders and writes the final blended result to memory.

Tilers reduce memory traffic required for the framebuffer. As the hardware renders a single tile at a time, it keeps a "cached" copy of that tile of the framebuffer (called the "tilebuffer"). The tilebuffer is small, just a few kilobytes, but tilebuffer access is _fast_. Writing to the tilebuffer is cheap, and unlike immediate renderers, blending is almost free. Because main memory access is expensive and mobile GPUs can't afford dedicated video memory, tilers are suited to mobile GPUs, like Arm's Mali, Imaginations's PowerVR, and Apple's AGX.

Yes, AGX is a _mobile_ GPU, designed for the iPhone. The M1 is a screaming fast desktop, but its unified memory and tiler GPU have roots in mobile phones. Tilers work well on the desktop, but there are some drawbacks.

First, at the start of a frame, the contents of the tilebuffer are undefined. If the application needs to preserve existing framebuffer contents, the driver needs to load the framebuffer from main memory and store it into the tilebuffer. This is expensive.

Second, because all vertex shaders are run before any fragment shaders, the hardware needs a buffer to store the outputs of all vertex shaders. In general, there is much more data required than space inside the GPU, so this buffer must be in main memory. This is also expensive.

## Identifying the Buffer

**Ah-ha**. Because AGX is a tiler, it requires a buffer of _all_ per-vertex data. We fault when we use too _much_ total per-vertex data, overflowing the buffer.

…So how do we allocate a larger buffer?

On some tilers, like older versions of Arm's Mali GPU, the userspace driver computes how large this "varyings" buffer should be and allocates it. To fix the faults, we can try increasing the sizes of all buffers we allocate, in the hopes that one of them contains the per-vertex data.

No dice.

It's prudent to observe what Apple's Metal driver does. We can cook up a Metal program drawing variable amounts of geometry and trace all GPU memory allocations that Metal performs while running our program. Doing so, we learn that increasing the amount of geometry drawn does _not_ increase the sizes of any allocated buffers. In fact, it doesn't change _anything_ in the command buffer submitted to the kernel, except for the single "number of vertices" field in the draw command.

We _know_ that buffer exists. If it's not allocated by userspace – and by now it seems that it's not – it must be allocated by the kernel or firmware.

## The Overflow Mechanism

Here's a funny thought: maybe we don't specify the size of the buffer at all. Maybe it's _okay_ for it to overflow, and there's a way to handle the overflow.

It's time for a little reconnaissance. Digging through what little public documentation exists for AGX, we learn from one WWDC presentation:

> "The Tiled Vertex Buffer stores the Tiling phase output, which includes the post-transform vertex data… But it may cause a Partial Render if full. A Partial Render is when the GPU splits the render pass in order to flush the contents of that buffer."

Bullseye. The buffer we're chasing, the "tiled vertex buffer", can overflow. To cope, the GPU stops accepting new geometry, renders the existing geometry, and restarts rendering.

Since partial renders hurt performance, Metal application developers need to know about them to optimize their applications. There should be _performance counters_ flagging this issue. Poking around, we find two:

*   Number of partial renders.
*   Number of bytes used of the parameter buffer.

Wait, what's a "parameter buffer"?

## PowerVR Connection

Remember the rumours that AGX is derived from PowerVR? The public PowerVR optimization guides explain:

> "[The] list containing pointers to each vertex passed in from the application… is called the **parameter buffer** (PB) and is stored in system memory along with the vertex data. Each varying requires additional space in the parameter buffer."

The Tiled Vertex Buffer _is_ the Parameter Buffer. PB is the PowerVR name, TVB is the public Apple name, and PB is still an internal Apple name.

What happens when PowerVR overflows the parameter buffer?

An old PowerVR presentation says that when the parameter buffer is full, the "render is flushed", meaning "flushed data must be retrieved from the frame buffer as successive tile renders are performed". In other words, it performs a partial render.

## The Broken Partial Render

Back to the Apple M1, it seems the hardware is failing to perform a partial render. Let's revisit the broken render.

Notice _parts_ of the model are correctly rendered. The parts that are not only have the black clear colour of the scene rendered at the start. Let's consider the logical order of events.

First, the hardware runs vertex shaders for the bunny until the parameter buffer overflows. This works: the partial geometry is correct.

Second, the hardware rasterizes the partial geometry and runs the fragment shaders. This works: the shading is correct.

Third, the hardware flushes the partial render to the framebuffer. This must work for us to see anything at all.

Fourth, the hardware runs vertex shaders for the rest of the bunny's geometry. This ought to work: the configuration is identical to the original vertex shaders.

Fifth, the hardware rasterizes and shades the rest of the geometry, blending with the old partial render. Because AGX is a tiler, to preserve that existing partial render, the hardware needs to load it back into the tilebuffer. We have no idea how it does this.

Finally, the hardware flushes the render to the framebuffer. This should work as it did the first time.

## Auxiliary Programs

The only problematic step is _loading the framebuffer back into the tilebuffer after a partial render_. Usually, the driver supplies two "extra" fragment shaders. One clears the tilebuffer at the start, and the other flushes out the tilebuffer contents at the end.

If the application needs the existing framebuffer contents preserved, instead of writing a clear colour, the "load tilebuffer" program instead reads from the framebuffer to reload the contents. Handling this requires quite a bit of code, but it works in our driver.

Looking closer, AGX requires more auxiliary programs.

The "store" program is supplied _twice_. I noticed this when initially bringing up the hardware, but the reason for the duplication was unclear. Omitting each copy separately and seeing what breaks, the reason becomes clear: one program flushes the _final_ render, and the other flushes a _partial render_.

…What about the program that loads the framebuffer into the tilebuffer?

When a partial render is possible, there are two "load" programs. One writes the clear colour or loads the framebuffer, depending on the application setting. We understand this one. The other _always_ loads the framebuffer.

…Always loads the framebuffer, as in, for loading back with a partial render even if there is a clear at the start of the frame?

## Testing with Metal

If this program is the issue, we can confirm easily. Metal must require it to draw the same bunny, so we can write a Metal application drawing the bunny and stomp over its GPU memory to replace this auxiliary load program with one always loading with black.

Doing so, Metal fails in a similar way. That means we're at the root cause. Looking at our own driver code, we don't specify _any_ program for this partial render load. Up until now, that's worked okay. If the parameter buffer is never overflowed, this program is unused. As soon as a partial render is required, however, failing to provide this program means the GPU dereferences a null pointer and faults. That explains our GPU faults at the beginning.

Following Metal, we supply our own program to load back the tilebuffer after a partial render…

…which does _not_ fix the rendering! Cursed, this GPU. The faults go away, but the render still isn't quite right for the first few frames, indicating partial renders are still broken.

## Dynamic Buffer Resizing

Curiously, the render "repairs itself" after a few frames, suggesting the parameter buffer stops overflowing. This implies the parameter buffer can be resized (by the kernel or by the firmware), and the system is growing the parameter buffer after a few frames in response to overflow. This mechanism makes sense:

*   The hardware can't allocate more parameter buffer space itself.
*   Overflowing the parameter buffer is expensive, as partial renders require tremendous memory bandwidth.
*   Overallocating the parameter buffer wastes memory for applications rendering simple geometry.

Starting the parameter buffer small and growing in response to overflow provides a balance, reducing the GPU's memory footprint and minimizing partial renders.

## The Depth Buffer Issue

Back to our misrendering. There are actually _two_ buffers being used by our program, a colour buffer (framebuffer)… and a depth buffer. The depth buffer isn't directly visible, but facilitates the "depth test", which discards far pixels that are occluded by other close pixels. While the partial render mechanism discards geometry, the depth test discards pixels.

That would explain the missing pixels on our bunny. The depth test is broken with partial renders. Why? The depth test depends on the depth buffer, so the depth buffer must _also_ be stored after a partial render and loaded back when resuming. Comparing a trace from our driver to a trace from Metal, looking for any relevant difference, we eventually stumble on the configuration required to make depth buffer flushes work.

And with that, we get our bunny — the final Phong shaded bunny correctly rendered.

---

**Footnotes:**

1. These explanations are massive oversimplifications of how modern GPUs work, but it's good enough for our purposes here.

2. Starting with the new Valhall architecture, Mali allocates varyings much more efficiently.

3. Why the duplication? I have not yet observed Metal using different programs for each. However, for front buffer rendering, partial renders need to be flushed to a temporary buffer for this scheme to work. Of course, you may as well use double buffering at that point.
