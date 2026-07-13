// agxrunlink.m — clean-room LINKED-pipeline hardware round-trip runner (EXP-M5-18).
//
// Sibling of tools/agxtest/agxrun.m. agxrun cannot dispatch a kernel that calls a
// `visible_function_table`: it needs the pipeline built with linkedFunctions AND a
// MTLVisibleFunctionTable bound at an argument index. This tool does both, forcing
// the pipeline to come FROM the (possibly byte-spliced) binary archive
// (MTLPipelineOptionFailOnBinaryArchiveMiss) so we can splice-and-observe the real
// out-of-line CALL machine code executing on hardware.
//
// CLEAN-ROOM: only the *public* Metal API on OUR OWN compiled MSL (the archive was
// built by shdumplink from our own source, possibly spliced out-of-band). Never
// disassembles/introspects any Apple binary.
//
// Build (device, CLT only):
//   clang -fobjc-arc -framework Metal -framework Foundation -o agxrunlink agxrunlink.m
//
// Usage:
//   agxrunlink --archive A.bin --source S.metal --function k --grid N --tg T \
//       --buf IDX=FILE ... --out IDX=NBYTES ... \
//       --vft TABLEBUFIDX=fnName0,fnName1,...   (fill vft slots 0.. with these fns)
//
// Same stdout protocol as agxrun (STATUS/OUT/GPUTIME_NS/...).

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void emit_status(const char *s) { printf("STATUS %s\n", s); }
static void fail(const char *status, const char *msg, NSError *err) {
    emit_status(status);
    if (err) printf("ERROR %s: %s\n", msg, [[err localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    fflush(stdout); exit(1);
}

typedef struct { int index; const char *path; } InBuf;
typedef struct { int index; long size; } OutBuf;

enum { OPT_NO_FAST_MATH = 128, OPT_VFT };
static const struct option longOpts[] = {
    {"archive", required_argument, NULL, 'a'},
    {"source",  required_argument, NULL, 's'},
    {"function",required_argument, NULL, 'f'},
    {"grid",    required_argument, NULL, 'g'},
    {"tg",      required_argument, NULL, 't'},
    {"buf",     required_argument, NULL, 'b'},
    {"out",     required_argument, NULL, 'o'},
    {"vft",     required_argument, NULL, OPT_VFT},
    {"no-fast-math", no_argument,  NULL, OPT_NO_FAST_MATH},
    {NULL, 0, NULL, 0}
};

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *archivePath=NULL, *sourcePath=NULL, *funcName=NULL;
        long grid=1, tg=1; BOOL fastMath=YES;
        InBuf ins[64]; int nins=0; OutBuf outs[64]; int nouts=0;
        int vftIndex = -1; char *vftFns = NULL;   // comma list of function names
        int c;
        while ((c = getopt_long(argc, argv, "a:s:f:g:t:b:o:", longOpts, NULL)) > 0) {
            switch (c) {
                case 'a': archivePath=optarg; break;
                case 's': sourcePath=optarg; break;
                case 'f': funcName=optarg; break;
                case 'g': grid=strtol(optarg,NULL,0); break;
                case 't': tg=strtol(optarg,NULL,0); break;
                case OPT_NO_FAST_MATH: fastMath=NO; break;
                case 'b': { char *eq=strchr(optarg,'='); if(!eq) fail("PIPELINE_FAIL","bad --buf",nil);
                    *eq=0; ins[nins].index=(int)strtol(optarg,NULL,0); ins[nins].path=eq+1; nins++; break; }
                case 'o': { char *eq=strchr(optarg,'='); if(!eq) fail("PIPELINE_FAIL","bad --out",nil);
                    *eq=0; outs[nouts].index=(int)strtol(optarg,NULL,0); outs[nouts].size=strtol(eq+1,NULL,0); nouts++; break; }
                case OPT_VFT: { char *eq=strchr(optarg,'='); if(!eq) fail("PIPELINE_FAIL","bad --vft (want IDX=fn0,fn1)",nil);
                    *eq=0; vftIndex=(int)strtol(optarg,NULL,0); vftFns=strdup(eq+1); break; }
                default: fprintf(stderr,"usage: see header\n"); return 1;
            }
        }
        if (!archivePath||!sourcePath||!funcName) fail("PIPELINE_FAIL","need --archive --source --function",nil);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) fail("PIPELINE_FAIL","no Metal device",nil);
        printf("DEVICE %s\n", [[dev name] UTF8String]);

        NSError *err=nil;
        NSString *src=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                                encoding:NSUTF8StringEncoding error:&err];
        if(!src) fail("COMPILE_FAIL","read source",err);
        MTLCompileOptions *copts=[MTLCompileOptions new]; [copts setFastMathEnabled:fastMath];
        id<MTLLibrary> lib=[dev newLibraryWithSource:src options:copts error:&err];
        if(!lib) fail("COMPILE_FAIL","newLibraryWithSource",err);
        id<MTLFunction> fn=[lib newFunctionWithName:[NSString stringWithUTF8String:funcName]];
        if(!fn) fail("FUNCTION_MISSING","newFunctionWithName",nil);

        // Collect the visible functions named for the table (in order) + all visibles for linking.
        NSMutableArray *tableFns=[NSMutableArray array];
        NSMutableArray *allVisible=[NSMutableArray array];
        for (NSString *n in [lib functionNames]) {
            id<MTLFunction> vf=[lib newFunctionWithName:n];
            if (vf && [vf functionType]==MTLFunctionTypeVisible) [allVisible addObject:vf];
        }
        if (vftFns) {
            char *tok=strtok(vftFns, ",");
            while(tok){ id<MTLFunction> vf=[lib newFunctionWithName:[NSString stringWithUTF8String:tok]];
                if(!vf) fail("FUNCTION_MISSING","vft function not found",nil);
                [tableFns addObject:vf]; tok=strtok(NULL,","); }
        }

        // Load the (possibly spliced) archive.
        MTLBinaryArchiveDescriptor *adesc=[MTLBinaryArchiveDescriptor new];
        [adesc setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:archivePath]]];
        id<MTLBinaryArchive> archive=[dev newBinaryArchiveWithDescriptor:adesc error:&err];
        if(!archive) fail("ARCHIVE_FAIL","newBinaryArchiveWithDescriptor",err);

        // Build the LINKED pipeline FROM the archive.
        MTLComputePipelineDescriptor *pdesc=[MTLComputePipelineDescriptor new];
        [pdesc setComputeFunction:fn];
        if ([allVisible count]>0) {
            MTLLinkedFunctions *lf=[MTLLinkedFunctions linkedFunctions];
            [lf setFunctions:allVisible];
            [pdesc setLinkedFunctions:lf];
        }
        [pdesc setBinaryArchives:@[archive]];
        id<MTLComputePipelineState> pso=
            [dev newComputePipelineStateWithDescriptor:pdesc
                                               options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                            reflection:nil error:&err];
        if(!pso) fail("PIPELINE_MISS","newComputePipelineStateWithDescriptor (FailOnBinaryArchiveMiss)",err);
        printf("FUNCTION %s\n", funcName);
        printf("PIPELINE_SOURCE archive\n");

        // Build the visible function table if requested.
        id<MTLVisibleFunctionTable> table=nil;
        if (vftIndex>=0 && [tableFns count]>0) {
            MTLVisibleFunctionTableDescriptor *td=[MTLVisibleFunctionTableDescriptor new];
            [td setFunctionCount:[tableFns count]];
            table=[pso newVisibleFunctionTableWithDescriptor:td];
            if(!table) fail("PIPELINE_FAIL","newVisibleFunctionTable",nil);
            for (NSUInteger i=0;i<[tableFns count];i++){
                id<MTLFunctionHandle> h=[pso functionHandleWithFunction:tableFns[i]];
                if(!h) fail("PIPELINE_FAIL","functionHandleWithFunction",nil);
                [table setFunction:h atIndex:i];
            }
        }

        id<MTLCommandQueue> queue=[dev newCommandQueue];
        id<MTLBuffer> bufs[64]={0};
        for(int i=0;i<nins;i++){
            NSData *d=[NSData dataWithContentsOfFile:[NSString stringWithUTF8String:ins[i].path]];
            if(!d) fail("PIPELINE_FAIL","read input buffer file",nil);
            bufs[ins[i].index]=[dev newBufferWithBytes:[d bytes] length:[d length] options:MTLResourceStorageModeShared];
        }
        for(int i=0;i<nouts;i++){ int idx=outs[i].index;
            if(!bufs[idx]) bufs[idx]=[dev newBufferWithLength:outs[i].size options:MTLResourceStorageModeShared]; }

        id<MTLCommandBuffer> cb=[queue commandBuffer];
        id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        for(int i=0;i<64;i++) if(bufs[i]) [enc setBuffer:bufs[i] offset:0 atIndex:i];
        if (table) {
            [enc setVisibleFunctionTable:table atBufferIndex:vftIndex];
            // Callees may read/write the same device buffers -> mark resident.
            for(int i=0;i<64;i++) if(bufs[i]) [enc useResource:bufs[i] usage:MTLResourceUsageRead|MTLResourceUsageWrite];
        }
        [enc dispatchThreads:MTLSizeMake(grid,1,1) threadsPerThreadgroup:MTLSizeMake(tg,1,1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if([cb status]==MTLCommandBufferStatusError) fail("CMDBUF_ERROR","command buffer failed",[cb error]);
        printf("GPUTIME_NS %llu\n",(unsigned long long)(([cb GPUEndTime]-[cb GPUStartTime])*1e9));

        for(int i=0;i<nouts;i++){ int idx=outs[i].index;
            const unsigned char *p=(const unsigned char*)[bufs[idx] contents]; long n=outs[i].size;
            char *hex=(char*)malloc(n*2+1); static const char H[]="0123456789abcdef";
            for(long j=0;j<n;j++){hex[j*2]=H[p[j]>>4];hex[j*2+1]=H[p[j]&0xf];} hex[n*2]=0;
            printf("OUT %d %s\n",idx,hex); free(hex); }
        emit_status("OK"); fflush(stdout); return 0;
    }
}
