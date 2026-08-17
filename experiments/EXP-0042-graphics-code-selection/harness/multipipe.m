// Clean-room graphics pipeline-selection probe.
// Inputs are the two authored .metal files beside this experiment. This program
// uses only public Metal/Foundation APIs and observes only our output data.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void die(NSString *what, NSError *error)
{
    fprintf(stderr, "FAIL %s: %s\n", what.UTF8String,
            error ? error.localizedDescription.UTF8String : "unknown");
    exit(2);
}

static NSString *load_source(const char *path)
{
    NSError *error = nil;
    NSString *source = [NSString stringWithContentsOfFile:@(path)
                                                  encoding:NSUTF8StringEncoding
                                                     error:&error];
    if (!source)
        die([NSString stringWithFormat:@"read %s", path], error);
    return source;
}

static id<MTLRenderPipelineState> make_pipeline(id<MTLDevice> device,
                                                NSString *source,
                                                NSString *label)
{
    NSError *error = nil;
    id<MTLLibrary> library = [device newLibraryWithSource:source
                                                  options:nil error:&error];
    if (!library)
        die([label stringByAppendingString:@" library"], error);

    MTLRenderPipelineDescriptor *desc = [MTLRenderPipelineDescriptor new];
    desc.label = label;
    desc.vertexFunction = [library newFunctionWithName:@"vs_main"];
    desc.fragmentFunction = [library newFunctionWithName:@"fs_main"];
    desc.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
    id<MTLRenderPipelineState> state =
        [device newRenderPipelineStateWithDescriptor:desc error:&error];
    if (!state)
        die([label stringByAppendingString:@" pipeline"], error);
    return state;
}

static void print_va(const char *name, id<MTLBuffer> buffer)
{
    printf("RESOURCE %s va=0x%llx size=0x%lx\n", name,
           (unsigned long long)buffer.gpuAddress, (unsigned long)buffer.length);
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

static void bind_and_draw(id<MTLRenderCommandEncoder> encoder, char pipeline,
                          id<MTLRenderPipelineState> state_a,
                          id<MTLRenderPipelineState> state_b,
                          id<MTLBuffer> vertices, id<MTLBuffer> params_a,
                          id<MTLBuffer> params_b)
{
    [encoder setRenderPipelineState:(pipeline == 'A' ? state_a : state_b)];
    [encoder setVertexBuffer:vertices offset:0 atIndex:0];
    if (pipeline == 'A') {
        [encoder setFragmentBuffer:params_a offset:0 atIndex:0];
    } else {
        [encoder setVertexBuffer:params_b offset:0 atIndex:1];
        [encoder setFragmentBuffer:params_b offset:0 atIndex:0];
    }
    [encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
}

int main(int argc, char **argv)
{
    @autoreleasepool {
        const char *source_a = "kernels/pipeline_a.metal";
        const char *source_b = "kernels/pipeline_b.metal";
        const char *order = "AB";
        const char *sequences = "A,B,AB,BA,ABAB,BABA,ABBA,BAAB";
        unsigned prealloc = 0;
        int dump = 0;

        for (int i = 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--source-a") && i + 1 < argc) source_a = argv[++i];
            else if (!strcmp(argv[i], "--source-b") && i + 1 < argc) source_b = argv[++i];
            else if (!strcmp(argv[i], "--compile-order") && i + 1 < argc) order = argv[++i];
            else if (!strcmp(argv[i], "--sequences") && i + 1 < argc) sequences = argv[++i];
            else if (!strcmp(argv[i], "--prealloc") && i + 1 < argc) prealloc = strtoul(argv[++i], 0, 0);
            else if (!strcmp(argv[i], "--dump")) dump = 1;
            else {
                fprintf(stderr, "usage: %s [--source-a P] [--source-b P] "
                        "[--compile-order AB|BA] [--prealloc N] "
                        "[--sequences CSV] [--dump]\n", argv[0]);
                return 2;
            }
        }
        if (strcmp(order, "AB") && strcmp(order, "BA")) {
            fprintf(stderr, "compile order must be AB or BA\n");
            return 2;
        }
        alarm(150);

        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) {
            fprintf(stderr, "FAIL no Metal device\n");
            return 2;
        }
        printf("DEVICE %s\n", device.name.UTF8String);
        printf("CONFIG compile_order=%s prealloc=%u sequences=%s\n",
               order, prealloc, sequences);
        printf("SOURCE A=%s B=%s\n", source_a, source_b);

        NSMutableArray<id<MTLBuffer>> *padding = [NSMutableArray array];
        for (unsigned i = 0; i < prealloc; ++i) {
            id<MTLBuffer> p = [device newBufferWithLength:(0x1000 + i * 0x100)
                                                  options:MTLResourceStorageModeShared];
            if (!p) { fprintf(stderr, "FAIL padding %u\n", i); return 2; }
            memset(p.contents, (int)(0x40 + i), p.length);
            [padding addObject:p];
        }

        NSString *a_text = load_source(source_a);
        NSString *b_text = load_source(source_b);
        id<MTLRenderPipelineState> state_a = nil, state_b = nil;
        if (!strcmp(order, "AB")) {
            state_a = make_pipeline(device, a_text, @"authored-A");
            state_b = make_pipeline(device, b_text, @"authored-B");
        } else {
            state_b = make_pipeline(device, b_text, @"authored-B");
            state_a = make_pipeline(device, a_text, @"authored-A");
        }

        static const float tri[6] = {-1.0f, -1.0f, 3.0f, -1.0f, -1.0f, 3.0f};
        id<MTLBuffer> vertices = [device newBufferWithBytes:tri length:sizeof(tri)
                                                    options:MTLResourceStorageModeShared];
        id<MTLBuffer> params_a = [device newBufferWithLength:0x100
                                                     options:MTLResourceStorageModeShared];
        id<MTLBuffer> params_b = [device newBufferWithLength:0x100
                                                     options:MTLResourceStorageModeShared];
        float *a = params_a.contents;
        a[0] = 0.92f; a[1] = 0.08f; a[2] = 0.16f; a[3] = 1.0f;
        float *b = params_b.contents;
        // Vertex recurrence: q=fma(q,1,0); UV scale/bias are zero.
        b[0] = 1.0f; b[1] = 1.0f; b[2] = 0.0f; b[3] = 0.0f;
        b[4] = 0.0f; b[5] = 0.0f; b[6] = 0.0f; b[7] = 0.0f;
        // Fragment colour[2], also used as the fma addend.
        b[8] = 0.05f; b[9] = 0.80f; b[10] = 0.20f; b[11] = 1.0f;
        b[12] = 0.0f; b[13] = 0.0f; b[14] = 0.0f; b[15] = 0.0f;
        print_va("vertices", vertices);
        print_va("params_a", params_a);
        print_va("params_b", params_b);
        if (padding.count) print_va("padding_0", padding[0]);

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
        if (!target) { fprintf(stderr, "FAIL buffer-backed target\n"); return 2; }
        print_va("target", target_buffer);

        id<MTLCommandQueue> queue = [device newCommandQueue];
        if (!queue) { fprintf(stderr, "FAIL queue\n"); return 2; }

        char *sequence_copy = strdup(sequences);
        char *save = NULL;
        unsigned submit = 0;
        for (char *sequence = strtok_r(sequence_copy, ",", &save); sequence;
             sequence = strtok_r(NULL, ",", &save), ++submit) {
            for (const char *p = sequence; *p; ++p) {
                if (*p != 'A' && *p != 'B') {
                    fprintf(stderr, "FAIL invalid sequence %s\n", sequence);
                    return 2;
                }
            }
            MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
            rp.colorAttachments[0].texture = target;
            rp.colorAttachments[0].loadAction = MTLLoadActionClear;
            rp.colorAttachments[0].storeAction = MTLStoreActionStore;
            rp.colorAttachments[0].clearColor = MTLClearColorMake(0.0, 0.0, 0.0, 1.0);

            id<MTLCommandBuffer> command = [queue commandBuffer];
            command.label = [NSString stringWithFormat:@"sequence-%s", sequence];
            id<MTLRenderCommandEncoder> encoder =
                [command renderCommandEncoderWithDescriptor:rp];
            for (const char *p = sequence; *p; ++p)
                bind_and_draw(encoder, *p, state_a, state_b, vertices, params_a, params_b);
            [encoder endEncoding];
            [command commit];
            [command waitUntilCompleted];
            if (command.status != MTLCommandBufferStatusCompleted) {
                fprintf(stderr, "FAIL submit=%u sequence=%s status=%ld error=%s\n",
                        submit, sequence, (long)command.status,
                        command.error.localizedDescription.UTF8String);
                return 3;
            }

            unsigned char *pixels = target_buffer.contents;
            unsigned char *sample = pixels + 32 * bytes_per_row + 32 * 4;
            printf("RESULT submit=%u sequence=%s final=%c status=completed "
                   "sample_bgra=%02x%02x%02x%02x fnv1a=%016llx\n",
                   submit, sequence, sequence[strlen(sequence) - 1], sample[0],
                   sample[1], sample[2], sample[3],
                   fnv1a(pixels, target_buffer.length));
            fflush(stdout);
            if (dump) {
                kill(getpid(), SIGUSR1);
                usleep(650000);
            }
        }
        free(sequence_copy);
        alarm(0);
        return 0;
    }
}
