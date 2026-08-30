// sampheap.m — EXP-0159 family FD (TEX-21, TEX-22). Authored by the clean-room RE team.
//
// Bindless sampler ceiling / dedup / destruction / ID-reuse / index-selection
// probe on G17P.  Modes:
//   ceiling — dedup check, then walk distinct sampler creations far past the
//             published maxArgumentBufferSamplerCount, recording IDs, density,
//             live-ID uniqueness and the exact failure (if any) at the ceiling.
//   index   — declared-array ceiling probe, then a heap with canary samplers at
//             boundary indices INCLUDING indices >= 500000 and canaries whose
//             own resource ID is >= 500000, selected with a runtime index
//             (uniform + per-lane) and checked against an independent-path
//             ([[sampler(0)]]) fingerprint.
//   reuse   — destroyed-ID behaviour: does a released sampler's ID come back,
//             and does a heap entry still holding it then select the new sampler?
//   oob     — raw out-of-table resource IDs written straight into heap entries.
//             HANG-PRONE: run under gpulease.
//
// Every command-buffer error is re-run to a majority of 3 with its OS fault
// classification recorded verbatim (FIELD-SWEEP-PROTOCOL.md sec.7).
//
// Clean-room: PUBLIC Metal API + OWN-SHADER (kernels/sampheap.metal).
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <mach/mach.h>

static void rec(NSDictionary *d) {
    NSData *j = [NSJSONSerialization dataWithJSONObject:d options:0 error:nil];
    printf("REC %.*s\n", (int)[j length], (const char *)[j bytes]);
    fflush(stdout);
}
static NSString *errstr(NSError *e) { return e ? [e localizedDescription] : @""; }
static NSString *F(double x) { return [NSString stringWithFormat:@"%.9g", x]; }

static uint64_t rssBytes(void) {
    task_vm_info_data_t info; mach_msg_type_number_t n = TASK_VM_INFO_COUNT;
    if (task_info(mach_task_self(), TASK_VM_INFO, (task_info_t)&info, &n) != KERN_SUCCESS) return 0;
    return info.phys_footprint;
}

typedef void (^EncodeBlock)(id<MTLComputeCommandEncoder> ce);
static int runMajority(__strong id<MTLCommandQueue> *q, id<MTLDevice> dev,
                       id<MTLComputePipelineState> pso, id<MTLBuffer> outbuf,
                       NSUInteger outLen, MTLSize grid, MTLSize tg,
                       EncodeBlock enc, NSString **outFault, int *outErrs) {
    int attempts = 0, errs = 0;
    NSString *fc = @"";
    for (attempts = 1; attempts <= 3; attempts++) {
        memset([outbuf contents], 0xA5, outLen);      // poisoned read-back buffer
        id<MTLCommandBuffer> cb = [*q commandBuffer];
        id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
        [ce setComputePipelineState:pso];
        enc(ce);
        [ce dispatchThreads:grid threadsPerThreadgroup:tg];
        [ce endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] == MTLCommandBufferStatusError) {
            errs++; fc = errstr([cb error]);
            *q = [dev newCommandQueue];
            continue;
        }
        // A dispatch that reports OK but leaves the poisoned read-back buffer
        // untouched has not done its job; retry it rather than record the
        // poison as data.  (Seen once on G17P under concurrent GPU load.)
        if (outLen >= 4 && *(const uint32_t *)[outbuf contents] == 0xA5A5A5A5u) {
            errs++; fc = @"dispatch reported OK but left the poisoned output unwritten";
            continue;
        }
        break;
    }
    if (outFault) *outFault = fc;
    if (outErrs) *outErrs = errs;
    return attempts;
}
static NSString *classify(int errs, NSString *fc) {
    if (errs < 3) return nil;
    return ([fc rangeOfString:@"InnocentVictim"].location != NSNotFound) ? @"victim" : @"fault";
}

static id<MTLTexture> makeTex(id<MTLDevice> dev) {
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Float
                                                                                  width:4 height:4 mipmapped:YES];
    td.mipmapLevelCount = 3; td.usage = MTLTextureUsageShaderRead; td.storageMode = MTLStorageModeShared;
    id<MTLTexture> t = [dev newTextureWithDescriptor:td];
    for (int L = 0; L < 3; L++) {
        int w = 4 >> L; if (w < 1) w = 1;
        float *px = malloc(sizeof(float) * w * w);
        for (int y = 0; y < w; y++) for (int x = 0; x < w; x++) px[y*w+x] = 1000.0f*L + 100.0f*y + x;
        [t replaceRegion:MTLRegionMake2D(0,0,w,w) mipmapLevel:L withBytes:px bytesPerRow:4*w];
        free(px);
    }
    return t;
}
// Canary class c in 0..5: (lodMaxClamp = c/3) x (address-mode combo = c%3).
// gen != 0 makes an otherwise-equivalent but NON-dedup-identical descriptor, so
// a second generation of canaries lands on fresh (high) resource IDs.
static MTLSamplerDescriptor *classDesc(int c, int gen) {
    MTLSamplerDescriptor *d = [MTLSamplerDescriptor new];
    d.supportArgumentBuffers = YES;
    d.minFilter = d.magFilter = MTLSamplerMinMagFilterNearest;
    d.mipFilter = MTLSamplerMipFilterNearest;
    d.lodMaxClamp = (float)(c / 3);
    int combo = c % 3;
    d.sAddressMode = (combo == 1) ? MTLSamplerAddressModeRepeat : MTLSamplerAddressModeClampToEdge;
    d.tAddressMode = (combo == 2) ? MTLSamplerAddressModeRepeat : MTLSamplerAddressModeClampToEdge;
    d.rAddressMode = MTLSamplerAddressModeClampToEdge;
    if (gen) d.maxAnisotropy = 1 + gen;   // no effect at an explicit level; makes the descriptor distinct
    return d;
}

int main(int argc, char **argv) {
  @autoreleasepool {
    if (argc < 3) { fprintf(stderr, "usage: sampheap <source.metal> <mode> [walk_target]\n"); return 2; }
    NSString *mode = [NSString stringWithUTF8String:argv[2]];
    NSUInteger walkTarget = (argc >= 4) ? (NSUInteger)strtoul(argv[3], NULL, 0) : 2000000;
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    NSError *err = nil;
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:argv[1]]
                                              encoding:NSUTF8StringEncoding error:&err];
    if (!src) { rec(@{@"family":@"fd",@"case":@"source",@"outcome":@"fault",@"note":errstr(err)}); return 2; }
    NSUInteger MAXS = [dev maxArgumentBufferSamplerCount];
    rec(@{@"family":@"fd",@"case":@"cap_query",@"observed":@(MAXS),@"outcome":@"ok",@"target":@"G17P",
          @"note":@"MTLDevice.maxArgumentBufferSamplerCount"});

    // ================================================================ ceiling
    if ([mode isEqualToString:@"ceiling"]) {
        MTLSamplerDescriptor *a = [MTLSamplerDescriptor new]; a.supportArgumentBuffers = YES;
        MTLSamplerDescriptor *b = [MTLSamplerDescriptor new]; b.supportArgumentBuffers = YES;
        id<MTLSamplerState> sa = [dev newSamplerStateWithDescriptor:a];
        id<MTLSamplerState> sb = [dev newSamplerStateWithDescriptor:b];
        rec(@{@"family":@"fd",@"case":@"dedup_identical",
              @"observed":[NSString stringWithFormat:@"%llu,%llu",
                           (unsigned long long)[sa gpuResourceID]._impl,
                           (unsigned long long)[sb gpuResourceID]._impl],
              @"match":@([sa gpuResourceID]._impl == [sb gpuResourceID]._impl),
              @"outcome":@"ok",@"target":@"G17P",@"note":@"two identical MTLSamplerDescriptors"});
        MTLSamplerDescriptor *c = [MTLSamplerDescriptor new]; c.supportArgumentBuffers = YES;
        c.magFilter = MTLSamplerMinMagFilterLinear;
        id<MTLSamplerState> sc = [dev newSamplerStateWithDescriptor:c];
        rec(@{@"family":@"fd",@"case":@"dedup_control_distinct",
              @"observed":[NSString stringWithFormat:@"%llu,%llu",
                           (unsigned long long)[sa gpuResourceID]._impl,
                           (unsigned long long)[sc gpuResourceID]._impl],
              @"match":@([sa gpuResourceID]._impl != [sc gpuResourceID]._impl),
              @"outcome":@"ok",@"target":@"G17P",@"note":@"differ only in magFilter"});
        // dedup of a NON-argument-buffer sampler (control for the ID space)
        MTLSamplerDescriptor *nd = [MTLSamplerDescriptor new]; nd.supportArgumentBuffers = NO;
        nd.lodMaxClamp = 3.0f;
        id<MTLSamplerState> sn = [dev newSamplerStateWithDescriptor:nd];
        BOOL hasID = YES; uint64_t nid = 0;
        @try { nid = [sn gpuResourceID]._impl; } @catch (id ex) { hasID = NO; }
        rec(@{@"family":@"fd",@"case":@"nonargbuf_sampler_id",@"observed":@(nid),
              @"outcome":(hasID?@"ok":@"reject"),@"target":@"G17P",
              @"note":@"supportArgumentBuffers=NO: does it still consume a table slot?"});

        NSMutableArray *keep = [NSMutableArray arrayWithObjects:sa, sc, sn, nil];
        NSMutableSet *ids = [NSMutableSet setWithObjects:@([sa gpuResourceID]._impl),
                                                        @([sc gpuResourceID]._impl), nil];
        NSUInteger made = 2, firstNil = 0, firstDup = 0, firstNonDense = 0;
        NSDate *t0 = [NSDate date];
        for (NSUInteger i = 0; i < walkTarget; i++) {
            @autoreleasepool {
                MTLSamplerDescriptor *d = [MTLSamplerDescriptor new];
                d.supportArgumentBuffers = YES;
                // distinct descriptors: vary lodMaxClamp, an ordinary API property.
                // lodMinClamp is deliberately left at its default (PRE_REGISTRATION sec.4).
                d.lodMaxClamp = (float)(i + 4);
                id<MTLSamplerState> s = [dev newSamplerStateWithDescriptor:d];
                if (!s) { firstNil = made + 1; break; }
                uint64_t rid = [s gpuResourceID]._impl;
                if ([ids containsObject:@(rid)] && !firstDup) firstDup = made + 1;
                if (rid != made + 1 && !firstNonDense) firstNonDense = made + 1;
                [ids addObject:@(rid)];
                [keep addObject:s];
                made++;
                if (made <= 4 || made == MAXS - 1 || made == MAXS || made == MAXS + 1 ||
                    made == MAXS + 2 || (made % 250000) == 0) {
                    rec(@{@"family":@"fd",@"case":[NSString stringWithFormat:@"created_%lu",(unsigned long)made],
                          @"value":@(made),@"observed":@(rid),@"match":@(rid == made),
                          @"outcome":@"ok",@"target":@"G17P",
                          @"rss_mb":@(rssBytes()/(1024*1024)),
                          @"elapsed_s":F(-[t0 timeIntervalSinceNow]),
                          @"note":@"gpuResourceID._impl of the n-th distinct sampler"});
                }
                if (-[t0 timeIntervalSinceNow] > 240.0) break;    // wall-clock budget
                if (rssBytes() > 4500ull*1024*1024) break;        // memory guard
            }
        }
        rec(@{@"family":@"fd",@"case":@"ceiling_walk",@"observed":@(made),@"value":@(MAXS),
              @"outcome":(firstNil ? @"reject" : @"ok"),
              @"match":@(firstNil == MAXS + 1),
              @"target":@"G17P",@"rss_mb":@(rssBytes()/(1024*1024)),
              @"elapsed_s":F(-[t0 timeIntervalSinceNow]),
              @"note":[NSString stringWithFormat:
                       @"distinct argument-buffer sampler states created=%lu (walk target %lu); "
                       @"first nil at n=%lu (0=never); unique IDs=%lu; first live-ID duplicate at "
                       @"n=%lu (0=never); first non-dense ID at n=%lu (0=never)",
                       (unsigned long)made,(unsigned long)walkTarget,(unsigned long)firstNil,
                       (unsigned long)[ids count],(unsigned long)firstDup,(unsigned long)firstNonDense]});
        rec(@{@"family":@"fd",@"case":@"__done",@"outcome":@"ok",@"target":@"G17P"});
        return 0;
    }

    // ---- declared-array ceiling (compile-time), for the dispatch modes
    if ([mode isEqualToString:@"index"]) {
        for (NSNumber *n in @[@500000, @500001, @1000000, @2000000]) {
            NSString *s = [src stringByReplacingOccurrencesOfString:@"#define SCAP 500000"
                           withString:[NSString stringWithFormat:@"#define SCAP %@", n]];
            NSError *e = nil;
            id<MTLLibrary> l = [dev newLibraryWithSource:s options:[MTLCompileOptions new] error:&e];
            NSMutableDictionary *r = [@{@"family":@"fd",
                                        @"case":[NSString stringWithFormat:@"declared_scap_%@",n],
                                        @"value":n,@"observed":(l?@"accept":@"reject"),
                                        @"outcome":(l?@"ok":@"reject"),@"target":@"G17P"} mutableCopy];
            if (!l) r[@"note"] = errstr(e);
            else r[@"encoded_length"] = @([[[l newFunctionWithName:@"k_samp"]
                                            newArgumentEncoderWithBufferIndex:0] encodedLength]);
            rec(r);
        }
    }

    // ---- shared setup: declare the heap at 1,000,000 entries so indices >= 500000
    //      are inside the declared array.
    NSUInteger HCAP = [mode isEqualToString:@"index"] ? 1000000 : 500000;
    NSString *hsrc = [src stringByReplacingOccurrencesOfString:@"#define SCAP 500000"
                      withString:[NSString stringWithFormat:@"#define SCAP %lu",(unsigned long)HCAP]];
    id<MTLLibrary> lib = [dev newLibraryWithSource:hsrc options:[MTLCompileOptions new] error:&err];
    if (!lib) { rec(@{@"family":@"fd",@"case":@"compile",@"outcome":@"reject",@"note":errstr(err)}); return 2; }
    NSError *e1=nil,*e2=nil,*e3=nil;
    id<MTLFunction> fD = [lib newFunctionWithName:@"k_direct"];
    id<MTLFunction> fS = [lib newFunctionWithName:@"k_samp"];
    id<MTLFunction> fP = [lib newFunctionWithName:@"k_samp_perlane"];
    id<MTLComputePipelineState> pD = [dev newComputePipelineStateWithFunction:fD error:&e1];
    id<MTLComputePipelineState> pS = [dev newComputePipelineStateWithFunction:fS error:&e2];
    id<MTLComputePipelineState> pP = [dev newComputePipelineStateWithFunction:fP error:&e3];
    if (!pD || !pS || !pP) {
        rec(@{@"family":@"fd",@"case":@"pso",@"outcome":@"reject",
              @"note":[NSString stringWithFormat:@"%@|%@|%@",errstr(e1),errstr(e2),errstr(e3)]});
        return 2;
    }
    id<MTLArgumentEncoder> aenc = [fS newArgumentEncoderWithBufferIndex:0];
    NSUInteger encLen = [aenc encodedLength];
    id<MTLBuffer> heap = [dev newBufferWithLength:encLen options:MTLResourceStorageModeShared];
    rec(@{@"family":@"fd",@"case":@"heap_alloc",@"observed":@(encLen),@"value":@(HCAP),
          @"outcome":(heap?@"ok":@"fault"),@"target":@"G17P",
          @"note":[NSString stringWithFormat:@"array<sampler,%lu> encodedLength; %.3f bytes/entry",
                   (unsigned long)HCAP,(double)encLen/(double)HCAP]});
    if (!heap) return 2;
    [aenc setArgumentBuffer:heap offset:0];
    id<MTLTexture> tex = makeTex(dev);
    __block id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLBuffer> outbuf = [dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
    id<MTLBuffer> idxbuf = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];

    // fingerprint helper (independent path)
    float (^fingerprint)(id<MTLSamplerState>, NSString *) = ^float(id<MTLSamplerState> s, NSString *label) {
        NSString *fc = @""; int errs = 0;
        runMajority(&q, dev, pD, outbuf, 64, MTLSizeMake(1,1,1), MTLSizeMake(1,1,1),
                    ^(id<MTLComputeCommandEncoder> ce) {
            [ce setBuffer:outbuf offset:0 atIndex:0];
            [ce setTexture:tex atIndex:0];
            [ce setSamplerState:s atIndex:0];
        }, &fc, &errs);
        float v = *(const float *)[outbuf contents];
        rec(@{@"family":@"fd",@"case":label,@"observed":F(v),
              @"outcome":(classify(errs,fc) ?: @"ok"),@"fault_class":fc,@"cb_errors":@(errs),
              @"resource_id":@((unsigned long long)[s gpuResourceID]._impl),@"target":@"G17P",
              @"note":@"independent path: sampler bound directly at [[sampler(0)]]"});
        return v;
    };

    // ================================================================== index
    if ([mode isEqualToString:@"index"]) {
        // generation 0: six canary classes, low resource IDs
        NSMutableArray *g0 = [NSMutableArray array];
        float fp0[6];
        for (int c = 0; c < 6; c++) {
            id<MTLSamplerState> s = [dev newSamplerStateWithDescriptor:classDesc(c, 0)];
            [g0 addObject:s];
            fp0[c] = fingerprint(s, [NSString stringWithFormat:@"fingerprint_g0_class%d", c]);
        }
        // fillers: push the resource-ID watermark past the published ceiling
        NSMutableArray *fill = [NSMutableArray array];
        for (NSUInteger i = 0; i < MAXS + 100; i++) @autoreleasepool {
            MTLSamplerDescriptor *d = [MTLSamplerDescriptor new];
            d.supportArgumentBuffers = YES; d.lodMaxClamp = (float)(i + 10);
            id<MTLSamplerState> s = [dev newSamplerStateWithDescriptor:d];
            if (!s) break;
            [fill addObject:s];
        }
        rec(@{@"family":@"fd",@"case":@"filler_watermark",@"observed":@([fill count]),
              @"outcome":@"ok",@"target":@"G17P",@"rss_mb":@(rssBytes()/(1024*1024)),
              @"note":@"filler samplers created to push the resource-ID watermark past the ceiling"});
        // generation 1: the same six classes again, now on HIGH resource IDs
        NSMutableArray *g1 = [NSMutableArray array];
        float fp1[6];
        for (int c = 0; c < 6; c++) {
            id<MTLSamplerState> s = [dev newSamplerStateWithDescriptor:classDesc(c, 1)];
            [g1 addObject:s];
            fp1[c] = fingerprint(s, [NSString stringWithFormat:@"fingerprint_g1_class%d", c]);
        }
        // canary placement: index -> (sampler, expected fingerprint)
        NSArray *canIdx = @[@0,@1,@2,@255,@256,@65535,@65536,@262143,@499997,@499998,@499999,
                            @500000,@500001,@524288,@999998,@999999];
        NSMutableArray *canFP = [NSMutableArray array];
        for (NSUInteger i = 0; i < [canIdx count]; i++) {
            BOOL high = ([canIdx[i] unsignedIntegerValue] >= 499997);   // high indices get HIGH-ID samplers
            int c = (int)(i % 6);
            id<MTLSamplerState> s = high ? g1[c] : g0[c];
            [aenc setSamplerState:s atIndex:[canIdx[i] unsignedIntegerValue]];
            [canFP addObject:@(high ? fp1[c] : fp0[c])];
        }
        const uint64_t *hb = (const uint64_t *)[heap contents];
        for (NSNumber *k in canIdx)
            rec(@{@"family":@"fd",@"case":[NSString stringWithFormat:@"entry_bytes_%@",k],@"value":k,
                  @"observed":[NSString stringWithFormat:@"%016llx",
                               (unsigned long long)hb[[k unsignedIntegerValue]]],
                  @"outcome":@"ok",@"target":@"G17P"});

        NSArray *probes = @[@0,@1,@2,@3,@255,@256,@65535,@65536,@262143,@499996,@499997,@499998,
                            @499999,@500000,@500001,@500002,@524288,@999998,@999999,@1000000,@2000000];
        for (NSNumber *k in probes) {
            NSUInteger pos = [canIdx indexOfObject:k];
            uint32_t idx = [k unsignedIntValue];
            memcpy([idxbuf contents], &idx, 4);
            NSString *fc = @""; int errs = 0;
            runMajority(&q, dev, pS, outbuf, 64, MTLSizeMake(1,1,1), MTLSizeMake(1,1,1),
                        ^(id<MTLComputeCommandEncoder> ce) {
                [ce setBuffer:heap offset:0 atIndex:0];
                [ce setBuffer:idxbuf offset:0 atIndex:1];
                [ce setBuffer:outbuf offset:0 atIndex:2];
                [ce setTexture:tex atIndex:0];
            }, &fc, &errs);
            uint32_t rawv = *(const uint32_t *)[outbuf contents];
            float got = *(const float *)[outbuf contents];
            float expect = (pos == NSNotFound) ? 0.0f/0.0f : [canFP[pos] floatValue];
            BOOL match = (pos != NSNotFound) && (got == expect) && errs < 3;
            NSString *cl = classify(errs, fc);
            NSString *outcome = cl ? cl
                : (rawv == 0xA5A5A5A5u ? @"unwritten"
                   : (pos == NSNotFound ? (got == 0.0f ? @"silent_zero" : @"unpopulated_nonzero")
                                        : (match ? @"ok" : @"wrong_value")));
            rec(@{@"family":@"fd",@"case":[NSString stringWithFormat:@"index_%@",k],@"value":k,
                  @"observed":F(got),
                  @"oracle":(pos==NSNotFound ? @"unpopulated" : F(expect)),
                  @"heap_entry":[NSString stringWithFormat:@"%016llx",(unsigned long long)hb[idx < HCAP ? idx : 0]],
                  @"populated":@(pos != NSNotFound),@"match":@(match),@"outcome":outcome,
                  @"in_declared_array":@(idx < HCAP),
                  @"fault_class":fc,@"cb_errors":@(errs),@"target":@"G17P"});
        }
        {
            uint32_t lanes[8] = {0,1,2,262143,499999,500000,500001,999999};
            id<MTLBuffer> lb = [dev newBufferWithBytes:lanes length:sizeof(lanes)
                                               options:MTLResourceStorageModeShared];
            NSString *fc = @""; int errs = 0;
            runMajority(&q, dev, pP, outbuf, 64, MTLSizeMake(8,1,1), MTLSizeMake(8,1,1),
                        ^(id<MTLComputeCommandEncoder> ce) {
                [ce setBuffer:heap offset:0 atIndex:0];
                [ce setBuffer:lb offset:0 atIndex:1];
                [ce setBuffer:outbuf offset:0 atIndex:2];
                [ce setTexture:tex atIndex:0];
            }, &fc, &errs);
            const float *o = (const float *)[outbuf contents];
            NSMutableString *obs=[NSMutableString string], *exp=[NSMutableString string];
            BOOL all = YES;
            for (int i = 0; i < 8; i++) {
                NSUInteger pos = [canIdx indexOfObject:@(lanes[i])];
                float e = (pos == NSNotFound) ? 0.0f/0.0f : [canFP[pos] floatValue];
                [obs appendFormat:@"%.9g ", (double)o[i]]; [exp appendFormat:@"%.9g ", (double)e];
                if (!(o[i] == e)) all = NO;
            }
            rec(@{@"family":@"fd",@"case":@"perlane_divergent",@"observed":obs,@"oracle":exp,
                  @"match":@(all && errs < 3),
                  @"outcome":(classify(errs,fc) ?: (all?@"ok":@"wrong_value")),
                  @"fault_class":fc,@"cb_errors":@(errs),
                  @"note":@"lanes 0,1,2,262143,499999,500000,500001,999999",@"target":@"G17P"});
        }
        rec(@{@"family":@"fd",@"case":@"__done",@"outcome":@"ok",@"target":@"G17P"});
        return 0;
    }

    // ================================================================== reuse
    if ([mode isEqualToString:@"reuse"]) {
        // class 5 (fingerprint 1001) is released; class 2 (fingerprint 3) replaces it.
        id<MTLSamplerState> ref5 = [dev newSamplerStateWithDescriptor:classDesc(5, 7)];
        float f5 = fingerprint(ref5, @"fingerprint_released_class");
        id<MTLSamplerState> ref2 = [dev newSamplerStateWithDescriptor:classDesc(2, 8)];
        float f2 = fingerprint(ref2, @"fingerprint_replacement_class");
        uint64_t deadID = 0;
        uint64_t *hb = (uint64_t *)[heap contents];
        @autoreleasepool {
            id<MTLSamplerState> s = [dev newSamplerStateWithDescriptor:classDesc(5, 11)];
            deadID = [s gpuResourceID]._impl;
            [aenc setSamplerState:s atIndex:0];
            rec(@{@"family":@"fd",@"case":@"reuse_before_release",@"observed":@(deadID),
                  @"heap_entry":[NSString stringWithFormat:@"%016llx",(unsigned long long)hb[0]],
                  @"outcome":@"ok",@"target":@"G17P",
                  @"note":@"ID of the sampler about to be released (class 5)"});
        }   // released here
        for (int i = 0; i < 3; i++) @autoreleasepool { (void)[dev newCommandQueue]; }
        id<MTLSamplerState> s2 = [dev newSamplerStateWithDescriptor:classDesc(2, 12)];
        uint64_t newID = [s2 gpuResourceID]._impl;
        rec(@{@"family":@"fd",@"case":@"reuse_after_release",@"observed":@(newID),@"value":@(deadID),
              @"match":@(newID == deadID),@"outcome":@"ok",@"target":@"G17P",
              @"heap_entry":[NSString stringWithFormat:@"%016llx",(unsigned long long)hb[0]],
              @"note":@"does a released sampler's ID come back to the next distinct creation?"});
        uint32_t idx = 0; memcpy([idxbuf contents], &idx, 4);
        NSString *fc = @""; int errs = 0;
        runMajority(&q, dev, pS, outbuf, 64, MTLSizeMake(1,1,1), MTLSizeMake(1,1,1),
                    ^(id<MTLComputeCommandEncoder> ce) {
            [ce setBuffer:heap offset:0 atIndex:0]; [ce setBuffer:idxbuf offset:0 atIndex:1];
            [ce setBuffer:outbuf offset:0 atIndex:2]; [ce setTexture:tex atIndex:0];
        }, &fc, &errs);
        float got = *(const float *)[outbuf contents];
        rec(@{@"family":@"fd",@"case":@"stale_id_sample",@"observed":F(got),
              @"oracle":[NSString stringWithFormat:@"released=%.9g replacement=%.9g",(double)f5,(double)f2],
              @"outcome":(classify(errs,fc) ?: @"ok"),@"fault_class":fc,@"cb_errors":@(errs),
              @"heap_entry":[NSString stringWithFormat:@"%016llx",(unsigned long long)hb[0]],
              @"target":@"G17P",
              @"note":@"heap entry 0 still holds the RELEASED sampler's ID; sampling through it"});
        rec(@{@"family":@"fd",@"case":@"__done",@"outcome":@"ok",@"target":@"G17P"});
        return 0;
    }

    // ==================================================================== oob
    if ([mode isEqualToString:@"oob"]) {
        // Baseline: a real sampler at entry 0, so a change is attributable.
        id<MTLSamplerState> ref = [dev newSamplerStateWithDescriptor:classDesc(5, 0)];
        float fref = fingerprint(ref, @"oob_reference_fingerprint");
        [aenc setSamplerState:ref atIndex:0];
        uint64_t *hb = (uint64_t *)[heap contents];
        uint64_t goodID = hb[0];
        uint64_t ids[] = {0ull, 1ull, 499999ull, 500000ull, 500001ull, 1000000ull,
                          0xFFFFFFFFull, 0xFFFFFFFFFFFFFFFFull, 0x8000000000000000ull};
        const char *names[] = {"id_0","id_1","id_499999","id_500000","id_500001","id_1000000",
                               "id_0xFFFFFFFF","id_0xFFFFFFFFFFFFFFFF","id_0x8000000000000000"};
        for (unsigned i = 0; i < sizeof(ids)/sizeof(ids[0]); i++) {
            hb[0] = ids[i];
            uint32_t idx = 0; memcpy([idxbuf contents], &idx, 4);
            NSString *fc = @""; int errs = 0;
            runMajority(&q, dev, pS, outbuf, 64, MTLSizeMake(1,1,1), MTLSizeMake(1,1,1),
                        ^(id<MTLComputeCommandEncoder> ce) {
                [ce setBuffer:heap offset:0 atIndex:0]; [ce setBuffer:idxbuf offset:0 atIndex:1];
                [ce setBuffer:outbuf offset:0 atIndex:2]; [ce setTexture:tex atIndex:0];
            }, &fc, &errs);
            uint32_t raw = *(const uint32_t *)[outbuf contents];
            float got = *(const float *)[outbuf contents];
            rec(@{@"family":@"fd",@"case":[NSString stringWithUTF8String:names[i]],
                  @"value":@(ids[i]),@"observed":F(got),
                  @"observed_hex":[NSString stringWithFormat:@"%08x",raw],
                  @"oracle":[NSString stringWithFormat:@"good_id=%llu fingerprint=%.9g",
                             (unsigned long long)goodID,(double)fref],
                  @"outcome":(classify(errs,fc) ?:
                              (raw==0xA5A5A5A5u?@"unwritten":(got==0.0f?@"silent_zero":@"ok"))),
                  @"fault_class":fc,@"cb_errors":@(errs),@"target":@"G17P",
                  @"note":@"raw resource ID written directly into heap entry 0"});
        }
        hb[0] = goodID;   // restore and re-validate the baseline after the arm
        uint32_t idx = 0; memcpy([idxbuf contents], &idx, 4);
        NSString *fc = @""; int errs = 0;
        runMajority(&q, dev, pS, outbuf, 64, MTLSizeMake(1,1,1), MTLSizeMake(1,1,1),
                    ^(id<MTLComputeCommandEncoder> ce) {
            [ce setBuffer:heap offset:0 atIndex:0]; [ce setBuffer:idxbuf offset:0 atIndex:1];
            [ce setBuffer:outbuf offset:0 atIndex:2]; [ce setTexture:tex atIndex:0];
        }, &fc, &errs);
        float got = *(const float *)[outbuf contents];
        rec(@{@"family":@"fd",@"case":@"oob_baseline_after",@"observed":F(got),@"oracle":F(fref),
              @"match":@(got == fref),
              @"outcome":(classify(errs,fc) ?: (got == fref ? @"ok" : @"wrong_value")),
              @"fault_class":fc,@"cb_errors":@(errs),@"target":@"G17P",
              @"note":@"baseline re-validation after the out-of-table arm"});
        rec(@{@"family":@"fd",@"case":@"__done",@"outcome":@"ok",@"target":@"G17P"});
        return 0;
    }
    fprintf(stderr, "unknown mode %s\n", argv[2]);
    return 2;
  }
}
