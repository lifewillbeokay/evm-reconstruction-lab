import Foundation
import Metal
guard let device = MTLCreateSystemDefaultDevice() else { fatalError("A Metal-capable macOS device is required") }
let source = """
#include <metal_stdlib>
using namespace metal;
constant ulong rc[24]={0x0000000000000001UL,0x0000000000008082UL,0x800000000000808aUL,0x8000000080008000UL,0x000000000000808bUL,0x0000000080000001UL,0x8000000080008081UL,0x8000000000008009UL,0x000000000000008aUL,0x0000000000000088UL,0x0000000080008009UL,0x000000008000000aUL,0x000000008000808bUL,0x800000000000008bUL,0x8000000000008089UL,0x8000000000008003UL,0x8000000000008002UL,0x8000000000000080UL,0x000000000000800aUL,0x800000008000000aUL,0x8000000080008081UL,0x8000000000008080UL,0x0000000080000001UL,0x8000000080008008UL};
constant uint rot[24]={1,3,6,10,15,21,28,36,45,55,2,14,27,41,56,8,25,43,62,18,39,61,20,44};
constant uint pil[24]={10,7,11,17,18,3,5,16,8,21,24,4,15,23,19,13,12,2,20,14,22,9,6,1};
inline ulong rol(ulong x,uint y){return (x<<y)|(x>>(64-y));}
kernel void mine(constant ulong *tpl [[buffer(0)]],constant ulong &start [[buffer(1)]],constant uint *targets [[buffer(2)]],constant uint &count [[buffer(3)]],device atomic_uint *hits [[buffer(4)]],uint gid [[thread_position_in_grid]]) {
 ulong s[25]={0},c[5];
 #pragma unroll
 for(uint i=0;i<17;i++)s[i]=tpl[i];
 ulong value=start+gid;
 #pragma unroll
 for(uint i=0;i<12;i++){
   uint n=(value>>(5*i))&31; uint ch=n<10?'0'+n:'a'+n-10; uint pos=10+i;
   s[pos/8]|=((ulong)ch)<<(8*(pos%8));
 }
 #pragma unroll
 for(uint r=0;r<23;r++){
  #pragma unroll
  for(uint i=0;i<5;i++)c[i]=s[i]^s[i+5]^s[i+10]^s[i+15]^s[i+20];
  #pragma unroll
  for(uint i=0;i<5;i++){ulong t=c[(i+4)%5]^rol(c[(i+1)%5],1);for(uint j=0;j<25;j+=5)s[j+i]^=t;}
  ulong t=s[1];
  #pragma unroll
  for(uint i=0;i<24;i++){uint j=pil[i];ulong v=s[j];s[j]=rol(t,rot[i]);t=v;}
  #pragma unroll
  for(uint j=0;j<25;j+=5){for(uint i=0;i<5;i++)c[i]=s[j+i];for(uint i=0;i<5;i++)s[j+i]=c[i]^((~c[(i+1)%5])&c[(i+2)%5]);}
  s[0]^=rc[r];
 }
 #pragma unroll
 for(uint i=0;i<5;i++)c[i]=s[i]^s[i+5]^s[i+10]^s[i+15]^s[i+20];
 ulong a=s[0]^c[4]^rol(c[1],1);
 ulong b=rol(s[6]^c[0]^rol(c[2],1),44);
 ulong d=rol(s[12]^c[1]^rol(c[3],1),43);
 uint hash=(uint)(a^((~b)&d)^rc[23]);
 for(uint j=0;j<count;j++)if(hash==targets[j]){uint k=atomic_fetch_add_explicit(&hits[0],1,memory_order_relaxed);if(k<20){atomic_store_explicit(&hits[1+3*k],j,memory_order_relaxed);atomic_store_explicit(&hits[2+3*k],(uint)value,memory_order_relaxed);atomic_store_explicit(&hits[3+3*k],(uint)(value>>32),memory_order_relaxed);}}
}
"""

// Portable reference and independent verification: evm_lab.selectors.
// The search synthesizes names; it cannot recover original names.
let lib = try device.makeLibrary(source: source, options: nil)
let pipeline = try device.makeComputePipelineState(function: lib.makeFunction(name: "mine")!)
let queue = device.makeCommandQueue()!
struct Job: Codable { var suffix: String; var targets: [String]; var offset: UInt64? }
let argv = CommandLine.arguments
func fail(_ message: String) -> Never { fputs(message + "\n", stderr); exit(2) }
guard argv.count >= 3 && argv.count <= 5 else {
    fail("Usage: mine-selectors JOBS.json FOUND.json [MAX_BATCHES=1] [BATCH_SIZE=1048576]")
}
let config = argv[1], output = argv[2]
guard URL(fileURLWithPath: config).standardizedFileURL != URL(fileURLWithPath: output).standardizedFileURL else {
    fail("Jobs and results must be different files")
}
guard let maxBatches = Int(argv.count > 3 ? argv[3] : "1"), maxBatches > 0,
      let batch = Int(argv.count > 4 ? argv[4] : "1048576"), batch > 0 && batch <= (1 << 26) else {
    fail("Positive batch limit and batch size <= 67108864 required")
}
var jobs = try JSONDecoder().decode([Job].self, from: Data(contentsOf: URL(fileURLWithPath: config)))
for job in jobs {
    guard job.suffix.hasPrefix("("), job.suffix.hasSuffix(")"),
          job.suffix.utf8.count <= 113, job.suffix.utf8.allSatisfy({ $0 > 32 && $0 < 127 }),
          !job.targets.isEmpty, job.targets.count <= 20,
          job.targets.allSatisfy({ $0.count == 8 && UInt32($0, radix: 16) != nil }) else {
        fail("Jobs require an ASCII ABI suffix <=113 bytes and 1..20 eight-digit hex selectors without 0x")
    }
}
var found: [String:String] = [:]
if FileManager.default.fileExists(atPath: output) {
    found = try JSONDecoder().decode([String:String].self, from: Data(contentsOf: URL(fileURLWithPath: output)))
}
let prefix = Array("recovered_".utf8)
var batches = 0
while jobs.contains(where: { $0.targets.contains(where: { found[$0] == nil }) }) && batches < maxBatches {
    for idx in jobs.indices {
        if batches >= maxBatches { break }
        let todo = jobs[idx].targets.filter { found[$0] == nil }
        if todo.isEmpty { continue }
        var start = jobs[idx].offset ?? 0
        guard start <= (UInt64(1) << 60) - UInt64(batch) else { fail("60-bit name space exhausted") }
        var bytes = [UInt8](repeating: 0, count: 136)
        for (i,b) in prefix.enumerated() { bytes[i] = b }
        for (i,b) in jobs[idx].suffix.utf8.enumerated() { bytes[22+i] = b }
        bytes[22+jobs[idx].suffix.utf8.count] = 1
        bytes[135] |= 128
        let buf = device.makeBuffer(bytes: bytes, length: 136, options: .storageModeShared)!
        let startbuf = device.makeBuffer(bytes: &start, length: 8, options: .storageModeShared)!
        let hashes = todo.map { UInt32($0,radix:16)!.byteSwapped }
        let targets = device.makeBuffer(bytes: hashes, length: 4*hashes.count, options: .storageModeShared)!
        var n = UInt32(hashes.count)
        let countbuf = device.makeBuffer(bytes: &n, length: 4, options: .storageModeShared)!
        let hits = device.makeBuffer(length: 4*64, options: .storageModeShared)!
        memset(hits.contents(), 0, 4*64)
        let cmd = queue.makeCommandBuffer()!, enc = cmd.makeComputeCommandEncoder()!
        enc.setComputePipelineState(pipeline)
        for (i,b) in [buf,startbuf,targets,countbuf,hits].enumerated() { enc.setBuffer(b,offset:0,index:i) }
        enc.dispatchThreads(MTLSize(width:batch,height:1,depth:1),
            threadsPerThreadgroup:MTLSize(width:min(128,pipeline.maxTotalThreadsPerThreadgroup),height:1,depth:1))
        enc.endEncoding(); cmd.commit(); cmd.waitUntilCompleted()
        if let error = cmd.error { fail("GPU error: \(error)") }
        let p = hits.contents().bindMemory(to:UInt32.self,capacity:64)
        guard p[0] <= 20 else { fail("Hit buffer overflow; rerun with a smaller batch size") }
        for k in 0..<Int(p[0]) {
            let j = Int(p[1+3*k])
            let v = UInt64(p[2+3*k]) | (UInt64(p[3+3*k]) << 32)
            var name = "recovered_"
            for i in 0..<12 {
                let x = (v >> (5*i)) & 31
                name.append(Character(UnicodeScalar(UInt8(x < 10 ? 48+x : 97+x-10))))
            }
            found[todo[j]] = name + jobs[idx].suffix
            print("FOUND \(todo[j]) \(found[todo[j]]!)")
        }
        jobs[idx].offset = start + UInt64(batch)
        batches += 1
        // Persist hits before advancing the resume cursor; interrupted writes may
        // repeat work but cannot skip a discovered hit.
        try JSONEncoder().encode(found).write(to:URL(fileURLWithPath:output),options:.atomic)
        try JSONEncoder().encode(jobs).write(to:URL(fileURLWithPath:config),options:.atomic)
    }
}
print("Completed \(batches) batches; \(found.count) recorded hits. Verify them independently with check-selector-hits.py.")
