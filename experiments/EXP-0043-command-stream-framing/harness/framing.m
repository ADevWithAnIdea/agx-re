// framing.m -- authored Metal workloads for Apple9 command-stream framing.
//
// CLEAN ROOM: public Metal API + OWN-SHADER only. Every shader source executed
// by this program is present below. The program asks the DATA-TRACE interposer
// to snapshot boundary data after completed command buffers. It does not read,
// inspect, or invoke tools on any Apple binary.
//
// Build:
//   xcrun clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation \
//       -o framing framing.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef enum {
    MODE_COMPUTE,
    MODE_COMPUTE_SPLIT,
    MODE_RENDER,
    MODE_RENDER_SPLIT,
    MODE_COMPUTE_RENDER,
    MODE_RENDER_COMPUTE,
    MODE_TWO_QUEUES,
} ProbeMode;

typedef struct {
    ProbeMode mode;
    const char *mode_name;
    long count;
    long submits;
    long pad;
    long pad_bytes;
    long width;
    long height;
    int alternate;
    int dump_final;
    int dump_each;
    useconds_t dump_wait_us;
} Config;

static void print_va(const char *name, uint64_t va)
{
    printf("VA %-16s = 0x%016llx le=", name, (unsigned long long)va);
    for (unsigned i = 0; i < 8; ++i)
        printf("%02x", (unsigned)((va >> (i * 8)) & 0xff));
    putchar('\n');
}

static int parse_mode(const char *s, ProbeMode *out)
{
    if (!strcmp(s, "compute"))       *out = MODE_COMPUTE;
    else if (!strcmp(s, "compute-split")) *out = MODE_COMPUTE_SPLIT;
    else if (!strcmp(s, "render"))   *out = MODE_RENDER;
    else if (!strcmp(s, "render-split")) *out = MODE_RENDER_SPLIT;
    else if (!strcmp(s, "compute-render")) *out = MODE_COMPUTE_RENDER;
    else if (!strcmp(s, "render-compute")) *out = MODE_RENDER_COMPUTE;
    else if (!strcmp(s, "two-queues")) *out = MODE_TWO_QUEUES;
    else return 0;
    return 1;
}

static void usage(const char *argv0)
{
    fprintf(stderr,
        "usage: %s [--mode compute|compute-split|render|render-split|"
        "compute-render|render-compute|two-queues] [--count N] [--submits N] "
        "[--alternate] [--pad N] [--pad-bytes N] [--w N] [--h N] "
        "[--dump] [--dump-each] [--dump-wait-us N]\n", argv0);
}

static id<MTLComputePipelineState> make_compute_pso(id<MTLDevice> dev,
                                                     NSString *name,
                                                     NSError **err)
{
    NSString *source =
        @"#include <metal_stdlib>\n"
         "using namespace metal;\n"
         "kernel void kernel_a(device uint *out [[buffer(0)]],\n"
         "                     constant uint &tag [[buffer(1)]],\n"
         "                     uint i [[thread_position_in_grid]]) {\n"
         "  out[i] = tag + i;\n"
         "}\n"
         "kernel void kernel_b(device uint *out [[buffer(0)]],\n"
         "                     constant uint &tag [[buffer(1)]],\n"
         "                     uint i [[thread_position_in_grid]]) {\n"
         "  out[i] = (tag ^ 0x10000000u) + i;\n"
         "}\n";
    id<MTLLibrary> lib = [dev newLibraryWithSource:source options:nil error:err];
    if (!lib) return nil;
    id<MTLFunction> fn = [lib newFunctionWithName:name];
    if (!fn) return nil;
    return [dev newComputePipelineStateWithFunction:fn error:err];
}

static id<MTLRenderPipelineState> make_render_pso(id<MTLDevice> dev,
                                                   NSString *fragment_name,
                                                   NSError **err)
{
    NSString *source =
        @"#include <metal_stdlib>\n"
         "using namespace metal;\n"
         "struct VOut { float4 position [[position]]; };\n"
         "vertex VOut vertex_main(uint vid [[vertex_id]],\n"
         "                        const device float2 *positions [[buffer(0)]]) {\n"
         "  VOut o; o.position = float4(positions[vid % 3], 0.0f, 1.0f); return o;\n"
         "}\n"
         "fragment float4 fragment_a(constant float4 &c [[buffer(0)]]) {\n"
         "  return c;\n"
         "}\n"
         "fragment float4 fragment_b(constant float4 &c [[buffer(0)]]) {\n"
         "  return float4(c.b, c.r, c.g, c.a);\n"
         "}\n";
    id<MTLLibrary> lib = [dev newLibraryWithSource:source options:nil error:err];
    if (!lib) return nil;
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = [lib newFunctionWithName:@"vertex_main"];
    pd.fragmentFunction = [lib newFunctionWithName:fragment_name];
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
    return [dev newRenderPipelineStateWithDescriptor:pd error:err];
}

static void encode_compute(id<MTLCommandBuffer> cb,
                           id<MTLComputePipelineState> pso_a,
                           id<MTLComputePipelineState> pso_b,
                           id<MTLBuffer> output,
                           long first, long count, int alternate, int split)
{
    id<MTLComputeCommandEncoder> enc = nil;
    for (long j = 0; j < count; ++j) {
        if (!enc || split) enc = [cb computeCommandEncoder];
        int use_b = alternate && ((first + j) & 1);
        [enc setComputePipelineState:(use_b ? pso_b : pso_a)];
        [enc setBuffer:output offset:0 atIndex:0];
        uint32_t tag = 0xa0000000u | ((uint32_t)(first + j) & 0xffffu);
        [enc setBytes:&tag length:sizeof(tag) atIndex:1];
        [enc dispatchThreads:MTLSizeMake(64, 1, 1)
          threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
        if (split) { [enc endEncoding]; enc = nil; }
    }
    if (enc) [enc endEncoding];
}

static MTLRenderPassDescriptor *make_pass(id<MTLTexture> target, int clear)
{
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture = target;
    rp.colorAttachments[0].loadAction = clear ? MTLLoadActionClear : MTLLoadActionLoad;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(0.0625, 0.125, 0.25, 1.0);
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    return rp;
}

static void encode_draws(id<MTLCommandBuffer> cb,
                         id<MTLRenderPipelineState> pso_a,
                         id<MTLRenderPipelineState> pso_b,
                         id<MTLBuffer> vertices,
                         id<MTLTexture> target,
                         long first, long count, int alternate, int split,
                         long width, long height, int *pass_started)
{
    id<MTLRenderCommandEncoder> enc = nil;
    for (long j = 0; j < count; ++j) {
        if (!enc || split) {
            MTLRenderPassDescriptor *rp = make_pass(target, !*pass_started);
            enc = [cb renderCommandEncoderWithDescriptor:rp];
            *pass_started = 1;
        }
        long sequence = first + j;
        int use_b = alternate && (sequence & 1);
        [enc setRenderPipelineState:(use_b ? pso_b : pso_a)];
        [enc setVertexBuffer:vertices offset:0 atIndex:0];
        float color[4] = {
            (float)((sequence & 7) + 1) / 8.0f,
            (float)(((sequence + 2) & 7) + 1) / 8.0f,
            (float)(((sequence + 4) & 7) + 1) / 8.0f,
            1.0f,
        };
        [enc setFragmentBytes:color length:sizeof(color) atIndex:0];
        double inset = (alternate && (sequence & 1)) ? 1.0 : 0.0;
        MTLViewport vp = { inset, inset, width - inset, height - inset, 0.0, 1.0 };
        [enc setViewport:vp];
        NSUInteger vertex_count = (sequence & 1) ? 6 : 3;
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0
                vertexCount:vertex_count instanceCount:1];
        if (split) { [enc endEncoding]; enc = nil; }
    }
    if (enc) [enc endEncoding];
}

static int wait_and_report(id<MTLCommandBuffer> cb, const char *name)
{
    [cb waitUntilCompleted];
    printf("COMPLETE %s status=%ld error=%s\n", name, (long)cb.status,
           cb.error ? [[cb.error localizedDescription] UTF8String] : "NONE");
    return cb.status == MTLCommandBufferStatusCompleted;
}

static void request_dump(useconds_t wait_us)
{
    fflush(stdout);
    kill(getpid(), SIGUSR1);
    usleep(wait_us);
}

int main(int argc, char **argv)
{
    @autoreleasepool {
        Config cfg = {
            .mode = MODE_COMPUTE, .mode_name = "compute", .count = 1,
            .submits = 1, .pad = 0, .pad_bytes = 4096, .width = 64,
            .height = 64, .alternate = 0, .dump_each = 0,
            .dump_final = 0,
            .dump_wait_us = 3000000,
        };
        for (int i = 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--mode") && i + 1 < argc) {
                cfg.mode_name = argv[++i];
                if (!parse_mode(cfg.mode_name, &cfg.mode)) { usage(argv[0]); return 2; }
            } else if (!strcmp(argv[i], "--count") && i + 1 < argc)
                cfg.count = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--submits") && i + 1 < argc)
                cfg.submits = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--pad") && i + 1 < argc)
                cfg.pad = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--pad-bytes") && i + 1 < argc)
                cfg.pad_bytes = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--w") && i + 1 < argc)
                cfg.width = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--h") && i + 1 < argc)
                cfg.height = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--dump-wait-us") && i + 1 < argc)
                cfg.dump_wait_us = (useconds_t)strtoul(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--alternate")) cfg.alternate = 1;
            else if (!strcmp(argv[i], "--dump")) cfg.dump_final = 1;
            else if (!strcmp(argv[i], "--dump-each")) cfg.dump_each = 1;
            else { usage(argv[0]); return 2; }
        }
        if (cfg.count < 1 || cfg.submits < 1 || cfg.pad < 0 ||
            cfg.pad_bytes < 1 || cfg.width < 2 || cfg.height < 2) {
            fprintf(stderr, "invalid non-positive configuration\n"); return 2;
        }

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { fprintf(stderr, "no Metal device\n"); return 1; }
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("CONFIG mode=%s count=%ld submits=%ld alternate=%d pad=%ld "
               "pad_bytes=%ld size=%ldx%ld dump_final=%d dump_each=%d dump_wait_us=%u\n",
               cfg.mode_name, cfg.count, cfg.submits, cfg.alternate, cfg.pad,
               cfg.pad_bytes, cfg.width, cfg.height, cfg.dump_final, cfg.dump_each,
               (unsigned)cfg.dump_wait_us);

        NSMutableArray *keep = [NSMutableArray array];
        for (long i = 0; i < cfg.pad; ++i) {
            id<MTLBuffer> b = [dev newBufferWithLength:(NSUInteger)cfg.pad_bytes
                                               options:MTLResourceStorageModeShared];
            if (!b) { fprintf(stderr, "padding allocation failed at %ld\n", i); return 1; }
            memset(b.contents, (int)(0x40 + (i & 0x3f)), (size_t)cfg.pad_bytes);
            [keep addObject:b];
            if (i == 0 || i == cfg.pad - 1) {
                char name[32]; snprintf(name, sizeof(name), "padding[%ld]", i);
                print_va(name, b.gpuAddress);
            }
        }

        NSError *err = nil;
        id<MTLComputePipelineState> cp_a = make_compute_pso(dev, @"kernel_a", &err);
        id<MTLComputePipelineState> cp_b = make_compute_pso(dev, @"kernel_b", &err);
        id<MTLRenderPipelineState> rp_a = make_render_pso(dev, @"fragment_a", &err);
        id<MTLRenderPipelineState> rp_b = make_render_pso(dev, @"fragment_b", &err);
        if (!cp_a || !cp_b || !rp_a || !rp_b) {
            fprintf(stderr, "pipeline creation failed: %s\n",
                    err ? [[err localizedDescription] UTF8String] : "unknown");
            return 1;
        }

        id<MTLBuffer> compute_out = [dev newBufferWithLength:64 * sizeof(uint32_t)
                                                     options:MTLResourceStorageModeShared];
        id<MTLBuffer> vertices = [dev newBufferWithLength:3 * 2 * sizeof(float)
                                                  options:MTLResourceStorageModeShared];
        float positions[6] = { -1.0f, -1.0f, 3.0f, -1.0f, -1.0f, 3.0f };
        memcpy(vertices.contents, positions, sizeof(positions));
        NSUInteger row_bytes = (NSUInteger)((cfg.width * 4 + 255) & ~255L);
        id<MTLBuffer> render_out = [dev newBufferWithLength:row_bytes * (NSUInteger)cfg.height
                                                   options:MTLResourceStorageModeShared];
        MTLTextureDescriptor *td = [MTLTextureDescriptor
            texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
            width:(NSUInteger)cfg.width height:(NSUInteger)cfg.height mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> target = [render_out newTextureWithDescriptor:td offset:0
                                                        bytesPerRow:row_bytes];
        if (!target) { fprintf(stderr, "buffer-backed render target rejected\n"); return 1; }
        print_va("compute_out", compute_out.gpuAddress);
        print_va("vertices", vertices.gpuAddress);
        print_va("render_out", render_out.gpuAddress);

        id<MTLCommandQueue> q0 = [dev newCommandQueue];
        id<MTLCommandQueue> q1 = [dev newCommandQueue];
        if (!q0 || !q1) { fprintf(stderr, "queue creation failed\n"); return 1; }

        int success = 1;
        for (long submit = 0; submit < cfg.submits; ++submit) {
            printf("SUBMIT %ld begin\n", submit);
            long base = submit * cfg.count;
            if (cfg.mode == MODE_TWO_QUEUES) {
                id<MTLCommandBuffer> cbc = [q0 commandBuffer];
                id<MTLCommandBuffer> cbr = [q1 commandBuffer];
                int pass_started = 0;
                encode_compute(cbc, cp_a, cp_b, compute_out, base, cfg.count,
                               cfg.alternate, 0);
                encode_draws(cbr, rp_a, rp_b, vertices, target, base, cfg.count,
                             cfg.alternate, 0, cfg.width, cfg.height, &pass_started);
                [cbc commit]; [cbr commit];
                success &= wait_and_report(cbc, "queue0-compute");
                success &= wait_and_report(cbr, "queue1-render");
            } else {
                id<MTLCommandBuffer> cb = [q0 commandBuffer];
                int pass_started = 0;
                switch (cfg.mode) {
                case MODE_COMPUTE:
                    encode_compute(cb, cp_a, cp_b, compute_out, base, cfg.count,
                                   cfg.alternate, 0); break;
                case MODE_COMPUTE_SPLIT:
                    encode_compute(cb, cp_a, cp_b, compute_out, base, cfg.count,
                                   cfg.alternate, 1); break;
                case MODE_RENDER:
                    encode_draws(cb, rp_a, rp_b, vertices, target, base, cfg.count,
                                 cfg.alternate, 0, cfg.width, cfg.height, &pass_started); break;
                case MODE_RENDER_SPLIT:
                    encode_draws(cb, rp_a, rp_b, vertices, target, base, cfg.count,
                                 cfg.alternate, 1, cfg.width, cfg.height, &pass_started); break;
                case MODE_COMPUTE_RENDER:
                    for (long j = 0; j < cfg.count; ++j) {
                        encode_compute(cb, cp_a, cp_b, compute_out, base + j, 1,
                                       cfg.alternate, 1);
                        encode_draws(cb, rp_a, rp_b, vertices, target, base + j, 1,
                                     cfg.alternate, 1, cfg.width, cfg.height, &pass_started);
                    }
                    break;
                case MODE_RENDER_COMPUTE:
                    for (long j = 0; j < cfg.count; ++j) {
                        encode_draws(cb, rp_a, rp_b, vertices, target, base + j, 1,
                                     cfg.alternate, 1, cfg.width, cfg.height, &pass_started);
                        encode_compute(cb, cp_a, cp_b, compute_out, base + j, 1,
                                       cfg.alternate, 1);
                    }
                    break;
                default: break;
                }
                [cb commit];
                success &= wait_and_report(cb, "queue0");
            }
            uint32_t *words = (uint32_t *)compute_out.contents;
            uint8_t *pixel = (uint8_t *)render_out.contents;
            printf("READBACK submit=%ld compute=%08x,%08x pixel_bgra=%02x%02x%02x%02x\n",
                   submit, words[0], words[1], pixel[0], pixel[1], pixel[2], pixel[3]);
            if (cfg.dump_each || (cfg.dump_final && submit == cfg.submits - 1))
                request_dump(cfg.dump_wait_us);
        }
        printf("VERDICT completed=%d\n", success);
        return success ? 0 : 1;
    }
}
