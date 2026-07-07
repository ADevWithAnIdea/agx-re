// ivar.m — parametric OWN Metal harness for INDIRECT (device-generated) commands.
//
// Part of EXP-0027 (cmdstream completeness: indirect commands). Extends EXP-0014's
// dvar.m / EXP-0011's cvar.m. Three families of "indirect" that we distinguish:
//
//   (A) draw with args-in-a-buffer:
//         drawPrimitives:indirectBuffer:            (MTLDrawPrimitivesIndirectArguments)
//         drawIndexedPrimitives:...indirectBuffer:  (MTLDrawIndexedPrimitivesIndirectArguments)
//   (B) dispatch with args-in-a-buffer:
//         dispatchThreadgroupsWithIndirectBuffer:   (MTLDispatchThreadgroupsIndirectArguments)
//   (C) full MTLIndirectCommandBuffer (ICB): encoded commands the GPU/shader consumes,
//         populated CPU-side here, executed with executeCommandsInBuffer:withRange:.
//
// The method is change-one-parameter: run the DIRECT form and the INDIRECT form with an
// otherwise byte-identical setup, capture the registered GPU BOs under the iotrace
// interposer, and byte-diff. We print the GPU VA of the indirect-args buffer / index
// buffer / ICB so the captured bytes can be correlated to a known VA.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API only. Our own MSL, compiled at runtime.
// Nothing disassembles any Apple binary. We only log DATA (our command buffers).
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o ivar ivar.m
//
// Usage:
//   ivar --mode MODE [--indexed] [--verts N] [--inst N] [--prim P]
//        [--gx N --gy N --gz N] [--tg N] [--icbn N] [--dump]
//   MODE : draw_direct | draw_indirect | disp_direct | disp_indirect | icb_draw | icb_disp
//   --icbn : number of commands to encode into the ICB (default 1)

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *label, uint64_t va) {
    printf("VA %-12s = 0x%016llx\n", label, (unsigned long long)va);
}

// ---- own MSL: minimal VS+FS and a minimal compute kernel ----
static NSString *gsrc(void) {
    return @"#include <metal_stdlib>\nusing namespace metal;\n"
            "struct VO { float4 pos [[position]]; float4 col; };\n"
            "vertex VO v_main(uint vid [[vertex_id]], const device float2* p [[buffer(0)]]) {\n"
            "  VO o; o.pos = float4(p[vid],0,1); o.col = float4(0.25,0.5,0.75,1); return o; }\n"
            "fragment float4 f_main(VO in [[stage_in]]) { return in.col; }\n";
}
static NSString *csrc(void) {
    return @"#include <metal_stdlib>\nusing namespace metal;\n"
            "kernel void c_main(device float* o [[buffer(0)]], const device float* a [[buffer(1)]],\n"
            "                   uint i [[thread_position_in_grid]]) { o[i] = a[i] + 3.0f; }\n";
}

static MTLPrimitiveType parse_prim(const char *s) {
    if (!strcmp(s,"point")) return MTLPrimitiveTypePoint;
    if (!strcmp(s,"line"))  return MTLPrimitiveTypeLine;
    if (!strcmp(s,"strip")) return MTLPrimitiveTypeTriangleStrip;
    return MTLPrimitiveTypeTriangle;
}

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *modeS="draw_direct", *primS="tri";
        long verts=3, inst=1, gx=64, gy=1, gz=1, tg=32, icbn=1;
        int indexed=0, doDump=0;
        for (int i=1;i<argc;i++){
            if(!strcmp(argv[i],"--mode")&&i+1<argc) modeS=argv[++i];
            else if(!strcmp(argv[i],"--prim")&&i+1<argc) primS=argv[++i];
            else if(!strcmp(argv[i],"--verts")&&i+1<argc) verts=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--inst")&&i+1<argc) inst=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--gx")&&i+1<argc) gx=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--gy")&&i+1<argc) gy=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--gz")&&i+1<argc) gz=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--tg")&&i+1<argc) tg=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--icbn")&&i+1<argc) icbn=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--indexed")) indexed=1;
            else if(!strcmp(argv[i],"--dump")) doDump=1;
        }
        MTLPrimitiveType prim=parse_prim(primS);
        id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
        printf("DEVICE %s\n",[[dev name] UTF8String]);
        printf("CONFIG mode=%s indexed=%ld prim=%s verts=%ld inst=%ld grid=(%ld,%ld,%ld) tg=%ld icbn=%ld\n",
               modeS,(long)indexed,primS,verts,inst,gx,gy,gz,tg,icbn);
        NSError *err=nil;
        id<MTLCommandQueue> q=[dev newCommandQueue];

        int isDraw = strncmp(modeS,"draw",4)==0 || strcmp(modeS,"icb_draw")==0;
        int isDisp = strncmp(modeS,"disp",4)==0 || strcmp(modeS,"icb_disp")==0;
        int isICB  = strncmp(modeS,"icb",3)==0;
        int isIndirectArgs = strstr(modeS,"indirect")!=NULL;

        // -------------------- DRAW families --------------------
        if (isDraw) {
            id<MTLLibrary> gl=[dev newLibraryWithSource:gsrc() options:nil error:&err];
            if(!gl){ printf("LIB_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
            MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
            pd.vertexFunction=[gl newFunctionWithName:@"v_main"];
            pd.fragmentFunction=[gl newFunctionWithName:@"f_main"];
            pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
            if(isICB) pd.supportIndirectCommandBuffers=YES;   // required for ICB setRenderPipelineState
            id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
            if(!pso){ printf("PSO_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

            long W=64,H=64,bpp=4; NSUInteger bpr=((W*bpp)+255)&~255UL;
            MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
            td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
            id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
            id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
            print_va("rtBuf",[rtb gpuAddress]);

            long nv=verts>0?verts:3;
            id<MTLBuffer> vb=[dev newBufferWithLength:(NSUInteger)(nv*8) options:MTLResourceStorageModeShared];
            float *vp=(float*)[vb contents]; vp[0]=-1;vp[1]=-1; vp[2]=3;vp[3]=-1; vp[4]=-1;vp[5]=3;
            print_va("vtxBuf",[vb gpuAddress]);

            id<MTLBuffer> ib=nil;
            if(indexed){ ib=[dev newBufferWithLength:(NSUInteger)(nv*2) options:MTLResourceStorageModeShared];
                uint16_t*ip=(uint16_t*)[ib contents]; for(long i=0;i<nv;i++) ip[i]=(uint16_t)i;
                print_va("idxBuf",[ib gpuAddress]); }

            // indirect-args buffer (args-in-buffer families) — DISTINCTIVE values for correlation
            id<MTLBuffer> argb=nil;
            if(isIndirectArgs){
                argb=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
                uint32_t*a=(uint32_t*)[argb contents]; memset(a,0,64);
                if(indexed){ // MTLDrawIndexedPrimitivesIndirectArguments
                    a[0]=(uint32_t)nv;   // indexCount
                    a[1]=(uint32_t)inst; // instanceCount
                    a[2]=0;              // indexStart
                    a[3]=0;              // baseVertex
                    a[4]=0;              // baseInstance
                } else {             // MTLDrawPrimitivesIndirectArguments
                    a[0]=(uint32_t)nv;   // vertexCount
                    a[1]=(uint32_t)inst; // instanceCount
                    a[2]=0;              // vertexStart
                    a[3]=0;              // baseInstance
                }
                print_va("argBuf",[argb gpuAddress]);
            }

            // ICB
            id<MTLIndirectCommandBuffer> icb=nil;
            if(isICB){
                MTLIndirectCommandBufferDescriptor *icbd=[MTLIndirectCommandBufferDescriptor new];
                icbd.commandTypes=MTLIndirectCommandTypeDraw;
                icbd.inheritBuffers=NO; icbd.inheritPipelineState=NO;
                icbd.maxVertexBufferBindCount=1; icbd.maxFragmentBufferBindCount=0;
                icb=[dev newIndirectCommandBufferWithDescriptor:icbd maxCommandCount:(NSUInteger)icbn options:0];
                for(long c=0;c<icbn;c++){
                    id<MTLIndirectRenderCommand> rc=[icb indirectRenderCommandAtIndex:(NSUInteger)c];
                    [rc setRenderPipelineState:pso];
                    [rc setVertexBuffer:vb offset:0 atIndex:0];
                    if(indexed) [rc drawIndexedPrimitives:prim indexCount:(NSUInteger)nv indexType:MTLIndexTypeUInt16
                                     indexBuffer:ib indexBufferOffset:0 instanceCount:(NSUInteger)inst baseVertex:0 baseInstance:0];
                    else        [rc drawPrimitives:prim vertexStart:0 vertexCount:(NSUInteger)nv
                                     instanceCount:(NSUInteger)inst baseInstance:0];
                }
                // ICB is a MTLResource; report its residency handle for the record
                printf("ICB created maxCount=%ld cmds=%ld\n", icbn, icbn);
            }

            MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor new];
            rp.colorAttachments[0].texture=target;
            rp.colorAttachments[0].loadAction=MTLLoadActionClear;
            rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);
            rp.colorAttachments[0].storeAction=MTLStoreActionStore;
            id<MTLCommandBuffer> cb=[q commandBuffer];
            id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
            MTLViewport vpt={0,0,(double)W,(double)H,0,1}; [enc setViewport:vpt];
            if(isICB){
                [enc useResource:vb usage:MTLResourceUsageRead];
                [enc setRenderPipelineState:pso];
                [enc executeCommandsInBuffer:icb withRange:NSMakeRange(0,(NSUInteger)icbn)];
            } else {
                [enc setRenderPipelineState:pso];
                [enc setVertexBuffer:vb offset:0 atIndex:0];
                if(isIndirectArgs){
                    if(indexed) [enc drawIndexedPrimitives:prim indexType:MTLIndexTypeUInt16 indexBuffer:ib
                                     indexBufferOffset:0 indirectBuffer:argb indirectBufferOffset:0];
                    else        [enc drawPrimitives:prim indirectBuffer:argb indirectBufferOffset:0];
                } else {
                    if(indexed) [enc drawIndexedPrimitives:prim indexCount:(NSUInteger)nv indexType:MTLIndexTypeUInt16
                                     indexBuffer:ib indexBufferOffset:0 instanceCount:(NSUInteger)inst];
                    else        [enc drawPrimitives:prim vertexStart:0 vertexCount:(NSUInteger)nv instanceCount:(NSUInteger)inst];
                }
            }
            [enc endEncoding];
            [cb commit]; [cb waitUntilCompleted];
            printf("SUBMIT done status=%ld\n",(long)[cb status]);
            unsigned char px[4]={0}; [target getBytes:px bytesPerRow:bpr fromRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0];
            printf("PIXEL b0..3=%02x%02x%02x%02x\n",px[0],px[1],px[2],px[3]);
            if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
            return 0;
        }

        // -------------------- DISPATCH families --------------------
        if (isDisp) {
            id<MTLLibrary> cl=[dev newLibraryWithSource:csrc() options:nil error:&err];
            if(!cl){ printf("LIB_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
            MTLComputePipelineDescriptor *cpd=[MTLComputePipelineDescriptor new];
            cpd.computeFunction=[cl newFunctionWithName:@"c_main"];
            if(isICB) cpd.supportIndirectCommandBuffers=YES;
            id<MTLComputePipelineState> cps=[dev newComputePipelineStateWithDescriptor:cpd options:0 reflection:nil error:&err];
            if(!cps){ printf("CPS_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

            long n=gx*gy*gz; if(n<1)n=1;
            id<MTLBuffer> ob=[dev newBufferWithLength:(NSUInteger)(n*4+256) options:MTLResourceStorageModeShared];
            id<MTLBuffer> ab=[dev newBufferWithLength:(NSUInteger)(n*4+256) options:MTLResourceStorageModeShared];
            print_va("outBuf",[ob gpuAddress]); print_va("inBuf",[ab gpuAddress]);

            id<MTLBuffer> argb=nil;
            if(isIndirectArgs){
                argb=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
                uint32_t*a=(uint32_t*)[argb contents]; memset(a,0,64);
                a[0]=(uint32_t)gx; a[1]=(uint32_t)gy; a[2]=(uint32_t)gz; // MTLDispatchThreadgroupsIndirectArguments
                print_va("argBuf",[argb gpuAddress]);
            }

            id<MTLIndirectCommandBuffer> icb=nil;
            if(isICB){
                MTLIndirectCommandBufferDescriptor *icbd=[MTLIndirectCommandBufferDescriptor new];
                icbd.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;
                icbd.inheritBuffers=NO; icbd.inheritPipelineState=NO;
                icbd.maxKernelBufferBindCount=2;
                icb=[dev newIndirectCommandBufferWithDescriptor:icbd maxCommandCount:(NSUInteger)icbn options:0];
                for(long c=0;c<icbn;c++){
                    id<MTLIndirectComputeCommand> cc=[icb indirectComputeCommandAtIndex:(NSUInteger)c];
                    [cc setComputePipelineState:cps];
                    [cc setKernelBuffer:ob offset:0 atIndex:0];
                    [cc setKernelBuffer:ab offset:0 atIndex:1];
                    MTLSize gsz={(NSUInteger)gx/ (NSUInteger)tg > 0 ? (NSUInteger)(gx/tg) : 1,1,1};
                    MTLSize tsz={(NSUInteger)tg,1,1};
                    [cc concurrentDispatchThreadgroups:gsz threadsPerThreadgroup:tsz];
                }
                printf("ICB created maxCount=%ld cmds=%ld\n", icbn, icbn);
            }

            id<MTLCommandBuffer> cb=[q commandBuffer];
            id<MTLComputeCommandEncoder> ce=[cb computeCommandEncoder];
            if(isICB){
                [ce useResource:ob usage:MTLResourceUsageWrite];
                [ce useResource:ab usage:MTLResourceUsageRead];
                [ce executeCommandsInBuffer:icb withRange:NSMakeRange(0,(NSUInteger)icbn)];
            } else {
                [ce setComputePipelineState:cps];
                [ce setBuffer:ob offset:0 atIndex:0];
                [ce setBuffer:ab offset:0 atIndex:1];
                MTLSize tsz={(NSUInteger)tg,1,1};
                if(isIndirectArgs){
                    [ce dispatchThreadgroupsWithIndirectBuffer:argb indirectBufferOffset:0 threadsPerThreadgroup:tsz];
                } else {
                    MTLSize gsz={(NSUInteger)(gx/tg>0?gx/tg:1),(NSUInteger)gy,(NSUInteger)gz};
                    [ce dispatchThreadgroups:gsz threadsPerThreadgroup:tsz];
                }
            }
            [ce endEncoding];
            [cb commit]; [cb waitUntilCompleted];
            printf("SUBMIT done status=%ld\n",(long)[cb status]);
            float *o=(float*)[ob contents]; printf("OUT o[0]=%f o[1]=%f\n",o[0],o[1]);
            if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
            return 0;
        }

        printf("ARGERR unknown mode %s\n", modeS);
        return 2;
    }
}
