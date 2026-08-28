// SPDX-License-Identifier: MIT
// Own-source Metal workload that deliberately overflows the tiled vertex buffer.

#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <string.h>
#include <unistd.h>

enum {
    attachment_count = 8,
    default_width = 512,
    default_height = 512,
};

static FILE *open_console(void)
{
    FILE *console = fopen("/dev/console", "w");
    if (console != NULL)
        setvbuf(console, NULL, _IONBF, 0);
    return console;
}

static const char *error_string(NSError *error)
{
    if (error == nil)
        return "none";
    return [[error localizedDescription] UTF8String];
}

static BOOL parse_dimension(const char *text, NSUInteger *value)
{
    char *end = NULL;
    errno = 0;
    unsigned long parsed = strtoul(text, &end, 0);
    if (errno != 0 || end == text || *end != '\0' || parsed == 0 ||
        parsed > 4096)
        return NO;
    *value = parsed;
    return YES;
}

static BOOL parse_triangle_count(const char *text, NSUInteger *value)
{
    char *end = NULL;
    errno = 0;
    unsigned long long parsed = strtoull(text, &end, 0);
    if (errno != 0 || end == text || *end != '\0' || parsed == 0 ||
        parsed > UINT32_MAX / 3)
        return NO;
    *value = (NSUInteger)parsed;
    return YES;
}

static BOOL parse_submission_count(const char *text, NSUInteger *value)
{
    char *end = NULL;
    errno = 0;
    unsigned long long parsed = strtoull(text, &end, 0);
    if (errno != 0 || end == text || *end != '\0' || parsed == 0 ||
        parsed > NSUIntegerMax)
        return NO;
    *value = (NSUInteger)parsed;
    return YES;
}

static NSString *library_path(const char *argv0)
{
    NSString *executable = [NSString stringWithUTF8String:argv0];
    if (![executable isAbsolutePath]) {
        executable = [[[NSFileManager defaultManager] currentDirectoryPath]
            stringByAppendingPathComponent:executable];
    }
    executable = [executable stringByStandardizingPath];
    return [[executable stringByDeletingLastPathComponent]
        stringByAppendingPathComponent:@"g17ppartial.metallib"];
}

static uint8_t component_value(NSUInteger x, NSUInteger y,
                               NSUInteger attachment, NSUInteger component)
{
    NSUInteger value;
    switch (component) {
    case 0:
        value = x + attachment * 17;
        break;
    case 1:
        value = y + attachment * 29;
        break;
    default:
        value = (x ^ y) + attachment * 43;
        break;
    }
    return 1 + value % 253;
}

static void list_counters(id<MTLDevice> device)
{
    printf("G17P_PARTIAL_COUNTER_SETS=%lu\n",
           (unsigned long)[[device counterSets] count]);
    for (id<MTLCounterSet> set in [device counterSets]) {
        printf("G17P_PARTIAL_COUNTER_SET name=%s count=%lu\n",
               [[set name] UTF8String], (unsigned long)[[set counters] count]);
        for (id<MTLCounter> counter in [set counters])
            printf("G17P_PARTIAL_COUNTER name=%s\n",
                   [[counter name] UTF8String]);
    }
}

int main(int argc, const char **argv)
{
    @autoreleasepool {
        setvbuf(stdout, NULL, _IONBF, 0);
        setvbuf(stderr, NULL, _IONBF, 0);

        NSUInteger width = default_width;
        NSUInteger height = default_height;
        BOOL concentrated = argc >= 4 && strcmp(argv[3], "concentrated") == 0;
        BOOL overflow = argc >= 4 && strcmp(argv[3], "overflow") == 0;
        BOOL accumulate = argc >= 4 && strcmp(argv[3], "accumulate") == 0;
        BOOL indirect = argc >= 4 && strcmp(argv[3], "indirect") == 0;
        BOOL counter_only = argc == 2 && strcmp(argv[1], "--list-counters") == 0;
        if (!counter_only && argc > 1 && !parse_dimension(argv[1], &width)) {
            fprintf(stderr, "G17P_PARTIAL_ERROR width\n");
            return 1;
        }
        if (!counter_only && argc > 2 && !parse_dimension(argv[2], &height)) {
            fprintf(stderr, "G17P_PARTIAL_ERROR height\n");
            return 1;
        }
        if (!counter_only && argc > 6) {
            fprintf(stderr, "G17P_PARTIAL_ERROR arguments\n");
            return 1;
        }
        if (!counter_only && argc >= 4 && !concentrated && !overflow &&
            !accumulate && !indirect) {
            fprintf(stderr, "G17P_PARTIAL_ERROR mode\n");
            return 1;
        }
        if (!counter_only && argc >= 5 && !overflow && !accumulate &&
            !indirect) {
            fprintf(stderr, "G17P_PARTIAL_ERROR triangle-count-mode\n");
            return 1;
        }

        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (device == nil) {
            fprintf(stderr, "G17P_PARTIAL_ERROR no-device\n");
            return 2;
        }
        if (counter_only) {
            list_counters(device);
            return 0;
        }

        const NSUInteger pixel_count = width * height;
        NSUInteger triangle_count = pixel_count;
        NSUInteger submission_count = 1;
        NSUInteger command_queue_count = 1;
        if ((overflow || accumulate || indirect) && argc >= 5 &&
            !parse_triangle_count(argv[4], &triangle_count)) {
            fprintf(stderr, "G17P_PARTIAL_ERROR triangle-count\n");
            return 1;
        }
        const char *submission_text = argc == 6 ? argv[5] :
            getenv("G17P_PARTIAL_SUBMISSIONS");
        if (submission_text != NULL &&
            !parse_submission_count(submission_text, &submission_count)) {
            fprintf(stderr, "G17P_PARTIAL_ERROR submission-count\n");
            return 1;
        }
        const char *queue_count_text = getenv("G17P_COMMAND_QUEUE_COUNT");
        if (queue_count_text != NULL &&
            (!parse_submission_count(queue_count_text, &command_queue_count) ||
             command_queue_count > submission_count)) {
            fprintf(stderr, "G17P_PARTIAL_ERROR command-queue-count\n");
            return 1;
        }
        const BOOL enqueue_all = getenv("G17P_ENQUEUE_ALL") != NULL;
        NSUInteger capture_after = 0;
        const char *capture_after_text = getenv("G17P_CAPTURE_AFTER");
        if (capture_after_text != NULL &&
            (!parse_submission_count(capture_after_text, &capture_after) ||
             capture_after >= submission_count)) {
            fprintf(stderr, "G17P_PARTIAL_ERROR capture-after\n");
            return 1;
        }
        const NSUInteger vertex_count = triangle_count * 3;
        const NSUInteger varying_count = vertex_count * attachment_count;
        if (pixel_count / width != height ||
            vertex_count / 3 != triangle_count ||
            varying_count / attachment_count != vertex_count ||
            varying_count > NSUIntegerMax / (4 * sizeof(float))) {
            fprintf(stderr, "G17P_PARTIAL_ERROR size-overflow\n");
            return 3;
        }
        const NSUInteger varying_size = (overflow || accumulate || indirect) ?
            4 * sizeof(float) :
            varying_count * 4 * sizeof(float);
        const NSUInteger bytes_per_row = (width * 4 + 255) & ~255UL;
        const NSUInteger output_size = bytes_per_row * height;

        FILE *console = open_console();
        printf("G17P_PARTIAL_START pid=%d device=%s width=%lu height=%lu "
               "triangles=%lu vertices=%lu varying_bytes=%lu submissions=%lu "
               "command_queues=%lu enqueue_all=%d mode=%s\n",
               getpid(), [[device name] UTF8String], (unsigned long)width,
               (unsigned long)height, (unsigned long)triangle_count,
               (unsigned long)vertex_count, (unsigned long)varying_size,
               (unsigned long)submission_count,
               (unsigned long)command_queue_count, enqueue_all,
               accumulate ? "accumulate" : (indirect ? "indirect" :
                   (overflow ? "overflow" :
                    (concentrated ? "concentrated" : "distributed"))));
        if (console != NULL)
            fprintf(console,
                    "G17P_PARTIAL_START pid=%d width=%lu height=%lu "
                    "triangles=%lu varying_bytes=%lu submissions=%lu "
                    "command_queues=%lu enqueue_all=%d mode=%s\n",
                    getpid(), (unsigned long)width, (unsigned long)height,
                    (unsigned long)triangle_count, (unsigned long)varying_size,
                    (unsigned long)submission_count,
                    (unsigned long)command_queue_count, enqueue_all,
                    accumulate ? "accumulate" : (indirect ? "indirect" :
                        (overflow ? "overflow" :
                         (concentrated ? "concentrated" : "distributed"))));

        NSError *error = nil;
        NSURL *url = [NSURL fileURLWithPath:library_path(argv[0])];
        printf("G17P_PARTIAL_LIBRARY_BEGIN path=%s\n", [[url path] UTF8String]);
        if (console != NULL)
            fprintf(console, "G17P_PARTIAL_LIBRARY_BEGIN path=%s\n",
                    [[url path] UTF8String]);
        id<MTLLibrary> library = [device newLibraryWithURL:url error:&error];
        if (library == nil) {
            fprintf(stderr, "G17P_PARTIAL_ERROR library path=%s error=%s\n",
                    [[[url path] stringByStandardizingPath] UTF8String],
                    error_string(error));
            if (console != NULL)
                fprintf(console, "G17P_PARTIAL_ERROR library error=%s\n",
                        error_string(error));
            return 4;
        }
        printf("G17P_PARTIAL_LIBRARY_READY\n");

        MTLRenderPipelineDescriptor *pipeline_desc =
            [[MTLRenderPipelineDescriptor alloc] init];
        pipeline_desc.vertexFunction =
            [library newFunctionWithName:@"partial_vertex"];
        pipeline_desc.fragmentFunction =
            [library newFunctionWithName:@"partial_fragment"];
        for (NSUInteger i = 0; i < attachment_count; ++i) {
            pipeline_desc.colorAttachments[i].pixelFormat = accumulate ?
                MTLPixelFormatR32Float : MTLPixelFormatBGRA8Unorm;
            if (overflow || accumulate || indirect) {
                pipeline_desc.colorAttachments[i].blendingEnabled = YES;
                pipeline_desc.colorAttachments[i].rgbBlendOperation =
                    MTLBlendOperationAdd;
                pipeline_desc.colorAttachments[i].alphaBlendOperation =
                    MTLBlendOperationAdd;
                pipeline_desc.colorAttachments[i].sourceRGBBlendFactor =
                    MTLBlendFactorOne;
                pipeline_desc.colorAttachments[i].destinationRGBBlendFactor =
                    MTLBlendFactorOne;
                pipeline_desc.colorAttachments[i].sourceAlphaBlendFactor =
                    MTLBlendFactorOne;
                pipeline_desc.colorAttachments[i].destinationAlphaBlendFactor =
                    MTLBlendFactorOne;
            }
        }
        printf("G17P_PARTIAL_PIPELINE_BEGIN\n");
        id<MTLRenderPipelineState> pipeline =
            [device newRenderPipelineStateWithDescriptor:pipeline_desc error:&error];
        if (pipeline == nil) {
            fprintf(stderr, "G17P_PARTIAL_ERROR pipeline error=%s\n",
                    error_string(error));
            if (console != NULL)
                fprintf(console, "G17P_PARTIAL_ERROR pipeline error=%s\n",
                        error_string(error));
            return 5;
        }
        printf("G17P_PARTIAL_PIPELINE_READY\n");

        id<MTLBuffer> varyings =
            [device newBufferWithLength:varying_size
                                options:MTLResourceStorageModeShared];
        if (varyings == nil) {
            fprintf(stderr, "G17P_PARTIAL_ERROR varying-buffer bytes=%lu\n",
                    (unsigned long)varying_size);
            if (console != NULL)
                fprintf(console,
                        "G17P_PARTIAL_ERROR varying-buffer bytes=%lu\n",
                        (unsigned long)varying_size);
            return 6;
        }
        float *varying_data = [varyings contents];
        for (NSUInteger vertex = 0;
             !overflow && !accumulate && !indirect && vertex < vertex_count;
             ++vertex) {
            const NSUInteger pixel = vertex / 3;
            const NSUInteger x = pixel % width;
            const NSUInteger y = pixel / width;
            for (NSUInteger attachment = 0; attachment < attachment_count;
                 ++attachment) {
                const NSUInteger base = (vertex * attachment_count + attachment) * 4;
                varying_data[base + 0] =
                    component_value(x, y, attachment, 0) / 255.0f;
                varying_data[base + 1] =
                    component_value(x, y, attachment, 1) / 255.0f;
                varying_data[base + 2] =
                    component_value(x, y, attachment, 2) / 255.0f;
                varying_data[base + 3] = 1.0f;
            }
        }

        id<MTLBuffer> outputs[attachment_count] = { nil };
        id<MTLTexture> targets[attachment_count] = { nil };
        MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor renderPassDescriptor];
        const BOOL load_existing = getenv("G17P_LOAD_EXISTING") != NULL;
        for (NSUInteger i = 0; i < attachment_count; ++i) {
            outputs[i] = [device newBufferWithLength:output_size
                                             options:MTLResourceStorageModeShared];
            if (outputs[i] == nil) {
                fprintf(stderr, "G17P_PARTIAL_ERROR output-buffer index=%lu\n",
                        (unsigned long)i);
                if (console != NULL)
                    fprintf(console,
                            "G17P_PARTIAL_ERROR output-buffer index=%lu\n",
                            (unsigned long)i);
                return 7;
            }
            memset([outputs[i] contents], 0, output_size);
            MTLTextureDescriptor *texture_desc =
                [MTLTextureDescriptor
                    texture2DDescriptorWithPixelFormat:(accumulate ?
                        MTLPixelFormatR32Float : MTLPixelFormatBGRA8Unorm)
                                                 width:width
                                                height:height
                                             mipmapped:NO];
            texture_desc.usage = MTLTextureUsageRenderTarget;
            texture_desc.storageMode = MTLStorageModeShared;
            targets[i] = [outputs[i] newTextureWithDescriptor:texture_desc
                                                        offset:0
                                                   bytesPerRow:bytes_per_row];
            if (targets[i] == nil) {
                fprintf(stderr, "G17P_PARTIAL_ERROR output-texture index=%lu\n",
                        (unsigned long)i);
                if (console != NULL)
                    fprintf(console,
                            "G17P_PARTIAL_ERROR output-texture index=%lu\n",
                            (unsigned long)i);
                return 8;
            }
            pass.colorAttachments[i].texture = targets[i];
            pass.colorAttachments[i].loadAction = load_existing ?
                MTLLoadActionLoad : MTLLoadActionClear;
            pass.colorAttachments[i].storeAction = MTLStoreActionStore;
            pass.colorAttachments[i].clearColor = MTLClearColorMake(0, 0, 0, 0);
        }

        NSMutableArray<id<MTLCommandQueue>> *queues =
            [NSMutableArray arrayWithCapacity:command_queue_count];
        for (NSUInteger i = 0; i < command_queue_count; ++i) {
            id<MTLCommandQueue> queue = [device newCommandQueue];
            if (queue == nil) {
                fprintf(stderr,
                        "G17P_PARTIAL_ERROR command-queue index=%lu\n",
                        (unsigned long)i);
                return 10;
            }
            [queues addObject:queue];
        }
        id<MTLBuffer> indirect_args = nil;
        if (indirect) {
            indirect_args = [device newBufferWithLength:4 * sizeof(uint32_t)
                                                options:MTLResourceStorageModeShared];
            if (indirect_args == nil) {
                fprintf(stderr, "G17P_PARTIAL_ERROR indirect-buffer\n");
                return 10;
            }
            uint32_t *args = [indirect_args contents];
            args[0] = (uint32_t)vertex_count;
            args[1] = 1;
            args[2] = 0;
            args[3] = 0;
        }
        uint32_t dimensions[4] = {
            (uint32_t)width, (uint32_t)height,
            accumulate ? 3u : ((overflow || indirect) ? 2u :
                (concentrated ? 1u : 0u)),
            (uint32_t)triangle_count,
        };
        MTLViewport viewport = {0, 0, width, height, 0, 1};
        BOOL exact = YES;
        NSUInteger completed_submissions = 0;
        MTLCommandBufferStatus last_status = MTLCommandBufferStatusNotEnqueued;
        NSError *last_error = nil;
        for (NSUInteger submission = 0; submission < submission_count;
             ++submission) {
            @autoreleasepool {
                if (!enqueue_all || submission == 0) {
                    for (NSUInteger i = 0; i < attachment_count; ++i)
                        memset([outputs[i] contents], 0, output_size);
                }

                const NSUInteger queue_index =
                    submission % command_queue_count;
                id<MTLCommandBuffer> command =
                    [queues[queue_index] commandBuffer];
                id<MTLRenderCommandEncoder> encoder =
                    [command renderCommandEncoderWithDescriptor:pass];
                [encoder setRenderPipelineState:pipeline];
                [encoder setVertexBytes:dimensions length:sizeof(dimensions)
                                atIndex:0];
                [encoder setVertexBuffer:varyings offset:0 atIndex:1];
                [encoder setViewport:viewport];
                if (indirect) {
                    [encoder drawPrimitives:MTLPrimitiveTypeTriangle
                              indirectBuffer:indirect_args
                        indirectBufferOffset:0];
                } else {
                    [encoder drawPrimitives:MTLPrimitiveTypeTriangle
                                vertexStart:0
                                vertexCount:vertex_count];
                }
                [encoder endEncoding];

                printf("G17P_PARTIAL_READY submission=%lu/%lu queue=%lu/%lu "
                       "input=0x%llx input_size=0x%lx output0=0x%llx "
                       "output_size=0x%lx\n",
                       (unsigned long)(submission + 1),
                       (unsigned long)submission_count,
                       (unsigned long)(queue_index + 1),
                       (unsigned long)command_queue_count,
                       (unsigned long long)[varyings gpuAddress],
                       (unsigned long)varying_size,
                       (unsigned long long)[outputs[0] gpuAddress],
                       (unsigned long)output_size);
                if (console != NULL)
                    fprintf(console,
                            "G17P_PARTIAL_READY submission=%lu/%lu "
                            "queue=%lu/%lu input=0x%llx input_size=0x%lx "
                            "output0=0x%llx output_size=0x%lx\n",
                            (unsigned long)(submission + 1),
                            (unsigned long)submission_count,
                            (unsigned long)(queue_index + 1),
                            (unsigned long)command_queue_count,
                            (unsigned long long)[varyings gpuAddress],
                            (unsigned long)varying_size,
                            (unsigned long long)[outputs[0] gpuAddress],
                            (unsigned long)output_size);

                if (submission == 0 &&
                    getenv("G17P_STOP_BEFORE_COMMIT") != NULL) {
                    printf("G17P_PARTIAL_STOP_BEFORE_COMMIT pid=%d\n",
                           getpid());
                    if (console != NULL)
                        fprintf(console,
                                "G17P_PARTIAL_STOP_BEFORE_COMMIT pid=%d\n",
                                getpid());
                    fflush(stdout);
                    fflush(stderr);
                    if (console != NULL)
                        fflush(console);
                    raise(SIGSTOP);
                }

                BOOL dump_before_commit =
                    getenv("G17P_DUMP_BEFORE_COMMIT") != NULL;
                BOOL dump_every_commit =
                    getenv("G17P_DUMP_EVERY_COMMIT") != NULL;
                if ((submission == 0 && dump_before_commit) ||
                    dump_every_commit) {
                    printf("G17P_PARTIAL_DUMP_BEFORE_COMMIT "
                           "submission=%lu/%lu\n",
                           (unsigned long)(submission + 1),
                           (unsigned long)submission_count);
                    kill(getpid(), SIGUSR1);
                    usleep(1000000);
                }

                if (submission == 0 &&
                    getenv("G17P_ARM_CAPTURE_BEFORE_FIRST_COMMIT") != NULL) {
                    printf("G17P_PARTIAL_ARM_CAPTURE next=1/%lu\n",
                           (unsigned long)submission_count);
                    if (console != NULL)
                        fprintf(console,
                                "G17P_PARTIAL_ARM_CAPTURE next=1/%lu\n",
                                (unsigned long)submission_count);
                    fflush(stdout);
                    if (console != NULL)
                        fflush(console);
                }

                [command commit];
                if (enqueue_all && submission + 1 < submission_count &&
                    (capture_after == 0 || submission + 1 > capture_after)) {
                    printf("G17P_PARTIAL_ENQUEUED submission=%lu/%lu\n",
                           (unsigned long)(submission + 1),
                           (unsigned long)submission_count);
                    if (console != NULL)
                        fprintf(console,
                                "G17P_PARTIAL_ENQUEUED submission=%lu/%lu\n",
                                (unsigned long)(submission + 1),
                                (unsigned long)submission_count);
                    continue;
                }
                [command waitUntilCompleted];

                NSUInteger exact_pixels[attachment_count] = { 0 };
                NSUInteger changed_bytes[attachment_count] = { 0 };
                float accumulated_max[attachment_count] = { 0 };
                for (NSUInteger attachment = 0;
                     attachment < attachment_count; ++attachment) {
                    const uint8_t *bytes = [outputs[attachment] contents];
                    for (NSUInteger y = 0; y < height; ++y) {
                        for (NSUInteger x = 0; x < width; ++x) {
                            const uint8_t expected[4] = {
                                component_value(x, y, attachment, 2),
                                component_value(x, y, attachment, 1),
                                component_value(x, y, attachment, 0),
                                255,
                            };
                            const uint8_t *pixel =
                                bytes + y * bytes_per_row + x * 4;
                            if (memcmp(pixel, expected, sizeof(expected)) == 0)
                                exact_pixels[attachment]++;
                            for (NSUInteger component = 0; component < 4;
                                 ++component) {
                                if (pixel[component] != 0)
                                    changed_bytes[attachment]++;
                            }
                        }
                    }
                    if (accumulate) {
                        const float *values = (const float *)bytes;
                        for (NSUInteger pixel = 0; pixel < pixel_count;
                             ++pixel) {
                            if (isfinite(values[pixel]) &&
                                values[pixel] > accumulated_max[attachment])
                                accumulated_max[attachment] = values[pixel];
                        }
                        printf("G17P_PARTIAL_ACCUM submission=%lu index=%lu "
                               "max=%.9g\n", (unsigned long)(submission + 1),
                               (unsigned long)attachment,
                               accumulated_max[attachment]);
                    }
                    printf("G17P_PARTIAL_TARGET submission=%lu index=%lu "
                           "exact_pixels=%lu/%lu changed_bytes=%lu "
                           "first=%02x%02x%02x%02x\n",
                           (unsigned long)(submission + 1),
                           (unsigned long)attachment,
                           (unsigned long)exact_pixels[attachment],
                           (unsigned long)pixel_count,
                           (unsigned long)changed_bytes[attachment], bytes[0],
                           bytes[1], bytes[2], bytes[3]);
                }

                BOOL submission_exact =
                    [command status] == MTLCommandBufferStatusCompleted;
                for (NSUInteger i = 0; i < attachment_count; ++i) {
                    if (accumulate)
                        submission_exact &= accumulated_max[i] >
                                (float)(i + 1) * 0.75f &&
                            accumulated_max[i] < (float)(i + 1) * 1.25f;
                    else if (concentrated || overflow || indirect)
                        submission_exact &= changed_bytes[i] != 0;
                    else
                        submission_exact &= exact_pixels[i] == pixel_count;
                }
                last_status = [command status];
                last_error = [command error];
                completed_submissions++;
                exact &= submission_exact;
                printf("G17P_PARTIAL_SUBMISSION_DONE submission=%lu/%lu "
                       "status=%ld error=%s exact=%d\n",
                       (unsigned long)(submission + 1),
                       (unsigned long)submission_count, (long)last_status,
                       error_string(last_error), submission_exact);
                if (capture_after == submission + 1) {
                    printf("G17P_PARTIAL_ARM_CAPTURE next=%lu/%lu\n",
                           (unsigned long)(submission + 2),
                           (unsigned long)submission_count);
                    if (console != NULL)
                        fprintf(console,
                                "G17P_PARTIAL_ARM_CAPTURE next=%lu/%lu\n",
                                (unsigned long)(submission + 2),
                                (unsigned long)submission_count);
                    fflush(stdout);
                    if (console != NULL)
                        fflush(console);
                }
            }
            if (!exact)
                break;
        }
        printf("G17P_PARTIAL_DONE status=%ld error=%s exact=%d "
               "submissions=%lu/%lu\n",
               (long)last_status, error_string(last_error), exact,
               (unsigned long)completed_submissions,
               (unsigned long)submission_count);
        if (console != NULL)
            fprintf(console,
                    "G17P_PARTIAL_DONE status=%ld exact=%d submissions=%lu/%lu\n",
                    (long)last_status, exact,
                    (unsigned long)completed_submissions,
                    (unsigned long)submission_count);
        return exact ? 0 : 9;
    }
}
