// texrun.m — clean-room OWN-SHADER compute runner WITH a multi-slice input
// texture (EXP-M4-10 isa6). Analogue of agxrun.m, but it binds a non-2D input
// texture (2d_array / 3d / cube / cube_array / 2d_ms) at [[texture(0)]], with a
// DISTINCT known value per slice (layer/z/face/sample), so we can splice the
// texture op's dim/index bytes and observe which slice the HW reads.
//
// CLEAN-ROOM: public Metal API on OUR OWN compiled shader (archive from shdump).
// Never disassembles any Apple binary. Splice-and-reload = public hwtestbed method.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o texrun texrun.m
//
// Usage: texrun --archive A.bin --source S.metal --function k \
//               --texkind {array|3d|cube|cubearray|ms} --nslices N --out 0=NBYTES
//   Slice i is filled with float value (100 + i). Prints OUT <idx> <hex>.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif
static void emit_status(const char *s){printf("STATUS %s\n",s);}
static void fail(const char*st,const char*m,NSError*e){emit_status(st);
  if(e)printf("ERROR %s: %s\n",m,[[e localizedDescription]UTF8String]);
  else if(m)printf("ERROR %s\n",m); fflush(stdout); exit(1);}

typedef struct{int index;long size;}OutBuf;
typedef struct{int index;int val;}IBuf;   // one int32 input value at [[buffer(index)]]
enum{OPT_NO_FAST_MATH=128,OPT_TEXKIND,OPT_NSLICES,OPT_SIZE,OPT_IBUF};
static const struct option L[]={
  {"archive",required_argument,0,'a'},{"source",required_argument,0,'s'},
  {"function",required_argument,0,'f'},{"out",required_argument,0,'o'},
  {"texkind",required_argument,0,OPT_TEXKIND},{"nslices",required_argument,0,OPT_NSLICES},
  {"size",required_argument,0,OPT_SIZE},{"ibuf",required_argument,0,OPT_IBUF},
  {"no-fast-math",no_argument,0,OPT_NO_FAST_MATH},{0,0,0,0}};

int main(int argc,char*argv[]){@autoreleasepool{
  const char*archivePath=0,*sourcePath=0,*funcName=0,*texkind="array";
  long nslices=4, dim=1; BOOL fastMath=YES;
  OutBuf outs[16]; int nouts=0; int c;
  IBuf ibufs[16]; int nib=0;
  while((c=getopt_long(argc,argv,"a:s:f:o:",L,0))>0){switch(c){
    case 'a':archivePath=optarg;break; case 's':sourcePath=optarg;break;
    case 'f':funcName=optarg;break;
    case OPT_TEXKIND:texkind=optarg;break;
    case OPT_NSLICES:nslices=strtol(optarg,0,0);break;
    case OPT_SIZE:dim=strtol(optarg,0,0);break;
    case OPT_NO_FAST_MATH:fastMath=NO;break;
    case OPT_IBUF:{char*eq=strchr(optarg,'=');*eq=0;ibufs[nib].index=(int)strtol(optarg,0,0);
      ibufs[nib].val=(int)strtol(eq+1,0,0);nib++;break;}
    case 'o':{char*eq=strchr(optarg,'=');*eq=0;outs[nouts].index=(int)strtol(optarg,0,0);
      outs[nouts].size=strtol(eq+1,0,0);nouts++;break;}
    default:return 1;}}
  if(!archivePath||!sourcePath||!funcName)fail("PIPELINE_FAIL","need --archive --source --function",0);

  id<MTLDevice>dev=MTLCreateSystemDefaultDevice();
  if(!dev)fail("PIPELINE_FAIL","no Metal device",0);
  printf("DEVICE %s\n",[[dev name]UTF8String]);
  NSError*err=0;
  NSString*src=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                encoding:NSUTF8StringEncoding error:&err];
  if(!src)fail("COMPILE_FAIL","read source",err);
  MTLCompileOptions*co=[MTLCompileOptions new];[co setFastMathEnabled:fastMath];
  id<MTLLibrary>lib=[dev newLibraryWithSource:src options:co error:&err];
  if(!lib)fail("COMPILE_FAIL","newLibraryWithSource",err);
  id<MTLFunction>fn=[lib newFunctionWithName:[NSString stringWithUTF8String:funcName]];
  if(!fn)fail("FUNCTION_MISSING","newFunctionWithName",0);

  MTLBinaryArchiveDescriptor*ad=[MTLBinaryArchiveDescriptor new];
  [ad setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:archivePath]]];
  id<MTLBinaryArchive>ar=[dev newBinaryArchiveWithDescriptor:ad error:&err];
  if(!ar)fail("ARCHIVE_FAIL","newBinaryArchiveWithDescriptor",err);
  MTLComputePipelineDescriptor*pd=[MTLComputePipelineDescriptor new];
  [pd setComputeFunction:fn];[pd setBinaryArchives:@[ar]];
  id<MTLComputePipelineState>pso=[dev newComputePipelineStateWithDescriptor:pd
     options:MTLPipelineOptionFailOnBinaryArchiveMiss reflection:nil error:&err];
  if(!pso)fail("PIPELINE_MISS","FailOnBinaryArchiveMiss",err);
  printf("FUNCTION %s\nPIPELINE_SOURCE archive\n",funcName);

  // --- Build the input texture with distinct per-slice values (R32Float). ----
  MTLTextureDescriptor*td=[MTLTextureDescriptor new];
  td.pixelFormat=MTLPixelFormatR32Float; td.width=dim; td.height=dim; td.depth=1;
  td.mipmapLevelCount=1; td.usage=MTLTextureUsageShaderRead;
  td.storageMode=MTLStorageModeShared;
  int isMS=0, nfill=(int)nslices;
  if(!strcmp(texkind,"array")){td.textureType=MTLTextureType2DArray;td.arrayLength=nslices;}
  else if(!strcmp(texkind,"3d")){td.textureType=MTLTextureType3D;td.depth=nslices;}
  else if(!strcmp(texkind,"cube")){td.textureType=MTLTextureTypeCube;nfill=6;}
  else if(!strcmp(texkind,"cubearray")){td.textureType=MTLTextureTypeCubeArray;td.arrayLength=nslices;nfill=6*(int)nslices;}
  else if(!strcmp(texkind,"ms")){td.textureType=MTLTextureType2DMultisample;td.sampleCount=(nslices>=4?4:2);td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;isMS=1;}
  else fail("PIPELINE_FAIL","unknown texkind",0);
  id<MTLTexture>tex=[dev newTextureWithDescriptor:td];
  if(!tex)fail("PIPELINE_FAIL","newTextureWithDescriptor",0);

  if(!isMS){
    // Fill slice i (array layer / cube face / cube-array slice) or z with value 100+i.
    if(td.textureType==MTLTextureType3D){
      for(int z=0;z<nslices;z++){float v=100.0f+z;
        [tex replaceRegion:MTLRegionMake3D(0,0,z,dim,dim,1) mipmapLevel:0 slice:0
             withBytes:&v bytesPerRow:dim*4 bytesPerImage:dim*dim*4];}
    } else {
      for(int s=0;s<nfill;s++){float v=100.0f+s;
        [tex replaceRegion:MTLRegionMake2D(0,0,dim,dim) mipmapLevel:0 slice:s
             withBytes:&v bytesPerRow:dim*4 bytesPerImage:dim*dim*4];}
    }
  } else {
    // MSAA: cannot replaceRegion. Fill sample s with 100+s via a render pass that
    // draws with a per-sample fragment (setVisibilityResult not applicable). We
    // Distinguish samples: render a fullscreen triangle with a per-sample
    // fragment (references [[sample_id]] -> forces sample-rate shading), writing
    // value 100 + sample_id into each sample. OUR OWN inline MSL.
    NSString*fillsrc=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "vertex float4 vfill(uint v [[vertex_id]]){float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};return float4(p[v],0,1);}\n"
      "fragment float ffill(uint sid [[sample_id]]){return 100.0+float(sid);}\n";
    id<MTLLibrary>flib=[dev newLibraryWithSource:fillsrc options:[MTLCompileOptions new] error:&err];
    if(!flib)fail("COMPILE_FAIL","msaa fill lib",err);
    MTLRenderPipelineDescriptor*rpd=[MTLRenderPipelineDescriptor new];
    rpd.vertexFunction=[flib newFunctionWithName:@"vfill"];
    rpd.fragmentFunction=[flib newFunctionWithName:@"ffill"];
    rpd.colorAttachments[0].pixelFormat=MTLPixelFormatR32Float;
    rpd.rasterSampleCount=(NSUInteger)td.sampleCount;
    id<MTLRenderPipelineState>rpso=[dev newRenderPipelineStateWithDescriptor:rpd error:&err];
    if(!rpso)fail("PIPELINE_FAIL","msaa fill pso",err);
    MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture=tex;rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,0);
    rp.colorAttachments[0].storeAction=MTLStoreActionStore;  // store all samples
    id<MTLCommandQueue>q0=[dev newCommandQueue];id<MTLCommandBuffer>cb0=[q0 commandBuffer];
    id<MTLRenderCommandEncoder>e0=[cb0 renderCommandEncoderWithDescriptor:rp];
    [e0 setRenderPipelineState:rpso];
    [e0 drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [e0 endEncoding];[cb0 commit];[cb0 waitUntilCompleted];
    if([cb0 status]==MTLCommandBufferStatusError)fail("CMDBUF_ERROR","msaa fill draw",[cb0 error]);
  }

  id<MTLBuffer>bufs[16]={0};
  for(int i=0;i<nib;i++){int v=ibufs[i].val;
    bufs[ibufs[i].index]=[dev newBufferWithBytes:&v length:4 options:MTLResourceStorageModeShared];}
  for(int i=0;i<nouts;i++){if(!bufs[outs[i].index])bufs[outs[i].index]=[dev newBufferWithLength:outs[i].size
     options:MTLResourceStorageModeShared];}
  id<MTLCommandQueue>queue=[dev newCommandQueue];
  id<MTLCommandBuffer>cb=[queue commandBuffer];
  id<MTLComputeCommandEncoder>enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:pso];
  [enc setTexture:tex atIndex:0];
  for(int i=0;i<16;i++)if(bufs[i])[enc setBuffer:bufs[i] offset:0 atIndex:i];
  [enc dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  if([cb status]==MTLCommandBufferStatusError)fail("CMDBUF_ERROR","command buffer failed",[cb error]);
  printf("GPUTIME_NS %llu\n",(unsigned long long)(([cb GPUEndTime]-[cb GPUStartTime])*1e9));
  for(int i=0;i<nouts;i++){int idx=outs[i].index;const unsigned char*p=[bufs[idx]contents];
    long n=outs[i].size;char*h=malloc(n*2+1);static const char H[]="0123456789abcdef";
    for(long j=0;j<n;j++){h[j*2]=H[p[j]>>4];h[j*2+1]=H[p[j]&0xf];}h[n*2]=0;
    printf("OUT %d %s\n",idx,h);free(h);}
  emit_status("OK");fflush(stdout);return 0;
}}
