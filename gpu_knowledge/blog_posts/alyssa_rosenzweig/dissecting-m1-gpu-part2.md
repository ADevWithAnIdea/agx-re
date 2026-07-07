# Dissecting the Apple M1 GPU, part II

> Source URL: https://rosenzweig.io/blog/asahi-gpu-part-2.html
> Redirect: https://alyssarosenzweig.ca/blog/asahi-gpu-part-2.html

## Overview

This blog post documents progress in reverse-engineering the Apple M1 GPU to develop open-source drivers. The author achieved a significant milestone: rendering a triangle using handwritten shader code and custom command buffer construction.

## Key Accomplishments

The developer successfully "drew a triangle with my own open-source code" where "vertex and fragment shaders are handwritten in machine code." This represents substantial progress toward a functional open-source GPU driver.

## Technical Approach

### Memory Structure Complexity

The GPU's command system relies on nested pointer structures in shared memory. As the author explains, "the application-provided vertex data are in their own buffers. An internal table in yet another buffer points each of these vertex buffers." This cascading architecture required careful mapping to understand how components reference one another.

### Incremental Development Strategy

Rather than constructing all buffers simultaneously, the developer employed "a piecemeal bring-up process." This methodical approach proved superior to alternatives like replay-based techniques, which "comes with the substantial drawback of fiendishly difficult debugging."

## The Memory Allocation Mystery

The most challenging discovery involved an auxiliary GPU memory structure tracking allocations. Despite identical parameters to Metal's allocation calls, custom allocations initially failed. The solution involved manipulating a table containing allocation handles—a "64-byte table entries in shared memory" structure whose purpose remained puzzling even after achieving success.

## Implementation Results

The completed work comprises "around 1700 lines of code" and demonstrates GPU rendering capabilities without substantial window system integration.
