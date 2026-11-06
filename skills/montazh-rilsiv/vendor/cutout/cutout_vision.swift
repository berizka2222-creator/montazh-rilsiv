// Person masks for every frame of a clip with Apple Vision (accurate person segmentation, Neural Engine).
//   cutout_vision in.mp4 masks_dir      -> masks_dir/00001.png ... (8-bit grey, frame size)
// A sequence handler keeps the mask steady from frame to frame. Prints DONE <frames> <seconds>.
import Foundation
import AVFoundation
import Vision
import CoreImage
import ImageIO
import UniformTypeIdentifiers

let args = CommandLine.arguments
let asset = AVURLAsset(url: URL(fileURLWithPath: args[1]))
let outDir = URL(fileURLWithPath: args[2], isDirectory: true)
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
let track = asset.tracks(withMediaType: .video).first!
let reader = try! AVAssetReader(asset: asset)
let out = AVAssetReaderTrackOutput(track: track, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
out.alwaysCopiesSampleData = false
reader.add(out); reader.startReading()

let seq = VNSequenceRequestHandler()
let req = VNGeneratePersonSegmentationRequest()
req.qualityLevel = .accurate
req.outputPixelFormat = kCVPixelFormatType_OneComponent8
let ctx = CIContext(options: [.workingColorSpace: NSNull()])
let grey = CGColorSpaceCreateDeviceGray()
let t0 = Date(); var n = 0
while let sb = out.copyNextSampleBuffer() {
    guard let pb = CMSampleBufferGetImageBuffer(sb) else { continue }
    autoreleasepool {
        let w = CVPixelBufferGetWidth(pb), h = CVPixelBufferGetHeight(pb)
        try! seq.perform([req], on: pb, orientation: .up)
        var m = CIImage(cvPixelBuffer: req.results!.first!.pixelBuffer)
        m = m.transformed(by: CGAffineTransform(scaleX: CGFloat(w) / m.extent.width, y: CGFloat(h) / m.extent.height))
        let cg = ctx.createCGImage(m, from: CGRect(x: 0, y: 0, width: w, height: h), format: .L8, colorSpace: grey)!
        n += 1
        let dst = CGImageDestinationCreateWithURL(outDir.appendingPathComponent(String(format: "%05d.png", n)) as CFURL, UTType.png.identifier as CFString, 1, nil)!
        CGImageDestinationAddImage(dst, cg, nil); CGImageDestinationFinalize(dst)
    }
}
print("DONE \(n) \(Int(Date().timeIntervalSince(t0)))")
