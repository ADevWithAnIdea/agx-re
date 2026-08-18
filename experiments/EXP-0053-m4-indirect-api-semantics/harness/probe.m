/* EXP-0053 authored public-Metal indirect-command probe. Apple code inspection: NONE. */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static const uint32_t SENTINEL = 0xd00dfeedu;

static int finish(id<MTLCommandBuffer> cb, const char *label) {
    [cb waitUntilCompleted];
    const char *error = cb.error ? cb.error.localizedDescription.UTF8String : "none";
    printf("COMMAND label=%s status=%ld error=%s\n", label, (long)cb.status, error);
    return cb.status == MTLCommandBufferStatusCompleted ? 0 : 1;
}

static uint64_t fnv1a(const void *bytes, size_t length) {
    const uint8_t *p = bytes;
    uint64_t hash = UINT64_C(1469598103934665603);
    for (size_t i = 0; i < length; ++i) { hash ^= p[i]; hash *= UINT64_C(1099511628211); }
    return hash;
}

static void print_hex_field(const char *name, const void *bytes, size_t length) {
    const uint8_t *p = bytes;
    printf(" %s=", name);
    for (size_t i = 0; i < length; ++i) printf("%02x", p[i]);
}

static void reset_compute(id<MTLBuffer> args, id<MTLBuffer> counter, id<MTLBuffer> output) {
    uint32_t *a = args.contents, *c = counter.contents, *o = output.contents;
    for (unsigned i = 0; i < args.length / 4; ++i) a[i] = SENTINEL;
    for (unsigned i = 0; i < counter.length / 4; ++i) c[i] = SENTINEL;
    for (unsigned i = 0; i < output.length / 4; ++i) o[i] = SENTINEL;
    c[1] = 0;
}

static int report_compute(const char *name, id<MTLBuffer> args, id<MTLBuffer> counter,
                          id<MTLBuffer> output, unsigned expected_threads) {
    uint32_t *a = args.contents, *c = counter.contents, *o = output.contents;
    unsigned mismatches = 0, guard_errors = 0;
    for (unsigned i = 0; i < expected_threads; ++i)
        if (o[4 + i] != (UINT32_C(0x51000000) ^ i)) ++mismatches;
    for (unsigned i = expected_threads; i < 64; ++i)
        if (o[4 + i] != SENTINEL) ++mismatches;
    for (unsigned i = 0; i < 4; ++i)
        guard_errors += (o[i] != SENTINEL) + (o[68 + i] != SENTINEL);
    guard_errors += (c[0] != SENTINEL) + (c[2] != SENTINEL);
    for (unsigned i = 0; i < 4; ++i)
        guard_errors += (a[i] != SENTINEL) + (a[7 + i] != SENTINEL);
    printf("COMPUTE case=%s expected_threads=%u counter=%u mismatches=%u guards=%u "
           "args=%u,%u,%u output_fnv=%016llx", name, expected_threads, c[1],
           mismatches, guard_errors, a[4], a[5], a[6],
           (unsigned long long)fnv1a(o, output.length));
    print_hex_field("arg_hex", a, args.length);
    print_hex_field("counter_hex", c, counter.length);
    print_hex_field("output_hex", o, output.length);
    printf("\n");
    return c[1] == expected_threads && mismatches == 0 && guard_errors == 0 ? 0 : 1;
}

static int run_compute(id<MTLCommandQueue> queue, id<MTLComputePipelineState> mark,
                       id<MTLComputePipelineState> produce, id<MTLBuffer> args,
                       id<MTLBuffer> counter, id<MTLBuffer> output,
                       const char *name, unsigned groups, BOOL mutate_after_encode,
                       BOOL gpu_produce) {
    reset_compute(args, counter, output);
    uint32_t *a = args.contents;
    a[4] = mutate_after_encode ? 1 : groups; a[5] = 1; a[6] = 1;
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    if (gpu_produce) {
        a[4] = a[5] = a[6] = 0;
        id<MTLComputeCommandEncoder> producer = [cb computeCommandEncoder];
        [producer setComputePipelineState:produce];
        [producer setBuffer:args offset:16 atIndex:0];
        [producer dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
        [producer endEncoding];
    }
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:mark];
    [enc setBuffer:counter offset:4 atIndex:0];
    [enc setBuffer:output offset:16 atIndex:1];
    [enc dispatchThreadgroupsWithIndirectBuffer:args indirectBufferOffset:16
                           threadsPerThreadgroup:MTLSizeMake(8,1,1)];
    [enc endEncoding];
    if (mutate_after_encode) { a[4] = groups; a[5] = 1; a[6] = 1; }
    [cb commit];
    if (finish(cb, name)) return 1;
    return report_compute(name, args, counter, output, groups * 8);
}

static void read_target(id<MTLTexture> target, uint8_t bytes[16]) {
    [target getBytes:bytes bytesPerRow:16 fromRegion:MTLRegionMake2D(0,0,4,1) mipmapLevel:0];
}

static void print_rgba(const uint8_t bytes[16], char text[33]) {
    for (unsigned i = 0; i < 16; ++i) snprintf(text + i * 2, 3, "%02x", bytes[i]);
}

static MTLRenderPassDescriptor *pass(id<MTLTexture> target) {
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture = target;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(1.0/255.0,2.0/255.0,3.0/255.0,4.0/255.0);
    return rp;
}

static int run_indirect_draw(id<MTLCommandQueue> queue, id<MTLRenderPipelineState> pso,
                             id<MTLTexture> target, unsigned vertex_count, const char *name) {
    id<MTLBuffer> args = [queue.device newBufferWithLength:48 options:MTLResourceStorageModeShared];
    uint32_t *words = args.contents;
    for (unsigned i = 0; i < 12; ++i) words[i] = SENTINEL;
    words[4] = vertex_count; words[5] = 1; words[6] = 0; words[7] = 0;
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:pass(target)];
    [enc setRenderPipelineState:pso];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle indirectBuffer:args indirectBufferOffset:16];
    [enc endEncoding]; [cb commit];
    if (finish(cb, name)) return 1;
    uint8_t bytes[16]; char hex[33]; read_target(target, bytes); print_rgba(bytes, hex);
    unsigned guards = 0;
    for (unsigned i = 0; i < 4; ++i) guards += words[i] != SENTINEL;
    for (unsigned i = 8; i < 12; ++i) guards += words[i] != SENTINEL;
    printf("DRAW case=%s vertices=%u guards=%u rgba=%s", name, vertex_count, guards, hex);
    print_hex_field("arg_hex", words, args.length);
    printf("\n");
    const char *expected = vertex_count ? "11223344112233441122334411223344"
                                        : "01020304010203040102030401020304";
    return guards == 0 && strcmp(hex, expected) == 0 ? 0 : 1;
}

static id<MTLIndirectCommandBuffer> make_icb(id<MTLDevice> dev) {
    MTLIndirectCommandBufferDescriptor *desc = [MTLIndirectCommandBufferDescriptor new];
    desc.commandTypes = MTLIndirectCommandTypeDraw;
    desc.inheritPipelineState = YES;
    desc.inheritBuffers = YES;
    desc.maxVertexBufferBindCount = 0;
    desc.maxFragmentBufferBindCount = 0;
    id<MTLIndirectCommandBuffer> icb = [dev newIndirectCommandBufferWithDescriptor:desc
        maxCommandCount:4 options:MTLResourceStorageModePrivate];
    for (NSUInteger i = 0; i < 4; ++i) {
        id<MTLIndirectRenderCommand> command = [icb indirectRenderCommandAtIndex:i];
        [command drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:6
                  instanceCount:1 baseInstance:i];
    }
    return icb;
}

static int run_icb(id<MTLCommandQueue> queue, id<MTLRenderPipelineState> pso,
                   id<MTLTexture> target, id<MTLIndirectCommandBuffer> icb,
                   NSRange range, BOOL optimize, const char *name, const char *expected) {
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    if (optimize) {
        id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder];
        [blit optimizeIndirectCommandBuffer:icb withRange:NSMakeRange(0,4)];
        [blit endEncoding];
    }
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:pass(target)];
    [enc setRenderPipelineState:pso];
    [enc executeCommandsInBuffer:icb withRange:range];
    [enc endEncoding]; [cb commit];
    if (finish(cb, name)) return 1;
    uint8_t bytes[16]; char hex[33]; read_target(target, bytes); print_rgba(bytes, hex);
    printf("ICB case=%s start=%lu count=%lu optimize=%d rgba=%s\n", name,
           (unsigned long)range.location, (unsigned long)range.length, (int)optimize, hex);
    return strcmp(hex, expected) == 0 ? 0 : 1;
}

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    @autoreleasepool {
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        printf("DEVICE %s\n", dev.name.UTF8String);
        printf("SUPPORT icb_api=attempted\n");
        NSError *error = nil;
        NSString *source =
          @"#include <metal_stdlib>\nusing namespace metal;\n"
           "kernel void mark(device atomic_uint *count [[buffer(0)]], device uint *out [[buffer(1)]], uint gid [[thread_position_in_grid]]) { out[gid]=0x51000000u^gid; atomic_fetch_add_explicit(count,1u,memory_order_relaxed); }\n"
           "kernel void produce(device uint *args [[buffer(0)]]) { args[0]=4; args[1]=1; args[2]=1; }\n"
           "struct V { float4 p [[position]]; float4 c; };\n"
           "vertex V vfull(uint id [[vertex_id]]) { const float2 q[3]={float2(-1,-1),float2(3,-1),float2(-1,3)}; V o; o.p=float4(q[id],0,1); o.c=float4(17.0/255.0,34.0/255.0,51.0/255.0,68.0/255.0); return o; }\n"
           "vertex V vicb(uint id [[vertex_id]], uint iid [[instance_id]]) { const float2 q[6]={float2(0,0),float2(1,0),float2(0,1),float2(0,1),float2(1,0),float2(1,1)}; float x0=-1.0+0.5*float(iid); V o; o.p=float4(x0+0.5*q[id].x,-1.0+2.0*q[id].y,0,1); const float4 c[4]={float4(16,32,48,255)/255.0,float4(64,80,96,255)/255.0,float4(112,128,144,255)/255.0,float4(160,176,192,255)/255.0}; o.c=c[iid]; return o; }\n"
           "fragment float4 frag(V in [[stage_in]]) { return in.c; }\n";
        id<MTLLibrary> lib = [dev newLibraryWithSource:source options:nil error:&error];
        if (!lib) { printf("FAIL library=%s\n", error.localizedDescription.UTF8String); return 3; }
        id<MTLComputePipelineState> mark = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"mark"] error:&error];
        id<MTLComputePipelineState> produce = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"produce"] error:&error];
        if (!mark || !produce) { printf("FAIL compute=%s\n", error.localizedDescription.UTF8String); return 4; }
        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        pd.vertexFunction = [lib newFunctionWithName:@"vfull"];
        pd.fragmentFunction = [lib newFunctionWithName:@"frag"];
        pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
        id<MTLRenderPipelineState> direct = [dev newRenderPipelineStateWithDescriptor:pd error:&error];
        pd.vertexFunction = [lib newFunctionWithName:@"vicb"];
        pd.supportIndirectCommandBuffers = YES;
        id<MTLRenderPipelineState> icbpso = [dev newRenderPipelineStateWithDescriptor:pd error:&error];
        if (!direct || !icbpso) { printf("FAIL render=%s\n", error.localizedDescription.UTF8String); return 5; }
        id<MTLCommandQueue> queue = [dev newCommandQueue];
        id<MTLBuffer> args = [dev newBufferWithLength:44 options:MTLResourceStorageModeShared];
        id<MTLBuffer> counter = [dev newBufferWithLength:12 options:MTLResourceStorageModeShared];
        id<MTLBuffer> output = [dev newBufferWithLength:288 options:MTLResourceStorageModeShared];
        int failed = 0;
        failed |= run_compute(queue, mark, produce, args, counter, output, "indirect-zero", 0, NO, NO);
        failed |= run_compute(queue, mark, produce, args, counter, output, "cpu-mutate-before-commit", 3, YES, NO);
        failed |= run_compute(queue, mark, produce, args, counter, output, "gpu-producer-prior-encoder", 4, NO, YES);

        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:4 height:1 mipmapped:NO];
        td.storageMode = MTLStorageModeShared; td.usage = MTLTextureUsageRenderTarget;
        id<MTLTexture> target = [dev newTextureWithDescriptor:td];
        failed |= run_indirect_draw(queue, direct, target, 0, "indirect-draw-zero");
        failed |= run_indirect_draw(queue, direct, target, 3, "indirect-draw-three");

        const char *clear = "01020304";
        const char *c0="102030ff", *c1="405060ff", *c2="708090ff", *c3="a0b0c0ff";
        char expected[33];
        id<MTLIndirectCommandBuffer> icb = make_icb(dev);
        if (!icb) { printf("RESULT UNSUPPORTED icb_allocation=nil\n"); return 2; }
        snprintf(expected, sizeof(expected), "%s%s%s%s", c0,c1,c2,c3);
        failed |= run_icb(queue, icbpso, target, icb, NSMakeRange(0,4), NO, "full", expected);
        snprintf(expected, sizeof(expected), "%s%s%s%s", c0,c1,clear,clear);
        failed |= run_icb(queue, icbpso, target, icb, NSMakeRange(0,2), NO, "prefix", expected);
        snprintf(expected, sizeof(expected), "%s%s%s%s", clear,clear,c2,c3);
        failed |= run_icb(queue, icbpso, target, icb, NSMakeRange(2,2), NO, "suffix", expected);
        snprintf(expected, sizeof(expected), "%s%s%s%s", clear,c1,c2,clear);
        failed |= run_icb(queue, icbpso, target, icb, NSMakeRange(1,2), NO, "middle", expected);
        snprintf(expected, sizeof(expected), "%s%s%s%s", clear,clear,clear,clear);
        failed |= run_icb(queue, icbpso, target, icb, NSMakeRange(0,0), NO, "empty", expected);

        [icb resetWithRange:NSMakeRange(1,2)];
        snprintf(expected, sizeof(expected), "%s%s%s%s", c0,clear,clear,c3);
        failed |= run_icb(queue, icbpso, target, icb, NSMakeRange(0,4), NO, "reset-middle", expected);
        id<MTLIndirectRenderCommand> restored = [icb indirectRenderCommandAtIndex:1];
        [restored drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:6 instanceCount:1 baseInstance:1];
        snprintf(expected, sizeof(expected), "%s%s%s%s", c0,c1,clear,c3);
        failed |= run_icb(queue, icbpso, target, icb, NSMakeRange(0,4), NO, "restore-one", expected);

        id<MTLIndirectCommandBuffer> optimized = make_icb(dev);
        snprintf(expected, sizeof(expected), "%s%s%s%s", c0,c1,c2,c3);
        failed |= run_icb(queue, icbpso, target, optimized, NSMakeRange(0,4), YES, "optimized-full", expected);
        printf("RESULT %s\n", failed ? "FAIL" : "OK");
        return failed ? 10 : 0;
    }
}
