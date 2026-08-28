// cmdprobe.m -- EXP-0110 authored Metal workloads for M4 command-stream
// relocation and link/chain-grammar probing.
//
// CLEAN ROOM: public Metal API + OWN-SHADER only. Every shader source
// executed by this program is authored below. The program asks the
// (unmodified, read-only) tools/iotrace DATA-TRACE interposer to snapshot
// boundary allocation metadata and BO contents after completed command
// buffers. It never reads, inspects, or invokes tools on any Apple binary.
//
// This intentionally repeats the EXP-0043/EXP-0049 authored dispatch/draw
// shape verbatim (grid 64x1x1 / threadgroup 32x1x1 compute; alternating
// 3/6-vertex non-indexed triangle draws) so the already-established
// structural signatures and 732/733 CDM / 328/329 VDM boundaries remain
// directly comparable. New knobs vs framing.m: --prior-queues (creates and
// USES N throwaway queues before the probe queue, to test queue-relative
// addressing) and larger --pad-bytes/--pad-count ranges (to test whether
// client heap growth relocates command-segment continuations).
//
// Build:
//   xcrun clang -fobjc-arc -Wno-deprecated-declarations -o cmdprobe cmdprobe.m \
//       -framework Metal -framework Foundation

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef struct {
    const char *mode_name; // "cdm" or "vdm"
    long count;
    long prior_queues;
    long pad_count;
    long pad_bytes;
    long width;
    long height;
    useconds_t dump_wait_us;
    int depth_test;   // vdm only: enable a depth attachment + less/write DS state
    int stencil_test; // vdm only: enable a stencil attachment + always/replace DS state
    int blend;        // vdm only: enable source-over alpha blending on color(0)
    int cull;         // vdm only: 0=none 1=front 2=back
    int prior_draws;  // prior queues issue a tiny DRAW instead of a compute dispatch
} Config;

static void print_va(const char *name, uint64_t va)
{
    printf("VA %-16s = 0x%016llx\n", name, (unsigned long long)va);
}

static void usage(const char *argv0)
{
    fprintf(stderr,
        "usage: %s --mode cdm|vdm [--count N] [--prior-queues N] "
        "[--pad-count N] [--pad-bytes N] [--w N] [--h N] [--dump-wait-us N] "
        "[--depth-test] [--stencil-test] [--blend] [--cull none|front|back]\n",
        argv0);
}

static id<MTLComputePipelineState> make_compute_pso(id<MTLDevice> dev, NSError **err)
{
    NSString *source =
        @"#include <metal_stdlib>\n"
         "using namespace metal;\n"
         "kernel void kernel_a(device uint *out [[buffer(0)]],\n"
         "                     constant uint &tag [[buffer(1)]],\n"
         "                     uint i [[thread_position_in_grid]]) {\n"
         "  out[i] = tag + i;\n"
         "}\n";
    id<MTLLibrary> lib = [dev newLibraryWithSource:source options:nil error:err];
    if (!lib) return nil;
    id<MTLFunction> fn = [lib newFunctionWithName:@"kernel_a"];
    if (!fn) return nil;
    return [dev newComputePipelineStateWithFunction:fn error:err];
}

static id<MTLRenderPipelineState> make_render_pso(id<MTLDevice> dev, const Config *cfg, NSError **err)
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
         "}\n";
    id<MTLLibrary> lib = [dev newLibraryWithSource:source options:nil error:err];
    if (!lib) return nil;
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = [lib newFunctionWithName:@"vertex_main"];
    pd.fragmentFunction = [lib newFunctionWithName:@"fragment_a"];
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
    if (cfg->blend) {
        pd.colorAttachments[0].blendingEnabled = YES;
        pd.colorAttachments[0].rgbBlendOperation = MTLBlendOperationAdd;
        pd.colorAttachments[0].alphaBlendOperation = MTLBlendOperationAdd;
        pd.colorAttachments[0].sourceRGBBlendFactor = MTLBlendFactorSourceAlpha;
        pd.colorAttachments[0].destinationRGBBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
        pd.colorAttachments[0].sourceAlphaBlendFactor = MTLBlendFactorOne;
        pd.colorAttachments[0].destinationAlphaBlendFactor = MTLBlendFactorZero;
    }
    if (cfg->depth_test) pd.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;
    if (cfg->stencil_test) pd.stencilAttachmentPixelFormat = MTLPixelFormatStencil8;
    return [dev newRenderPipelineStateWithDescriptor:pd error:err];
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
            .mode_name = NULL, .count = 2, .prior_queues = 0,
            .pad_count = 0, .pad_bytes = 0, .width = 64, .height = 64,
            .dump_wait_us = 3000000,
            .depth_test = 0, .stencil_test = 0, .blend = 0, .cull = 0,
            .prior_draws = 0,
        };
        for (int i = 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--mode") && i + 1 < argc) cfg.mode_name = argv[++i];
            else if (!strcmp(argv[i], "--count") && i + 1 < argc) cfg.count = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--prior-queues") && i + 1 < argc) cfg.prior_queues = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--pad-count") && i + 1 < argc) cfg.pad_count = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--pad-bytes") && i + 1 < argc) cfg.pad_bytes = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--w") && i + 1 < argc) cfg.width = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--h") && i + 1 < argc) cfg.height = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--dump-wait-us") && i + 1 < argc) cfg.dump_wait_us = (useconds_t)strtoul(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--depth-test")) cfg.depth_test = 1;
            else if (!strcmp(argv[i], "--stencil-test")) cfg.stencil_test = 1;
            else if (!strcmp(argv[i], "--blend")) cfg.blend = 1;
            else if (!strcmp(argv[i], "--prior-draws")) cfg.prior_draws = 1;
            else if (!strcmp(argv[i], "--cull") && i + 1 < argc) {
                const char *c = argv[++i];
                if (!strcmp(c, "none")) cfg.cull = 0;
                else if (!strcmp(c, "front")) cfg.cull = 1;
                else if (!strcmp(c, "back")) cfg.cull = 2;
                else { usage(argv[0]); return 2; }
            }
            else { usage(argv[0]); return 2; }
        }
        if (!cfg.mode_name || (strcmp(cfg.mode_name, "cdm") && strcmp(cfg.mode_name, "vdm"))) {
            usage(argv[0]); return 2;
        }
        if (cfg.count < 1 || cfg.prior_queues < 0 || cfg.pad_count < 0 || cfg.pad_bytes < 0) {
            fprintf(stderr, "invalid negative configuration\n"); return 2;
        }

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { fprintf(stderr, "no Metal device\n"); return 1; }
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("CONFIG mode=%s count=%ld prior_queues=%ld pad_count=%ld pad_bytes=%ld size=%ldx%ld dump_wait_us=%u\n",
               cfg.mode_name, cfg.count, cfg.prior_queues, cfg.pad_count,
               cfg.pad_bytes, cfg.width, cfg.height, (unsigned)cfg.dump_wait_us);

        NSError *err = nil;
        id<MTLComputePipelineState> cp = make_compute_pso(dev, &err);
        if (!cp) { fprintf(stderr, "compute pipeline failed: %s\n", err ? [[err localizedDescription] UTF8String] : "?"); return 1; }

        // --- prior queues: create + actually USE each one before the probe
        // queue exists, so any per-queue firmware-context allocation happens
        // eagerly (not lazily deferred to first submit on the probe queue).
        // --prior-draws makes each prior queue issue a tiny DRAW (VDM) rather
        // than a compute dispatch, to test whether the VDM/FF-state low-VA
        // region is per-queue or process/global-shared.
        id<MTLBuffer> prior_out = [dev newBufferWithLength:64 * sizeof(uint32_t)
                                                    options:MTLResourceStorageModeShared];
        id<MTLRenderPipelineState> prior_rp = nil;
        id<MTLBuffer> prior_vtx = nil;
        id<MTLTexture> prior_target = nil;
        if (cfg.prior_draws) {
            Config tiny_cfg = cfg; tiny_cfg.blend = 0; tiny_cfg.depth_test = 0; tiny_cfg.stencil_test = 0;
            prior_rp = make_render_pso(dev, &tiny_cfg, &err);
            if (!prior_rp) { fprintf(stderr, "prior render pipeline failed\n"); return 1; }
            prior_vtx = [dev newBufferWithLength:3 * 2 * sizeof(float) options:MTLResourceStorageModeShared];
            float pos[6] = { -1.0f, -1.0f, 3.0f, -1.0f, -1.0f, 3.0f };
            memcpy(prior_vtx.contents, pos, sizeof(pos));
            MTLTextureDescriptor *ptd = [MTLTextureDescriptor
                texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:8 height:8 mipmapped:NO];
            ptd.usage = MTLTextureUsageRenderTarget;
            ptd.storageMode = MTLStorageModePrivate;
            prior_target = [dev newTextureWithDescriptor:ptd];
        }
        for (long qi = 0; qi < cfg.prior_queues; ++qi) {
            id<MTLCommandQueue> pq = [dev newCommandQueue];
            if (!pq) { fprintf(stderr, "prior queue %ld failed\n", qi); return 1; }
            id<MTLCommandBuffer> cb = [pq commandBuffer];
            if (cfg.prior_draws) {
                MTLRenderPassDescriptor *prpd = [MTLRenderPassDescriptor new];
                prpd.colorAttachments[0].texture = prior_target;
                prpd.colorAttachments[0].loadAction = MTLLoadActionClear;
                prpd.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
                prpd.colorAttachments[0].storeAction = MTLStoreActionDontCare;
                id<MTLRenderCommandEncoder> renc = [cb renderCommandEncoderWithDescriptor:prpd];
                [renc setRenderPipelineState:prior_rp];
                [renc setVertexBuffer:prior_vtx offset:0 atIndex:0];
                float color[4] = { 1, 1, 1, 1 };
                [renc setFragmentBytes:color length:sizeof(color) atIndex:0];
                [renc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1];
                [renc endEncoding];
            } else {
                id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
                [enc setComputePipelineState:cp];
                [enc setBuffer:prior_out offset:0 atIndex:0];
                uint32_t tag = 0xd0000000u | (uint32_t)qi;
                [enc setBytes:&tag length:sizeof(tag) atIndex:1];
                [enc dispatchThreads:MTLSizeMake(64, 1, 1) threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
                [enc endEncoding];
            }
            [cb commit];
            if (!wait_and_report(cb, "prior-queue")) { fprintf(stderr, "prior queue %ld failed to complete\n", qi); return 1; }
        }

        // --- padding: authored client allocations BEFORE the probe's own
        // resources, to test whether client heap growth relocates command
        // segment continuations.
        NSMutableArray *keep = [NSMutableArray array];
        for (long i = 0; i < cfg.pad_count; ++i) {
            id<MTLBuffer> b = [dev newBufferWithLength:(NSUInteger)cfg.pad_bytes
                                               options:MTLResourceStorageModeShared];
            if (!b) { fprintf(stderr, "padding allocation failed at %ld\n", i); return 1; }
            memset(b.contents, (int)(0x40 + (i & 0x3f)), (size_t)cfg.pad_bytes);
            [keep addObject:b];
        }
        if (cfg.pad_count > 0) {
            print_va("padding[first]", ((id<MTLBuffer>)keep[0]).gpuAddress);
            print_va("padding[last]", ((id<MTLBuffer>)keep[keep.count - 1]).gpuAddress);
        }

        id<MTLCommandQueue> probe_q = [dev newCommandQueue];
        if (!probe_q) { fprintf(stderr, "probe queue creation failed\n"); return 1; }

        if (!strcmp(cfg.mode_name, "cdm")) {
            id<MTLBuffer> compute_out = [dev newBufferWithLength:64 * sizeof(uint32_t)
                                                         options:MTLResourceStorageModeShared];
            print_va("compute_out", compute_out.gpuAddress);
            id<MTLCommandBuffer> cb = [probe_q commandBuffer];
            id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
            for (long j = 0; j < cfg.count; ++j) {
                [enc setComputePipelineState:cp];
                [enc setBuffer:compute_out offset:0 atIndex:0];
                uint32_t tag = 0xa0000000u | ((uint32_t)j & 0xffffu);
                [enc setBytes:&tag length:sizeof(tag) atIndex:1];
                [enc dispatchThreads:MTLSizeMake(64, 1, 1) threadsPerThreadgroup:MTLSizeMake(32, 1, 1)];
            }
            [enc endEncoding];
            [cb commit];
            int ok = wait_and_report(cb, "probe-cdm");
            uint32_t *words = (uint32_t *)compute_out.contents;
            printf("READBACK compute=%08x,%08x\n", words[0], words[1]);
            request_dump(cfg.dump_wait_us);
            printf("VERDICT completed=%d\n", ok);
            return ok ? 0 : 1;
        } else {
            id<MTLComputePipelineState> unused_cp = cp; (void)unused_cp;
            id<MTLRenderPipelineState> rp = make_render_pso(dev, &cfg, &err);
            if (!rp) { fprintf(stderr, "render pipeline failed: %s\n", err ? [[err localizedDescription] UTF8String] : "?"); return 1; }
            id<MTLBuffer> vertices = [dev newBufferWithLength:3 * 2 * sizeof(float)
                                                      options:MTLResourceStorageModeShared];
            float positions[6] = { -1.0f, -1.0f, 3.0f, -1.0f, -1.0f, 3.0f };
            memcpy(vertices.contents, positions, sizeof(positions));
            print_va("vertices", vertices.gpuAddress);
            NSUInteger row_bytes = (NSUInteger)((cfg.width * 4 + 255) & ~255L);
            id<MTLBuffer> render_out = [dev newBufferWithLength:row_bytes * (NSUInteger)cfg.height
                                                       options:MTLResourceStorageModeShared];
            MTLTextureDescriptor *td = [MTLTextureDescriptor
                texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                width:(NSUInteger)cfg.width height:(NSUInteger)cfg.height mipmapped:NO];
            td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
            td.storageMode = MTLStorageModeShared;
            id<MTLTexture> target = [render_out newTextureWithDescriptor:td offset:0 bytesPerRow:row_bytes];
            if (!target) { fprintf(stderr, "buffer-backed render target rejected\n"); return 1; }
            print_va("render_out", render_out.gpuAddress);

            id<MTLTexture> depth_tex = nil, stencil_tex = nil;
            if (cfg.depth_test) {
                MTLTextureDescriptor *dtd = [MTLTextureDescriptor
                    texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float
                    width:(NSUInteger)cfg.width height:(NSUInteger)cfg.height mipmapped:NO];
                dtd.usage = MTLTextureUsageRenderTarget;
                dtd.storageMode = MTLStorageModePrivate;
                depth_tex = [dev newTextureWithDescriptor:dtd];
            }
            if (cfg.stencil_test) {
                MTLTextureDescriptor *std_ = [MTLTextureDescriptor
                    texture2DDescriptorWithPixelFormat:MTLPixelFormatStencil8
                    width:(NSUInteger)cfg.width height:(NSUInteger)cfg.height mipmapped:NO];
                std_.usage = MTLTextureUsageRenderTarget;
                std_.storageMode = MTLStorageModePrivate;
                stencil_tex = [dev newTextureWithDescriptor:std_];
            }
            id<MTLDepthStencilState> ds = nil;
            if (cfg.depth_test || cfg.stencil_test) {
                MTLDepthStencilDescriptor *dsd = [MTLDepthStencilDescriptor new];
                if (cfg.depth_test) {
                    dsd.depthCompareFunction = MTLCompareFunctionLess;
                    dsd.depthWriteEnabled = YES;
                }
                if (cfg.stencil_test) {
                    MTLStencilDescriptor *sd = [MTLStencilDescriptor new];
                    sd.stencilCompareFunction = MTLCompareFunctionAlways;
                    sd.depthStencilPassOperation = MTLStencilOperationReplace;
                    sd.readMask = 0xff; sd.writeMask = 0xff;
                    dsd.frontFaceStencil = sd; dsd.backFaceStencil = sd;
                }
                ds = [dev newDepthStencilStateWithDescriptor:dsd];
            }

            MTLRenderPassDescriptor *rpd = [MTLRenderPassDescriptor new];
            rpd.colorAttachments[0].texture = target;
            rpd.colorAttachments[0].loadAction = MTLLoadActionClear;
            rpd.colorAttachments[0].clearColor = MTLClearColorMake(0.0625, 0.125, 0.25, 1.0);
            rpd.colorAttachments[0].storeAction = MTLStoreActionStore;
            if (depth_tex) {
                rpd.depthAttachment.texture = depth_tex;
                rpd.depthAttachment.loadAction = MTLLoadActionClear;
                rpd.depthAttachment.clearDepth = 1.0;
                rpd.depthAttachment.storeAction = MTLStoreActionDontCare;
            }
            if (stencil_tex) {
                rpd.stencilAttachment.texture = stencil_tex;
                rpd.stencilAttachment.loadAction = MTLLoadActionClear;
                rpd.stencilAttachment.clearStencil = 0;
                rpd.stencilAttachment.storeAction = MTLStoreActionDontCare;
            }

            id<MTLCommandBuffer> cb = [probe_q commandBuffer];
            id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rpd];
            if (cfg.cull == 1) [enc setCullMode:MTLCullModeFront];
            else if (cfg.cull == 2) [enc setCullMode:MTLCullModeBack];
            if (ds) [enc setDepthStencilState:ds];
            if (cfg.stencil_test) [enc setStencilReferenceValue:1];
            for (long j = 0; j < cfg.count; ++j) {
                [enc setRenderPipelineState:rp];
                [enc setVertexBuffer:vertices offset:0 atIndex:0];
                float color[4] = {
                    (float)((j & 7) + 1) / 8.0f,
                    (float)(((j + 2) & 7) + 1) / 8.0f,
                    (float)(((j + 4) & 7) + 1) / 8.0f,
                    1.0f,
                };
                [enc setFragmentBytes:color length:sizeof(color) atIndex:0];
                NSUInteger vertex_count = (j & 1) ? 6 : 3;
                [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0
                        vertexCount:vertex_count instanceCount:1];
            }
            [enc endEncoding];
            [cb commit];
            int ok = wait_and_report(cb, "probe-vdm");
            uint8_t *pixel = (uint8_t *)render_out.contents;
            printf("READBACK pixel_bgra=%02x%02x%02x%02x\n", pixel[0], pixel[1], pixel[2], pixel[3]);
            request_dump(cfg.dump_wait_us);
            printf("VERDICT completed=%d\n", ok);
            return ok ? 0 : 1;
        }
    }
}
