// agxrender2.m — EXP-M5-17 extension of agxrender.m (clean-room OWN-SHADER render
// round-trip). Adds multi-texel / second-texture / second-sampler / mipmap binding
// so texture SAMPLE/READ operand fields can be resolved by an observed PIXEL delta.
//
// CLEAN-ROOM: uses only the *public* Metal API on OUR OWN compiled shader + OUR OWN
// texture data. It never disassembles or introspects any Apple binary. Splice-and-
// reload mirrors the public MIT applegpu hwtestbed; this is our own impl.
//
// Build (device, CLT only):
//   clang -fobjc-arc -framework Metal -framework Foundation -o agxrender2 agxrender2.m
//
// Slot-0 texture (pick ONE):
//   --tex-fill R,G,B,A            1x1 solid (compat)
//   --tex0-2x2 c0:c1             2x2, row y=0 = c0, row y=1 = c1  (coord matters, nearest)
//   --tex0-mip c0:c1            2x2 mipmapped: level0=c0, level1=c1 (LOD matters)
// Slot-1 texture:
//   --tex1-fill R,G,B,A          1x1 solid at [texture(1)]
// Samplers (each c = "nearest"|"linear"; default slot0=nearest):
//   --samp0 MODE  --samp1 MODE   bind sampler at [sampler(0)] / [sampler(1)]
// Each color c is "R,G,B,A" in 0..255.
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
    if (err)      printf("ERROR %s: %s\n", msg, [[err localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    fflush(stdout);
    exit(1);
}

static void parse_rgba(const char *s, unsigned char out[4]) {
    int r=0,g=0,b=0,a=255;
    sscanf(s, "%d,%d,%d,%d", &r,&g,&b,&a);
    out[0]=(unsigned char)r; out[1]=(unsigned char)g; out[2]=(unsigned char)b; out[3]=(unsigned char)a;
}
// "c0:c1" -> two rgba
static void parse_pair(const char *s, unsigned char c0[4], unsigned char c1[4]) {
    char buf[128]; strncpy(buf, s, sizeof(buf)-1); buf[sizeof(buf)-1]=0;
    char *colon = strchr(buf, ':');
    if (colon) { *colon = 0; parse_rgba(buf, c0); parse_rgba(colon+1, c1); }
    else { parse_rgba(buf, c0); memcpy(c1, c0, 4); }
}
// spec = "FILTER" or "FILTER:ADDRESS"; FILTER in {nearest,linear}, ADDRESS in {clamp,repeat,mirror}
static MTLSamplerMinMagFilter filt(const char *m) {
    return (m && strncmp(m,"linear",6)==0) ? MTLSamplerMinMagFilterLinear
                                           : MTLSamplerMinMagFilterNearest;
}
static MTLSamplerAddressMode addr(const char *m) {
    const char *c = m ? strchr(m,':') : NULL;
    if (!c) return MTLSamplerAddressModeClampToEdge;
    c++;
    if (strcmp(c,"repeat")==0) return MTLSamplerAddressModeRepeat;
    if (strcmp(c,"mirror")==0) return MTLSamplerAddressModeMirrorRepeat;
    return MTLSamplerAddressModeClampToEdge;
}

enum { OPT_WIDTH=128, OPT_HEIGHT, OPT_TEXFILL, OPT_T0_2X2, OPT_T0_MIP,
       OPT_T1_FILL, OPT_SAMP0, OPT_SAMP1, OPT_NO_FAST_MATH };
#define REQ required_argument
static const struct option longOpts[] = {
    {"archive",REQ,0,'a'},{"source",REQ,0,'s'},{"vertex",REQ,0,'v'},{"fragment",REQ,0,'f'},
    {"width",REQ,0,OPT_WIDTH},{"height",REQ,0,OPT_HEIGHT},
    {"tex-fill",REQ,0,OPT_TEXFILL},{"tex0-2x2",REQ,0,OPT_T0_2X2},{"tex0-mip",REQ,0,OPT_T0_MIP},
    {"tex1-fill",REQ,0,OPT_T1_FILL},{"samp0",REQ,0,OPT_SAMP0},{"samp1",REQ,0,OPT_SAMP1},
    {"no-fast-math",no_argument,0,OPT_NO_FAST_MATH},{0,0,0,0}
};

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *archivePath=NULL,*sourcePath=NULL,*vName=NULL,*fName=NULL;
        long W=1,H=1; BOOL fastMath=YES;
        int t0mode=0;                      // 0=none 1=solid 2=2x2 3=mip
        unsigned char t0c0[4]={0,0,0,255}, t0c1[4]={0,0,0,255};
        BOOL bindT1=NO; unsigned char t1c[4]={0,0,0,255};
        const char *samp0=NULL,*samp1=NULL;   // NULL => not bound
        int c;
        while ((c=getopt_long(argc,argv,"a:s:v:f:",longOpts,NULL))>0) {
            switch(c){
                case 'a':archivePath=optarg;break; case 's':sourcePath=optarg;break;
                case 'v':vName=optarg;break; case 'f':fName=optarg;break;
                case OPT_WIDTH:W=strtol(optarg,0,0);break; case OPT_HEIGHT:H=strtol(optarg,0,0);break;
                case OPT_NO_FAST_MATH:fastMath=NO;break;
                case OPT_TEXFILL: t0mode=1; parse_rgba(optarg,t0c0); memcpy(t0c1,t0c0,4);
                                  if(!samp0)samp0="nearest"; break;
                case OPT_T0_2X2:  t0mode=2; parse_pair(optarg,t0c0,t0c1);
                                  if(!samp0)samp0="nearest"; break;
                case OPT_T0_MIP:  t0mode=3; parse_pair(optarg,t0c0,t0c1);
                                  if(!samp0)samp0="nearest"; break;
                case OPT_T1_FILL: bindT1=YES; parse_rgba(optarg,t1c); break;
                case OPT_SAMP0:   samp0=optarg; break;
                case OPT_SAMP1:   samp1=optarg; break;
                default: fprintf(stderr,"bad arg\n"); return 1;
            }
        }
        if(!archivePath||!sourcePath||!vName||!fName)
            fail("PIPELINE_FAIL","need --archive --source --vertex --fragment",nil);

        id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
        if(!dev) fail("PIPELINE_FAIL","no Metal device",nil);
        printf("DEVICE %s\n",[[dev name] UTF8String]);
        NSError *err=nil;

        NSString *src=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                                encoding:NSUTF8StringEncoding error:&err];
        if(!src) fail("COMPILE_FAIL","read source",err);
        MTLCompileOptions *copts=[MTLCompileOptions new]; [copts setFastMathEnabled:fastMath];
        id<MTLLibrary> lib=[dev newLibraryWithSource:src options:copts error:&err];
        if(!lib) fail("COMPILE_FAIL","newLibraryWithSource",err);
        id<MTLFunction> vfn=[lib newFunctionWithName:[NSString stringWithUTF8String:vName]];
        id<MTLFunction> ffn=[lib newFunctionWithName:[NSString stringWithUTF8String:fName]];
        if(!vfn||!ffn) fail("FUNCTION_MISSING","newFunctionWithName",nil);

        MTLBinaryArchiveDescriptor *adesc=[MTLBinaryArchiveDescriptor new];
        [adesc setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:archivePath]]];
        id<MTLBinaryArchive> archive=[dev newBinaryArchiveWithDescriptor:adesc error:&err];
        if(!archive) fail("ARCHIVE_FAIL","newBinaryArchiveWithDescriptor",err);

        MTLRenderPipelineDescriptor *pdesc=[MTLRenderPipelineDescriptor new];
        [pdesc setVertexFunction:vfn]; [pdesc setFragmentFunction:ffn];
        pdesc.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
        [pdesc setBinaryArchives:@[archive]];
        id<MTLRenderPipelineState> pso=
            [dev newRenderPipelineStateWithDescriptor:pdesc
                                              options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                           reflection:nil error:&err];
        if(!pso) fail("PIPELINE_MISS","newRenderPipelineState (FailOnBinaryArchiveMiss)",err);
        printf("VERTEX %s\nFRAGMENT %s\nPIPELINE_SOURCE archive\n",vName,fName);

        // Render target.
        MTLTextureDescriptor *td=
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                               width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
        td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
        id<MTLTexture> target=[dev newTextureWithDescriptor:td];

        // Slot-0 input texture.
        id<MTLTexture> tex0=nil;
        if(t0mode==1){
            MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:1 height:1 mipmapped:NO];
            d.usage=MTLTextureUsageShaderRead; d.storageMode=MTLStorageModeShared;
            tex0=[dev newTextureWithDescriptor:d];
            [tex0 replaceRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0 withBytes:t0c0 bytesPerRow:4];
        } else if(t0mode==2){
            MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:2 height:2 mipmapped:NO];
            d.usage=MTLTextureUsageShaderRead; d.storageMode=MTLStorageModeShared;
            tex0=[dev newTextureWithDescriptor:d];
            // row y=0 -> c0, row y=1 -> c1  (nearest: uv 0.25->texel row0, 0.75->row1)
            unsigned char px[16];
            memcpy(px+0,t0c0,4); memcpy(px+4,t0c0,4);   // y=0
            memcpy(px+8,t0c1,4); memcpy(px+12,t0c1,4);  // y=1
            [tex0 replaceRegion:MTLRegionMake2D(0,0,2,2) mipmapLevel:0 withBytes:px bytesPerRow:8];
        } else if(t0mode==3){
            MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:2 height:2 mipmapped:YES];
            d.usage=MTLTextureUsageShaderRead; d.storageMode=MTLStorageModeShared;
            tex0=[dev newTextureWithDescriptor:d];
            unsigned char l0[16]; for(int i=0;i<4;i++) memcpy(l0+i*4,t0c0,4);
            [tex0 replaceRegion:MTLRegionMake2D(0,0,2,2) mipmapLevel:0 withBytes:l0 bytesPerRow:8]; // level0=c0
            [tex0 replaceRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:1 withBytes:t0c1 bytesPerRow:4]; // level1=c1
        }

        // Slot-1 input texture.
        id<MTLTexture> tex1=nil;
        if(bindT1){
            MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:2 height:2 mipmapped:NO];
            d.usage=MTLTextureUsageShaderRead; d.storageMode=MTLStorageModeShared;
            tex1=[dev newTextureWithDescriptor:d];
            unsigned char px[16]; for(int i=0;i<4;i++) memcpy(px+i*4,t1c,4);
            [tex1 replaceRegion:MTLRegionMake2D(0,0,2,2) mipmapLevel:0 withBytes:px bytesPerRow:8];
        }

        // Samplers.
        id<MTLSamplerState> s0=nil,s1=nil;
        if(samp0){ MTLSamplerDescriptor *sd=[MTLSamplerDescriptor new];
            sd.minFilter=filt(samp0); sd.magFilter=filt(samp0);
            sd.mipFilter=MTLSamplerMipFilterNearest;
            sd.sAddressMode=addr(samp0); sd.tAddressMode=addr(samp0); sd.rAddressMode=addr(samp0);
            s0=[dev newSamplerStateWithDescriptor:sd]; }
        if(samp1){ MTLSamplerDescriptor *sd=[MTLSamplerDescriptor new];
            sd.minFilter=filt(samp1); sd.magFilter=filt(samp1);
            sd.mipFilter=MTLSamplerMipFilterNearest;
            sd.sAddressMode=addr(samp1); sd.tAddressMode=addr(samp1); sd.rAddressMode=addr(samp1);
            s1=[dev newSamplerStateWithDescriptor:sd]; }

        MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor new];
        rp.colorAttachments[0].texture=target;
        rp.colorAttachments[0].loadAction=MTLLoadActionClear;
        rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
        rp.colorAttachments[0].storeAction=MTLStoreActionStore;

        id<MTLCommandQueue> queue=[dev newCommandQueue];
        id<MTLCommandBuffer> cb=[queue commandBuffer];
        id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        if(tex0)[enc setFragmentTexture:tex0 atIndex:0];
        if(tex1)[enc setFragmentTexture:tex1 atIndex:1];
        if(s0)[enc setFragmentSamplerState:s0 atIndex:0];
        if(s1)[enc setFragmentSamplerState:s1 atIndex:1];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
        if([cb status]==MTLCommandBufferStatusError)
            fail("CMDBUF_ERROR","command buffer failed",[cb error]);
        printf("GPUTIME_NS %llu\n",(unsigned long long)(([cb GPUEndTime]-[cb GPUStartTime])*1e9));

        printf("SIZE %ld %ld\n",W,H);
        unsigned char *px=(unsigned char*)malloc((size_t)W*H*4);
        [target getBytes:px bytesPerRow:(NSUInteger)(W*4)
              fromRegion:MTLRegionMake2D(0,0,(NSUInteger)W,(NSUInteger)H) mipmapLevel:0];
        for(long y=0;y<H;y++)for(long x=0;x<W;x++){
            unsigned char *p=px+(y*W+x)*4;
            printf("PIXEL %ld %ld bgra=%02x%02x%02x%02x rgba_unorm=%.3f,%.3f,%.3f,%.3f\n",
                   x,y,p[0],p[1],p[2],p[3],p[2]/255.0,p[1]/255.0,p[0]/255.0,p[3]/255.0);
        }
        free(px);
        emit_status("OK"); fflush(stdout); return 0;
    }
}
