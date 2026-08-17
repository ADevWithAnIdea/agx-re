/* EXP-0052 authored Metal timestamp probe. Apple binary/code inspection: NONE. */
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>

static id<MTLCounterSet> timestamp_set(id<MTLDevice> dev) {
    for (id<MTLCounterSet> set in dev.counterSets)
        if ([set.name isEqualToString:MTLCommonCounterSetTimestamp]) return set;
    return nil;
}

static void print_samples(const char *label, id<MTLCounterSampleBuffer> sb,
                          NSUInteger location, NSUInteger count) {
    NSData *data = [sb resolveCounterRange:NSMakeRange(location, count)];
    if (!data) {
        printf("SAMPLES %s base=%lu count=0 resolve=nil\n", label,
               (unsigned long)location);
        return;
    }
    const uint64_t *values = data.bytes;
    NSUInteger n = data.length / sizeof(uint64_t);
    printf("SAMPLES %s base=%lu count=%lu", label, (unsigned long)location,
           (unsigned long)n);
    for (NSUInteger i = 0; i < n; ++i)
        printf(" v%lu=%llu", (unsigned long)i, (unsigned long long)values[i]);
    printf("\n");
}

static void encode_pass(id<MTLCommandBuffer> cb, id<MTLRenderPipelineState> pso,
                        id<MTLTexture> target, id<MTLBuffer> iterations,
                        id<MTLCounterSampleBuffer> samples, NSUInteger base) {
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture = target;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(0.0, 0.0, 0.0, 1.0);
    rp.sampleBufferAttachments[0].sampleBuffer = samples;
    rp.sampleBufferAttachments[0].startOfVertexSampleIndex = base + 0;
    rp.sampleBufferAttachments[0].endOfVertexSampleIndex = base + 1;
    rp.sampleBufferAttachments[0].startOfFragmentSampleIndex = base + 2;
    rp.sampleBufferAttachments[0].endOfFragmentSampleIndex = base + 3;

    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    [enc setFragmentBuffer:iterations offset:0 atIndex:0];
    MTLViewport viewport = {0, 0, 64, 64, 0, 1};
    [enc setViewport:viewport];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
}

static int complete(id<MTLCommandBuffer> cb, const char *label) {
    [cb waitUntilCompleted];
    const char *error = cb.error ? cb.error.localizedDescription.UTF8String : "none";
    printf("COMMAND %s status=%ld error=%s gpuStart=%.9f gpuEnd=%.9f\n", label,
           (long)cb.status, error, cb.GPUStartTime, cb.GPUEndTime);
    return cb.status == MTLCommandBufferStatusCompleted ? 0 : 1;
}

int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    @autoreleasepool {
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        printf("DEVICE %s\n", dev.name.UTF8String);
        printf("SUPPORT dispatch=%d draw=%d stage=%d\n",
               (int)[dev supportsCounterSampling:MTLCounterSamplingPointAtDispatchBoundary],
               (int)[dev supportsCounterSampling:MTLCounterSamplingPointAtDrawBoundary],
               (int)[dev supportsCounterSampling:MTLCounterSamplingPointAtStageBoundary]);

        const long delays[] = {0, 100000, 1000000, 5000000};
        for (unsigned i = 0; i < 64; ++i) {
            MTLTimestamp c0 = 0, g0 = 0, c1 = 0, g1 = 0;
            [dev sampleTimestamps:&c0 gpuTimestamp:&g0];
            struct timespec delay = {0, delays[i % 4]};
            nanosleep(&delay, NULL);
            [dev sampleTimestamps:&c1 gpuTimestamp:&g1];
            printf("CAL i=%u delay_ns=%ld c0=%llu g0=%llu c1=%llu g1=%llu\n",
                   i, delays[i % 4], (unsigned long long)c0, (unsigned long long)g0,
                   (unsigned long long)c1, (unsigned long long)g1);
        }

        if (![dev supportsCounterSampling:MTLCounterSamplingPointAtStageBoundary]) {
            printf("FAIL stage-boundary sampling unsupported\n");
            return 2;
        }
        id<MTLCounterSet> set = timestamp_set(dev);
        if (!set) { printf("FAIL timestamp counter set missing\n"); return 3; }

        NSError *error = nil;
        MTLCounterSampleBufferDescriptor *sd = [MTLCounterSampleBufferDescriptor new];
        sd.counterSet = set;
        sd.sampleCount = 64;
        sd.storageMode = MTLStorageModeShared;
        sd.label = @"EXP-0052 authored timestamp samples";
        id<MTLCounterSampleBuffer> samples =
            [dev newCounterSampleBufferWithDescriptor:sd error:&error];
        if (!samples) {
            printf("FAIL sample buffer %s\n", error.localizedDescription.UTF8String);
            return 4;
        }

        NSString *source =
            @"#include <metal_stdlib>\nusing namespace metal;\n"
             "struct V { float4 p [[position]]; };\n"
             "vertex V vmain(uint id [[vertex_id]]) {\n"
             "  const float2 q[3] = {float2(-1,-1),float2(3,-1),float2(-1,3)};\n"
             "  V o; o.p=float4(q[id],0,1); return o;\n"
             "}\n"
             "fragment float4 fmain(device const uint *count [[buffer(0)]]) {\n"
             "  float x=0.1234567f; uint n=count[0];\n"
             "  for (uint k=0; k<n; ++k) x=fma(x,0.99991f,0.00007f);\n"
             "  return float4(fract(x),0.25f,0.75f,1.0f);\n"
             "}\n";
        id<MTLLibrary> library = [dev newLibraryWithSource:source options:nil error:&error];
        if (!library) { printf("FAIL library %s\n", error.localizedDescription.UTF8String); return 5; }
        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        pd.vertexFunction = [library newFunctionWithName:@"vmain"];
        pd.fragmentFunction = [library newFunctionWithName:@"fmain"];
        pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
        id<MTLRenderPipelineState> pso =
            [dev newRenderPipelineStateWithDescriptor:pd error:&error];
        if (!pso) { printf("FAIL pipeline %s\n", error.localizedDescription.UTF8String); return 6; }

        MTLTextureDescriptor *td = [MTLTextureDescriptor
            texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm
            width:64 height:64 mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> target = [dev newTextureWithDescriptor:td];
        uint32_t light_count = 1, heavy_count = 4096;
        id<MTLBuffer> light = [dev newBufferWithBytes:&light_count length:sizeof(light_count)
                                               options:MTLResourceStorageModeShared];
        id<MTLBuffer> heavy = [dev newBufferWithBytes:&heavy_count length:sizeof(heavy_count)
                                               options:MTLResourceStorageModeShared];
        id<MTLCommandQueue> queue = [dev newCommandQueue];

        print_samples("pre-commit", samples, 0, 4);
        id<MTLCommandBuffer> first = [queue commandBuffer];
        encode_pass(first, pso, target, light, samples, 0);
        [first commit];
        print_samples("in-flight", samples, 0, 4);
        if (complete(first, "light-initial")) return 7;
        print_samples("post-light", samples, 0, 4);

        id<MTLCommandBuffer> second = [queue commandBuffer];
        encode_pass(second, pso, target, heavy, samples, 4);
        [second commit];
        if (complete(second, "heavy-initial")) return 8;
        print_samples("post-heavy", samples, 4, 4);

        id<MTLCommandBuffer> pair = [queue commandBuffer];
        encode_pass(pair, pso, target, light, samples, 8);
        encode_pass(pair, pso, target, heavy, samples, 12);
        [pair commit];
        if (complete(pair, "two-pass-one-command")) return 9;
        print_samples("post-two-pass", samples, 8, 8);

        for (unsigned repetition = 0; repetition < 5; ++repetition) {
            NSUInteger base = 16 + repetition * 8;
            id<MTLCommandBuffer> a = [queue commandBuffer];
            encode_pass(a, pso, target, light, samples, base);
            [a commit];
            if (complete(a, "light-repeat")) return 10;
            id<MTLCommandBuffer> b = [queue commandBuffer];
            encode_pass(b, pso, target, heavy, samples, base + 4);
            [b commit];
            if (complete(b, "heavy-repeat")) return 11;
            char label[32]; snprintf(label, sizeof(label), "post-pair-%u", repetition);
            print_samples(label, samples, base, 8);
        }

        unsigned char pixel[4] = {0};
        [target getBytes:pixel bytesPerRow:4 fromRegion:MTLRegionMake2D(0,0,1,1)
              mipmapLevel:0];
        printf("PIXEL %02x%02x%02x%02x\n", pixel[0],pixel[1],pixel[2],pixel[3]);
        printf("RESULT OK\n");
        return 0;
    }
}
