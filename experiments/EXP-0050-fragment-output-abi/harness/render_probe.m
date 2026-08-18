/*
 * EXP-0050 clean-room fragment-output probe.
 *
 * This program compiles only kernels/output_matrix.metal through public Metal,
 * serializes an archive containing that selected authored VS/FS pipeline, then
 * forces pipeline creation from the archive. It observes only authored render
 * targets and a user counter. It captures no command/state BO and inspects no
 * Apple or auxiliary program bytes.
 */
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

typedef struct {
    const char *name;
    const char *fragment;
    unsigned color_mask;
    BOOL depth;
    NSUInteger samples;
    BOOL counter;
} Case;

static const Case cases[] = {
    {"c0",                    "f_c0",                    0x1, NO,  1, NO},
    {"c1-only",               "f_c1_only",               0x2, NO,  1, NO},
    {"c2-only",               "f_c2_only",               0x4, NO,  1, NO},
    {"c0-c2-decl02",          "f_c0_c2_decl02",          0x5, NO,  1, NO},
    {"c0-c2-decl20",          "f_c0_c2_decl20",          0x5, NO,  1, NO},
    {"mrt3-decl012",          "f_mrt3_decl012",          0x7, NO,  1, NO},
    {"mrt3-decl210",          "f_mrt3_decl210",          0x7, NO,  1, NO},
    {"mrt3-swap12",           "f_mrt3_swap12",           0x7, NO,  1, NO},
    {"color-depth",           "f_color_depth",           0x1, YES, 1, NO},
    {"depth-color-decl",      "f_depth_color_decl",      0x1, YES, 1, NO},
    {"depth-only",            "f_depth_only",            0x0, YES, 1, NO},
    {"color-fixed-depth",     "f_color_fixed_depth",     0x1, YES, 1, NO},
    {"mask-f",                "f_mask_f",                0x1, NO,  4, NO},
    {"mask-5",                "f_mask_5",                0x1, NO,  4, NO},
    {"mask-a",                "f_mask_a",                0x1, NO,  4, NO},
    {"mask-0",                "f_mask_0",                0x1, NO,  4, NO},
    {"mask-5-declfirst",      "f_mask_5_declfirst",      0x1, NO,  4, NO},
    {"discard-half",          "f_discard_half",          0x1, NO,  1, NO},
    {"atomic-all",            "f_atomic_all",            0x1, NO,  1, YES},
    {"atomic-before-discard", "f_atomic_before_discard", 0x1, NO,  1, YES},
    {"atomic-after-discard",  "f_atomic_after_discard",  0x1, NO,  1, YES},
};

static void fail(const char *status, const char *where, NSError *err) {
    printf("STATUS %s\n", status);
    if (err) printf("ERROR %s: %s\n", where, [[err localizedDescription] UTF8String]);
    else printf("ERROR %s\n", where);
    fflush(stdout);
    exit(1);
}

static const Case *find_case(const char *name) {
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i)
        if (!strcmp(cases[i].name, name)) return &cases[i];
    return NULL;
}

static MTLRenderPipelineDescriptor *pipeline_descriptor(id<MTLFunction> vfn,
                                                        id<MTLFunction> ffn,
                                                        const Case *c) {
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = vfn;
    pd.fragmentFunction = ffn;
    pd.rasterSampleCount = c->samples;
    for (NSUInteger i = 0; i < 3; ++i)
        if (c->color_mask & (1u << i))
            pd.colorAttachments[i].pixelFormat = MTLPixelFormatRGBA8Unorm;
    if (c->depth) pd.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;
    return pd;
}

static void print_hex(const char *label, const uint8_t *bytes, size_t size) {
    printf("%s ", label);
    for (size_t i = 0; i < size; ++i) printf("%02x", bytes[i]);
    printf("\n");
}

enum { OPT_ARCHIVE_OUT = 128, OPT_ARCHIVE_IN };
static const struct option long_opts[] = {
    {"case",        required_argument, NULL, 'c'},
    {"source",      required_argument, NULL, 's'},
    {"archive-out", required_argument, NULL, OPT_ARCHIVE_OUT},
    {"archive-in",  required_argument, NULL, OPT_ARCHIVE_IN},
    {NULL, 0, NULL, 0},
};

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *case_name = NULL, *source_path = NULL;
        const char *archive_out = NULL, *archive_in = NULL;
        int opt;
        while ((opt = getopt_long(argc, argv, "c:s:", long_opts, NULL)) > 0) {
            switch (opt) {
                case 'c': case_name = optarg; break;
                case 's': source_path = optarg; break;
                case OPT_ARCHIVE_OUT: archive_out = optarg; break;
                case OPT_ARCHIVE_IN: archive_in = optarg; break;
                default: return 2;
            }
        }
        if (!case_name || !source_path || (!!archive_out == !!archive_in)) {
            fprintf(stderr, "need --case --source and exactly one archive option\n");
            return 2;
        }
        const Case *c = find_case(case_name);
        if (!c) { fprintf(stderr, "unknown case %s\n", case_name); return 2; }

        NSError *err = nil;
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) fail("NO_DEVICE", "MTLCreateSystemDefaultDevice", nil);
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("CASE %s fragment=%s colors=0x%x depth=%u samples=%lu counter=%u\n",
               c->name, c->fragment, c->color_mask, c->depth,
               (unsigned long)c->samples, c->counter);

        NSString *source = [NSString stringWithContentsOfFile:
            [NSString stringWithUTF8String:source_path]
            encoding:NSUTF8StringEncoding error:&err];
        if (!source) fail("SOURCE_FAIL", "read authored MSL", err);
        MTLCompileOptions *options = [MTLCompileOptions new];
        options.fastMathEnabled = NO;
        id<MTLLibrary> lib = [dev newLibraryWithSource:source options:options error:&err];
        if (!lib) fail("COMPILE_FAIL", "newLibraryWithSource", err);
        id<MTLFunction> vfn = [lib newFunctionWithName:@"v_main"];
        id<MTLFunction> ffn = [lib newFunctionWithName:
            [NSString stringWithUTF8String:c->fragment]];
        if (!vfn || !ffn) fail("FUNCTION_FAIL", "newFunctionWithName", nil);

        MTLRenderPipelineDescriptor *pd = pipeline_descriptor(vfn, ffn, c);
        NSURL *archive_url = nil;
        if (archive_out) {
            id<MTLRenderPipelineState> compile_pso =
                [dev newRenderPipelineStateWithDescriptor:pd error:&err];
            if (!compile_pso) fail("PIPELINE_COMPILE_FAIL", "baseline pipeline", err);
            (void)compile_pso;
            MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
            id<MTLBinaryArchive> writable = [dev newBinaryArchiveWithDescriptor:ad error:&err];
            if (!writable) fail("ARCHIVE_FAIL", "create writable archive", err);
            if (![writable addRenderPipelineFunctionsWithDescriptor:pd error:&err])
                fail("ARCHIVE_FAIL", "add authored pipeline", err);
            archive_url = [NSURL fileURLWithPath:[NSString stringWithUTF8String:archive_out]];
            if (![writable serializeToURL:archive_url error:&err])
                fail("ARCHIVE_FAIL", "serialize authored archive", err);
        } else {
            archive_url = [NSURL fileURLWithPath:[NSString stringWithUTF8String:archive_in]];
        }

        MTLBinaryArchiveDescriptor *load_ad = [MTLBinaryArchiveDescriptor new];
        load_ad.url = archive_url;
        id<MTLBinaryArchive> archive = [dev newBinaryArchiveWithDescriptor:load_ad error:&err];
        if (!archive) fail("ARCHIVE_FAIL", "load authored archive", err);
        pd.binaryArchives = @[archive];
        id<MTLRenderPipelineState> pso =
            [dev newRenderPipelineStateWithDescriptor:pd
                                              options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                           reflection:nil error:&err];
        if (!pso) fail("PIPELINE_MISS", "forced authored archive pipeline", err);
        printf("PIPELINE_SOURCE archive\n");

        const NSUInteger W = 4, H = 1;
        const double clear[3][4] = {
            {1.0/255.0, 2.0/255.0, 3.0/255.0, 4.0/255.0},
            {5.0/255.0, 6.0/255.0, 7.0/255.0, 8.0/255.0},
            {9.0/255.0, 10.0/255.0, 11.0/255.0, 12.0/255.0},
        };
        id<MTLTexture> render_color[3] = {nil, nil, nil};
        id<MTLTexture> read_color[3] = {nil, nil, nil};
        for (NSUInteger i = 0; i < 3; ++i) {
            if (!(c->color_mask & (1u << i))) continue;
            if (c->samples == 1) {
                MTLTextureDescriptor *td = [MTLTextureDescriptor
                    texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm
                    width:W height:H mipmapped:NO];
                td.usage = MTLTextureUsageRenderTarget;
                td.storageMode = MTLStorageModeShared;
                render_color[i] = [dev newTextureWithDescriptor:td];
                read_color[i] = render_color[i];
            } else {
                MTLTextureDescriptor *ms = [MTLTextureDescriptor new];
                ms.textureType = MTLTextureType2DMultisample;
                ms.pixelFormat = MTLPixelFormatRGBA8Unorm;
                ms.width = W; ms.height = H; ms.depth = 1;
                ms.mipmapLevelCount = 1; ms.arrayLength = 1;
                ms.sampleCount = c->samples;
                ms.usage = MTLTextureUsageRenderTarget;
                ms.storageMode = MTLStorageModePrivate;
                render_color[i] = [dev newTextureWithDescriptor:ms];
                MTLTextureDescriptor *rs = [MTLTextureDescriptor
                    texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm
                    width:W height:H mipmapped:NO];
                rs.usage = MTLTextureUsageRenderTarget;
                rs.storageMode = MTLStorageModeShared;
                read_color[i] = [dev newTextureWithDescriptor:rs];
            }
            if (!render_color[i] || !read_color[i])
                fail("RESOURCE_FAIL", "color texture", nil);
        }

        id<MTLTexture> depth = nil;
        if (c->depth) {
            MTLTextureDescriptor *dd = [MTLTextureDescriptor
                texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float
                width:W height:H mipmapped:NO];
            dd.usage = MTLTextureUsageRenderTarget;
            dd.storageMode = MTLStorageModeShared;
            depth = [dev newTextureWithDescriptor:dd];
            if (!depth) fail("RESOURCE_FAIL", "depth texture", nil);
        }
        id<MTLBuffer> counter = [dev newBufferWithLength:0x4000
                                                 options:MTLResourceStorageModeShared];
        if (!counter) fail("RESOURCE_FAIL", "counter buffer", nil);
        memset([counter contents], 0, 0x4000);

        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
        for (NSUInteger i = 0; i < 3; ++i) {
            if (!(c->color_mask & (1u << i))) continue;
            rp.colorAttachments[i].texture = render_color[i];
            rp.colorAttachments[i].loadAction = MTLLoadActionClear;
            rp.colorAttachments[i].clearColor = MTLClearColorMake(
                clear[i][0], clear[i][1], clear[i][2], clear[i][3]);
            if (c->samples == 1) {
                rp.colorAttachments[i].storeAction = MTLStoreActionStore;
            } else {
                rp.colorAttachments[i].resolveTexture = read_color[i];
                rp.colorAttachments[i].storeAction = MTLStoreActionMultisampleResolve;
            }
        }
        if (c->depth) {
            rp.depthAttachment.texture = depth;
            rp.depthAttachment.loadAction = MTLLoadActionClear;
            rp.depthAttachment.clearDepth = 0.875;
            rp.depthAttachment.storeAction = MTLStoreActionStore;
        }

        id<MTLDepthStencilState> dss = nil;
        if (c->depth) {
            MTLDepthStencilDescriptor *dsd = [MTLDepthStencilDescriptor new];
            dsd.depthCompareFunction = MTLCompareFunctionAlways;
            dsd.depthWriteEnabled = YES;
            dss = [dev newDepthStencilStateWithDescriptor:dsd];
        }

        id<MTLCommandQueue> queue = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [queue commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        if (dss) [enc setDepthStencilState:dss];
        if (c->counter) [enc setFragmentBuffer:counter offset:0 atIndex:0];
        MTLViewport viewport = {0.0, 0.0, W, H, 0.0, 1.0};
        [enc setViewport:viewport];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] != MTLCommandBufferStatusCompleted || [cb error])
            fail("CMDBUF_ERROR", "render", [cb error]);

        uint8_t pixels[W * H * 4];
        for (NSUInteger i = 0; i < 3; ++i) {
            char label[32]; snprintf(label, sizeof(label), "COLOR%lu_HEX", (unsigned long)i);
            if (!(c->color_mask & (1u << i))) {
                printf("%s absent\n", label);
                continue;
            }
            memset(pixels, 0, sizeof(pixels));
            [read_color[i] getBytes:pixels bytesPerRow:W * 4
                         fromRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0];
            print_hex(label, pixels, sizeof(pixels));
        }
        if (c->depth) {
            uint8_t depth_bytes[W * H * 4];
            [depth getBytes:depth_bytes bytesPerRow:W * 4
                 fromRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0];
            print_hex("DEPTH_HEX", depth_bytes, sizeof(depth_bytes));
            float values[W * H]; memcpy(values, depth_bytes, sizeof(values));
            printf("DEPTH_VALUES %.9g %.9g %.9g %.9g\n",
                   values[0], values[1], values[2], values[3]);
        } else {
            printf("DEPTH_HEX absent\n");
        }
        printf("COUNTER %u\n", *(uint32_t *)[counter contents]);
        printf("STATUS OK\n");
        fflush(stdout);
        return 0;
    }
}
