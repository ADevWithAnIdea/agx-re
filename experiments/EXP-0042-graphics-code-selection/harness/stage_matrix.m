// Four-way small/large VS x FS clean-room pipeline-resource probe.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void fail(const char *what, NSError *error)
{
    fprintf(stderr, "FAIL %s: %s\n", what,
            error ? error.localizedDescription.UTF8String : "unknown");
    exit(2);
}

static id<MTLRenderPipelineState> make_pipeline(id<MTLDevice> device,
                                                id<MTLLibrary> library,
                                                NSString *vertex,
                                                NSString *fragment,
                                                NSString *label)
{
    MTLRenderPipelineDescriptor *desc = [MTLRenderPipelineDescriptor new];
    desc.label = label;
    desc.vertexFunction = [library newFunctionWithName:vertex];
    desc.fragmentFunction = [library newFunctionWithName:fragment];
    desc.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
    NSError *error = nil;
    id<MTLRenderPipelineState> state =
        [device newRenderPipelineStateWithDescriptor:desc error:&error];
    if (!state) fail(label.UTF8String, error);
    return state;
}

static unsigned long long fnv1a(const unsigned char *data, size_t size)
{
    unsigned long long h = 1469598103934665603ULL;
    for (size_t i = 0; i < size; ++i) {
        h ^= data[i];
        h *= 1099511628211ULL;
    }
    return h;
}

int main(int argc, char **argv)
{
    @autoreleasepool {
        const char *source_path = "kernels/stage_matrix.metal";
        int dump = 0;
        for (int i = 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--source") && i + 1 < argc) source_path = argv[++i];
            else if (!strcmp(argv[i], "--dump")) dump = 1;
            else { fprintf(stderr, "usage: %s [--source P] [--dump]\n", argv[0]); return 2; }
        }
        alarm(150);
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        NSError *error = nil;
        NSString *source = [NSString stringWithContentsOfFile:@(source_path)
                                                      encoding:NSUTF8StringEncoding
                                                         error:&error];
        if (!source) fail("read source", error);
        id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
        if (!library) fail("compile library", error);

        // Creation order is the controlled SS,SF,LS,LF order.
        id<MTLRenderPipelineState> states[6] = {
            make_pipeline(device, library, @"vs_small", @"fs_small", @"SS"),
            make_pipeline(device, library, @"vs_small", @"fs_large", @"SF"),
            make_pipeline(device, library, @"vs_large", @"fs_small", @"LS"),
            make_pipeline(device, library, @"vs_large", @"fs_large", @"LF"),
            make_pipeline(device, library, @"vs_small", @"fs_equal_a", @"EA"),
            make_pipeline(device, library, @"vs_small", @"fs_equal_b", @"EB"),
        };
        const char *names[6] = {"SS", "SF", "LS", "LF", "EA", "EB"};

        static const float tri[6] = {-1.0f, -1.0f, 3.0f, -1.0f, -1.0f, 3.0f};
        id<MTLBuffer> vertices = [device newBufferWithBytes:tri length:sizeof(tri)
                                                    options:MTLResourceStorageModeShared];
        id<MTLBuffer> params = [device newBufferWithLength:0x100
                                                   options:MTLResourceStorageModeShared];
        float *p = params.contents;
        p[0] = 1.0f; p[1] = 1.0f; p[2] = 0.0f; p[3] = 0.0f;
        p[4] = 0.0f; p[5] = 0.0f; p[6] = 0.0f; p[7] = 0.0f;
        p[8] = 0.90f; p[9] = 0.10f; p[10] = 0.18f; p[11] = 1.0f;
        p[12] = 0.06f; p[13] = 0.78f; p[14] = 0.22f; p[15] = 1.0f;

        const NSUInteger width = 64, height = 64, bytes_per_row = 256;
        id<MTLBuffer> target_buffer = [device newBufferWithLength:bytes_per_row * height
                                                         options:MTLResourceStorageModeShared];
        MTLTextureDescriptor *td =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                               width:width height:height mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> target = [target_buffer newTextureWithDescriptor:td offset:0
                                                           bytesPerRow:bytes_per_row];
        if (!target) fail("target", nil);
        printf("DEVICE %s\n", device.name.UTF8String);
        printf("CONFIG order=SS,SF,LS,LF source=%s\n", source_path);
        printf("RESOURCE vertices=0x%llx params=0x%llx target=0x%llx\n",
               (unsigned long long)vertices.gpuAddress,
               (unsigned long long)params.gpuAddress,
               (unsigned long long)target_buffer.gpuAddress);

        id<MTLCommandQueue> queue = [device newCommandQueue];
        static const unsigned schedule[12] = {0, 1, 2, 3, 4, 5, 0, 1, 2, 3, 4, 5};
        for (unsigned submit = 0; submit < 12; ++submit) {
            unsigned which = schedule[submit];
            MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
            rp.colorAttachments[0].texture = target;
            rp.colorAttachments[0].loadAction = MTLLoadActionClear;
            rp.colorAttachments[0].storeAction = MTLStoreActionStore;
            rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
            id<MTLCommandBuffer> command = [queue commandBuffer];
            id<MTLRenderCommandEncoder> encoder =
                [command renderCommandEncoderWithDescriptor:rp];
            [encoder setRenderPipelineState:states[which]];
            [encoder setVertexBuffer:vertices offset:0 atIndex:0];
            [encoder setVertexBuffer:params offset:0 atIndex:1];
            [encoder setFragmentBuffer:params offset:0 atIndex:0];
            [encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            [encoder endEncoding];
            [command commit];
            [command waitUntilCompleted];
            if (command.status != MTLCommandBufferStatusCompleted)
                fail("command", command.error);
            unsigned char *pixels = target_buffer.contents;
            unsigned char *sample = pixels + 32 * bytes_per_row + 32 * 4;
            printf("RESULT submit=%u pipeline=%s vs=%s fs=%s sample_bgra=%02x%02x%02x%02x "
                   "fnv1a=%016llx status=completed\n", submit, names[which],
                   (which == 2 || which == 3) ? "large" : "small",
                   which == 1 || which == 3 ? "large" :
                   (which == 4 ? "equal_a" : (which == 5 ? "equal_b" : "small")),
                   sample[0], sample[1], sample[2], sample[3],
                   fnv1a(pixels, target_buffer.length));
            fflush(stdout);
            if (dump) { kill(getpid(), SIGUSR1); usleep(650000); }
        }
        alarm(0);
        return 0;
    }
}
