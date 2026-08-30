// pre-freeze feasibility pilot only (EXP-0159). Not evidence.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
int main(int argc,char**argv){@autoreleasepool{
  id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
  int N = argc>1?atoi(argv[1]):10000;
  NSMutableArray *keep=[NSMutableArray array];
  NSDate *t0=[NSDate date];
  // dedup check: two identical descriptors
  MTLSamplerDescriptor *d0=[MTLSamplerDescriptor new]; d0.supportArgumentBuffers=YES;
  id<MTLSamplerState> s0=[dev newSamplerStateWithDescriptor:d0];
  MTLSamplerDescriptor *d0b=[MTLSamplerDescriptor new]; d0b.supportArgumentBuffers=YES;
  id<MTLSamplerState> s0b=[dev newSamplerStateWithDescriptor:d0b];
  printf("DEDUP id_a=%llu id_b=%llu\n",(unsigned long long)s0.gpuResourceID._impl,(unsigned long long)s0b.gpuResourceID._impl);
  for(int i=0;i<N;i++){
    MTLSamplerDescriptor *d=[MTLSamplerDescriptor new];
    d.supportArgumentBuffers=YES;
    d.lodMaxClamp = 1.0f + (float)i;   // distinct descriptors
    id<MTLSamplerState> s=[dev newSamplerStateWithDescriptor:d];
    if(!s){printf("NIL_AT %d\n",i);break;}
    [keep addObject:s];
    if(i<4||i==N-1) printf("SAMP %d id=%llu\n",i,(unsigned long long)s.gpuResourceID._impl);
  }
  printf("MADE %lu elapsed=%.2f\n",(unsigned long)keep.count,-[t0 timeIntervalSinceNow]);
  return 0;}}
